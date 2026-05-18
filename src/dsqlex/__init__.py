"""
DSQLEX — SQL-like DSL for evaluating dynamic financial calculations.

Public API
----------
eval(expression, context, **opts)   → value  (raises DsqlexError on failure)
parse(expression)                   → AST    (raises DsqlexError on failure)
tokenize(expression)                → tokens (raises DsqlexError on failure)
evaluate_ast(ast, context, **opts)  → value  (raises DsqlexError on failure)

Options (keyword args)
----------------------
resolver        callable(name, visited) → value
                Called for identifiers not found in context.
event_resolver  callable(type, subtype, context, opts_dict) → value
                Called for EVENT() function invocations.
visited         frozenset[str] — already-visited names (circular-ref detection).
"""

from ._errors import DsqlexError
from ._tokens import Token
from ._ast import (
    Select, Number, String, Boolean, Null, Identifier,
    BinaryOp, CaseExpr, WhenClause, FunctionCall,
    InExpr, NotInExpr, LikeExpr, NotLikeExpr,
)
from ._lexer import tokenize as _tokenize
from ._parser import parse as _parse
from ._evaluator import evaluate as _evaluate


__all__ = [
    "DsqlexError",
    "Token",
    # AST node types (useful for type-checking / pattern matching on parse output)
    "Select", "Number", "String", "Boolean", "Null", "Identifier",
    "BinaryOp", "CaseExpr", "WhenClause", "FunctionCall",
    "InExpr", "NotInExpr", "LikeExpr", "NotLikeExpr",
    # Public functions
    "eval", "parse", "tokenize", "evaluate_ast",
]


def tokenize(expression: str) -> list[Token]:
    """Tokenize *expression* and return a list of Token objects.

    Raises DsqlexError on any lexical error.
    """
    if not isinstance(expression, str):
        raise DsqlexError("expression must be a str")
    return _tokenize(expression)


def parse(expression: str):
    """Parse *expression* and return the AST root (a Select node).

    Raises DsqlexError on any lexical or parse error.
    """
    if not isinstance(expression, str):
        raise DsqlexError("expression must be a str")
    tokens = _tokenize(expression)
    return _parse(tokens)


def evaluate_ast(ast, context: dict, **opts):
    """Evaluate a pre-parsed *ast* against *context*.

    Raises DsqlexError on any evaluation error.
    This function is exposed separately to support AST-caching strategies.
    """
    return _evaluate(ast, context, opts or {})


def eval(expression: str, context: dict, **opts):  # noqa: A001
    """Evaluate *expression* against *context* and return the result.

    Raises DsqlexError on any lexical, parse, or evaluation error.

    Parameters
    ----------
    expression : str
    context : dict[str, Any]
    resolver : callable(name, visited) → value, optional
    event_resolver : callable(type, subtype, context, opts_dict) → value, optional
    visited : frozenset[str], optional
    """
    if not isinstance(expression, str):
        raise DsqlexError("expression must be a str")
    if not isinstance(context, dict):
        raise DsqlexError("context must be a dict")
    tokens = _tokenize(expression)
    ast = _parse(tokens)
    return _evaluate(ast, context, opts or {})
