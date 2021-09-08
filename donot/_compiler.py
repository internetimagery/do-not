import sys
import dis
import inspect
from types import CodeType
from itertools import chain
from collections import namedtuple

from donot._ast import (
    parse,
    add_op,
    op_offset,
    Inputs,
    Guard,
    FinalExpression,
    Execution,
)


PY2 = sys.version_info[0] == 2
PY38 = sys.version_info[0] == 3 and sys.version_info[1] >= 8

if PY2:
    to_bytes = lambda a: bytes(bytearray(a))
else:
    to_bytes = bytes

Function = namedtuple("Function", ("defaults", "code"))

LOAD_FAST = dis.opmap["LOAD_FAST"]
LOAD_CONST = dis.opmap["LOAD_CONST"]
POP_JUMP_IF_TRUE = dis.opmap["POP_JUMP_IF_TRUE"]
POP_JUMP_IF_FALSE = dis.opmap["POP_JUMP_IF_FALSE"]
JUMP_FORWARD = dis.opmap["JUMP_FORWARD"]
RETURN_VALUE = dis.opmap["RETURN_VALUE"]


def compile_(code):
    """Parse"""
    for execution in parse(code):
        compile_execution(code, execution)


def compile_execution(code, execution):
    for guard in execution.guards:
        compile_guard(code, execution.inputs, guard)


def compile_guard(code, inputs, guard):
    defaults = tuple(a for a in guard.names if a not in inputs.names)
    layout = tuple(chain((".0",), inputs.names, defaults))

    updated_inputs = _retarget_locals(code.co_varnames, layout, inputs.stack)
    updated_guard = _retarget_locals(code.co_varnames, layout, guard.stack)

    post_stack = []
    add_op(
        post_stack,
        POP_JUMP_IF_TRUE if guard.state else POP_JUMP_IF_FALSE,
        len(inputs.stack)
        + len(guard.stack)
        + op_offset(POP_JUMP_IF_TRUE)
        + op_offset(LOAD_CONST)
        + op_offset(JUMP_FORWARD),
    )
    add_op(post_stack, LOAD_CONST, len(code.co_consts))
    add_op(post_stack, JUMP_FORWARD, op_offset(LOAD_CONST))
    add_op(post_stack, LOAD_CONST, len(code.co_consts) + 1)
    add_op(post_stack, RETURN_VALUE)

    new_code = _clone_code(
        code,
        list(chain(updated_inputs, updated_guard, post_stack)),
        (True, False),
        layout,
        len(defaults) + 1,
    )
    return new_code


def _retarget_locals(varnames, layout, stack):
    for i, b in enumerate(stack):
        if stack[i - 1] in dis.haslocal:
            b = layout.index(varnames[b])
        yield b


def _clone_code(code, byte_stack, consts, varnames, argcount):
    """Helper for building a new code object out of the old"""
    args = (
        argcount,  # code.co_argcount,
        0,  # code.co_posonlyargcount,
        0,  # code.co_kwonlyargcount,
        len(varnames),  # code.co_nlocals,
        max(code.co_stacksize, len(varnames)) + 1,
        inspect.CO_OPTIMIZED | inspect.CO_NEWLOCALS | inspect.CO_NESTED,
        to_bytes(byte_stack),
        code.co_consts + consts,
        code.co_names,
        varnames,
        code.co_filename,
        "<generated>",
        code.co_firstlineno,
        code.co_lnotab,
        code.co_freevars,
        code.co_cellvars,
    )
    if PY2:
        args = args[:1] + args[3:]
    elif not PY38:
        args = args[:1] + args[2:]

    return CodeType(*args)


# Pull all parts.
# walk backwards, building func.
# perhaps using pure is still the way to go? can we use map?

if __name__ == "__main__":

    g = (
        a
        for (a, b) in ()
        if a < 123 and a > 321
        if b
        for c in somestuff(wit.mtt)
        if something(c.attribute.another)
    )
    compile_(g.gi_code)
