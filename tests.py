import unittest

from donot import do


class Nothing:
    """Demo Maybe monad"""

    def __init__(self, val=None):
        self.val = val

    def map(self, func):
        return self

    def flat_map(self, func):
        return self

    def filter(self, func):
        return self

    def __eq__(self, other):
        return self.val == other.val

    def __repr__(self):
        return "{0.__class__.__name__}({0.val})".format(self)

    def __iter__(self):
        # Expose interface flat_map + pure
        yield {"flat_map": self.flat_map, "map": self.map, "filter": self.filter}


class Just(Nothing):
    def map(self, func):
        return Just(func(self.val))

    def flat_map(self, func):
        return func(self.val)

    def filter(self, func):
        return self if func(self.val) else Nothing()


class Reader:
    def __init__(self, val):
        self._func = val if callable(val) else lambda _: val

    def map(self, func):
        return self.__class__(lambda env: func(self._func(env)))

    def flat_map(self, func):
        return self.__class__(lambda env: func(self._func(env)).run(env))

    def run(self, env):
        return self._func(env)

    @classmethod
    def ask(cls):
        return cls(lambda env: env)

    def __iter__(self):
        yield {"flat_map": self.flat_map, "map": self.map}


class TestDoNot(unittest.TestCase):
    def test_simple(self):
        val = do((v1, v2, v3) for v1 in Just(10) for v2 in Just(20) for v3 in Just(30))
        self.assertEqual(val, Just((10, 20, 30)))

    def test_nothing(self):
        val = do(
            (v1, v2, v3)
            for v1 in Just(10)
            for v2 in Nothing()  # Short circut
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
        self.assertEqual(val, Nothing())

        val = do(
            (v1, v2, v3)
            for v1 in Just(10)
            for v2 in Just(20)
            if not v2
            for v3 in Just(30)
        )
        self.assertEqual(val, Nothing())

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
        val = do(v + 1 for v in Just(1) for v in Just(v + 1))
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

        val = do(v for v in Just(1) for v in Just(v + 2) for v in Just(v + 3))
        self.assertEqual(val, Just(6))

        var = 1
        val = do(v for v in Just(1) for v in Just(v + var))
        self.assertEqual(val, Just(2))

    def test_rerun(self):
        def add_one(num):
            return do(v1 + v2 for v1 in Just(1) for v2 in Just(num))

        self.assertEqual(
            [add_one(i) for i in range(3)],
            [Just(1), Just(2), Just(3)],
        )

    def test_non_monad(self):
        with self.assertRaises(TypeError):
            do(v for v in (1, 2, 3))  # Not a monad value

    def test_non_comprehension(self):
        with self.assertRaises(TypeError):
            do(iter((1, 2, 3)))  # Not a generator expression

    def test_empty_iterable(self):
        with self.assertRaises(TypeError):
            do(v for v in Just(10) for v in ())

    def test_value_unpacking(self):
        val = do(
            v1 + v2 + v3
            for (v1, v2) in Just((1, 2))  # Unpacking values
            for (v3, v1) in Just((3, 4))
        )
        self.assertEqual(val, Just(9))

        val = do(
            "{}-{}-{}-{}-{}".format(v1, v2, v3, v4, v5)
            for (v1, (v2, (v3, v4))) in Just((1, (2, (3, 4))))
            for v5 in Just(v1 + v2 + v3 + v4)
        )
        self.assertEqual(val, Just("1-2-3-4-10"))

    def test_env(self):
        def add_name(name):
            return do("{} {}".format(name, lastname) for lastname in Reader.ask())

        val = do(
            "{} and {}".format(name1, name2)
            for name1 in add_name("Joe")
            for name2 in add_name("Joanne")
        ).run("Bloggs")
        self.assertEqual(val, "Joe Bloggs and Joanne Bloggs")

    def test_no_filter(self):
        with self.assertRaises(TypeError):
            do(a for a in Reader.ask() if a)

    def test_nested(self):

        val = do(
            a + b
            for a in Just(10)
            for b in do(
                c + d
                for c in Just(20)
                for d in Just(30)
            )
        )
        self.assertEqual(val, Just(60))

if __name__ == "__main__":
    unittest.main()
