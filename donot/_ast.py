import sys
import dis
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


Inputs = namedtuple("Inputs", ("names", "start", "stop", "stack"))
Guard = namedtuple("Guard", ("names", "state", "start", "stop", "stack"))
Expression = namedtuple("Expression", ("names", "start", "stop", "stack"))
FinalExpression = namedtuple("FinalExpression", ("names", "start", "stop", "stack"))
Execution = namedtuple("Execution", ("inputs", "guards", "expression"))


def parse(code):
    """
    Parse out the deconstructed for-comprehension into its operational parts.

    Inputs = Where the values initially get stored. Right after a generator has had another value requested.
        This is where we want to start breaking up our map/flatmap as a new value is about to enter.
    Guard = An attempt to exit out of the expression all together. This is an empty if statement that typically
        would exit out of the generator loop. In this case we want to send this expression to the filter command.
    Expression = A expression that generates a value. Not used as a guard. This includes expressions that build the
        generators typically, and for us is the expression that generates our monad value.
    FinalExpression = Same as Expression, but this is the end of the chain. We want to map over this value.

    Execution = Chain of operations (above).

    """
    iter_bytes = _unpack_opargs(code.co_code)
    assert next(iter_bytes)[1] == LOAD_FAST
    operations = []
    for operation in _parse_inputs(code, iter_bytes):
        if operations and isinstance(operation, Inputs):
            yield Execution(operations[0], tuple(operations[1:-1]), operations[-1])
            operations = []
        operations.append(operation)
    yield Execution(operations[0], tuple(operations[1:-1]), operations[-1])


def _parse_inputs(code, iter_bytes):
    assert next(iter_bytes)[1] == FOR_ITER
    inputs = []
    bytestack = []
    num_unpack = 1
    start_offset = end_offset = 0
    while num_unpack:
        num_unpack -= 1

        (i, op, arg) = next(iter_bytes)
        add_op(bytestack, op, arg)
        end_offset = i + op_offset(op)
        if not start_offset:
            start_offset = i
        if op == STORE_FAST:
            inputs.append(code.co_varnames[arg])
        elif op == UNPACK_SEQUENCE:
            num_unpack += arg
        else:
            raise AssertionError("Unexpected operation {}".format(dis.opname[op]))
    yield Inputs(inputs, start_offset, end_offset, add_op([], LOAD_FAST, 0) + bytestack)
    for expr in _parse_expression(code, iter_bytes):
        yield expr


def _parse_expression(code, iter_bytes):
    names = set()
    start_offset = end_offset = 0
    bytestack = []
    for idx, op, arg in iter_bytes:
        end_offset = idx
        if not start_offset:
            start_offset = idx

        if op == LOAD_FAST:
            names.add(code.co_varnames[arg])

        if op == GET_ITER:
            yield Expression(names, start_offset, end_offset, bytestack)
            for var in _parse_inputs(code, iter_bytes):
                yield var
            return

        if op == YIELD_VALUE:
            # We are at the end!
            add_op(bytestack, RETURN_VALUE)
            yield FinalExpression(names, start_offset, end_offset, bytestack)
            return

        if op in dis.hasjabs and FOR_ITER == as_byte(code.co_code[arg]):
            yield Guard(
                names,
                "TRUE" in dis.opname[op],
                start_offset,
                end_offset,
                bytestack,
            )
            for expr in _parse_expression(code, iter_bytes):
                yield expr
            return
        add_op(bytestack, op, arg)


# Lifted from dis.disassemble
if PY2 or PY35:
    as_byte = ord

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
        n = len(code)
        i = 0
        extended_arg = 0
        while i < n:
            j = i
            op = ord(code[i])
            i = i + 1
            if op >= dis.HAVE_ARGUMENT:
                arg = ord(code[i]) + ord(code[i + 1]) * 256 + extended_arg
                extended_arg = 0
                i = i + 2
                if op == dis.EXTENDED_ARG:
                    extended_arg = arg * 65536
            else:
                arg = None
            yield (j, op, arg)


else:
    as_byte = int

    def add_op(stack, operation, arg=0):
        stack.extend((operation, arg))
        return stack

    def op_offset(op):
        return 2

    def _unpack_opargs(code):
        extended_arg = 0
        for i in range(0, len(code), 2):
            op = code[i]
            if op >= dis.HAVE_ARGUMENT:
                arg = code[i + 1] | extended_arg
                extended_arg = (arg << 8) if op == dis.EXTENDED_ARG else 0
            else:
                arg = None
            yield (i, op, arg)


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
    print(list(parse(g.gi_code)))
