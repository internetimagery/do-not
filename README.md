# Python meets do notation [![Build Status](https://app.travis-ci.com/internetimagery/do-not.svg?branch=main)](https://app.travis-ci.com/internetimagery/do-not)

Monaic do notation with python for comprehensions

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

That said... here is a basic working Maybe example (using attrs):

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
