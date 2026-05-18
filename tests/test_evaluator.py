"""Evaluator tests — ports Dsqlex.EvaluatorTest from the Elixir reference."""
import pytest
from decimal import Decimal
from dsqlex import evaluate_ast, DsqlexError
from dsqlex import (
    Select, Number, String, Boolean, Null, Identifier,
    BinaryOp, CaseExpr, WhenClause, FunctionCall,
    InExpr, NotInExpr, LikeExpr, NotLikeExpr,
)


# ---------------------------------------------------------------------------
# Test context (mirrors the Elixir @context)
# ---------------------------------------------------------------------------

CTX = {
    "x": Decimal("100.00"),
    "y": Decimal("20.00"),
    "category": "B",
    "rate": Decimal("5.00"),
    "status": "active",
    "group_id": 33,
    "nullable_field": None,
    "flag": True,
}


# ---------------------------------------------------------------------------
# Shorthand helpers (mirrors Elixir helper functions)
# ---------------------------------------------------------------------------

def sel(expr):
    return Select(expr)

def num(n):
    return Number(n)

def s(v):
    return String(v)

def ident(name):
    return Identifier(name)

def b(v):
    return Boolean(v)

def null():
    return Null()

def binop(op, left, right):
    return BinaryOp(op, left, right)

def case_expr(whens, else_clause):
    return CaseExpr(tuple(whens), else_clause)

def when_clause(cond, result):
    return WhenClause(cond, result)

def call(name, args):
    return FunctionCall(name, tuple(args))

def ev(ast, **opts):
    return evaluate_ast(ast, CTX, **opts)


# ---------------------------------------------------------------------------
# Literals
# ---------------------------------------------------------------------------

class TestLiterals:
    def test_evaluates_number_as_decimal(self):
        result = ev(sel(num("42")))
        assert isinstance(result, Decimal)
        assert result == Decimal("42")

    def test_evaluates_string(self):
        assert ev(sel(s("hello"))) == "hello"

    def test_evaluates_boolean(self):
        assert ev(sel(b(True))) is True
        assert ev(sel(b(False))) is False

    def test_evaluates_null(self):
        assert ev(sel(null())) is None


# ---------------------------------------------------------------------------
# Identifiers
# ---------------------------------------------------------------------------

class TestIdentifiers:
    def test_looks_up_identifier_in_context(self):
        assert ev(sel(ident("category"))) == "B"

    def test_returns_decimal_for_numeric_fields(self):
        result = ev(sel(ident("x")))
        assert result == Decimal("100.00")

    def test_returns_none_for_nullable_field(self):
        assert ev(sel(ident("nullable_field"))) is None

    def test_errors_on_unknown_field(self):
        with pytest.raises(DsqlexError, match="Unknown field: unknown_field"):
            ev(sel(ident("unknown_field")))


# ---------------------------------------------------------------------------
# Arithmetic
# ---------------------------------------------------------------------------

class TestArithmetic:
    def test_addition(self):
        assert ev(sel(binop("plus", num("10"), num("5")))) == Decimal("15")

    def test_subtraction(self):
        assert ev(sel(binop("minus", num("10"), num("3")))) == Decimal("7")

    def test_multiplication(self):
        assert ev(sel(binop("multiply", num("4"), num("5")))) == Decimal("20")

    def test_division(self):
        assert ev(sel(binop("divide", num("100"), num("5")))) == Decimal("20")

    def test_division_with_context_values(self):
        result = ev(sel(binop("divide", ident("x"), ident("rate"))))
        assert result == Decimal("20")

    def test_nested_arithmetic(self):
        # (10 + 5) * 2 = 30
        ast = sel(binop("multiply", binop("plus", num("10"), num("5")), num("2")))
        assert ev(ast) == Decimal("30")


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------

