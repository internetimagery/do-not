# Python meets do notation [![Build Status](https://app.travis-ci.com/internetimagery/do-not.svg?branch=main)](https://app.travis-ci.com/internetimagery/do-not)

Monaic do notation with python for comprehensions. Currently tested on python 2.7, 3.6 ~ 3.9.

A simple repurposing of the generator comprehension to serve as do notation / for comprehension. Similar to Scala for comprehensions.

Example...

```python

def get_shoe_asset():
    selection = current_selection()
    if not selection:
        return None
    if len(selection) != 1:
        return None
    costume = get_costume(selection)
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
    if len(selection) == 1
    for costume in get_costume(selection)
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
    current_selection()                                 # for selection in current_selection()
    .filter(lambda selection: len(selection == 1))      # if len(selection) == 1
    .flat_map(lambda selection:				# 
        get_costume(selection).flat_map(lambda costume: # for costume in get_costume(selection)
	    get_shoes(costume).map(lambda shoes:        # for shoes in get_shoes(costume)
	        shoes.asset_type                        # shoes.asset_type
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

This library intentionally does not bundle implimentations of monads itself. It is a utility for existing implimentations to hook into.

----

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
	
```

Equal to:

```python

value = Just(1).flat_map(lambda v1:
    Just(2).flat_map(lambda v2:
        Just(3).flat_map(lambda v3:
	    v1 + v2 + v3
	)
    )
)

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

How does this work?

Upon execution, the generator code object is introspected, and a new code object built.

Thankfully we can leave the majority of the original code object intact. So even though the underlying bytecode is not guranteed to be consistent amongst python versions, we only need a tiny subset of it to remain stable.


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

[GenMonads; A similar and inspirational project.](https://github.com/underspecified/GenMonads)

----

TODO: Find a better way to generically handle if statements in the body. Having it work like a case statement
(as it currently is) is useful in some situations. However it's more likely useful to have a meaningful return
value instead. Some monads like Maybe/Either support switching to their alternate path, but for many others it makes
no sense. A possible solution could be a second argument to "do" that acts as a fallback default. Or for the monad
to expose another interface that handles this for us (and we use that instead of "pure" where available).

Scala uses "withFilter" and if you don't support that, you're not using that monad. Perhaps that is the way forward here too...
though not many monads can make use of it.

Also guards can exist as expressions... eg

```python
val = do(
    v1 + v2
    for v1 in Just(10)
    for v2 in Just(11) if v1 else Nothing()
)
```
