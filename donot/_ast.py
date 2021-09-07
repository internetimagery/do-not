import sys
import dis
from collections import namedtuple

PY2 = sys.version_info[0] == 2
PY35 = sys.version_info[0] == 3 and sys.version_info[1] <= 5

if PY2:
    to_bytes = lambda a: bytes(bytearray(a))
    as_byte = ord
else:
    to_bytes = bytes
    as_byte = lambda x: x

LOAD_FAST = dis.opmap["LOAD_FAST"]
STORE_FAST = dis.opmap["STORE_FAST"]
UNPACK_SEQUENCE = dis.opmap["UNPACK_SEQUENCE"]
GET_ITER = dis.opmap["GET_ITER"]
FOR_ITER = dis.opmap["FOR_ITER"]
YIELD_VALUE = dis.opmap["YIELD_VALUE"]


Inputs = namedtuple("Inputs", ("names", "start", "stop"))
Expression = namedtuple("Expression", ("names", "start", "stop"))
Guard = namedtuple("Guard", ("names", "state", "start", "stop"))
Execution = namedtuple("Execution", ("expressions"))



def parse(code):
    iter_bytes = _unpack_opargs(code.co_code)
    assert next(iter_bytes)[1] == LOAD_FAST
    expressions = []
    for expr in _parse_inputs(code, iter_bytes):
        if expressions and isinstance(expr, Inputs):
            yield Execution(tuple(expressions))
            expressions = []
        expressions.append(expr)
    if expressions:
        yield Execution(tuple(expressions))


def _parse_inputs(code, iter_bytes):
    assert next(iter_bytes)[1] == FOR_ITER
    inputs = []
    num_unpack = 1
    start_offset = end_offset = 0
    while num_unpack:
        num_unpack -= 1

        (i, op, arg) = next(iter_bytes)
        end_offset = i + _offset(op)
        if not start_offset:
            start_offset = i
        if op == STORE_FAST:
            inputs.append(code.co_varnames[arg])
        elif op == UNPACK_SEQUENCE:
            num_unpack += arg
        else:
            raise AssertionError("Unexpected operation {}".format(dis.opname[op]))
    yield Inputs(tuple(inputs), start_offset, end_offset)
    for expr in _parse_expression(code, iter_bytes):
        yield expr


def _parse_expression(code, iter_bytes):
    names = set()
    start_offset = end_offset = 0
    for idx, op, arg in iter_bytes:
        end_offset = idx
        if not start_offset:
            start_offset = idx

        if op == LOAD_FAST:
            names.add(code.co_varnames[arg])

        if op == GET_ITER:
            yield Expression(tuple(names), start_offset, end_offset)
            for var in _parse_inputs(code, iter_bytes):
                yield var
            return

        if op == YIELD_VALUE:
            # We are at the end!
            yield Expression(tuple(names), start_offset, end_offset)
            return

        if op in dis.hasjabs and FOR_ITER == as_byte(code.co_code[arg]):
            yield Guard(tuple(names), "TRUE" in dis.opname[op], start_offset, end_offset)
            for expr in _parse_expression(code, iter_bytes):
                yield expr
            return



# Lifted from dis.disassemble
if PY2 or PY35:
    as_byte = ord
    def _offset(op):
        if op >= dis.HAVE_ARGUMENT:
            return 3
        return 1

    def _unpack_opargs(code):
        n = len(code)
        i = 0
        extended_arg = 0
        while i < n:
            j = i
            op = ord(code[i])
            i = i+1
            if op >= dis.HAVE_ARGUMENT:
                arg = ord(code[i]) + ord(code[i+1])*256 + extended_arg
                extended_arg = 0
                i = i+2
                if op == dis.EXTENDED_ARG:
                    extended_arg = arg*65536
            else:
                arg = None
            yield (j, op, arg)

else:
    as_byte = int
    def _offset(op):
        return 2

    def _unpack_opargs(code):
        extended_arg = 0
        for i in range(0, len(code), 2):
            op = code[i]
            if op >= dis.HAVE_ARGUMENT:
                arg = code[i+1] | extended_arg
                extended_arg = (arg << 8) if op == dis.EXTENDED_ARG else 0
            else:
                arg = None
            yield (i, op, arg)


if __name__ == "__main__":

    g = (a for (a, b) in () if a < 123 and a > 321 if b for c in somestuff(wit.mtt) if something(c.attribute.another))
    dis.dis(g)
    print(list(parse(g.gi_code)))
