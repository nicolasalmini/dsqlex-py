"""Integration tests — ports Dsqlex.IntegrationTest from the Elixir reference."""
import pytest
from decimal import Decimal
import dsqlex
from dsqlex import DsqlexError


# ---------------------------------------------------------------------------
# Sample context (mirrors @sample_context)
# ---------------------------------------------------------------------------

SAMPLE = {
    "price": Decimal("500.00"),
    "quantity": Decimal("100.00"),
    "category": "B",
    "rate": Decimal("5.00"),
    "status": "completed",
    "group_id": 33,
    "label": "hello world",
    "tax": Decimal("10.00"),
    "discount": Decimal("2.00"),
    "bonus": None,
}


def run(expression, context=None):
    if context is None:
        context = SAMPLE
    return dsqlex.eval(expression, context)


# ---------------------------------------------------------------------------
# Simple expressions
# ---------------------------------------------------------------------------

class TestSimpleExpressions:
    def test_select_a_field(self):
        assert run("SELECT price") == Decimal("500.00")

    def test_select_a_literal(self):
        assert run("SELECT 42") == Decimal("42")

    def test_select_a_string(self):
        assert run("SELECT 'hello'") == "hello"


# ---------------------------------------------------------------------------
# Arithmetic calculations
# ---------------------------------------------------------------------------

class TestArithmetic:
    def test_simple_division(self):
        assert run("SELECT price / rate") == Decimal("100")

    def test_addition(self):
        assert run("SELECT price + quantity") == Decimal("600.00")

    def test_complex_arithmetic_with_parentheses(self):
        assert run("SELECT (price + tax) / rate") == Decimal("102")

    def test_nested_parentheses(self):
        assert run("SELECT ((price / rate) + discount)") == Decimal("102.00")


# ---------------------------------------------------------------------------
# Comparisons and logic
# ---------------------------------------------------------------------------

class TestComparisonsAndLogic:
    def test_equality_check(self):
        assert run("SELECT category = 'B'") is True
        assert run("SELECT category = 'A'") is False

    def test_numeric_comparison(self):
        assert run("SELECT price > 100") is True
        assert run("SELECT price < 100") is False

    def test_and_condition(self):
        assert run("SELECT category = 'B' AND group_id = 33") is True
        assert run("SELECT category = 'A' AND group_id = 33") is False

    def test_or_condition(self):
        assert run("SELECT category = 'A' OR group_id = 33") is True
        assert run("SELECT category = 'A' OR group_id = 99") is False

    def test_chained_and(self):
        assert run("SELECT category = 'B' AND group_id = 33 AND status = 'completed'") is True

    def test_mixed_and_or_with_parentheses(self):
        assert run("SELECT (category = 'A' OR category = 'B') AND group_id = 33") is True
        assert run("SELECT category = 'B' AND (group_id = 33 OR group_id = 55)") is True


# ---------------------------------------------------------------------------
# CASE/WHEN — the main use case
# ---------------------------------------------------------------------------

class TestCaseWhen:
    def test_conditional_selection_category_b(self):
        result = run("""
            SELECT CASE
              WHEN category = 'A' THEN quantity
              WHEN category != 'A' THEN (price / rate)
            END
        """)
        assert result == Decimal("100")

    def test_conditional_selection_category_a(self):
        ctx = {**SAMPLE, "category": "A"}
        result = run("""
            SELECT CASE
              WHEN category = 'A' THEN quantity
              WHEN category != 'A' THEN (price / rate)
            END
        """, ctx)
        assert result == Decimal("100.00")

    def test_multiple_conditions_with_else(self):
        result = run("""
            SELECT CASE
              WHEN status = 'pending' THEN 'waiting'
              WHEN status = 'completed' THEN 'done'
              ELSE 'unknown'
            END
        """)
        assert result == "done"

    def test_complex_condition_in_when(self):
        result = run("""
            SELECT CASE
              WHEN category = 'B' AND price > 100 THEN 'large B item'
              ELSE 'other'
            END
        """)
        assert result == "large B item"

    def test_nested_case(self):
        result = run("""
            SELECT CASE
              WHEN category = 'B' THEN
                CASE
                  WHEN price > 1000 THEN 'large'
                  ELSE 'small'
                END
              ELSE 'other'
            END
        """)
        assert result == "small"


