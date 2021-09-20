# Python meets do notation [![Build Status](https://app.travis-ci.com/internetimagery/do-not.svg?branch=main)](https://app.travis-ci.com/internetimagery/do-not)

Monaic do notation with python for comprehensions. Currently tested on python 2.7, 3.6 ~ 3.9, pypy, pypy3.

A simple repurposing of the generator comprehension to serve as do notation / for comprehension. Similar to Scala for comprehensions.

Example...

```python

def get_shoe_asset():
    selection = current_selection()
    if not selection:
        return None
    if len(selection) != 1 or selecton[0].asset_type != "human":
        return None
    costume = get_costume(selection[0])
    if not costume:
        return None
    shoes = get_shoes(costume)
    if not shoes:
        return None
    return shoes.asset_type

```

Could be written with the Maybe/Option monad in do notation as such:

```python

asset_type = do(
    shoes.asset_type
    for selection in current_selection()
    if len(selection) == 1 and selection[0].asset_type == "human"
    for costume in get_costume(selection[0])
    for shoes in get_shoes(costume)
)

```

## Syntax Breakdown

Taking the previous example, we can break up the syntax into what it is doing "under the hood".
It's important to know how to write out the same code in long form, to truly understand what it is doing.

Also to understand that while there is a little bit of magic going on (to get the syntax working), it's nothing that
cannot be backed out of in the future and written easily by hand.

- _if-statements_ in the body translate to "filter" calls.
- _for A in B_ statements translate to "flat_map" calls.
- _for A in B_ the final statement translates to a "map" call.


```python

asset_type = (
    current_selection()                                                 # for selection in current_selection()
    .filter(lambda selection:
    	len(selection == 1) and selection[0].asset_type == "human"      # if len(selection) == 1 and selection[0].asset_type == "human"
    ).flat_map(lambda selection:				        # 
        get_costume(selection).flat_map(lambda costume:                 # for costume in get_costume(selection)
	    get_shoes(costume).map(lambda shoes:                        # for shoes in get_shoes(costume)
	        shoes.asset_type                                        # shoes.asset_type
	    )
	)
    )
)

```

## Installation

Install direct from github:

```
pip install git+https://github.com/internetimagery/do-not.git#egg=donot
```

```python
from donot import do
```

## Usage

```python
def __iter__(self):
    yield {
        "map": self.map,
	"flat_map": self.flat_map,
	"filter": self.filter, # Not required
    }
```

In order to have your monadic classes support this functionality, all they have to do is expose their interface through `__iter__`.
There is no need to have an explicit requirement on this library in order to support it. Furthermore other features could be added as new dict keys in the future (for this library or any other).

The supported interfaces are:

* __map__: Callable that takes a function, and returns the result of the function wrapped in the same context.
* __flat_map__: Callable that takes a _function that returns the same context_, and returns that value.
* __filter__: Callable that takes a _function that returns a boolean_. Propagates values if True else provides some fallback value.

So long as the exposed interface is a callable that accepts a function, and behaves in a standard way, nothing more is needed.
This means you can use methods with different names (chain/bind/and_then/etc) and even use regular functions and dataclasses,
and it's all supported (so long as the dataclasses are given this `__iter__` functionality, perhaps in a mixin).

## Static Type Checking

This library contains a stub file to provide static type hints to checkers. With some trickery on the supporting monads part, we can get 90% of the way to complete type checking.
Unfortunately python does not support higher kinded types, and so the return type cannot be correctly inferred (we can get the inner type from the generator, but not the outer monad type).

This means type annotations are really required.

```python
val: Just[str] = do(
    a 
    for a in Just("parameter!")
)
```

Complete example below:

