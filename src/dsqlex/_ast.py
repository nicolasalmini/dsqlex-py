from __future__ import annotations
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Select:
    expr: Any


@dataclass(frozen=True)
class Number:
    value: str  # raw string; converted to Decimal at eval time


@dataclass(frozen=True)
class String:
    value: str


@dataclass(frozen=True)
class Boolean:
    value: bool


@dataclass(frozen=True)
class Null:
    pass


@dataclass(frozen=True)
class Identifier:
    name: str


@dataclass(frozen=True)
class BinaryOp:
    op: str   # 'plus', 'minus', 'multiply', 'divide', 'eq', 'neq', 'lt', 'gt', 'lte', 'gte', 'and', 'or'
    left: Any
    right: Any


@dataclass(frozen=True)
class UnaryOp:
    op: str
    operand: Any


@dataclass(frozen=True)
class CaseExpr:
    when_clauses: tuple  # tuple of WhenClause
    else_clause: Any     # None or AST node


@dataclass(frozen=True)
class WhenClause:
    condition: Any
    result: Any


@dataclass(frozen=True)
class FunctionCall:
    name: str   # 'round', 'coalesce', 'upper', 'lower', 'abs', 'concat', 'event'
    args: tuple  # tuple of AST nodes


@dataclass(frozen=True)
class InExpr:
    expr: Any
    items: tuple  # tuple of AST nodes


@dataclass(frozen=True)
class NotInExpr:
    expr: Any
    items: tuple


@dataclass(frozen=True)
class LikeExpr:
    expr: Any
    pattern: Any


@dataclass(frozen=True)
class NotLikeExpr:
    expr: Any
    pattern: Any
