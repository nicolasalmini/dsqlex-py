"""Recursive-descent parser: token list → AST."""
from ._errors import DsqlexError
from ._tokens import Token
from ._ast import (
    Select, Number, String, Boolean, Null, Identifier,
    BinaryOp, CaseExpr, WhenClause, FunctionCall,
    InExpr, NotInExpr, LikeExpr, NotLikeExpr,
)

_ADDITIVE_OPS = frozenset(["plus", "minus"])
_MULTIPLICATIVE_OPS = frozenset(["multiply", "divide"])
_COMPARISON_OPS = frozenset(["eq", "neq", "lt", "gt", "lte", "gte"])


class _Parser:
    def __init__(self, tokens: list[Token]) -> None:
        self.tokens = tokens
        self.pos = 0

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _peek(self) -> Token | None:
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return None

    def _consume(self) -> Token:
        t = self.tokens[self.pos]
        self.pos += 1
        return t

    def _match(self, type_: str, value=None) -> bool:
        t = self._peek()
        if t is None:
            return False
        if t.type != type_:
            return False
        return value is None or t.value == value

    def _expect_keyword(self, kw: str) -> None:
        if self._match("keyword", kw):
            self._consume()
        else:
            got = repr(self._peek())
            raise DsqlexError(f"Expected {kw.upper()}, got: {got}")

    # ------------------------------------------------------------------
    # Top-level
    # ------------------------------------------------------------------

    def parse(self):
        ast = self._parse_select()
        if self.pos < len(self.tokens):
            remaining = self.tokens[self.pos :]
            raise DsqlexError(f"Unexpected tokens: {remaining}")
        return ast

    def _parse_select(self):
        if self._match("keyword", "select"):
            self._consume()
        return Select(self._parse_expression())

    # ------------------------------------------------------------------
    # Level 1: logical (lowest precedence)
    # ------------------------------------------------------------------

    def _parse_expression(self):
        return self._parse_logical()

    def _parse_logical(self):
        left = self._parse_comparison()
        if self._match("keyword", "and"):
            self._consume()
            right = self._parse_comparison()
            node = BinaryOp("and", left, right)
            return self._parse_and_chain(node)
        if self._match("keyword", "or"):
            self._consume()
            right = self._parse_comparison()
            node = BinaryOp("or", left, right)
            return self._parse_or_chain(node)
        return left

    def _parse_and_chain(self, left):
        if self._match("keyword", "and"):
            self._consume()
            right = self._parse_comparison()
            return self._parse_and_chain(BinaryOp("and", left, right))
        if self._match("keyword", "or"):
            raise DsqlexError("Ambiguous expression: mixing AND/OR requires parentheses")
        return left

    def _parse_or_chain(self, left):
        if self._match("keyword", "or"):
            self._consume()
            right = self._parse_comparison()
            return self._parse_or_chain(BinaryOp("or", left, right))
        if self._match("keyword", "and"):
            raise DsqlexError("Ambiguous expression: mixing AND/OR requires parentheses")
        return left

    # ------------------------------------------------------------------
    # Level 2: comparison
    # ------------------------------------------------------------------

    def _parse_comparison(self):
        left = self._parse_arithmetic()

        t = self._peek()
        if t is None:
            return left

        # Standard comparison operators
        if t.type == "operator" and t.value in _COMPARISON_OPS:
            self._consume()
            right = self._parse_arithmetic()
            # No chaining allowed
            t2 = self._peek()
            if t2 is not None and t2.type == "operator" and t2.value in _COMPARISON_OPS:
                raise DsqlexError("Cannot chain comparison operators. Use parentheses.")
            return BinaryOp(t.value, left, right)

        # expr IN (...)
        if t.type == "keyword" and t.value == "in":
            self._consume()
            items = self._parse_in_list()
            return InExpr(left, tuple(items))

        # expr NOT IN (...) or expr NOT LIKE pattern
        if t.type == "keyword" and t.value == "not":
            t2_pos = self.pos + 1
            if t2_pos < len(self.tokens):
                t2 = self.tokens[t2_pos]
                if t2.type == "keyword" and t2.value == "in":
                    self._consume()  # NOT
                    self._consume()  # IN
                    items = self._parse_in_list()
                    return NotInExpr(left, tuple(items))
                if t2.type == "keyword" and t2.value == "like":
                    self._consume()  # NOT
                    self._consume()  # LIKE
                    pattern = self._parse_primary()
                    return NotLikeExpr(left, pattern)

        # expr IS [NOT] NULL/TRUE/FALSE
        if t.type == "keyword" and t.value == "is":
            self._consume()  # IS
            negate = False
            if self._match("keyword", "not"):
                self._consume()
                negate = True
            kw = self._peek()
            if kw is None or kw.type != "keyword" or kw.value not in ("null", "true", "false"):
                raise DsqlexError(f"Expected NULL, TRUE, or FALSE after IS{'  NOT' if negate else ''}")
            self._consume()
            if kw.value == "null":
                literal = Null()
            elif kw.value == "true":
                literal = Boolean(True)
            else:
                literal = Boolean(False)
            op = "neq" if negate else "eq"
            return BinaryOp(op, left, literal)

        # expr LIKE pattern
        if t.type == "keyword" and t.value == "like":
            self._consume()
            pattern = self._parse_primary()
            return LikeExpr(left, pattern)

        return left

    def _parse_in_list(self) -> list:
        if not self._match("lparen"):
            raise DsqlexError("Expected '(' after IN")
        self._consume()
        items = []
        if self._match("rparen"):
            self._consume()
            return items
        items.append(self._parse_primary())
        while self._match("comma"):
            self._consume()
            items.append(self._parse_primary())
        if not self._match("rparen"):
            raise DsqlexError("Expected closing parenthesis ')' after IN list")
        self._consume()
        return items

    # ------------------------------------------------------------------
    # Level 3: arithmetic
    # ------------------------------------------------------------------

    def _parse_arithmetic(self):
        left = self._parse_primary()

        t = self._peek()
        if t is None or t.type != "operator":
            return left

        if t.value in _ADDITIVE_OPS:
            self._consume()
            right = self._parse_primary()
            return self._parse_additive_chain(BinaryOp(t.value, left, right))

        if t.value in _MULTIPLICATIVE_OPS:
            self._consume()
            right = self._parse_primary()
            return self._parse_multiplicative_chain(BinaryOp(t.value, left, right))

        return left

    def _parse_additive_chain(self, left):
        t = self._peek()
        if t is None or t.type != "operator":
            return left
        if t.value in _ADDITIVE_OPS:
            self._consume()
            right = self._parse_primary()
            return self._parse_additive_chain(BinaryOp(t.value, left, right))
        if t.value in _MULTIPLICATIVE_OPS:
            raise DsqlexError("Ambiguous expression: mixing +/- and */÷ requires parentheses")
        return left

    def _parse_multiplicative_chain(self, left):
        t = self._peek()
        if t is None or t.type != "operator":
            return left
        if t.value in _MULTIPLICATIVE_OPS:
            self._consume()
            right = self._parse_primary()
            return self._parse_multiplicative_chain(BinaryOp(t.value, left, right))
        if t.value in _ADDITIVE_OPS:
            raise DsqlexError("Ambiguous expression: mixing +/- and */÷ requires parentheses")
        return left

    # ------------------------------------------------------------------
    # Level 4: primary (highest precedence)
    # ------------------------------------------------------------------

    def _parse_primary(self):
        t = self._peek()
        if t is None:
            raise DsqlexError(f"Unexpected end of input")

        # Number literal
        if t.type == "number":
            self._consume()
            return Number(t.value)

        # String literal
        if t.type == "string":
            self._consume()
            return String(t.value)

        # Identifier
        if t.type == "identifier":
            self._consume()
            return Identifier(t.value)

        # Boolean / NULL keywords
        if t.type == "keyword" and t.value == "null":
            self._consume()
            return Null()
        if t.type == "keyword" and t.value == "true":
            self._consume()
            return Boolean(True)
        if t.type == "keyword" and t.value == "false":
            self._consume()
            return Boolean(False)

        # Parenthesized expression — resets to lowest precedence
        if t.type == "lparen":
            self._consume()
            expr = self._parse_expression()
            if not self._match("rparen"):
                raise DsqlexError("Expected closing parenthesis ')'")
            self._consume()
            return expr

        # CASE WHEN … THEN … [WHEN …] [ELSE …] END
        if t.type == "keyword" and t.value == "case":
            self._consume()
            when_clauses = self._parse_when_clauses()
            else_clause = self._parse_else_clause()
            self._expect_keyword("end")
            return CaseExpr(tuple(when_clauses), else_clause)

        # Function call: FUNC(arg1, arg2, …)
        if t.type == "function":
            fname = t.value
            self._consume()
            if not self._match("lparen"):
                raise DsqlexError(f"Expected '(' after function {fname.upper()}")
            self._consume()
            args = self._parse_function_args()
            if not self._match("rparen"):
                raise DsqlexError("Expected closing parenthesis ')' after function arguments")
            self._consume()
            return FunctionCall(fname, tuple(args))

        raise DsqlexError(f"Unexpected token: {[t]}")

    # ------------------------------------------------------------------
    # CASE/WHEN helpers
    # ------------------------------------------------------------------

    def _parse_when_clauses(self) -> list[WhenClause]:
        clauses = [self._parse_when_clause()]
        while self._match("keyword", "when"):
            clauses.append(self._parse_when_clause())
        return clauses

    def _parse_when_clause(self) -> WhenClause:
        if not self._match("keyword", "when"):
            raise DsqlexError("Expected WHEN clause")
        self._consume()
        condition = self._parse_expression()
        self._expect_keyword("then")
        result = self._parse_expression()
        return WhenClause(condition, result)

    def _parse_else_clause(self):
        if self._match("keyword", "else"):
            self._consume()
            return self._parse_expression()
        return None

    # ------------------------------------------------------------------
    # Function argument list
    # ------------------------------------------------------------------

    def _parse_function_args(self) -> list:
        if self._match("rparen"):
            return []
        args = [self._parse_expression()]
        while self._match("comma"):
            self._consume()
            args.append(self._parse_expression())
        return args


def parse(tokens: list[Token]):
    """Parse a token list into an AST. Raises DsqlexError on failure."""
    return _Parser(tokens).parse()
