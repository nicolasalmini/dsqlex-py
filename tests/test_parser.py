"""Parser tests — ports Dsqlex.ParserTest from the Elixir reference."""
import pytest
from dsqlex import parse, DsqlexError
from dsqlex import (
    Select, Number, String, Boolean, Null, Identifier,
    BinaryOp, UnaryOp, CaseExpr, WhenClause, FunctionCall,
    InExpr, NotInExpr, LikeExpr, NotLikeExpr,
)


# ---------------------------------------------------------------------------
# Literals
# ---------------------------------------------------------------------------

class TestLiterals:
    def test_parses_number(self):
        assert parse("SELECT 42") == Select(Number("42"))
        assert parse("SELECT 3.14") == Select(Number("3.14"))

    def test_parses_string(self):
        assert parse("SELECT 'hello'") == Select(String("hello"))
        assert parse("SELECT ''") == Select(String(""))

    def test_parses_identifier(self):
        assert parse("SELECT my_var") == Select(Identifier("my_var"))
        assert parse("SELECT x") == Select(Identifier("x"))

    def test_parses_boolean(self):
        assert parse("SELECT TRUE") == Select(Boolean(True))
        assert parse("SELECT FALSE") == Select(Boolean(False))

    def test_parses_null(self):
        assert parse("SELECT NULL") == Select(Null())


# ---------------------------------------------------------------------------
# Arithmetic operators
# ---------------------------------------------------------------------------

class TestArithmeticOperators:
    def test_parses_single_addition(self):
        assert parse("SELECT 1 + 2") == Select(BinaryOp("plus", Number("1"), Number("2")))

    def test_parses_single_subtraction(self):
        assert parse("SELECT 5 - 3") == Select(BinaryOp("minus", Number("5"), Number("3")))

    def test_parses_single_multiplication(self):
        assert parse("SELECT 2 * 3") == Select(BinaryOp("multiply", Number("2"), Number("3")))

    def test_parses_single_division(self):
        assert parse("SELECT a / b") == Select(BinaryOp("divide", Identifier("a"), Identifier("b")))

    def test_allows_same_group_additive_chains(self):
        # left-associative: ((a - b) - c) - d
        ast = parse("SELECT a - b - c - d")
        assert ast == Select(
            BinaryOp("minus",
                BinaryOp("minus",
                    BinaryOp("minus", Identifier("a"), Identifier("b")),
                    Identifier("c")),
                Identifier("d"))
        )
        # left-associative: (1 + 2) + 3
        ast = parse("SELECT 1 + 2 + 3")
        assert ast == Select(
            BinaryOp("plus",
                BinaryOp("plus", Number("1"), Number("2")),
                Number("3"))
        )
        # mixed +/- in the same chain is allowed
        ast = parse("SELECT a + b - c + d")
        assert ast == Select(
            BinaryOp("plus",
                BinaryOp("minus",
                    BinaryOp("plus", Identifier("a"), Identifier("b")),
                    Identifier("c")),
                Identifier("d"))
        )

    def test_allows_same_group_multiplicative_chains(self):
        ast = parse("SELECT a * b * c")
        assert ast == Select(
            BinaryOp("multiply",
                BinaryOp("multiply", Identifier("a"), Identifier("b")),
                Identifier("c"))
        )
        ast = parse("SELECT a * b / c")
        assert ast == Select(
            BinaryOp("divide",
                BinaryOp("multiply", Identifier("a"), Identifier("b")),
                Identifier("c"))
        )

    def test_rejects_mixing_additive_and_multiplicative(self):
        with pytest.raises(DsqlexError, match="Ambiguous expression: mixing"):
            parse("SELECT 1 + 2 * 3")
        with pytest.raises(DsqlexError, match="Ambiguous expression: mixing"):
            parse("SELECT a / b + c")
        with pytest.raises(DsqlexError, match="Ambiguous expression: mixing"):
            parse("SELECT a - b - c - d / e")
        # Inner parens don't cure the outer mix
        with pytest.raises(DsqlexError, match="Ambiguous expression: mixing"):
            parse("SELECT a - b - (c - d) / e")

    def test_allows_chained_arithmetic_with_parentheses(self):
        ast = parse("SELECT (1 + 2) + 3")
        assert isinstance(ast.expr, BinaryOp) and ast.expr.op == "plus"
        assert isinstance(ast.expr.left, BinaryOp) and ast.expr.left.op == "plus"

        ast = parse("SELECT (1 + 2) * 3")
        assert isinstance(ast.expr, BinaryOp) and ast.expr.op == "multiply"
        assert isinstance(ast.expr.left, BinaryOp) and ast.expr.left.op == "plus"

    def test_allows_cross_group_with_parentheses(self):
        # (a - b - c - d) / e
        ast = parse("SELECT (a - b - c - d) / e")
        assert ast == Select(
            BinaryOp("divide",
                BinaryOp("minus",
                    BinaryOp("minus",
                        BinaryOp("minus", Identifier("a"), Identifier("b")),
                        Identifier("c")),
                    Identifier("d")),
                Identifier("e"))
        )
        # (a / e) - b - c - d
        ast = parse("SELECT (a / e) - b - c - d")
        assert ast == Select(
            BinaryOp("minus",
                BinaryOp("minus",
                    BinaryOp("minus",
                        BinaryOp("divide", Identifier("a"), Identifier("e")),
                        Identifier("b")),
                    Identifier("c")),
                Identifier("d"))
        )
        # a - b - ((c - d) / e)
        ast = parse("SELECT a - b - ((c - d) / e)")
        assert ast == Select(
            BinaryOp("minus",
                BinaryOp("minus", Identifier("a"), Identifier("b")),
                BinaryOp("divide",
                    BinaryOp("minus", Identifier("c"), Identifier("d")),
                    Identifier("e")))
        )


