"""AST evaluator: walks the AST against a context dict and returns a value."""
from __future__ import annotations

import re
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from ._errors import DsqlexError
from ._ast import (
    Select, Number, String, Boolean, Null, Identifier,
    BinaryOp, CaseExpr, WhenClause, FunctionCall,
    InExpr, NotInExpr, LikeExpr, NotLikeExpr,
)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def evaluate(ast, context: dict, opts: dict | None = None) -> Any:
    """Evaluate *ast* against *context*. Raises DsqlexError on any error."""
    if not isinstance(context, dict):
        raise DsqlexError("context must be a dict")
    if opts is None:
        opts = {}
    return _eval(ast, context, opts)


# ---------------------------------------------------------------------------
# Core recursive evaluator
# ---------------------------------------------------------------------------

def _eval(node, context: dict, opts: dict) -> Any:
    if isinstance(node, Select):
        return _eval(node.expr, context, opts)

    if isinstance(node, Number):
        return Decimal(node.value)

    if isinstance(node, String):
        return node.value

    if isinstance(node, Boolean):
        return node.value

    if isinstance(node, Null):
        return None

    if isinstance(node, Identifier):
        return _eval_identifier(node.name, context, opts)

    if isinstance(node, BinaryOp):
        return _eval_binary_op(node, context, opts)

    if isinstance(node, CaseExpr):
        return _eval_case_expr(node, context, opts)

    if isinstance(node, FunctionCall):
        return _eval_function(node, context, opts)

    if isinstance(node, InExpr):
        value = _eval(node.expr, context, opts)
        return any(_compare(value, _eval(item, context, opts)) == "eq" for item in node.items)

    if isinstance(node, NotInExpr):
        value = _eval(node.expr, context, opts)
        return not any(_compare(value, _eval(item, context, opts)) == "eq" for item in node.items)

    if isinstance(node, LikeExpr):
        value = str(_eval(node.expr, context, opts))
        pattern = str(_eval(node.pattern, context, opts))
        return _like_match(value, pattern)

    if isinstance(node, NotLikeExpr):
        value = str(_eval(node.expr, context, opts))
        pattern = str(_eval(node.pattern, context, opts))
        return not _like_match(value, pattern)

    raise DsqlexError(f"Unknown AST node: {type(node).__name__}")


# ---------------------------------------------------------------------------
# Identifier resolution
# ---------------------------------------------------------------------------

def _eval_identifier(name: str, context: dict, opts: dict) -> Any:
    # Direct context lookup takes precedence
    if name in context:
        return context[name]

    # Dot-path access into nested dicts/lists
    if "." in name:
        return _resolve_dot_path(name, context)

    # Optional resolver for unknown identifiers
    resolver = opts.get("resolver")
    if resolver is not None:
        visited: frozenset = opts.get("visited", frozenset())
        if name in visited:
            raise DsqlexError(f"Circular reference detected: {name}")
        return resolver(name, visited)

    raise DsqlexError(f"Unknown field: {name}")


def _resolve_dot_path(path: str, context: dict) -> Any:
    parts = path.split(".")
    return _resolve_parts(parts, context, path)


def _resolve_parts(parts: list[str], current: Any, full_path: str) -> Any:
    if not parts:
        return current

    if isinstance(current, dict):
        key = parts[0]
        if key not in current:
            raise DsqlexError(f"Unknown field: {full_path} (failed at '{key}')")
        return _resolve_parts(parts[1:], current[key], full_path)

    if isinstance(current, list):
        results = [_resolve_parts(parts, item, full_path) for item in current]
        if all(_decimal_like(r) for r in results):
            return sum((_to_decimal(r) for r in results), Decimal("0"))
        return results

    raise DsqlexError(f"Cannot access '{parts[0]}' on non-map value in path '{full_path}'")


# ---------------------------------------------------------------------------
# Binary operations
# ---------------------------------------------------------------------------

def _eval_binary_op(node: BinaryOp, context: dict, opts: dict) -> Any:
    op = node.op

    # Logical operators (short-circuit)
    if op == "and":
        left_val = _eval(node.left, context, opts)
        if not _is_truthy(left_val):
            return left_val
        return _eval(node.right, context, opts)

    if op == "or":
        left_val = _eval(node.left, context, opts)
        if _is_truthy(left_val):
            return left_val
        return _eval(node.right, context, opts)

    left_val = _eval(node.left, context, opts)
    right_val = _eval(node.right, context, opts)

    # Arithmetic
    if op == "plus":
        return Decimal.__add__(_to_decimal(left_val), _to_decimal(right_val))
    if op == "minus":
        return Decimal.__sub__(_to_decimal(left_val), _to_decimal(right_val))
    if op == "multiply":
        return Decimal.__mul__(_to_decimal(left_val), _to_decimal(right_val))
    if op == "divide":
        return Decimal.__truediv__(_to_decimal(left_val), _to_decimal(right_val))

    # Comparison
    cmp = _compare(left_val, right_val)
    if op == "eq":
        return cmp == "eq"
    if op == "neq":
        return cmp != "eq"
    if op == "lt":
        return cmp == "lt"
    if op == "gt":
        return cmp == "gt"
    if op == "lte":
        return cmp in ("lt", "eq")
    if op == "gte":
        return cmp in ("gt", "eq")

    raise DsqlexError(f"Unknown operator: {op}")


# ---------------------------------------------------------------------------
# CASE expression
# ---------------------------------------------------------------------------

def _eval_case_expr(node: CaseExpr, context: dict, opts: dict) -> Any:
    for when in node.when_clauses:
        if _is_truthy(_eval(when.condition, context, opts)):
            return _eval(when.result, context, opts)
    if node.else_clause is not None:
        return _eval(node.else_clause, context, opts)
    return None


