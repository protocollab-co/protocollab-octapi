"""AST node definitions for the local expression language (extended from protocollab)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List as _List, Union

# ---------------------------------------------------------------------------
# Type alias for any AST node
# ---------------------------------------------------------------------------
ASTNode = Union[
    "Literal",
    "Name",
    "Attribute",
    "Subscript",
    "UnaryOp",
    "BinOp",
    "Ternary",
    "Call",
    "List",
    "Dict",
]


# ---------------------------------------------------------------------------
# Leaf nodes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Literal:
    """An integer, float, string, or boolean literal value."""

    value: Any  # int | float | str | bool


@dataclass(frozen=True)
class Name:
    """A bare identifier that looks up a value in the evaluation context."""

    name: str


# ---------------------------------------------------------------------------
# Compound nodes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Attribute:
    """Dotted attribute access: ``parent.field_name``."""

    obj: ASTNode
    attr: str


@dataclass(frozen=True)
class Subscript:
    """Indexing: ``arr[0]``, ``arr[-1]``."""

    obj: ASTNode
    index: ASTNode


@dataclass(frozen=True)
class UnaryOp:
    """Unary prefix operator: ``-x``, ``not flag``, ``#arr``."""

    op: str  # "-" | "not" | "#"
    operand: ASTNode


@dataclass(frozen=True)
class BinOp:
    """Binary infix operator."""

    left: ASTNode
    op: str
    right: ASTNode


@dataclass(frozen=True)
class Ternary:
    """Python-style ternary: ``value_if_true if condition else value_if_false``."""

    value_if_true: ASTNode
    condition: ASTNode
    value_if_false: ASTNode


@dataclass(frozen=True)
class Call:
    """Function call: ``func(arg1, arg2, ...)``."""

    func: ASTNode
    args: tuple


@dataclass(frozen=True)
class List:
    """List / array literal: ``[a, b, c]``."""

    elements: tuple


@dataclass(frozen=True)
class Dict:
    """Dictionary / table literal: ``{key: value, ...}``.

    Each item in *pairs* is a 2-tuple ``(key_node, value_node)``.
    """

    pairs: tuple
