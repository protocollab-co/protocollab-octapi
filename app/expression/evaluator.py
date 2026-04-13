"""Evaluate a parsed AST in a field-value context."""

from __future__ import annotations

import operator
from typing import Any, Callable

from app.expression.ast_nodes import (
    ASTNode,
    Attribute,
    BinOp,
    Call,
    Dict,
    List,
    Literal,
    Name,
    Subscript,
    Ternary,
    UnaryOp,
)


class ExpressionEvalError(Exception):
    """Raised when expression evaluation fails at runtime."""

    def __init__(self, message: str, expr_source: str = "") -> None:
        self.expr_source = expr_source
        super().__init__(message)


# ---------------------------------------------------------------------------
# Operator dispatch table
# ---------------------------------------------------------------------------
_BINOP_TABLE: dict[str, Callable[[Any, Any], Any]] = {
    "+": operator.add,
    "-": operator.sub,
    "*": operator.mul,
    "/": operator.truediv,
    "//": operator.floordiv,
    "%": operator.mod,
    "<<": operator.lshift,
    ">>": operator.rshift,
    "&": operator.and_,
    "^": operator.xor,
    "|": operator.or_,
    "==": operator.eq,
    "!=": operator.ne,
    "<": operator.lt,
    ">": operator.gt,
    "<=": operator.le,
    ">=": operator.ge,
    "and": lambda a, b: a and b,
    "or": lambda a, b: a or b,
}

# Safe built-in callables permitted in expressions
_SAFE_CALLABLES: dict[str, Callable[..., Any]] = {
    "len": len,
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
}


def evaluate(node: ASTNode, context: dict[str, Any]) -> Any:
    """Recursively evaluate *node* in the given *context*.

    Raises
    ------
    ExpressionEvalError
        On runtime errors such as division by zero, missing field, etc.
    """
    match node:
        case Literal(value=v):
            return v

        case Name(name=n):
            if n in _SAFE_CALLABLES:
                return _SAFE_CALLABLES[n]
            if n not in context:
                raise ExpressionEvalError(
                    f"Undefined field {n!r}. Available: {sorted(context)}"
                )
            return context[n]

        case Attribute(obj=obj_node, attr=attr):
            obj_val = evaluate(obj_node, context)
            if isinstance(obj_val, dict):
                if attr not in obj_val:
                    raise ExpressionEvalError(f"Attribute {attr!r} not found in {obj_val!r}")
                return obj_val[attr]
            try:
                return getattr(obj_val, attr)
            except AttributeError:
                raise ExpressionEvalError(f"Object {obj_val!r} has no attribute {attr!r}")

        case Subscript(obj=obj_node, index=idx_node):
            obj_val = evaluate(obj_node, context)
            idx_val = evaluate(idx_node, context)
            try:
                return obj_val[idx_val]
            except (IndexError, KeyError, TypeError) as exc:
                raise ExpressionEvalError(str(exc))

        case UnaryOp(op="-", operand=operand):
            val = evaluate(operand, context)
            try:
                return -val
            except TypeError:
                raise ExpressionEvalError(f"Cannot negate {val!r}")

        case UnaryOp(op="not", operand=operand):
            return not evaluate(operand, context)

        case UnaryOp(op="#", operand=operand):
            val = evaluate(operand, context)
            try:
                return len(val)
            except TypeError:
                raise ExpressionEvalError(f"Cannot get length of {val!r}")

        case BinOp(left=left, op=op, right=right):
            fn = _BINOP_TABLE.get(op)
            if fn is None:
                raise ExpressionEvalError(f"Unknown operator {op!r}")
            lval = evaluate(left, context)
            rval = evaluate(right, context)
            try:
                return fn(lval, rval)
            except ZeroDivisionError:
                raise ExpressionEvalError("Division by zero")
            except TypeError as exc:
                raise ExpressionEvalError(str(exc))

        case Ternary(condition=cond, value_if_true=vt, value_if_false=vf):
            if evaluate(cond, context):
                return evaluate(vt, context)
            return evaluate(vf, context)

        case Call(func=func_node, args=args):
            fn_val = evaluate(func_node, context)
            if not callable(fn_val):
                raise ExpressionEvalError(f"{fn_val!r} is not callable")
            arg_vals = [evaluate(a, context) for a in args]
            try:
                return fn_val(*arg_vals)
            except Exception as exc:
                raise ExpressionEvalError(f"Call failed: {exc}")

        case List(elements=elems):
            return [evaluate(e, context) for e in elems]

        case Dict(pairs=pairs):
            return {evaluate(k, context): evaluate(v, context) for k, v in pairs}

        case _:
            raise ExpressionEvalError(f"Unknown AST node type: {type(node)!r}")
