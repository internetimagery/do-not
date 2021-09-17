import typing as _typ


MAP: _typ.Final[str]
FLATMAP: _typ.Final[str]
FILTER: _typ.Final[str]
HANDLER_NAMES: _typ.Final[_typ.Tuple[str, str, str]]

def do(generator: _typ.Generator) -> _typ.Any: ...
