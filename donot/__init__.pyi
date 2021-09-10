from typing import overload, TypeVar, Generator, Any, Type

T = TypeVar("T")

@overload
def do(generator: Generator, type_: Type[T]) -> T: ...

@overload
def do(generator: Generator) -> Any: ...
