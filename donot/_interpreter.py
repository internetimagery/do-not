import sys

from types import FunctionType
from weakref import WeakKeyDictionary

from donot._ast import parse
from donot._compiler import compile_code

PY38 = sys.version_info[0] == 3 and sys.version_info[1] >= 8

if PY38:
    from types import CellType
else:
    CellType = lambda v: (lambda: v).__closure__[0]

_CACHE = WeakKeyDictionary()


def do(generator, handler=None):
    """
    Simple do notation for python monads.

    >>> val = do(
    >>>     v1 + v2
    >>>     for v1 in Just(10)
    >>>     for v2 in Just(20)
    >>> )
    >>> assert val == Just(30)

    Desugared:

    >>> Just(10).flat_map(lambda v1:
    >>>     Just(20).flat_map(lambda v2, v1=v1:
    >>>         Just.pure(v1 + v2)))

    if-expressions in the final expression work as expected

    >>> val = do(
    >>>     "yes" if v > 10 else "no"
    >>>     for v in Just(11)
    >>> )
    >>> assert val == Just("yes")

    if-expressions in the body call the filter interface. A TypeError
    is raised if this is not supplied for the monad in use.

    >>> val = do(
    >>>     v1 + v2
    >>>     for v1 in Just(10)
    >>>     if v1 > 20 # Short circut
    >>>     for v2 in Just(20)
    >>> )
    >>> assert val == Nothing() # Last value returned before if-expression

    Assignments (let val = <expr>) don't work, and neither does mapping due to the limited syntax
    of the comprehension language. However they can still be wrapped in the monadic
    structure and then flatmapped by the expression.

    >>> add_one = lambda a: a + 1
    >>> val = do(
    >>>     v2
    >>>     for v1 in Just(1)
    >>>     for v2 in Just(add_one(v1))
    >>> )
    >>> assert val == Just(2)

    This notation extension does not attempt to impliment a suite of monadic tooling to fit
    its structure. Instead to support this notation in your monads,
    they need to expose their interface through iter.
    This should be fairly simple to achieve and allows it to be relatively interface
    agnostic (how many ways can we name "bind"? methods or functions?).

    Example:

    >>> def __iter__(self):
    >>>     yield {
    >>>         "map": self.map, # fmap etc ...
    >>>         "flat_map": self.flat_map, # chain # and_then # bind # etc...
    >>>         "filter": self.filter # Optional, only if monad supports it.
    >>>     }
    """
    try:
        monad = generator.gi_frame.f_locals[".0"]
    except (AttributeError, KeyError):
        raise TypeError(
            "Provided argument is not a valid generator expression. Got: '{}'".format(
                generator
            )
        )
    gen_code = generator.gi_code

    cached_code = _CACHE.get(gen_code)
    if not cached_code:
        node = parse(gen_code)
        cached_code = _CACHE[gen_code] = compile_code(gen_code, node)

    func = FunctionType(
        cached_code,  # The code itself
        generator.gi_frame.f_globals,  # globals dict
        "<do_block>",  # name of func
        (handler or _handle_interface,),
        tuple(CellType(generator.gi_frame.f_locals[v]) for v in gen_code.co_freevars),
    )
    return func(monad)


def _handle_interface(name, monad, func):
    try:
        # Type error allowed to raise directly.
        interface = next(iter(monad))
    except StopIteration:
        raise TypeError(
            "Interface not supplied. Please yield a dict exposing the monadic interface from {}".format(
                monad
            )
        )

    try:
        caller = interface[name]
    except KeyError:
        raise TypeError("{} not exposed through {}".format(name, monad))

    return caller(func)