class TestComparison:
    def test_equality_true(self):
        assert ev(sel(binop("eq", ident("category"), s("B")))) is True

    def test_equality_false(self):
        assert ev(sel(binop("eq", ident("category"), s("A")))) is False

    def test_inequality(self):
        assert ev(sel(binop("neq", ident("category"), s("A")))) is True

    def test_less_than(self):
        assert ev(sel(binop("lt", num("5"), num("10")))) is True

    def test_greater_than(self):
        assert ev(sel(binop("gt", ident("x"), num("50")))) is True

    def test_less_than_or_equal(self):
        assert ev(sel(binop("lte", num("10"), num("10")))) is True

    def test_greater_than_or_equal(self):
        assert ev(sel(binop("gte", ident("group_id"), num("33")))) is True

    def test_numeric_comparison_with_decimals(self):
        assert ev(sel(binop("gt", ident("x"), ident("y")))) is True


# ---------------------------------------------------------------------------
# Logical operators
# ---------------------------------------------------------------------------

class TestLogicalOperators:
    def test_and_both_true(self):
        ast = sel(binop("and",
            binop("eq", ident("category"), s("B")),
            binop("eq", ident("group_id"), num("33"))))
        assert ev(ast) is True

    def test_and_one_false(self):
        ast = sel(binop("and",
            binop("eq", ident("category"), s("A")),
            binop("eq", ident("group_id"), num("33"))))
        assert ev(ast) is False

    def test_or_one_true(self):
        ast = sel(binop("or",
            binop("eq", ident("category"), s("A")),
            binop("eq", ident("group_id"), num("33"))))
        assert ev(ast) is True

    def test_or_both_false(self):
        ast = sel(binop("or",
            binop("eq", ident("category"), s("A")),
            binop("eq", ident("group_id"), num("99"))))
        assert ev(ast) is False

    def test_chained_and(self):
        ast = sel(binop("and",
            binop("and",
                binop("eq", ident("category"), s("B")),
                binop("eq", ident("group_id"), num("33"))),
            binop("eq", ident("status"), s("active"))))
        assert ev(ast) is True


# ---------------------------------------------------------------------------
# CASE/WHEN
# ---------------------------------------------------------------------------

class TestCaseWhen:
    def test_returns_first_matching_when_result(self):
        ast = sel(case_expr([
            when_clause(binop("eq", ident("category"), s("A")), s("first")),
            when_clause(binop("eq", ident("category"), s("B")), s("second")),
        ], None))
        assert ev(ast) == "second"

    def test_returns_else_when_no_when_matches(self):
        ast = sel(case_expr([
            when_clause(binop("eq", ident("category"), s("A")), s("first")),
            when_clause(binop("eq", ident("category"), s("C")), s("third")),
        ], s("other")))
        assert ev(ast) == "other"

    def test_returns_none_when_no_match_and_no_else(self):
        ast = sel(case_expr([
            when_clause(binop("eq", ident("category"), s("A")), s("first")),
        ], None))
        assert ev(ast) is None

    def test_evaluates_complex_when_conditions(self):
        ast = sel(case_expr([
            when_clause(
                binop("and",
                    binop("eq", ident("category"), s("B")),
                    binop("gt", ident("x"), num("50"))),
                s("big B"))
        ], s("other")))
        assert ev(ast) == "big B"

    def test_conditional_division_use_case(self):
        ast = sel(case_expr([
            when_clause(binop("eq", ident("category"), s("A")), ident("y")),
            when_clause(binop("neq", ident("category"), s("A")),
                        binop("divide", ident("x"), ident("rate"))),
        ], None))
        result = ev(ast)
        assert result == Decimal("20")


# ---------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------