# ---------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------

class TestFunctions:
    def test_round_calculation_result(self):
        assert run("SELECT ROUND(price / rate, 2)") == Decimal("100.00")

    def test_coalesce_with_null(self):
        assert run("SELECT COALESCE(bonus, 0)") == Decimal("0")

    def test_coalesce_with_non_null(self):
        assert run("SELECT COALESCE(quantity, 0)") == Decimal("100.00")

    def test_upper(self):
        assert run("SELECT UPPER(label)") == "HELLO WORLD"

    def test_nested_functions(self):
        result = run("SELECT ROUND(COALESCE((price / rate), quantity), 2)")
        assert result == Decimal("100.00")

    def test_function_in_case_result(self):
        result = run("""
            SELECT CASE
              WHEN category = 'B' THEN ROUND(price / rate, 2)
              ELSE quantity
            END
        """)
        assert result == Decimal("100.00")

    def test_concat_strings(self):
        assert run("CONCAT('Hello', ' ', 'World')") == "Hello World"

    def test_concat_with_fields(self):
        assert run("CONCAT(label, ' in ', category)") == "hello world in B"

    def test_concat_in_case(self):
        result = run("""
            CASE
              WHEN category = 'B' THEN CONCAT('Category: ', category)
              ELSE CONCAT('Other: ', category)
            END
        """)
        assert result == "Category: B"


# ---------------------------------------------------------------------------
# Advanced calculation scenarios
# ---------------------------------------------------------------------------

class TestAdvancedScenarios:
    def test_net_value_after_deductions(self):
        assert run("SELECT (price - tax) / rate") == Decimal("98")

    def test_percentage_calculation(self):
        assert run("SELECT (tax / price) * 100") == Decimal("2.00")

    def test_conditional_value_selection(self):
        result = run("""
            SELECT CASE
              WHEN category = 'A' THEN discount
              ELSE (tax / rate)
            END
        """)
        assert result == Decimal("2")

    def test_complex_conditional_rule(self):
        result = run("""
            SELECT CASE
              WHEN category = 'A' AND quantity > 50 THEN ROUND(quantity * 1.1, 2)
              WHEN category != 'A' AND price > 100 THEN ROUND((price / rate) * 1.05, 2)
              ELSE 0
            END
        """)
        # category=B, price=500 > 100, so: ROUND((500/5) * 1.05, 2) = ROUND(105.00, 2) = 105.00
        assert result == Decimal("105.00")


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

class TestErrorHandling:
    def test_lexer_error_unterminated_string(self):
        with pytest.raises(DsqlexError, match="Unterminated string"):
            run("SELECT 'hello")

    def test_parser_error_missing_parenthesis(self):
        with pytest.raises(DsqlexError, match="Expected closing parenthesis"):
            run("SELECT (1 + 2")

    def test_parser_error_ambiguous_expression(self):
        with pytest.raises(DsqlexError, match="Ambiguous expression"):
            run("SELECT 1 + 2 * 3")

    def test_evaluator_error_unknown_field(self):
        with pytest.raises(DsqlexError, match="Unknown field: nonexistent"):
            run("SELECT nonexistent")


# ---------------------------------------------------------------------------
# Cross-event references (resolver pattern)
# ---------------------------------------------------------------------------

EVENT_FORMULAS = {
    "event_a": "x + y",
    "event_b": "z - event_a",
    "event_c": "event_a + event_b",
    "event_circular": "event_circular + 1",
}

REF_CTX = {
    "x": Decimal("100"),
    "y": Decimal("20"),
    "z": Decimal("200"),
}


def make_resolver(formulas, context):
    def resolver(name, visited):
        if name in formulas:
            new_visited = visited | {name}
            return dsqlex.eval(
                formulas[name], context,
                resolver=make_resolver(formulas, context),
                visited=new_visited,
            )
        raise DsqlexError(f"Unknown event: {name}")
    return resolver


