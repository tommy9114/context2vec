import torch
import torch.nn as nn
import numpy


class NegativeSampling(nn.Module):

    def __init__(self,
                 embed_size,
                 counter,
                 n_negatives,
                 power,
                 device,
                 ignore_index):
        super(NegativeSampling, self).__init__()

        self.counter = counter
        self.n_negatives = n_negatives
        self.power = power
        self.device = device

        self.W = nn.Embedding(num_embeddings=len(counter),
                              embedding_dim=embed_size,
                              padding_idx=ignore_index)
        self.W.weight.data.zero_()
        self.logsigmoid = nn.LogSigmoid()
        self.sampler = WalkerAlias(numpy.power(counter, power))

    def negative_sampling(self, shape):
        if self.n_negatives > 0:
            return torch.tensor(self.sampler.sample(shape=shape), dtype=torch.long, device=self.device)
        else:
            raise NotImplementedError

    def forward(self, sentence, context):
        size = sentence.size(0)
        emb = self.W(sentence)
        pos_loss = self.logsigmoid((emb*context).sum(1))

        neg_samples = self.negative_sampling(shape=(size, self.n_negatives))
        neg_emb = self.W(neg_samples)
        neg_loss = self.logsigmoid((-neg_emb*context.unsqueeze(1)).sum(2)).sum(1)
        return -(pos_loss+neg_loss).sum()


class WalkerAlias(object):
    '''
    This is from Chainer's implementation.
    You can find the original code at 
    https://github.com/chainer/chainer/blob/v4.4.0/chainer/utils/walker_alias.py
    This class is
        Copyright (c) 2015 Preferred Infrastructure, Inc.
        Copyright (c) 2015 Preferred Networks, Inc.
    '''
    def __init__(self, probs):
        prob = numpy.array(probs, numpy.float32)
        prob /= numpy.sum(prob)
        threshold = numpy.ndarray(len(probs), numpy.float32)
        values = numpy.ndarray(len(probs) * 2, numpy.int32)
        il, ir = 0, 0
        pairs = list(zip(prob, range(len(probs))))
        pairs.sort()
        for prob, i in pairs:
            p = prob * len(probs)
            while p > 1 and ir < il:
                values[ir * 2 + 1] = i
                p -= 1.0 - threshold[ir]
                ir += 1
            threshold[il] = p
            values[il * 2] = i
            il += 1
        # fill the rest
        for i in range(ir, len(probs)):
            values[i * 2 + 1] = 0

        assert((values < len(threshold)).all())
        self.threshold = threshold
        self.values = values

    def sample(self, shape):
        ps = numpy.random.uniform(0, 1, shape)
        pb = ps * len(self.threshold)
        index = pb.astype(numpy.int32)
        left_right = (self.threshold[index] < pb - index).astype(numpy.int32)
        return self.values[index * 2 + left_right]