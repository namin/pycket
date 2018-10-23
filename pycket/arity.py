#! /usr/bin/env python
# -*- coding: utf-8 -*-

from pycket.util  import memoize
from rpython.rlib import jit
import values

class Arity(object):
    _immutable_fields_ = ['arity_list[*]', 'at_least']

    def __init__(self, arity_list, at_least):
        self.arity_list = arity_list
        self.at_least = at_least

    def __repr__(self):
        return "Arity(arity_list=%r, at_least=%r)" % (self.arity_list, self.at_least)

    def get_arity_list(self):
        return self.arity_list

    def get_at_least(self):
        return self.at_least

    @jit.elidable
    def list_includes(self, arity):
        return arity in self.arity_list

    @jit.elidable
    def arity_includes(self, arity):
        return ((self.at_least != -1 and arity >= self.at_least) or
                self.list_includes(arity))

    @jit.elidable
    def shift_arity(self, shift):
        arity_list = [i + shift for i in self.arity_list if i + shift > -1]
        at_least = max(self.at_least + shift, -1)
        return Arity(arity_list, at_least)

    @jit.elidable
    def arity_bits(self):
        # FIXME: handle bignums
        import math
        if self.at_least == -1:
            m = 0
        else:
            m = -int(math.pow(2, self.at_least))
        for n in self.arity_list:
            m = m | int(math.pow(2, n))
        return values.W_Fixnum(m)

    @staticmethod
    @memoize
    def geq(n):
        return Arity([], n)

    @staticmethod
    @memoize
    def oneof(*lst):
        return Arity(list(lst), -1)

Arity.unknown = Arity.geq(0)
Arity.ZERO    = Arity.oneof(0)
Arity.ONE     = Arity.oneof(1)
Arity.TWO     = Arity.oneof(2)
Arity.THREE   = Arity.oneof(3)