class TestFunctions:
    def test_round_with_precision(self):
        ast = sel(call("round", [num("3.14159"), num("2")]))
        assert ev(ast) == Decimal("3.14")

    def test_round_with_expression(self):
        ast = sel(call("round", [
            binop("divide", ident("x"), ident("rate")),
            num("2"),
        ]))
        assert ev(ast) == Decimal("20.00")

    def test_coalesce_returns_first_non_null(self):
        ast = sel(call("coalesce", [ident("nullable_field"), num("0")]))
        assert ev(ast) == Decimal("0")

    def test_coalesce_returns_first_value_if_not_null(self):
        ast = sel(call("coalesce", [ident("y"), num("0")]))
        assert ev(ast) == Decimal("20.00")

    def test_upper(self):
        assert ev(sel(call("upper", [ident("category")]))) == "B"
        assert ev(sel(call("upper", [s("hello")]))) == "HELLO"

    def test_lower(self):
        assert ev(sel(call("lower", [s("HELLO")]))) == "hello"

    def test_abs(self):
        assert ev(sel(call("abs", [num("-42")]))) == Decimal("42")

    def test_concat_with_two_strings(self):
        assert ev(sel(call("concat", [s("hello"), s(" world")]))) == "hello world"

    def test_concat_with_multiple_arguments(self):
        assert ev(sel(call("concat", [ident("status"), s(" - "), ident("category")]))) == "active - B"

    def test_concat_coerces_numbers_to_strings(self):
        assert ev(sel(call("concat", [s("Value: "), ident("x")]))) == "Value: 100.00"

    def test_nested_functions(self):
        # ROUND(COALESCE(x / rate, y), 2) = ROUND(20, 2) = 20.00
        ast = sel(call("round", [
            call("coalesce", [
                binop("divide", ident("x"), ident("rate")),
                ident("y"),
            ]),
            num("2"),
        ]))
        assert ev(ast) == Decimal("20.00")


# ---------------------------------------------------------------------------
# Type handling
# ---------------------------------------------------------------------------

class TestTypeHandling:
    def test_compares_decimal_to_integer(self):
        # group_id=33 (int) vs num("33") (Decimal)
        assert ev(sel(binop("eq", ident("group_id"), num("33")))) is True

    def test_compares_strings(self):
        assert ev(sel(binop("lt", s("apple"), s("banana")))) is True


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

class TestErrorHandling:
    def test_unknown_field_returns_error(self):
        with pytest.raises(DsqlexError):
            ev(sel(ident("nonexistent")))


# ---------------------------------------------------------------------------
# Resolver
# ---------------------------------------------------------------------------

class TestResolver:
    def test_resolves_unknown_identifier_via_resolver(self):
        def resolver(name, visited):
            if name == "event_a":
                return Decimal("42")
            raise DsqlexError(f"Unknown: {name}")

        ast = sel(binop("plus", ident("event_a"), num("10")))
        result = evaluate_ast(ast, {}, resolver=resolver)
        assert result == Decimal("52")

    def test_context_takes_precedence_over_resolver(self):
        def resolver(name, visited):
            return Decimal("999")

        ast = sel(ident("x"))
        result = evaluate_ast(ast, CTX, resolver=resolver)
        assert result == Decimal("100.00")

    def test_resolver_error_is_propagated(self):
        def resolver(name, visited):
            raise DsqlexError(f"Event not found: {name}")

        ast = sel(ident("missing_event"))
        with pytest.raises(DsqlexError, match="Event not found: missing_event"):
            evaluate_ast(ast, {}, resolver=resolver)

    def test_circular_reference_is_detected(self):
        def resolver(name, visited):
            return Decimal("1")

        ast = sel(ident("event_a"))
        with pytest.raises(DsqlexError, match="Circular reference detected: event_a"):
            evaluate_ast(ast, {}, resolver=resolver, visited=frozenset(["event_a"]))

    def test_resolver_works_inside_arithmetic(self):
        def resolver(name, visited):
            return {"event_a": Decimal("100"), "event_b": Decimal("30")}[name]

        ast = sel(binop("minus", ident("event_a"), ident("event_b")))
        result = evaluate_ast(ast, {}, resolver=resolver)
        assert result == Decimal("70")

    def test_resolver_works_inside_case_when(self):
        def resolver(name, visited):
            if name == "event_a":
                return Decimal("50")
            raise DsqlexError(f"Unknown: {name}")

        ast = sel(case_expr([
            when_clause(binop("gt", ident("event_a"), num("10")), ident("event_a")),
        ], num("0")))
        result = evaluate_ast(ast, {}, resolver=resolver)
        assert result == Decimal("50")


