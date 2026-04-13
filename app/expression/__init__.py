"""app.expression — local copy of protocollab.expression, extended for OctAPI.

Provides a safe expression engine used to transpile array_filter conditions to Lua.
"""

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
from app.expression.evaluator import ExpressionEvalError, evaluate
from app.expression.lexer import ExpressionSyntaxError, Token, TokenKind, tokenize
from app.expression.parser import Parser, parse_expr
from app.expression.validator import ExprError, validate_expr

__all__ = [
    # AST nodes
    "ASTNode",
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
    # Lexer
    "Token",
    "TokenKind",
    "tokenize",
    # Parser
    "Parser",
    "parse_expr",
    # Evaluator
    "evaluate",
    # Errors
    "ExpressionSyntaxError",
    "ExpressionEvalError",
    # Static validator
    "ExprError",
    "validate_expr",
]
