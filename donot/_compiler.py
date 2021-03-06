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
    MapExpr,
    FlatMapExpr,
)


PY2 = sys.version_info[0] == 2
PY38 = sys.version_info[0] == 3 and sys.version_info[1] >= 8

if PY2:
    to_bytes = lambda a: bytes(bytearray(a))
else:
    to_bytes = bytes

FilterFunc = namedtuple("FilterFunc", ("stack"))
MapFunc = namedtuple("MapFunc", ("stack"))
FlatMapFunc = namedtuple("FlatMapFunc", ("stack"))
ComposedFunc = namedtuple("ComposedFunc", ("stack"))

INTERFACE = "Interface.Handler"

MAP = "map"
FLATMAP = "flat_map"
FILTER = "filter"

LOAD_FAST = dis.opmap["LOAD_FAST"]
STORE_FAST = dis.opmap["STORE_FAST"]
LOAD_CONST = dis.opmap["LOAD_CONST"]
LOAD_CLOSURE = dis.opmap["LOAD_CLOSURE"]
MAKE_CLOSURE = dis.opmap.get("MAKE_CLOSURE")
GET_ITER = dis.opmap["GET_ITER"]
FOR_ITER = dis.opmap["FOR_ITER"]
BUILD_TUPLE = dis.opmap["BUILD_TUPLE"]
POP_JUMP_IF_TRUE = dis.opmap["POP_JUMP_IF_TRUE"]
POP_JUMP_IF_FALSE = dis.opmap["POP_JUMP_IF_FALSE"]
JUMP_FORWARD = dis.opmap["JUMP_FORWARD"]
RETURN_VALUE = dis.opmap["RETURN_VALUE"]
MAKE_FUNCTION = dis.opmap["MAKE_FUNCTION"]
CALL_FUNCTION = dis.opmap["CALL_FUNCTION"]


def compile_code(code, node):
    """Parse"""
    # Dependency on our handler through all functions
    defaults = frozenset([INTERFACE])
    new_code = _compile_node(code, node, defaults)
    result = _clone_code(
        code,
        "<do_notation>",
        (),
        add_op(new_code.stack, RETURN_VALUE),
        defaults,
    )
    return result


def _compile_node(code, node, depend):
    defaults = depend - node.inputs.names

    if isinstance(node, MapExpr):
        return _compile_map(code, node, defaults)

    if isinstance(node, Guard):
        return _compose_two(
            code,
            _compile_guard(code, node, defaults),
            _compile_node(code, node.next, depend | node.inputs.names),
        )

    if isinstance(node, FlatMapExpr):
        return _compile_flatmap(
            code,
            node,
            defaults,
            _compile_node(code, node.next, depend | node.inputs.names),
        )
    raise TypeError("Unknown type {}".format(node))


def _compile_flatmap(code, node, defaults, inner_code):
    """
    Run inner function through flat map
    """
    new_code = _clone_code(
        code,
        "<flatmap>",
        _retarget_lnotab(
            node.lnotab,
            len(node.inputs.stack),
        ),
        chain(
            node.inputs.stack,
            node.stack,
            add_op([], STORE_FAST, ".0"),
            inner_code.stack,
            add_op([], RETURN_VALUE),
        ),
        defaults,
    )

    stack = []
    add_op(stack, LOAD_FAST, INTERFACE)  # Load interface
    add_op(stack, LOAD_CONST, FLATMAP)  # Load interface name
    add_op(stack, LOAD_FAST, ".0")  # Load monad
    add_op(stack, GET_ITER)
    stack.extend(_make_function(code, new_code))
    add_op(stack, CALL_FUNCTION, 3)
    return FlatMapFunc(stack)


def _compose_two(code, code1, code2):
    """
    Compose two functions
    """
    return ComposedFunc(
        list(chain(code1.stack, add_op([], STORE_FAST, ".0"), code2.stack))
    )


def _compile_map(code, node, defaults):
    """
    Create code for the final "map" operation.
    """
    updated_expression = _retarget_jumps(
        node.start - len(node.inputs.stack), node.stack
    )
    new_code = _clone_code(
        code,
        "<map>",
        _retarget_lnotab(node.lnotab, len(node.inputs.stack)),
        chain(node.inputs.stack, updated_expression),
        defaults,
    )

    stack = []
    add_op(stack, LOAD_FAST, INTERFACE)  # Load interface
    add_op(stack, LOAD_CONST, MAP)  # Load interface name
    add_op(stack, LOAD_FAST, ".0")  # Load monad
    add_op(stack, GET_ITER)
    stack.extend(_make_function(code, new_code))
    add_op(stack, CALL_FUNCTION, 3)
    return MapFunc(stack)


def _compile_guard(code, node, defaults):
    """
    Create code out of a guard, translates into "filter" code.
    """
    updated_guard = _retarget_jumps(node.start - len(node.inputs.stack), node.stack)

    post_stack = []
    add_op(
        post_stack,
        POP_JUMP_IF_TRUE if node.state else POP_JUMP_IF_FALSE,
        len(node.inputs.stack)
        + len(node.stack)
        + op_offset(POP_JUMP_IF_TRUE)
        + op_offset(LOAD_CONST)
        + op_offset(JUMP_FORWARD),
    )
    add_op(post_stack, LOAD_CONST, True)
    add_op(post_stack, JUMP_FORWARD, op_offset(LOAD_CONST))
    add_op(post_stack, LOAD_CONST, False)
    add_op(post_stack, RETURN_VALUE)

    new_code = _clone_code(
        code,
        "<guard>",
        _retarget_lnotab(node.lnotab, len(node.inputs.stack)),
        chain(node.inputs.stack, updated_guard, post_stack),
        defaults,
    )

    stack = []
    add_op(stack, LOAD_FAST, INTERFACE)  # Load interface
    add_op(stack, LOAD_CONST, FILTER)  # Load interface name
    add_op(stack, LOAD_FAST, ".0")  # Load monad
    add_op(stack, GET_ITER)
    stack.extend(_make_function(code, new_code))
    add_op(stack, CALL_FUNCTION, 3)

    return FilterFunc(stack)