# ---------------------------------------------------------------------------
# Dot-path nested map access
# ---------------------------------------------------------------------------

class TestDotPath:
    def test_simple_dot_path(self):
        ctx = {"config": {"pricing": Decimal("1.02")}}
        ast = Select(Identifier("config.pricing"))
        result = evaluate_ast(ast, ctx)
        assert result == Decimal("1.02")

    def test_multi_level_dot_path(self):
        ctx = {"config": {"pricing": {"margin_rate": Decimal("2.9")}}}
        ast = Select(Identifier("config.pricing.margin_rate"))
        result = evaluate_ast(ast, ctx)
        assert result == Decimal("2.9")

    def test_dot_path_in_arithmetic_expression(self):
        ctx = {
            "base_amount": Decimal("100"),
            "config": {"pricing": {"settlement_rate": Decimal("1.02")}},
        }
        ast = Select(BinaryOp("multiply",
            Identifier("base_amount"),
            Identifier("config.pricing.settlement_rate")))
        result = evaluate_ast(ast, ctx)
        assert result == Decimal("102.00")

    def test_dot_path_with_unknown_nested_key_raises_error(self):
        ctx = {"config": {"pricing": Decimal("1.02")}}
        ast = Select(Identifier("config.nonexistent"))
        with pytest.raises(DsqlexError, match="Unknown field: config.nonexistent"):
            evaluate_ast(ast, ctx)

    def test_dot_path_through_list_sums_numeric_values(self):
        ctx = {"adjustments": [
            {"adjustment_amount": Decimal("100.00")},
            {"adjustment_amount": Decimal("50.00")},
            {"adjustment_amount": Decimal("25.00")},
        ]}
        ast = Select(Identifier("adjustments.adjustment_amount"))
        result = evaluate_ast(ast, ctx)
        assert result == Decimal("175.00")

    def test_dot_path_through_list_with_nested_map_sums(self):
        ctx = {"adjustments": [
            {"config": {"pricing": {"margin_rate": Decimal("1.5")}}},
            {"config": {"pricing": {"margin_rate": Decimal("2.5")}}},
        ]}
        ast = Select(Identifier("adjustments.config.pricing.margin_rate"))
        result = evaluate_ast(ast, ctx)
        assert result == Decimal("4.0")

    def test_dot_path_through_list_returns_list_for_non_numeric(self):
        ctx = {"adjustments": [
            {"status": "CO"},
            {"status": "PE"},
        ]}
        ast = Select(Identifier("adjustments.status"))
        result = evaluate_ast(ast, ctx)
        assert result == ["CO", "PE"]

    def test_dot_path_through_single_map(self):
        ctx = {"order_data": {"amount": Decimal("500.00")}}
        ast = Select(Identifier("order_data.amount"))
        result = evaluate_ast(ast, ctx)
        assert result == Decimal("500.00")


# ---------------------------------------------------------------------------
# EVENT() function
# ---------------------------------------------------------------------------

def make_mock_event_resolver(formulas: dict):
    import dsqlex
    def resolver(type_, subtype, eval_context, opts):
        key = f"{type_}.{subtype}"
        if key in formulas:
            return dsqlex.eval(formulas[key], eval_context, **opts)
        raise DsqlexError(f"No formula found for EVENT({type_}, {subtype})")
    return resolver


