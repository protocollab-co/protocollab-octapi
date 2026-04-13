"""Static validation of expressions — checks for syntax issues."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.expression.ast_nodes import (
    ASTNode,
    Attribute,
    BinOp,
    Call,
    Dict,
    List,
    Name,
    Subscript,
    Ternary,
    UnaryOp,
)
from app.expression.lexer import ExpressionSyntaxError
from app.expression.parser import parse_expr

if TYPE_CHECKING:
    pass


@dataclass
class ExprError:
    """A single expression validation error."""

    message: str
    pos: int = -1

    def __str__(self) -> str:
        if self.pos >= 0:
            return f"[pos {self.pos}] {self.message}"
        return self.message


def _collect_names(node: ASTNode, names: set[str]) -> None:
    """Recursively collect all free Name references in *node*."""
    match node:
        case Name(name=n):
            names.add(n)
        case Attribute(obj=obj):
            _collect_names(obj, names)
        case Subscript(obj=obj, index=idx):
            _collect_names(obj, names)
            _collect_names(idx, names)
        case UnaryOp(operand=op):
            _collect_names(op, names)
        case BinOp(left=l, right=r):
            _collect_names(l, names)
            _collect_names(r, names)
        case Ternary(condition=c, value_if_true=vt, value_if_false=vf):
            _collect_names(c, names)
            _collect_names(vt, names)
            _collect_names(vf, names)
        case Call(func=f, args=args):
            _collect_names(f, names)
            for a in args:
                _collect_names(a, names)
        case List(elements=elems):
            for e in elems:
                _collect_names(e, names)
        case Dict(pairs=pairs):
            for k, v in pairs:
                _collect_names(k, names)
                _collect_names(v, names)


def validate_expr(expr_str: str) -> list[ExprError]:
    """Statically validate *expr_str*.

    Returns
    -------
    list[ExprError]
        Empty list means the expression is valid.
    """
    try:
        parse_expr(expr_str)
    except ExpressionSyntaxError as exc:
        return [ExprError(message=str(exc), pos=exc.pos)]
    return []