# ---------------------------------------------------------------------------
# Comparison operators
# ---------------------------------------------------------------------------

class TestComparisonOperators:
    def test_parses_equality(self):
        assert parse("SELECT x = 1") == Select(BinaryOp("eq", Identifier("x"), Number("1")))

    def test_parses_inequality(self):
        assert parse("SELECT x != 'test'") == Select(BinaryOp("neq", Identifier("x"), String("test")))

    def test_parses_less_than(self):
        assert parse("SELECT x < 10") == Select(BinaryOp("lt", Identifier("x"), Number("10")))

    def test_parses_greater_than(self):
        assert parse("SELECT x > 0") == Select(BinaryOp("gt", Identifier("x"), Number("0")))

    def test_parses_less_than_or_equal(self):
        assert parse("SELECT x <= 100") == Select(BinaryOp("lte", Identifier("x"), Number("100")))

    def test_parses_greater_than_or_equal(self):
        assert parse("SELECT x >= 0") == Select(BinaryOp("gte", Identifier("x"), Number("0")))

    def test_rejects_chained_comparisons(self):
        with pytest.raises(DsqlexError, match="Cannot chain comparison"):
            parse("SELECT 1 < 2 < 3")


# ---------------------------------------------------------------------------
# Logical operators
# ---------------------------------------------------------------------------