class TestCrossEventReferences:
    def test_event_b_references_event_a(self):
        # event_a = 100 + 20 = 120
        # event_b = 200 - event_a = 200 - 120 = 80
        resolver = make_resolver(EVENT_FORMULAS, REF_CTX)
        result = dsqlex.eval("event_b", REF_CTX, resolver=resolver)
        assert result == Decimal("80")

    def test_event_c_references_event_a_and_event_b(self):
        # event_c = event_a + event_b = 120 + 80 = 200
        resolver = make_resolver(EVENT_FORMULAS, REF_CTX)
        result = dsqlex.eval("event_c", REF_CTX, resolver=resolver)
        assert result == Decimal("200")

    def test_direct_event_reference(self):
        resolver = make_resolver(EVENT_FORMULAS, REF_CTX)
        result = dsqlex.eval("event_a", REF_CTX, resolver=resolver)
        assert result == Decimal("120")

    def test_circular_reference_is_detected(self):
        resolver = make_resolver(EVENT_FORMULAS, REF_CTX)
        with pytest.raises(DsqlexError, match="Circular reference detected: event_circular"):
            dsqlex.eval("event_circular", REF_CTX, resolver=resolver)

    def test_unknown_event_returns_error(self):
        resolver = make_resolver(EVENT_FORMULAS, REF_CTX)
        with pytest.raises(DsqlexError, match="Unknown event: nonexistent_event"):
            dsqlex.eval("nonexistent_event", REF_CTX, resolver=resolver)

    def test_event_reference_in_arithmetic(self):
        # (event_a * 2) = 240
        resolver = make_resolver(EVENT_FORMULAS, REF_CTX)
        result = dsqlex.eval("event_a * 2", REF_CTX, resolver=resolver)
        assert result == Decimal("240")

    def test_event_reference_in_case_expression(self):
        resolver = make_resolver(EVENT_FORMULAS, REF_CTX)
        result = dsqlex.eval("""
            CASE
              WHEN event_a > 100 THEN event_b
              ELSE 0
            END
        """, REF_CTX, resolver=resolver)
        assert result == Decimal("80")


# ---------------------------------------------------------------------------
# EVENT() function — end to end
# ---------------------------------------------------------------------------

def mock_event_resolver(formulas):
    def resolver(type_, subtype, eval_context, opts):
        key = f"{type_}.{subtype}"
        if key in formulas:
            return dsqlex.eval(formulas[key], eval_context, **opts)
        raise DsqlexError(f"No formula found for EVENT({type_}, {subtype})")
    return resolver


def run_with_events(expression, context, formulas):
    resolver = mock_event_resolver(formulas)
    return dsqlex.eval(expression, context, event_resolver=resolver)


