import sys
import dis
from itertools import chain
from collections import namedtuple

PY2 = sys.version_info[0] == 2
PY35 = sys.version_info[0] == 3 and sys.version_info[1] <= 5


LOAD_FAST = dis.opmap["LOAD_FAST"]
STORE_FAST = dis.opmap["STORE_FAST"]
UNPACK_SEQUENCE = dis.opmap["UNPACK_SEQUENCE"]
GET_ITER = dis.opmap["GET_ITER"]
FOR_ITER = dis.opmap["FOR_ITER"]
YIELD_VALUE = dis.opmap["YIELD_VALUE"]
RETURN_VALUE = dis.opmap["RETURN_VALUE"]


Inputs = namedtuple("Inputs", ("names", "stack"))
Guard = namedtuple(
    "Guard", ("names", "inputs", "state", "start", "lnotab", "stack", "next")
)
FlatMapExpr = namedtuple(
    "FlatMapExpr", ("names", "inputs", "start", "lnotab", "stack", "next")
)
MapExpr = namedtuple("MapExpr", ("names", "inputs", "start", "lnotab", "stack"))


def parse(code):
    """
    Parse out the deconstructed for-comprehension into its operational parts.

    Inputs = Where the values initially get stored. Right after a generator has had another value requested.
        This is where we want to start breaking up our map/flatmap as a new value is about to enter.
    Guard = An attempt to exit out of the expression all together. This is an empty if statement that typically
        would exit out of the generator loop. In this case we want to send this expression to the filter command.
    FlatMapExpr = A expression that generates a value. Not used as a guard. This includes expressions that build the
        generators typically, and for us is the expression that generates our monad value.
    MapExpr = Same as FlatMapExpr, but this is the end of the chain. We want to map over this value.

    """
    iter_bytes = _unpack_opargs(code.co_code)
    assert next(iter_bytes)[1] == LOAD_FAST
    return _parse_inputs(code, iter_bytes)


def _parse_inputs(code, iter_bytes):
    assert next(iter_bytes)[1] == FOR_ITER
    inputs = set()
    bytestack = add_op([], LOAD_FAST, 0)
    num_unpack = 1
    start_offset = 0
    while num_unpack:
        num_unpack -= 1

        (i, op, arg) = next(iter_bytes)
        if not start_offset:
            start_offset = i
        add_op(bytestack, op, arg)
        if op == STORE_FAST:
            inputs.add(code.co_varnames[arg])
        elif op == UNPACK_SEQUENCE:
            num_unpack += arg
        else:
            raise AssertionError("Unexpected operation {}".format(dis.opname[op]))
    node = Inputs(
        inputs,
        bytestack,
    )
    return _parse_expression(code, iter_bytes, node)


def _parse_expression(code, iter_bytes, inputs):
    names = set()
    start_offset = 0
    bytestack = []
    for idx, op, arg in iter_bytes:
        if not start_offset:
            start_offset = idx

        if op == STORE_FAST:
            raise RuntimeError("OH NO!")

        if op == LOAD_FAST:
            names.add(code.co_varnames[arg])

        if op == GET_ITER:
            peek = next(iter_bytes)
            if peek[1] == FOR_ITER:
                iter_bytes = chain((peek,), iter_bytes)
                return FlatMapExpr(
                    names,
                    inputs,
                    start_offset,
                    _get_lnotab(code, start_offset, start_offset + len(bytestack)),
                    bytestack,
                    _parse_inputs(code, iter_bytes),
                )
            else:
                add_op(bytestack, op, arg)
                op, arg = peek[1], peek[2]

        if op == YIELD_VALUE:
            # We are at the end!
            add_op(bytestack, RETURN_VALUE)
            return MapExpr(
                names,
                inputs,
                start_offset,
                _get_lnotab(code, start_offset, start_offset + len(bytestack)),
                bytestack,
            )

        if op in dis.hasjabs and _jumps_out(code.co_code, arg):
            return Guard(
                names,
                inputs,
                "TRUE" in dis.opname[op],
                start_offset,
                _get_lnotab(code, start_offset, start_offset + len(bytestack)),
                bytestack,
                _parse_expression(code, iter_bytes, inputs),
            )

        add_op(bytestack, op, arg)


def _jumps_out(code, arg):
    # Sometimes the jump targets the FOR_ITER directly.
    # Other times there are a couple of jumps before we get there.
    while True:
        op = as_byte(code[arg])
        if op == FOR_ITER:
            return True
        elif op not in dis.hasjabs:
            return False
        arg = as_byte(code[arg + 1])
    raise RuntimeError("Could not determine jump target")


def _get_lnotab(code, start_offset, stop_offset):
    """Get absolute values for the line number table"""
    for offset, line in dis.findlinestarts(code):
        if offset >= start_offset and offset <= stop_offset:
            yield offset - start_offset, line


# Lifted from dis.disassemble
if PY2:
    as_byte = ord
else:
    as_byte = int

if PY2 or PY35:

    def add_op(stack, operation, arg=None):
        if arg is None:
            stack.append(operation)
        else:
            stack.extend((operation, arg, 0))
        return stack

    def op_offset(op):
        if op >= dis.HAVE_ARGUMENT:
            return 3
        return 1

    def _unpack_opargs(code):
        extended_arg = 0
        code_iter = enumerate(as_byte(c) for c in code)
        for i, op in code_iter:
            if op >= dis.HAVE_ARGUMENT:
                arg = next(code_iter)[1] + next(code_iter)[1] * 256 + extended_arg
                extended_arg = 0
                if op == dis.EXTENDED_ARG:
                    extended_arg = arg * 65536
            else:
                arg = None
            yield i, op, arg


else:
    as_byte = int

    def add_op(stack, operation, arg=None):
        stack.extend((operation, 0 if arg is None else arg))
        return stack

    def op_offset(op):
        return 2

    def _unpack_opargs(code):
        extended_arg = 0
        code_iter = iter(code)
        for i, (op, arg) in enumerate(zip(code_iter, code_iter)):
            if op >= dis.HAVE_ARGUMENT:
                arg |= extended_arg
                extended_arg = (arg << 8) if op == dis.EXTENDED_ARG else 0
            else:
                arg = None
            yield (i * 2, op, arg)


if __name__ == "__main__":

    g = (
        a
        for (a, b) in ()
        if a < 123 and a > 321
        if b
        for c in somestuff(wit.mtt)
        if something(c.attribute.another)
    )
    dis.dis(g.gi_code)
    from pprint import pprint

    pprint(list(parse(g.gi_code)))
