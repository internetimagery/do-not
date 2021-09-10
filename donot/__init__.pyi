import typing as _typ

_T = _typ.TypeVar("_T")


class _DoType(_typ.Generic[_T]):
    def __call__(self, generator: _typ.Generator) -> _T: ...

class _Do(object):

    def __getitem__(self, item: _typ.Type[_T]) -> _DoType[_T]: ...

    def __call__(self, generator: _typ.Generator): ...

do = _Do()