class TestEventFunctionEndToEnd:
    def test_event_2_args_uses_current_context(self):
        formulas = {"ORDER_PLACED.FEE": "amount * rate"}
        ctx = {"amount": Decimal("100"), "rate": Decimal("0.05")}
        result = run_with_events("EVENT(ORDER_PLACED, FEE)", ctx, formulas)
        assert result == Decimal("5.000")

    def test_event_3_args_map_context_source(self):
        formulas = {"P.REC": "amount"}
        ctx = {
            "amount": Decimal("999"),
            "order_data": {"amount": Decimal("500")},
        }
        result = run_with_events("EVENT(P, REC, order_data)", ctx, formulas)
        assert result == Decimal("500")

    def test_event_3_args_list_context_source_implicit_sum(self):
        formulas = {"R.REC": "amount"}
        ctx = {
            "adjustments": [
                {"amount": Decimal("50")},
                {"amount": Decimal("30")},
            ]
        }
        result = run_with_events("EVENT(R, REC, adjustments)", ctx, formulas)
        assert result == Decimal("80")

    def test_net_total_pattern(self):
        formulas = {
            "ORDER_PLACED.ORDER_TOTAL": "amount",
            "RETURN_PROCESSED.RETURN_TOTAL": "amount",
        }
        ctx = {
            "order_data": {"amount": Decimal("1000")},
            "adjustments": [
                {"amount": Decimal("200")},
                {"amount": Decimal("100")},
            ],
        }
        result = run_with_events(
            "EVENT(ORDER_PLACED, ORDER_TOTAL, order_data) - EVENT(RETURN_PROCESSED, RETURN_TOTAL, adjustments)",
            ctx, formulas)
        assert result == Decimal("700")

    def test_event_in_case_expression(self):
        formulas = {"P.FEE": "amount * rate"}
        ctx = {"currency": "USD", "amount": Decimal("100"), "rate": Decimal("0.03")}
        result = run_with_events("""
            CASE
              WHEN currency = 'USD' THEN EVENT(P, FEE)
              ELSE 0
            END
        """, ctx, formulas)
        assert result == Decimal("3.00")

    def test_circular_event_reference_detected(self):
        formulas = {"A.X": "EVENT(B, Y)", "B.Y": "EVENT(A, X)"}
        with pytest.raises(DsqlexError, match="Circular reference detected: A.X"):
            run_with_events("EVENT(A, X)", {}, formulas)

    def test_event_with_missing_formula_returns_error(self):
        with pytest.raises(DsqlexError, match="No formula found for EVENT"):
            run_with_events("EVENT(UNKNOWN, MISSING_SUBTYPE)", {}, {})

    def test_nested_event_references(self):
        formulas = {
            "A.CALC": "amount * 2",
            "B.CALC": "EVENT(A, CALC) + 10",
        }
        ctx = {"amount": Decimal("50")}
        # B.CALC = EVENT(A, CALC) + 10 = (50 * 2) + 10 = 110
        result = run_with_events("EVENT(B, CALC)", ctx, formulas)
        assert result == Decimal("110")


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_string_literal(self):
        assert run("SELECT ''") == ""

    def test_zero_values(self):
        assert run("SELECT 0") == Decimal("0")

    def test_negative_result(self):
        assert run("SELECT 10 - 20") == Decimal("-10")

    def test_decimal_precision_maintained(self):
        result = run("SELECT 1 / 3")
        assert isinstance(result, Decimal)

    def test_whitespace_handling(self):
        assert run("SELECT    price   /   rate") is not None
        assert run("SELECT\n  price\n  /\n  rate") is not None

    def test_case_insensitive_keywords(self):
        assert run("select price") == Decimal("500.00")
        assert run("SELECT CASE when category = 'B' then price ELSE 0 end") == Decimal("500.00")

    def test_select_is_optional(self):
        assert run("price") == Decimal("500.00")
        assert run("price / rate") == Decimal("100")
        assert run("(price / rate) + discount") == Decimal("102.00")
        assert run("CASE WHEN category = 'B' THEN price ELSE quantity END") == Decimal("500.00")
        assert run("ROUND(price, 2)") == Decimal("500.00")


# ---------------------------------------------------------------------------
# IN operator
# ---------------------------------------------------------------------------

class TestInOperator:
    def test_string_in_list_match(self):
        assert run("category IN ('A', 'B', 'C')") is True

    def test_string_in_list_no_match(self):
        assert run("category IN ('X', 'Y')") is False

    def test_number_in_list(self):
        ctx = {"country_id": Decimal("33")}
        assert run("country_id IN (33, 44, 55)", ctx) is True

    def test_not_in(self):
        assert run("category NOT IN ('X', 'Y')") is True
        assert run("category NOT IN ('A', 'B')") is False

    def test_in_combined_with_and(self):
        assert run("category IN ('A', 'B') AND status = 'completed'") is True

    def test_in_combined_with_or(self):
        assert run("category IN ('X', 'Y') OR status = 'completed'") is True


# ---------------------------------------------------------------------------
# IS / IS NOT operator
# ---------------------------------------------------------------------------

IS_CTX = {
    "a": Decimal("1.00"),
    "b": None,
    "flag": True,
    "tag": "x",
}


