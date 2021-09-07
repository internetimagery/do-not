# Python meets do notation [![Build Status](https://app.travis-ci.com/internetimagery/do-not.svg?branch=main)](https://app.travis-ci.com/internetimagery/do-not)

Monaic do notation with python for comprehensions. Currently tested on python 2.7, 3.6 ~ 3.9.

A simple repurposing of the generator comprehension to serve as do notation / for comprehension.

Example...

```python

def get_shoe_asset():
    selection = current_selection()
    if not selection:
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
    for costume in get_costume(selection)
    for shoes in get_shoes(costume)
)

```

> How can I use this for myself?

This library does not bundle an implimentation of Monads itself, by design. Instead it
asks if you can support it, by using ```__iter__``` to expose whatever interface
your existing monadic system is using.

```python
def __iter__(self):
    yield self.flat_map
    yield self.pure
```

The interface is queried through iter, and it is expected that it return a callable
with the standard interfaces for flat_map and pure. There is no restriction that they be named those functions. Chain, bind, andThen, unit, point, lift. Methods, or functions. It doesn't matter so long as they are callable and take a value.

* flat_map: Callable that takes a value, and returns a value wrapped in the same context.
* pure: Constructor that takes a value and wraps it in a context.

That said... here is a basic Maybe example (using attrs):

```python

@attr.s
def Nothing:
    """ Represents the lack of a value """
    def map(self, func):
    	return self

    def flat_map(self, func):
    	return self

    def __iter__(self): # Expose interface to do notation
        yield self.flat_map
	yield self.__class__

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

Or dependency injection with Reader:

```python

@attr.s
class Reader:
    func = attr.ib()

    @classmethod
    def pure(cls, value):
        return cls(lambda _: value)

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
    	yield self.flat_map
	yield self.pure


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
