# MIT License
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import sys

PY2 = sys.version_info[0] == 2

import dis
import inspect
from weakref import WeakKeyDictionary
from types import CodeType, FunctionType
if PY2:
    CellType = lambda v: (lambda: v).func_closure[0]
    to_bytes = lambda a: bytes(bytearray(a))
    as_byte = ord
else:
    from types import CellType
    to_bytes = bytes
    as_byte = lambda x: x


# Retain our processed code to save on code recalls
_cache = WeakKeyDictionary()


def do(generator):
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

    if-expressions in the body act as a short circut, returning the last executed

    >>> val = do(
    >>>     v1 + v2
    >>>     for v1 in Just(10)
    >>>     if v1 > 20 # Short circut
    >>>     for v2 in Just(20)
    >>> )
    >>> assert val == Just(10) # Last value returned before if-expression

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
    >>>     yield self.flat_map # chain # and_then # bind # __call__ # etc...
    >>>     yield self.pure # unit # lift # point # __new__ # etc...
    """
    try:
        monad = generator.gi_frame.f_locals[".0"]
    except (AttributeError, KeyError):
        raise TypeError(
            "Provided argument is not a valid generator expression. Got: '{}'".format(generator)
        )
    try:
        flat_map, pure = next(monad), next(monad)
    except StopIteration:
        raise TypeError(
            "Monad interface not exposed correctly. Please ensure you yield 'flat_map' then 'pure'"
        )

    code = generator.gi_code
    cached_code = _cache.get(code)
    if not cached_code:
        code_iter = _unpack_opargs(code.co_code)
        assert LOAD_FAST == next(code_iter)[1] # skip first command
        cached_code, _ = _cache[code], _ = _extract_code(code, code_iter)

    func = FunctionType(
        cached_code,  # The code itself
        generator.gi_frame.f_globals,  # globals dict
        "<do_block>",  # name of func
        (pure,),
        tuple(CellType(generator.gi_frame.f_locals[v]) for v in code.co_freevars),
    )
    return flat_map(func)


STORE_FAST = dis.opmap["STORE_FAST"]
LOAD_FAST = dis.opmap["LOAD_FAST"]
LOAD_CONST = dis.opmap["LOAD_CONST"]
LOAD_CLOSURE = dis.opmap["LOAD_CLOSURE"]
BUILD_TUPLE = dis.opmap["BUILD_TUPLE"]
MAKE_CLOSURE = dis.opmap.get("MAKE_CLOSURE") # Python2
MAKE_FUNCTION = dis.opmap["MAKE_FUNCTION"]
CALL_FUNCTION = dis.opmap["CALL_FUNCTION"]
RETURN_VALUE = dis.opmap["RETURN_VALUE"]
YIELD_VALUE = dis.opmap["YIELD_VALUE"]
GET_ITER = dis.opmap["GET_ITER"]
FOR_ITER = dis.opmap["FOR_ITER"]
JUMP_FORWARD = dis.opmap["JUMP_FORWARD"]
UNPACK_SEQUENCE = dis.opmap["UNPACK_SEQUENCE"]

# Lifted from dis.disassemble
if PY2:
    def _pack_opargs(stack, op, arg=None):
        if arg is None:
            stack.append(op)
        else:
            stack.extend((op, arg, 0))
        return stack

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

    def _make_function(add_op, code, defaults, layout):
        # Load up all defaults that were requested by the nested funcion.
        for a in defaults:
            add_op(LOAD_FAST, layout.index(a))

        # If we are in a closure, we have to handle passing the closure forward.
        # Build a tuple with all closure variables (for simplicity) and pass that on.
        if code.co_freevars:
            for a in range(len(code.co_freevars)):
                add_op(LOAD_CLOSURE, a)
            add_op(BUILD_TUPLE, len(code.co_freevars))

        # Finally tack on our nested function creation and call.
        # Adding in a spot where we can short circut and return should we need to.
        add_op(LOAD_CONST, len(code.co_consts))  # Code object for nested code
        add_op(MAKE_CLOSURE if code.co_freevars else MAKE_FUNCTION, len(defaults))

else:
    # PY3
    def _pack_opargs(stack, op, arg=None):
        stack.extend((op, arg or 0))
        return stack

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

    def _make_function(add_op, code, defaults, layout):
        # Load up all defaults that were requested by the nested funcion.
        for a in defaults:
            add_op(LOAD_FAST, layout.index(a))
        add_op(BUILD_TUPLE, len(defaults))

        # If we are in a closure, we have to handle passing the closure forward.
        # Build a tuple with all closure variables (for simplicity) and pass that on.
        if code.co_freevars:
            for a in range(len(code.co_freevars)):
                add_op(LOAD_CLOSURE, a)
            add_op(BUILD_TUPLE, len(code.co_freevars))

        # Finally tack on our nested function creation and call.
        # Adding in a spot where we can short circut and return should we need to.
        add_op(LOAD_CONST, len(code.co_consts))  # Code object for nested code
        add_op(LOAD_CONST, len(code.co_consts) + 1)  # Code name for nested code
        add_op(MAKE_FUNCTION, 9 if code.co_freevars else 1)  # 9 = closure+defaults, 1 = defaults


def _extract_code(code, byte_iter):
    stack = []
    add_op = lambda o, a=None: _pack_opargs(stack, o, a)
    add_op(LOAD_FAST, 0) # Load inital argument
    initial_arg_offset = len(stack)

    assert FOR_ITER == next(byte_iter)[1]

    # First thing the generator does it to store its variables. Keep it doing that,
    # and track which variables we get added in this scope from the function just run.

    inputs = []
    num_unpack = 1
    offset = 0
    while num_unpack:
        num_unpack -= 1

        (i, op, arg) = next(byte_iter)
        if not offset:
            offset = i - initial_arg_offset
        if op == STORE_FAST:
            inputs.append(code.co_varnames[arg])
        elif op == UNPACK_SEQUENCE:
            num_unpack += arg
        else:
            raise AssertionError("Unexpected operation {}".format(dis.opname[op]))
        add_op(op, arg)

    inputs = tuple(inputs) # Inputs provided by the most recent generator.


    for _, op, arg in byte_iter:

        # Found start of inner iterator.
        # This command gets the previous iterator in order to loop over it
        # but in this case, it's where we want to break up the logic.
        if op == GET_ITER:
            #####################################################################
            # Becomes: return <expr>.flat_map(<code>)                           #
            # Or: return <expr>.flat_map(<code>) if <cond> else M.pure(<val>) #
            #####################################################################

            # Build nested function. Get back its code object, and the variables it
            # expects to be supplied as defaults.
            nested_code, nested_defaults = _extract_code(code, byte_iter)

            # Build up our list of arguments we need provided to us as defaults.
            # Our dependencies if you will...
            defaults = tuple(v for v in nested_defaults if v not in inputs)

            # Build out our layout for function arguments and variable indices
            var_layout = (".0",) + defaults + inputs

            # Get number of arguments. Number determines which variables will be in the
            # functions signature. All the defaults we need plus one for ".0".
            num_args = len(defaults) + 1

            stack = [
                # Retarget jumps, and mark jumps that leave the stack (in body if expressions)
                (-1 if as_byte(code.co_code[s]) == FOR_ITER else s - offset) if stack[i-1] in dis.hasjabs else
                # Retarget local variables to the new local layout
                (s and var_layout.index(code.co_varnames[s])) if stack[i-1] in dis.haslocal else s
                for i, s in enumerate(stack)
            ]

            # Request the flat_map interface from the provided monad.
            # Since we don't know exactly how big our stack will be; Mark the jump point as
            # something invalid, and we will fix it later.
            add_op(GET_ITER)
            for_index = len(stack) + 1 # Store for alteration later
            add_op(FOR_ITER, -99)
            post_for_index = len(stack)

            _make_function(add_op, code, nested_defaults, var_layout)

            add_op(CALL_FUNCTION, 1)  # 1 = Num arguments from the stack. Always one in our case.
            # Fallback for if statements that need to break out
            jump_index = len(stack) + 1
            add_op(JUMP_FORWARD, -99) # Jump over the fallback
            fallback_index = len(stack)
            add_op(LOAD_FAST, 1) # Load M.pure
            add_op(LOAD_FAST, 0) # Load last value
            add_op(CALL_FUNCTION, 1) # Run pure over value
            # And back
            return_index = len(stack)
            add_op(RETURN_VALUE) # Return result of expression

            # Fix up the jumps that need fixing.
            stack = [
                # Retarget "if expressions" that short circut, to use our fallback instead.
                fallback_index if stack[i-1] in dis.hasjabs and s == -1 else s
                for i, s in enumerate(stack)
            ]
            stack[jump_index] = return_index - fallback_index
            stack[for_index] = fallback_index - post_for_index
            return _clone_code(code, to_bytes(stack), (nested_code, "<generated>"), var_layout, num_args), defaults

        # Found end of iterator
        # This is where we would otherwise be yielding a value, so it's
        # ultimately the same as the final return location. This also means it's where
        # the final expression resides.
        if op == YIELD_VALUE:
            ####################################################
            # Becomes: return M.pure(<expr>)                 #
            # Or: return M.pure(<expr> if <cond> else <val>) #
            ####################################################

            # Collect arguments not provided by the most recent generator for use as default
            # arguments to this function (provided by the previous function in the stack).
            # Include a requirement on the M.pure function.
            defaults = ("M.pure",) + tuple(v for v in code.co_varnames[1:] if v not in inputs)

            # Organize a layout for our argument order. We want the values provided to us
            # to be after the defaults (ie not in the range of actual function arguments).
            var_layout = (".0",) + defaults + inputs

            # Number represents which variable names will be represented as function arguments.
            # All our defaults, plus one for ".0" input.
            num_args = len(defaults) + 1

            stack = [
                # Retarget jumps, and mark jumps that leave the stack (in body if expressions)
                (-1 if as_byte(code.co_code[s]) == FOR_ITER else s - offset) if stack[i-1] in dis.hasjabs else
                # Retarget local variables to the new local layout
                (s and var_layout.index(code.co_varnames[s])) if stack[i-1] in dis.haslocal else s
                for i, s in enumerate(stack)
            ]

            add_op(STORE_FAST, 0) # Store evaluation in ".0"
            # Include fallback for if statements
            fallback_index = len(stack)
            add_op(LOAD_FAST, 1) # Load M.pure
            add_op(LOAD_FAST, 0) # Load the last value
            # And back from fallback
            add_op(CALL_FUNCTION, 1)
            add_op(RETURN_VALUE)

            stack = [
                # Retarget "if expressions" that short circut, to use our fallback instead.
                fallback_index if stack[i-1] in dis.hasjabs and s == -1 else s
                for i, s in enumerate(stack)
            ]
            return _clone_code(code, to_bytes(stack), (), var_layout, num_args), defaults

        # Keep accumulating commands as we walk through the code
        add_op(op, arg)

def _clone_code(code, bytecode, consts, varnames, argcount):
    """ Helper for building a new code object out of the old """
    args = (
        argcount, # code.co_argcount,
        0,  # code.co_posonlyargcount,
        0,  # code.co_kwonlyargcount,
        len(varnames), #code.co_nlocals,
        max(code.co_stacksize, len(varnames)) + 1,
        inspect.CO_OPTIMIZED | inspect.CO_NEWLOCALS | inspect.CO_NESTED,
        bytecode,
        code.co_consts + consts, # Add our nested function as constant
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

    return CodeType(*args)