class TestIsIsNot:
    def test_is_null_true_when_nil(self):
        assert run("b IS NULL", IS_CTX) is True

    def test_is_null_false_when_not_nil(self):
        assert run("a IS NULL", IS_CTX) is False

    def test_is_not_null_true_when_not_nil(self):
        assert run("a IS NOT NULL", IS_CTX) is True

    def test_is_not_null_false_when_nil(self):
        assert run("b IS NOT NULL", IS_CTX) is False

    def test_is_true_true_when_field_true(self):
        assert run("flag IS TRUE", IS_CTX) is True

    def test_is_true_false_when_field_false(self):
        ctx = {**IS_CTX, "flag": False}
        assert run("flag IS TRUE", ctx) is False

    def test_is_false_true_when_field_false(self):
        ctx = {**IS_CTX, "flag": False}
        assert run("flag IS FALSE", ctx) is True

    def test_is_not_true_true_when_field_false(self):
        ctx = {**IS_CTX, "flag": False}
        assert run("flag IS NOT TRUE", ctx) is True

    def test_is_not_false_true_when_field_true(self):
        assert run("flag IS NOT FALSE", IS_CTX) is True

    def test_is_null_in_case_when(self):
        result = run("""
            CASE
              WHEN b IS NULL THEN 'missing'
              ELSE 'present'
            END
        """, IS_CTX)
        assert result == "missing"

    def test_is_not_null_combined_with_and(self):
        assert run("a IS NOT NULL AND tag = 'x'", IS_CTX) is True


# ---------------------------------------------------------------------------
# LIKE operator
# ---------------------------------------------------------------------------

class TestLikeOperator:
    def test_like_percent_wildcard_contains(self):
        assert run("label LIKE '%world%'") is True

    def test_like_percent_wildcard_starts_with(self):
        assert run("label LIKE 'hello%'") is True

    def test_like_percent_wildcard_ends_with(self):
        assert run("label LIKE '%world'") is True

    def test_like_exact_match(self):
        assert run("label LIKE 'hello world'") is True
        assert run("label LIKE 'hello'") is False

    def test_like_underscore_wildcard(self):
        assert run("category LIKE '_'") is True
        assert run("label LIKE '_'") is False

    def test_like_is_case_insensitive(self):
        assert run("label LIKE 'HELLO WORLD'") is True
        assert run("label LIKE '%WORLD'") is True
        assert run("status LIKE 'COMPLETED'") is True

    def test_not_like(self):
        assert run("label NOT LIKE '%xyz%'") is True
        assert run("label NOT LIKE '%world%'") is False

    def test_like_combined_with_and(self):
        assert run("label LIKE '%hello%' AND status = 'completed'") is True

    def test_like_and_in_combined(self):
        assert run("category IN ('A', 'B') AND label LIKE '%world%'") is True


class TestNullAndExtremesEndToEnd:
    def test_null_propagates_through_arithmetic(self):
        assert run("SELECT bonus + 1") is None
        assert run("SELECT price * bonus") is None

    def test_round_and_abs_with_null(self):
        assert run("SELECT ROUND(bonus, 2)") is None
        assert run("SELECT ABS(bonus)") is None

    def test_least_greatest_end_to_end(self):
        assert run("SELECT LEAST(price, quantity, rate)") == Decimal("5.00")
        assert run("SELECT GREATEST(price, quantity, rate)") == Decimal("500.00")

    def test_least_null_propagates(self):
        assert run("SELECT LEAST(price, bonus)") is None

    def test_question_mark_identifier_in_context(self):
        assert run("SELECT eligible?", {"eligible?": True}) is True


class TestUnaryMinusEndToEnd:
    def test_negated_literal(self):
        assert run("SELECT -2.5") == Decimal("-2.5")

    def test_negated_field(self):
        assert run("SELECT -price") == Decimal("-500.00")

    def test_multiplication_by_negative_literal(self):
        assert run("SELECT price * -1") == Decimal("-500.00")

    def test_negated_parenthesized_expression(self):
        assert run("SELECT -(1 + 2)") == Decimal("-3")

    def test_subtraction_of_negated_operand(self):
        assert run("SELECT 5 - - 2") == Decimal("7")

    def test_negative_value_in_in_list(self):
        context = {"balance": Decimal("-42")}
        assert run("balance IN (-42, 0)", context) is True
        assert run("balance IN (-41, 0)", context) is False

    def test_negating_null_returns_none(self):
        assert run("SELECT -bonus") is None
        assert run("SELECT -NULL") is None
