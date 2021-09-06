import unittest

from donot import do

class Nothing:
    """ Demo Maybe monad """

    def __init__(self, val=None):
        self.val = val

    def flat_map(self, func):
        return self

    def __eq__(self, other):
        return self.val == other.val

    def __repr__(self):
        return "{0.__class__.__name__}({0.val})".format(self)

    def __iter__(self):
        # Expose interface flat_map + pure
        yield self.flat_map
        yield self.__class__

class Just(Nothing):

    def flat_map(self, func):
        return func(self.val)


class TestDoNot(unittest.TestCase):

    def test_simple(self):
        val = do(
            (v1, v2, v3)
            for v1 in Just(10)
            for v2 in Just(20)
            for v3 in Just(30)
        )
        self.assertEqual(val, Just((10, 20, 30)))

    def test_nothing(self):
        val = do(
            (v1, v2, v3)
            for v1 in Just(10)
            for v2 in Nothing() # Short circut
            for v3 in Just(30)
        )
        self.assertEqual(val, Nothing())

    def test_short_circut(self):
        val = do(
            (v1, v2, v3)
            for v1 in Just(10)
            if not v1
            for v2 in Just(20)
            for v3 in Just(30)
        )
        self.assertEqual(val, Just(10)) # Last evaluated

        val = do(
            (v1, v2, v3)
            for v1 in Just(10)
            for v2 in Just(20)
            if not v2
            for v3 in Just(30)
        )
        self.assertEqual(val, Just(20)) # Last evaluated

    def test_if_expression(self):
        val = do(
            (v1, v2, v3) if not v3 else "hey"
            for v1 in Just(10)
            for v2 in Just(20)
            for v3 in Just(30)
        )
        self.assertEqual(val, Just("hey"))

        val = do(
            v1 if not v1 else v2 if not v2 else v3 if not v3 else "fallback"
            for v1 in Just(10)
            for v2 in Just(20)
            for v3 in Just(30)
        )
        self.assertEqual(val, Just("fallback"))

    def test_using_vars_inscope(self):
        val = do(
            v + 1
            for v in Just(1)
            for v in Just(v + 1)
        )
        self.assertEqual(val, Just(3))

    def test_redefining_vars(self):
        val = do(
            v1 + v2 + v3
            for v1 in Just("1")
            for v2 in Just("2")
            for v1 in Just("3")
            for v3 in Just("4")
        )
        self.assertEqual(val, Just("324"))

        val = do(
            v
            for v in Just(1)
            for v in Just(v + 2)
            for v in Just(v + 3)
        )
        self.assertEqual(val, Just(6))

        var = 1
        val = do(
            v
            for v in Just(1)
            for v in Just(v + var)
        )
        self.assertEqual(val, Just(2))

    def test_rerun(self):

        def add_one(num):
            return do(
                v1 + v2
                for v1 in Just(1)
                for v2 in Just(num)
            )
        self.assertEqual(
            [add_one(i) for i in range(3)],
            [Just(1), Just(2), Just(3)],
        )

    def test_non_monad(self):
        with self.assertRaises(TypeError):
            do(v for v in (1,2,3)) # Not a monad value

    def test_non_comprehension(self):
        with self.assertRaises(TypeError):
            do(iter((1,2,3))) # Not a generator expression

    def test_empty_iterable(self):
        # Using iterable of zero length in body. Falls back to last value.
        # This is not behaviour to be relied on however.
        self.assertEqual(
            do(v for v in Just(10) for v in ()),
            Just(10),
        )

    def test_value_unpacking(self):
        val = do(
            v1 + v2 + v3
            for (v1, v2) in Just((1, 2)) # Unpacking values
            for (v3, v1) in Just((3, 4))
        )
        self.assertEqual(val, Just(9))

        val = do(
            "{}-{}-{}-{}-{}".format(v1, v2, v3, v4, v5)
            for (v1, (v2, (v3, v4))) in Just((1, (2, (3, 4))))
            for v5 in Just(v1 + v2 + v3 + v4)
        )
        self.assertEqual(val, Just("1-2-3-4-10"))