class TestLogicalOperators:
    def test_parses_single_and(self):
        ast = parse("SELECT a = 1 AND b = 2")
        assert isinstance(ast.expr, BinaryOp) and ast.expr.op == "and"

    def test_parses_single_or(self):
        ast = parse("SELECT a = 1 OR b = 2")
        assert isinstance(ast.expr, BinaryOp) and ast.expr.op == "or"

    def test_allows_chaining_same_logical_operator(self):
        ast = parse("SELECT a = 1 AND b = 2 AND c = 3")
        # left-associative: (a=1 AND b=2) AND c=3
        assert isinstance(ast.expr, BinaryOp) and ast.expr.op == "and"
        assert isinstance(ast.expr.left, BinaryOp) and ast.expr.left.op == "and"

        ast = parse("SELECT a = 1 OR b = 2 OR c = 3")
        assert isinstance(ast.expr, BinaryOp) and ast.expr.op == "or"
        assert isinstance(ast.expr.left, BinaryOp) and ast.expr.left.op == "or"

    def test_rejects_mixing_and_or_without_parentheses(self):
        with pytest.raises(DsqlexError, match="Ambiguous expression: mixing AND/OR"):
            parse("SELECT a = 1 AND b = 2 OR c = 3")
        with pytest.raises(DsqlexError, match="Ambiguous expression: mixing AND/OR"):
            parse("SELECT a = 1 OR b = 2 AND c = 3")

    def test_allows_mixing_and_or_with_parentheses(self):
        ast = parse("SELECT (a = 1 AND b = 2) OR c = 3")
        assert isinstance(ast.expr, BinaryOp) and ast.expr.op == "or"
        assert isinstance(ast.expr.left, BinaryOp) and ast.expr.left.op == "and"

        ast = parse("SELECT a = 1 AND (b = 2 OR c = 3)")
        assert isinstance(ast.expr, BinaryOp) and ast.expr.op == "and"
        assert isinstance(ast.expr.right, BinaryOp) and ast.expr.right.op == "or"


# ---------------------------------------------------------------------------
# Parentheses
# ---------------------------------------------------------------------------

class TestParentheses:
    def test_parses_parenthesized_expression(self):
        assert parse("SELECT (42)") == Select(Number("42"))

    def test_parses_nested_parentheses(self):
        ast = parse("SELECT ((1 + 2))")
        assert isinstance(ast.expr, BinaryOp) and ast.expr.op == "plus"

    def test_rejects_unclosed_parenthesis(self):
        with pytest.raises(DsqlexError, match="Expected closing parenthesis"):
            parse("SELECT (1 + 2")


# ---------------------------------------------------------------------------
# CASE/WHEN
# ---------------------------------------------------------------------------

class TestCaseWhen:
    def test_parses_simple_case_when(self):
        ast = parse("SELECT CASE WHEN x = 1 THEN 'one' END")
        assert isinstance(ast.expr, CaseExpr)
        assert len(ast.expr.when_clauses) == 1
        assert ast.expr.else_clause is None
        wc = ast.expr.when_clauses[0]
        assert isinstance(wc, WhenClause)
        assert isinstance(wc.condition, BinaryOp) and wc.condition.op == "eq"
        assert wc.result == String("one")

    def test_parses_case_when_with_else(self):
        ast = parse("SELECT CASE WHEN x = 1 THEN 'one' ELSE 'other' END")
        assert isinstance(ast.expr, CaseExpr)
        assert len(ast.expr.when_clauses) == 1
        assert ast.expr.else_clause == String("other")

    def test_parses_multiple_when_clauses(self):
        ast = parse("""
            SELECT CASE
              WHEN x = 1 THEN 'one'
              WHEN x = 2 THEN 'two'
              WHEN x = 3 THEN 'three'
            END
        """)
        assert isinstance(ast.expr, CaseExpr)
        assert len(ast.expr.when_clauses) == 3

    def test_parses_nested_case(self):
        ast = parse("""
            SELECT CASE
              WHEN x = 1 THEN CASE WHEN y = 2 THEN 'nested' ELSE 'inner' END
              ELSE 'outer'
            END
        """)
        assert isinstance(ast.expr, CaseExpr)
        wc = ast.expr.when_clauses[0]
        assert isinstance(wc.result, CaseExpr)
        assert ast.expr.else_clause == String("outer")

    def test_rejects_case_without_when(self):
        with pytest.raises(DsqlexError):
            parse("SELECT CASE END")

    def test_rejects_case_without_end(self):
        with pytest.raises(DsqlexError, match="Expected END"):
            parse("SELECT CASE WHEN x = 1 THEN 'one'")