def _retarget_lnotab(lnotab, instruction_offset):
    for offset, line in lnotab:
        yield offset + instruction_offset, line


def _retarget_jumps(offset, stack):
    """Change absolute jump targets to match new numbering"""
    last_op = None
    for op in stack:
        if last_op in dis.hasjabs:
            op -= offset
        yield op
        last_op = op


def _clone_code(code, name, lnotab, byte_stack, defaults):
    """Helper for building a new code object out of the old"""
    consts = list(code.co_consts)
    varnames = [".0"]
    varnames.extend(defaults)
    nonlocal_ = {"stacksize": 1}

    def retarget(byte_stack):
        op = None
        for arg in byte_stack:

            if op in dis.haslocal:
                if type(arg) == int:
                    arg = code.co_varnames[arg]
                try:
                    yield varnames.index(arg)
                except ValueError:  # Not yet in varnames
                    yield len(varnames)
                    varnames.append(arg)

            elif op in dis.hasconst:  # Initial constants are just reused
                if type(arg) != int:
                    try:
                        yield consts.index(arg)
                    except ValueError:  # Not yet in consts
                        yield len(consts)
                        consts.append(arg)
                else:
                    yield arg
            else:
                yield arg

            if isinstance(op, int) and "LOAD" in dis.opname[op]:
                nonlocal_["stacksize"] += 1
            op = arg

    bytes_ = to_bytes(retarget(byte_stack))

    args = (
        len(defaults) + 1,  # code.co_argcount,
        0,  # code.co_posonlyargcount,
        0,  # code.co_kwonlyargcount,
        len(varnames),  # code.co_nlocals,
        nonlocal_["stacksize"],
        inspect.CO_OPTIMIZED | inspect.CO_NEWLOCALS | inspect.CO_NESTED,
        bytes_,
        tuple(consts),
        code.co_names,
        tuple(varnames),
        code.co_filename,
        name,
        code.co_firstlineno,
        to_bytes(_compress_lnotab(lnotab, code.co_firstlineno)),  # code.co_lnotab,
        code.co_freevars,
        code.co_cellvars,
    )
    if PY2:
        args = args[:1] + args[3:]
    elif not PY38:
        args = args[:1] + args[2:]

    return CodeType(*args)


def _compress_lnotab(lnotab, firstline):
    # Return table back to its relative state
    last_offset = 0
    last_line = firstline
    for offset, line in lnotab:
        yield offset - last_offset
        line_offset = line - last_line
        if line_offset < 0:
            line_offset += 0x100
        yield line_offset

        last_offset, last_line = offset, line


# Lifted from dis.disassemble
if PY2:

    def _make_function(code, nested_code):
        # Load up all defaults that were requested by the nested funcion.
        has_closure = code.co_freevars

        stack = []
        for i in range(1, nested_code.co_argcount):
            add_op(
                stack,
                LOAD_FAST,
                nested_code.co_varnames[i],
            )

        # If we are in a closure, we have to handle passing the closure forward.
        # Build a tuple with all closure variables (for simplicity) and pass that on.
        if has_closure:
            for a in range(len(nested_code.co_freevars)):
                add_op(stack, LOAD_CLOSURE, a)
            add_op(stack, BUILD_TUPLE, len(nested_code.co_freevars))

        # Finally tack on our nested function creation and call.
        # Adding in a spot where we can short circut and return should we need to.
        add_op(stack, LOAD_CONST, nested_code)  # Code object for nested code
        add_op(
            stack,
            MAKE_CLOSURE if has_closure else MAKE_FUNCTION,
            nested_code.co_argcount - 1,
        )
        return stack


else:

    def _make_function(code, nested_code):
        # Load up all defaults that were requested by the nested funcion.
        has_defaults = nested_code.co_argcount > 1
        has_closure = code.co_freevars

        stack = []
        if has_defaults:
            for i in range(1, nested_code.co_argcount):
                add_op(
                    stack,
                    LOAD_FAST,
                    nested_code.co_varnames[i],
                )
            add_op(stack, BUILD_TUPLE, nested_code.co_argcount - 1)

        # If we are in a closure, we have to handle passing the closure forward.
        # Build a tuple with all closure variables (for simplicity) and pass that on.
        if has_closure:
            for a in range(len(nested_code.co_freevars)):
                add_op(stack, LOAD_CLOSURE, a)
            add_op(stack, BUILD_TUPLE, len(nested_code.co_freevars))

        # Finally tack on our nested function creation and call.
        # Adding in a spot where we can short circut and return should we need to.
        add_op(stack, LOAD_CONST, nested_code)  # Code object for nested code
        add_op(stack, LOAD_CONST, nested_code.co_name)  # Code name for nested code
        add_op(
            stack,
            MAKE_FUNCTION,
            (0x08 if has_closure else 0x00) | (0x01 if has_defaults else 0x00),
        )
        return stack