# ---------------------------------------------------------------------------
# Function calls
# ---------------------------------------------------------------------------

def _eval_function(node: FunctionCall, context: dict, opts: dict) -> Any:
    name = node.name
    args = node.args

    if name == "round":
        if len(args) != 2:
            raise DsqlexError("ROUND requires exactly 2 arguments")
        value = _to_decimal(_eval(args[0], context, opts))
        precision = int(_to_decimal(_eval(args[1], context, opts)))
        return _round(value, precision)

    if name == "coalesce":
        for arg in args:
            result = _eval(arg, context, opts)
            if result is not None:
                return result
        return None

    if name == "upper":
        if len(args) != 1:
            raise DsqlexError("UPPER requires exactly 1 argument")
        return str(_eval(args[0], context, opts)).upper()

    if name == "lower":
        if len(args) != 1:
            raise DsqlexError("LOWER requires exactly 1 argument")
        return str(_eval(args[0], context, opts)).lower()

    if name == "abs":
        if len(args) != 1:
            raise DsqlexError("ABS requires exactly 1 argument")
        return abs(_to_decimal(_eval(args[0], context, opts)))

    if name == "concat":
        return "".join(str(_eval(arg, context, opts)) for arg in args)

    if name == "event":
        return _eval_event(args, context, opts)

    raise DsqlexError(f"Unknown function: {name}")


# ---------------------------------------------------------------------------
# EVENT() function
# ---------------------------------------------------------------------------

def _eval_event(args, context: dict, opts: dict) -> Any:
    if len(args) == 2:
        type_node, subtype_node = args
        if not (isinstance(type_node, Identifier) and isinstance(subtype_node, Identifier)):
            raise DsqlexError("EVENT arguments must be identifiers")
        return _resolve_event(type_node.name, subtype_node.name, context, opts)

    if len(args) == 3:
        type_node, subtype_node, source_node = args
        if not all(isinstance(n, Identifier) for n in (type_node, subtype_node, source_node)):
            raise DsqlexError("EVENT arguments must be identifiers")
        source_name = source_node.name
        if source_name not in context:
            raise DsqlexError(f"EVENT context source '{source_name}' not found in context")
        sub_context = context[source_name]
        if isinstance(sub_context, list):
            results = [
                _resolve_event(type_node.name, subtype_node.name, item, opts)
                for item in sub_context
            ]
            return sum((_to_decimal(r) for r in results), Decimal("0"))
        if isinstance(sub_context, dict):
            return _resolve_event(type_node.name, subtype_node.name, sub_context, opts)
        raise DsqlexError(
            f"EVENT context source '{source_name}' must be a map or list of maps"
        )

    raise DsqlexError(
        "EVENT requires 2 or 3 arguments: EVENT(type, subtype) or EVENT(type, subtype, context_source)"
    )


def _resolve_event(type_: str, subtype: str, eval_context: dict, opts: dict) -> Any:
    event_resolver = opts.get("event_resolver")
    if event_resolver is None:
        raise DsqlexError("EVENT() calls require an :event_resolver option")

    event_key = f"{type_}.{subtype}"
    visited: frozenset = opts.get("visited", frozenset())

    if event_key in visited:
        raise DsqlexError(f"Circular reference detected: {event_key}")

    new_visited = visited | {event_key}
    new_opts = {**opts, "visited": new_visited}

    return event_resolver(type_, subtype, eval_context, new_opts)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_truthy(value: Any) -> bool:
    """Elixir semantics: everything except None and False is truthy."""
    return value is not None and value is not False


def _to_decimal(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        raise DsqlexError(f"Cannot convert boolean to Decimal")
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, str):
        return Decimal(value)
    raise DsqlexError(f"Cannot convert {type(value).__name__} to Decimal")


def _round(value: Decimal, precision: int) -> Decimal:
    quantizer = Decimal(10) ** -precision
    return value.quantize(quantizer, rounding=ROUND_HALF_UP)


def _compare(a: Any, b: Any) -> str:
    """Return 'eq', 'lt', 'gt', or 'neq' (for nil vs non-nil)."""
    if a is None and b is None:
        return "eq"
    if a is None or b is None:
        return "neq"

    # Decimal comparisons (at least one side is Decimal)
    if isinstance(a, Decimal) or isinstance(b, Decimal):
        try:
            da = _to_decimal(a)
            db = _to_decimal(b)
            if da == db:
                return "eq"
            return "lt" if da < db else "gt"
        except Exception:
            pass

    # Generic comparison
    if a == b:
        return "eq"
    try:
        return "lt" if a < b else "gt"
    except TypeError:
        return "neq"


def _like_match(value: str, pattern: str) -> bool:
    """Case-insensitive SQL LIKE matching: % = any sequence, _ = any one char."""
    # Protect wildcards with NUL-delimited placeholders before regex-escaping.
    # NUL bytes are safe: they can't appear in user strings and re.escape passes
    # them through unchanged (they have no special meaning in Python regex).
    _PERCENT_PH = "\x00PCT\x00"
    _UNDER_PH = "\x00UND\x00"
    tmp = pattern.replace("%", _PERCENT_PH).replace("_", _UNDER_PH)
    escaped = re.escape(tmp)
    # Replace the (still-intact) placeholders with regex equivalents.
    # Important: use regular strings here, not raw strings.
    regex_str = escaped.replace(_PERCENT_PH, ".*").replace(_UNDER_PH, ".")
    return bool(re.fullmatch(regex_str, value, re.IGNORECASE))


def _decimal_like(value: Any) -> bool:
    if isinstance(value, Decimal):
        return True
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return True
    if isinstance(value, str):
        try:
            Decimal(value)
            return True
        except Exception:
            return False
    return False