class TestEventFunction:
    def test_event_2_args_evaluates_with_current_context(self):
        formulas = {"ORDER_PLACED.SERVICE_FEE": "amount * rate"}
        resolver = make_mock_event_resolver(formulas)
        ctx = {"amount": Decimal("100"), "rate": Decimal("0.05")}
        ast = sel(call("event", [ident("ORDER_PLACED"), ident("SERVICE_FEE")]))
        result = evaluate_ast(ast, ctx, event_resolver=resolver)
        assert result == Decimal("5.000")

    def test_event_3_args_single_map_context_source(self):
        formulas = {"ORDER_PLACED.ORDER_TOTAL": "amount"}
        resolver = make_mock_event_resolver(formulas)
        ctx = {
            "amount": Decimal("999"),
            "order_data": {"amount": Decimal("500")},
        }
        ast = sel(call("event", [ident("ORDER_PLACED"), ident("ORDER_TOTAL"), ident("order_data")]))
        result = evaluate_ast(ast, ctx, event_resolver=resolver)
        assert result == Decimal("500")

    def test_event_3_args_list_context_source_implicit_sum(self):
        formulas = {"RETURN_PROCESSED.RETURN_TOTAL": "amount"}
        resolver = make_mock_event_resolver(formulas)
        ctx = {"adjustments": [
            {"amount": Decimal("50")},
            {"amount": Decimal("30")},
            {"amount": Decimal("20")},
        ]}
        ast = sel(call("event", [ident("RETURN_PROCESSED"), ident("RETURN_TOTAL"), ident("adjustments")]))
        result = evaluate_ast(ast, ctx, event_resolver=resolver)
        assert result == Decimal("100")

    def test_event_empty_list_returns_zero(self):
        formulas = {"RETURN_PROCESSED.RETURN_TOTAL": "amount"}
        resolver = make_mock_event_resolver(formulas)
        ctx = {"adjustments": []}
        ast = sel(call("event", [ident("RETURN_PROCESSED"), ident("RETURN_TOTAL"), ident("adjustments")]))
        result = evaluate_ast(ast, ctx, event_resolver=resolver)
        assert result == Decimal("0")

    def test_net_total_pattern(self):
        formulas = {
            "ORDER_PLACED.ORDER_TOTAL": "amount",
            "RETURN_PROCESSED.RETURN_TOTAL": "amount",
        }
        resolver = make_mock_event_resolver(formulas)
        ctx = {
            "order_data": {"amount": Decimal("500")},
            "adjustments": [
                {"amount": Decimal("50")},
                {"amount": Decimal("30")},
            ],
        }
        ast = sel(binop("minus",
            call("event", [ident("ORDER_PLACED"), ident("ORDER_TOTAL"), ident("order_data")]),
            call("event", [ident("RETURN_PROCESSED"), ident("RETURN_TOTAL"), ident("adjustments")])))
        result = evaluate_ast(ast, ctx, event_resolver=resolver)
        assert result == Decimal("420")

    def test_event_errors_when_no_resolver(self):
        ast = sel(call("event", [ident("TYPE"), ident("SUBTYPE")]))
        with pytest.raises(DsqlexError, match="event_resolver"):
            evaluate_ast(ast, {})

    def test_event_errors_when_formula_not_found(self):
        resolver = make_mock_event_resolver({})
        ast = sel(call("event", [ident("UNKNOWN"), ident("EVENT")]))
        with pytest.raises(DsqlexError, match="No formula found"):
            evaluate_ast(ast, {}, event_resolver=resolver)

    def test_event_errors_when_context_source_not_found(self):
        resolver = make_mock_event_resolver({"T.S": "x"})
        ast = sel(call("event", [ident("T"), ident("S"), ident("missing_field")]))
        with pytest.raises(DsqlexError, match="not found in context"):
            evaluate_ast(ast, {}, event_resolver=resolver)

    def test_event_errors_with_wrong_number_of_args(self):
        resolver = make_mock_event_resolver({})
        ast = sel(call("event", [ident("ONLY_ONE")]))
        with pytest.raises(DsqlexError, match="EVENT requires 2 or 3 arguments"):
            evaluate_ast(ast, {}, event_resolver=resolver)

    def test_event_circular_reference_detection(self):
        formulas = {
            "A.X": "EVENT(B, Y)",
            "B.Y": "EVENT(A, X)",
        }
        resolver = make_mock_event_resolver(formulas)
        ast = sel(call("event", [ident("A"), ident("X")]))
        with pytest.raises(DsqlexError, match="Circular reference detected: A.X"):
            evaluate_ast(ast, {}, event_resolver=resolver)

    def test_event_in_case_expression(self):
        formulas = {"P.FEE": "amount * rate"}
        resolver = make_mock_event_resolver(formulas)
        ctx = {"currency": "USD", "amount": Decimal("100"), "rate": Decimal("0.03")}
        ast = sel(case_expr([
            when_clause(binop("eq", ident("currency"), s("USD")),
                        call("event", [ident("P"), ident("FEE")])),
        ], num("0")))
        result = evaluate_ast(ast, ctx, event_resolver=resolver)
        assert result == Decimal("3.00")

    def test_event_arithmetic_with_scalar_and_list_context(self):
        formulas = {"P.REC": "amount", "R.REC": "amount"}
        resolver = make_mock_event_resolver(formulas)
        ctx = {
            "order_data": {"amount": Decimal("1000")},
            "adjustments": [
                {"amount": Decimal("100")},
                {"amount": Decimal("200")},
                {"amount": Decimal("150")},
            ],
        }
        # EVENT(P, REC, order_data) - EVENT(R, REC, adjustments) = 1000 - 450 = 550
        ast = sel(binop("minus",
            call("event", [ident("P"), ident("REC"), ident("order_data")]),
            call("event", [ident("R"), ident("REC"), ident("adjustments")])))
        result = evaluate_ast(ast, ctx, event_resolver=resolver)
        assert result == Decimal("550")