# ---------------------------------------------------------------------------
# Function calls
# ---------------------------------------------------------------------------

class TestFunctionCalls:
    def test_parses_function_with_single_argument(self):
        assert parse("SELECT UPPER(x)") == Select(FunctionCall("upper", (Identifier("x"),)))

    def test_parses_function_with_multiple_arguments(self):
        assert parse("SELECT ROUND(x, 2)") == Select(
            FunctionCall("round", (Identifier("x"), Number("2")))
        )

    def test_parses_nested_function_calls(self):
        ast = parse("SELECT ROUND(COALESCE(x, 0), 2)")
        assert isinstance(ast.expr, FunctionCall) and ast.expr.name == "round"
        assert len(ast.expr.args) == 2
        inner = ast.expr.args[0]
        assert isinstance(inner, FunctionCall) and inner.name == "coalesce"

    def test_parses_function_with_expression_argument(self):
        ast = parse("SELECT ROUND(a / b, 2)")
        assert isinstance(ast.expr, FunctionCall) and ast.expr.name == "round"
        first_arg = ast.expr.args[0]
        assert isinstance(first_arg, BinaryOp) and first_arg.op == "divide"

    def test_rejects_function_without_closing_paren(self):
        with pytest.raises(DsqlexError, match="Expected closing parenthesis"):
            parse("SELECT ROUND(x, 2")


# ---------------------------------------------------------------------------
# SELECT is optional
# ---------------------------------------------------------------------------

class TestSelectOptional:
    def test_parses_without_select(self):
        assert parse("42") == Select(Number("42"))

    def test_parses_complex_without_select(self):
        ast = parse("x / y")
        assert isinstance(ast.expr, BinaryOp) and ast.expr.op == "divide"

    def test_parses_case_without_select(self):
        ast = parse("CASE WHEN x = 1 THEN 'yes' ELSE 'no' END")
        assert isinstance(ast.expr, CaseExpr)


# ---------------------------------------------------------------------------
# IN and NOT IN
# ---------------------------------------------------------------------------

class TestInNotIn:
    def test_parses_simple_in(self):
        ast = parse("x IN ('a', 'b')")
        assert ast == Select(InExpr(Identifier("x"), (String("a"), String("b"))))

    def test_parses_in_with_numbers(self):
        ast = parse("x IN (1, 2, 3)")
        assert ast == Select(InExpr(Identifier("x"), (Number("1"), Number("2"), Number("3"))))

    def test_parses_not_in(self):
        ast = parse("x NOT IN ('a', 'b')")
        assert ast == Select(NotInExpr(Identifier("x"), (String("a"), String("b"))))

    def test_parses_in_with_single_item(self):
        ast = parse("x IN ('a')")
        assert ast == Select(InExpr(Identifier("x"), (String("a"),)))

    def test_parses_in_combined_with_and(self):
        ast = parse("x IN ('a', 'b') AND y > 10")
        assert isinstance(ast.expr, BinaryOp) and ast.expr.op == "and"
        assert isinstance(ast.expr.left, InExpr)
        assert isinstance(ast.expr.right, BinaryOp) and ast.expr.right.op == "gt"

    def test_rejects_in_without_closing_paren(self):
        with pytest.raises(DsqlexError):
            parse("x IN ('a', 'b'")


# ---------------------------------------------------------------------------
# IS and IS NOT
# ---------------------------------------------------------------------------