```python

from typing import Any, Callable, Generic, Iterator, TypeVar, TYPE_CHECKING
from donot import do

A = TypeVar("A")
B = TypeVar("B")

class Monad(Generic[A]):
    def __init__(self, value: A) -> None:
        self._value = value

    def map(self, func: Callable[[A], B]) -> Monad[B]:
        return Monad(func(self._value))

    def flat_map(self, func: Callable[[A], Monad[B]]) -> Monad[B]:
        return func(self._value)

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, self.__class__):
            return NotImplemented
        return self._value == other._value

    def __iter__(self) -> Iterator[A]:
        # Ensure we type-ignore this line. We're lying about the
	# return type, to correctly type within the do block. ;)
        yield {"map": self.map, "flat_map": self.flat_map} # type: ignore

val1 = do(v for v in Monad("hi"))
assert val1 == Monad("hi")

val2: Monad[str] = do(v for v in Monad("hi"))
assert val2 == Monad("hi")

if TYPE_CHECKING:
    # Without higher kinded type support, we cannot correctly infer
    # the output... even though we know the inner value.
    reveal_type(val1) # Note: Revealed type is "Any"

    # So instead we can at least provide the type as a parameter
    # to "force" it to work "correctly".
    # NOTE: Anything can go in there, so it truly is an escape hatch...
    reveal_type(val2) # Note: Revealed type is "Monad[str]"

    # Types are correctly detected within the expression if typed on the __iter__ return (as above).
    val = do(v1 + v2 for v1 in Monad("hi") for v2 in Monad(2)) # Error: Unsupported types "str" and "int"

```

## Extensions

While this tool by default expects a simple dict to be presented exposing the objects
interface. If this is not something you wish to use, this functionality
can be overridden.

```python

from functools import partial
from donot import do, MAP, FLATMAP, FILTER

def my_handler(name: str, obj: Iterator, func: Callable[[A], B]):
    # Name is the interface name; map; flat_map; filter.
    # Obj is the object returned from the __iter__ method being invoked.
    # Func is the next function in the chain.
    if name == MAP:
        ...
    elif name == FLATMAP:
        ...
    elif name == FILTER:
        ...

new_do = partial(do, handler=my_handler)

```

----

## More Examples

This library intentionally does __not__ bundle implimentations of monads itself. It is a utility for existing implimentations to hook into.

Though monads are not provided here...  here are some basic examples (using attrs):

#### Maybe/Option (for handling a potentially missing value)

```python

@attr.s
def Nothing:
    """ Represents the lack of a value """
    def map(self, func):
    	return self

    def flat_map(self, func):
    	return self

    def filter(self, func):
        return self

    def __iter__(self): # Expose interface to do notation
	yield {"map": self.map, "flat_map": self.flat_map}

@attr.s
def Just(Nothing):
    """ Represents an existing value """
    value = attr.ib()

    def map(self, func):
        return self.__class__(func(self.value))

    def flat_map(self, func):
        return func(self.value)

    def filter(self, func):
        return self if func(self.value) else Nothing()

```

```python

value = do(
    v1 + v2 + v3
    for v1 in Just(1)
    for v2 in Just(2)
    for v3 in Just(3)
)
assert value == Just(6)

value = do(
    v1 + v2 + v3
    for v1 in Just(1)
    for v2 in Nothing()
    for v3 in Just(3)
)
assert value == Nothing()
	
value = do(
    v1 + v2
    for v1 in Just(1)
    if v1 > 3 # Filters to "Nothing"
    for v2 in Just(3)
)
assert value == Nothing()
```

#### Reader (for handling a simple dependency injection)

```python

@attr.s
class Reader:
    func = attr.ib()

    def map(self, func):
        return self.__class__(lambda env: func(self.func(env)))

    def flat_map(self, func):
        return self.__class__(lambda env: func(self.func(env)).run(env))

    def run(self, env):
        return self.func(env)

    @classmethod
    def ask(cls):
    	""" Request the dependency """
        return cls(lambda env: env)

    def __iter__(self): # Expose interface to do notation
    	yield {"map": self.map, "flat_map": self.flat_map}

```

```python

def fullname(firstname):
    return do(
        "{} {}".format(firstname, lastname)
	for lastname in Reader.ask()
    )

people = do(
    "{} and {}".format(joe, joanne)
    for joe in fullname("Joe")
    for joanne in fullname("Joanne")
).run("Bloggs")
assert people == "Joe Bloggs and Joanne Bloggs"

```