# ---------------------------------------------------------------------------
# IN and NOT IN
# ---------------------------------------------------------------------------

class TestInNotIn:
    def test_string_in_list_match(self):
        ast = sel(InExpr(ident("category"), (s("A"), s("B"), s("C"))))
        assert ev(ast) is True

    def test_string_in_list_no_match(self):
        ast = sel(InExpr(ident("category"), (s("X"), s("Y"))))
        assert ev(ast) is False

    def test_number_in_list_match(self):
        ast = sel(InExpr(ident("x"), (num("50"), num("100.00"), num("200"))))
        assert ev(ast) is True

    def test_number_in_list_no_match(self):
        ast = sel(InExpr(ident("x"), (num("1"), num("2"))))
        assert ev(ast) is False

    def test_not_in_no_match_returns_true(self):
        ast = sel(NotInExpr(ident("category"), (s("X"), s("Y"))))
        assert ev(ast) is True

    def test_not_in_match_returns_false(self):
        ast = sel(NotInExpr(ident("category"), (s("A"), s("B"))))
        assert ev(ast) is False

    def test_in_with_single_item(self):
        ast = sel(InExpr(ident("category"), (s("B"),)))
        assert ev(ast) is True


# ---------------------------------------------------------------------------
# LIKE and NOT LIKE
# ---------------------------------------------------------------------------

class TestLikeNotLike:
    def test_like_percent_prefix_match(self):
        assert ev(sel(LikeExpr(ident("status"), s("%tive")))) is True

    def test_like_percent_suffix_match(self):
        assert ev(sel(LikeExpr(ident("status"), s("act%")))) is True

    def test_like_percent_both_sides(self):
        assert ev(sel(LikeExpr(ident("status"), s("%ctiv%")))) is True

    def test_like_exact_match(self):
        assert ev(sel(LikeExpr(ident("status"), s("active")))) is True

    def test_like_no_match(self):
        assert ev(sel(LikeExpr(ident("status"), s("%xyz%")))) is False

    def test_like_underscore_single_char_wildcard(self):
        assert ev(sel(LikeExpr(ident("category"), s("_")))) is True

    def test_like_underscore_does_not_match_multiple_chars(self):
        assert ev(sel(LikeExpr(ident("status"), s("_")))) is False

    def test_like_is_case_insensitive(self):
        assert ev(sel(LikeExpr(ident("status"), s("ACTIVE")))) is True

    def test_like_case_insensitive_with_wildcards(self):
        assert ev(sel(LikeExpr(ident("status"), s("%CTIV%")))) is True

    def test_not_like_no_match_returns_true(self):
        assert ev(sel(NotLikeExpr(ident("status"), s("%xyz%")))) is True

    def test_not_like_match_returns_false(self):
        assert ev(sel(NotLikeExpr(ident("status"), s("%active%")))) is False