class TestIsIsNot:
    def test_parses_is_null(self):
        assert parse("x IS NULL") == Select(BinaryOp("eq", Identifier("x"), Null()))

    def test_parses_is_not_null(self):
        assert parse("x IS NOT NULL") == Select(BinaryOp("neq", Identifier("x"), Null()))

    def test_parses_is_true(self):
        assert parse("flag IS TRUE") == Select(BinaryOp("eq", Identifier("flag"), Boolean(True)))

    def test_parses_is_not_true(self):
        assert parse("flag IS NOT TRUE") == Select(BinaryOp("neq", Identifier("flag"), Boolean(True)))

    def test_parses_is_false(self):
        assert parse("flag IS FALSE") == Select(BinaryOp("eq", Identifier("flag"), Boolean(False)))

    def test_parses_is_not_false(self):
        assert parse("flag IS NOT FALSE") == Select(BinaryOp("neq", Identifier("flag"), Boolean(False)))

    def test_is_null_combined_with_and(self):
        ast = parse("x IS NULL AND y = 1")
        assert isinstance(ast.expr, BinaryOp) and ast.expr.op == "and"
        left = ast.expr.left
        assert isinstance(left, BinaryOp) and left.op == "eq"
        assert left.left == Identifier("x")
        assert isinstance(left.right, Null)


# ---------------------------------------------------------------------------
# LIKE and NOT LIKE
# ---------------------------------------------------------------------------

class TestLikeNotLike:
    def test_parses_simple_like(self):
        assert parse("name LIKE '%test%'") == Select(
            LikeExpr(Identifier("name"), String("%test%"))
        )

    def test_parses_not_like(self):
        assert parse("name NOT LIKE '%test%'") == Select(
            NotLikeExpr(Identifier("name"), String("%test%"))
        )

    def test_parses_like_combined_with_and(self):
        ast = parse("name LIKE '%test%' AND status = 'active'")
        assert isinstance(ast.expr, BinaryOp) and ast.expr.op == "and"
        assert isinstance(ast.expr.left, LikeExpr)
        assert isinstance(ast.expr.right, BinaryOp) and ast.expr.right.op == "eq"


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

class TestErrorHandling:
    def test_rejects_unexpected_tokens_after_expression(self):
        with pytest.raises(DsqlexError, match="Unexpected tokens"):
            parse("SELECT 1 2")


class TestLeastGreatest:
    def test_parses_least_with_multiple_arguments(self):
        assert parse("SELECT LEAST(a, 1, 2)") == Select(
            FunctionCall("least", (Identifier("a"), Number("1"), Number("2")))
        )

    def test_parses_greatest(self):
        ast = parse("GREATEST(x, y)")
        assert isinstance(ast.expr, FunctionCall) and ast.expr.name == "greatest"
        assert ast.expr.args == (Identifier("x"), Identifier("y"))

    def test_parses_identifier_with_trailing_question_mark(self):
        assert parse("SELECT active?") == Select(Identifier("active?"))


class TestUnaryMinus:
    def test_parses_unary_minus_on_literal(self):
        assert parse("SELECT -1") == Select(UnaryOp("minus", Number("1")))

    def test_parses_unary_minus_on_right_side_of_multiplication(self):
        assert parse("SELECT amount * -1") == Select(
            BinaryOp("multiply", Identifier("amount"), UnaryOp("minus", Number("1")))
        )

    def test_parses_unary_minus_on_parenthesized_expression(self):
        assert parse("SELECT -(1 + 2)") == Select(
            UnaryOp("minus", BinaryOp("plus", Number("1"), Number("2")))
        )

    def test_parses_subtraction_of_negated_operand(self):
        assert parse("SELECT 5 - - 2") == Select(
            BinaryOp("minus", Number("5"), UnaryOp("minus", Number("2")))
        )

    def test_parses_nested_unary_minus(self):
        assert parse("SELECT - -5") == Select(
            UnaryOp("minus", UnaryOp("minus", Number("5")))
        )

    def test_double_dash_is_a_comment_not_unary(self):
        with pytest.raises(DsqlexError):
            parse("SELECT --5")

    def test_parses_unary_minus_in_in_list(self):
        assert parse("x IN (1, -2)") == Select(
            InExpr(Identifier("x"), (Number("1"), UnaryOp("minus", Number("2"))))
        )

    def test_rejects_mixing_additive_and_multiplicative_with_negated_operand(self):
        with pytest.raises(DsqlexError, match="Ambiguous expression"):
            parse("SELECT 1 + 2 * -3")