----

#### How does this work?

Upon execution, the generator code object is inspected, and a new code object built.

Thankfully we can leave the majority of the original code object intact. So even though the underlying bytecode is not guranteed to be consistent amongst python versions, we only need a tiny subset of it to remain stable. Thus there is very little that needs to exist for compatability with python 2.7, 3.6+ and pypy. Encouraging! :)

- Splitting on a ```GET_ITER``` followed by ```FOR_ITER``` lets us break up the "flat_map" and "map" ie the nested code.
- Splitting on a ```POP_JUMP_IF_TRUE``` (and family) when the target of the jump is a ```FOR_ITER``` lets us break out filters.
- Tracking the tuple size count after the split ```FOR_ITER``` gets us the end of the assigned variables (which we track).
- Everything in between is the main expression or the filter expression, which includes all the complexity we can simply leave as is.

- A new function is generated for each of the interfaces. Passing scoped variables as default arguments. Treated like dependencies.
- Also a handler for dealing with the interfaces is passed as an argument. The handler can be changed by calling code if desired.
- Generator closure and globals are simply copied into the functions.

#### Why use this syntax?

- Some other examples use yield, and async/await does that too. The trouble with yield is you cannot backtrack. Certain monads have the ability to rerun the function multiple times and generators do not allow this. Otherwise yield is a nice option.
- It's possible to override some built in operators (ie >>=) to store the value, and break up the ast. The trouble here is the complexity when anything else is allowed to exist. What happens when we use the operator in a loop for instance? How do we break up the code then? It's also an uphill battle with linters when changing the meaning behind defined syntax.
- Comprehension syntax is smaller, concise, manageable.
- Comprehensions fit within other code. Unlike decorators which need to exist outside a function, and transform the outer code as well.
- There is a precident set already in Scala with "for comprehensions" doing the same thing.
- In fact, a simple List monad can also be built to demo that these comprehension syntaxes are already somewhat monadic. eg

```python
@attr.s
class List:
    lst = attr.ib()

    def map(self, func):
        lst = []
	for item in self.lst:
	    lst.append(item)
	return List(lst)

    def flat_map(self, func):
        lst = []
	for inner in self.lst:
	    for item in func(inner).lst:
	        lst.append(item)
	return List(lst)

    def filter(self, func):
        lst = []
	for item in self.lst:
	    if func(item):
	        lst.append(item)
        return List(lst)

    def __iter__(self):
        yield {"map": self.map, "flat_map": self.flat_map, "filter": self.filter}
```

```python
result = do(
    v1 + v2
    for v1 in List([1,2,3])
    for v2 in List([4,5,6])
)
assert result.lst = [v1+v2 for v1 in [1,2,3] for v2 in [4,5,6]]
```
----

#### TODO

- Document things internally more clearly.
- Work on a static typing solution for return values. Thankfully internal values can be easily typed, but without higher kinded types the return value cannot be easily checked.
- Build a decorator that can pre-compile "do" generators (does it make sense to compile all generators?).
- Support walrus assignments in "guard" expressions. ie ```do(v1 + v2 for v1 in Just(10) if (v2 := v1 + 10))```

----

[Another similar approach using the AST and Haskell-like bind operator.](https://gist.github.com/internetimagery/7012246ac8aae8fa5e185f634db60582)

```python
@do
def add_em():
    num1 <<= Just(10)
    num2 <<= Just(20)
    return num1 + num2
assert add_em() == Just(30)
```

- [GenMonads; A similar and inspirational project.](https://github.com/underspecified/GenMonads)
- [monad-do; Another similar approach using yields and decorators.](https://pypi.org/project/monad-do/)

----

![monad meme](https://memegenerator.net/img/instances/59509745/what-if-i-told-you-that-a-monad-is-just-a-monoid-in-the-category-of-endofunctors.jpg)
