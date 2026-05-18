"""Lexer tests — ports Dsqlex.LexerTest from the Elixir reference."""
import pytest
from dsqlex import tokenize, DsqlexError, Token


def tok(type_, value=None):
    return Token(type_, value)


# ---------------------------------------------------------------------------
# Operators
# ---------------------------------------------------------------------------

class TestOperators:
    def test_single_char_operators(self):
        assert tokenize("+") == [tok("operator", "plus")]
        assert tokenize("-") == [tok("operator", "minus")]
        assert tokenize("*") == [tok("operator", "multiply")]
        assert tokenize("/") == [tok("operator", "divide")]
        assert tokenize("=") == [tok("operator", "eq")]
        assert tokenize("<") == [tok("operator", "lt")]
        assert tokenize(">") == [tok("operator", "gt")]

    def test_multi_char_operators(self):
        assert tokenize("!=") == [tok("operator", "neq")]
        assert tokenize("<=") == [tok("operator", "lte")]
        assert tokenize(">=") == [tok("operator", "gte")]

    def test_multi_char_takes_precedence_over_single_char(self):
        # "<=" then ">" → lte, gt
        assert tokenize("<=>") == [tok("operator", "lte"), tok("operator", "gt")]


# ---------------------------------------------------------------------------
# Delimiters
# ---------------------------------------------------------------------------

class TestDelimiters:
    def test_parentheses(self):
        assert tokenize("()") == [tok("lparen"), tok("rparen")]

    def test_comma(self):
        assert tokenize(",") == [tok("comma")]


# ---------------------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------------------

class TestNumbers:
    def test_integers(self):
        assert tokenize("123") == [tok("number", "123")]
        assert tokenize("0") == [tok("number", "0")]
        assert tokenize("999999") == [tok("number", "999999")]

    def test_decimals(self):
        assert tokenize("3.14") == [tok("number", "3.14")]
        assert tokenize("0.5") == [tok("number", "0.5")]
        assert tokenize("100.00") == [tok("number", "100.00")]

    def test_number_followed_by_operator(self):
        assert tokenize("10+20") == [
            tok("number", "10"),
            tok("operator", "plus"),
            tok("number", "20"),
        ]


# ---------------------------------------------------------------------------
# Strings
# ---------------------------------------------------------------------------

class TestStrings:
    def test_simple_string(self):
        assert tokenize("'hello'") == [tok("string", "hello")]
        assert tokenize("'hello world'") == [tok("string", "hello world")]

    def test_empty_string(self):
        assert tokenize("''") == [tok("string", "")]

    def test_string_with_numbers(self):
        assert tokenize("'abc123'") == [tok("string", "abc123")]

    def test_unterminated_string(self):
        with pytest.raises(DsqlexError, match="Unterminated string"):
            tokenize("'hello")


# ---------------------------------------------------------------------------
# Identifiers
# ---------------------------------------------------------------------------

class TestIdentifiers:
    def test_simple_identifier(self):
        assert tokenize("my_var") == [tok("identifier", "my_var")]

    def test_identifier_with_numbers(self):
        assert tokenize("field1") == [tok("identifier", "field1")]
        assert tokenize("var2_name") == [tok("identifier", "var2_name")]

    def test_identifier_starting_with_underscore(self):
        assert tokenize("_private") == [tok("identifier", "_private")]


# ---------------------------------------------------------------------------
# Keywords
# ---------------------------------------------------------------------------

class TestKeywords:
    def test_sql_keywords(self):
        assert tokenize("SELECT") == [tok("keyword", "select")]
        assert tokenize("CASE") == [tok("keyword", "case")]
        assert tokenize("WHEN") == [tok("keyword", "when")]
        assert tokenize("THEN") == [tok("keyword", "then")]
        assert tokenize("ELSE") == [tok("keyword", "else")]
        assert tokenize("END") == [tok("keyword", "end")]

    def test_logical_keywords(self):
        assert tokenize("AND") == [tok("keyword", "and")]
        assert tokenize("OR") == [tok("keyword", "or")]
        assert tokenize("NOT") == [tok("keyword", "not")]

    def test_literal_keywords(self):
        assert tokenize("NULL") == [tok("keyword", "null")]
        assert tokenize("TRUE") == [tok("keyword", "true")]
        assert tokenize("FALSE") == [tok("keyword", "false")]

    def test_keywords_are_case_insensitive(self):
        assert tokenize("select") == [tok("keyword", "select")]
        assert tokenize("Select") == [tok("keyword", "select")]
        assert tokenize("sElEcT") == [tok("keyword", "select")]


# ---------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------

class TestFunctions:
    def test_built_in_functions(self):
        assert tokenize("UPPER") == [tok("function", "upper")]
        assert tokenize("LOWER") == [tok("function", "lower")]
        assert tokenize("ROUND") == [tok("function", "round")]
        assert tokenize("COALESCE") == [tok("function", "coalesce")]
        assert tokenize("ABS") == [tok("function", "abs")]

    def test_nvl_is_alias_for_coalesce(self):
        assert tokenize("NVL") == [tok("function", "coalesce")]

    def test_event_function(self):
        assert tokenize("EVENT") == [tok("function", "event")]
        assert tokenize("event") == [tok("function", "event")]
        assert tokenize("Event") == [tok("function", "event")]

    def test_functions_are_case_insensitive(self):
        assert tokenize("round") == [tok("function", "round")]
        assert tokenize("Round") == [tok("function", "round")]


# ---------------------------------------------------------------------------
# Dot-path identifiers
# ---------------------------------------------------------------------------

class TestDotPathIdentifiers:
    def test_simple_dot_path(self):
        assert tokenize("config.pricing") == [tok("identifier", "config.pricing")]

    def test_multi_level_dot_path(self):
        assert tokenize("config.pricing.margin_rate") == [
            tok("identifier", "config.pricing.margin_rate")
        ]

    def test_dot_path_in_expression(self):
        assert tokenize("base_amount * config.pricing.settlement_rate") == [
            tok("identifier", "base_amount"),
            tok("operator", "multiply"),
            tok("identifier", "config.pricing.settlement_rate"),
        ]

    def test_dot_not_consumed_when_followed_by_digit(self):
        # 1.5 is a decimal number, not a dot-path
        assert tokenize("1.5") == [tok("number", "1.5")]


# ---------------------------------------------------------------------------
# Whitespace
# ---------------------------------------------------------------------------

class TestWhitespace:
    def test_ignores_spaces(self):
        assert tokenize("1 + 2") == [tok("number", "1"), tok("operator", "plus"), tok("number", "2")]

    def test_ignores_tabs(self):
        assert tokenize("1\t+\t2") == [tok("number", "1"), tok("operator", "plus"), tok("number", "2")]

    def test_ignores_newlines(self):
        assert tokenize("1\n+\n2") == [tok("number", "1"), tok("operator", "plus"), tok("number", "2")]

    def test_handles_multiple_spaces(self):
        assert tokenize("SELECT    x") == [tok("keyword", "select"), tok("identifier", "x")]


# ---------------------------------------------------------------------------
# Complex expressions
# ---------------------------------------------------------------------------

class TestComplexExpressions:
    def test_simple_arithmetic(self):
        assert tokenize("SELECT (x / y)") == [
            tok("keyword", "select"),
            tok("lparen"),
            tok("identifier", "x"),
            tok("operator", "divide"),
            tok("identifier", "y"),
            tok("rparen"),
        ]

    def test_case_when_expression(self):
        tokens = tokenize("SELECT CASE WHEN category = 'A' THEN x ELSE y END")
        assert tokens == [
            tok("keyword", "select"),
            tok("keyword", "case"),
            tok("keyword", "when"),
            tok("identifier", "category"),
            tok("operator", "eq"),
            tok("string", "A"),
            tok("keyword", "then"),
            tok("identifier", "x"),
            tok("keyword", "else"),
            tok("identifier", "y"),
            tok("keyword", "end"),
        ]

    def test_function_call_with_arguments(self):
        assert tokenize("ROUND(x, 2)") == [
            tok("function", "round"),
            tok("lparen"),
            tok("identifier", "x"),
            tok("comma"),
            tok("number", "2"),
            tok("rparen"),
        ]

    def test_nested_function_calls(self):
        assert tokenize("ROUND(COALESCE(x, 0), 2)") == [
            tok("function", "round"),
            tok("lparen"),
            tok("function", "coalesce"),
            tok("lparen"),
            tok("identifier", "x"),
            tok("comma"),
            tok("number", "0"),
            tok("rparen"),
            tok("comma"),
            tok("number", "2"),
            tok("rparen"),
        ]

    def test_comparison_with_and_or(self):
        assert tokenize("category = 'A' AND x > 100") == [
            tok("identifier", "category"),
            tok("operator", "eq"),
            tok("string", "A"),
            tok("keyword", "and"),
            tok("identifier", "x"),
            tok("operator", "gt"),
            tok("number", "100"),
        ]


# ---------------------------------------------------------------------------
# IN and LIKE
# ---------------------------------------------------------------------------

class TestInAndLike:
    def test_in_keyword(self):
        assert tokenize("x IN ('a', 'b')") == [
            tok("identifier", "x"),
            tok("keyword", "in"),
            tok("lparen"),
            tok("string", "a"),
            tok("comma"),
            tok("string", "b"),
            tok("rparen"),
        ]

    def test_not_in_keywords(self):
        assert tokenize("x NOT IN (1, 2, 3)") == [
            tok("identifier", "x"),
            tok("keyword", "not"),
            tok("keyword", "in"),
            tok("lparen"),
            tok("number", "1"),
            tok("comma"),
            tok("number", "2"),
            tok("comma"),
            tok("number", "3"),
            tok("rparen"),
        ]

    def test_like_keyword(self):
        assert tokenize("name LIKE '%test%'") == [
            tok("identifier", "name"),
            tok("keyword", "like"),
            tok("string", "%test%"),
        ]

    def test_not_like_keywords(self):
        assert tokenize("name NOT LIKE '%test%'") == [
            tok("identifier", "name"),
            tok("keyword", "not"),
            tok("keyword", "like"),
            tok("string", "%test%"),
        ]

    def test_in_and_like_are_case_insensitive(self):
        assert tokenize("x in ('a')") == tokenize("x IN ('a')")
        assert tokenize("x like '%a'") == tokenize("x LIKE '%a'")


# ---------------------------------------------------------------------------
# Empty input
# ---------------------------------------------------------------------------

class TestEmptyInput:
    def test_empty_string_returns_empty_list(self):
        assert tokenize("") == []

    def test_only_whitespace_returns_empty_list(self):
        assert tokenize("   ") == []
        assert tokenize("\n\t ") == []


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------

class TestComments:
    def test_double_dash_comment_to_end_of_input(self):
        assert tokenize("x -- this is a comment") == [tok("identifier", "x")]

    def test_double_dash_comment_ends_at_newline(self):
        assert tokenize("x -- comment\n+ y") == [
            tok("identifier", "x"),
            tok("operator", "plus"),
            tok("identifier", "y"),
        ]

    def test_hash_line_comment(self):
        assert tokenize("# top comment\nx # trailing comment") == [tok("identifier", "x")]

    def test_block_comment_inline(self):
        assert tokenize("x /* inline */ + y") == [
            tok("identifier", "x"),
            tok("operator", "plus"),
            tok("identifier", "y"),
        ]

    def test_block_comment_multi_line(self):
        assert tokenize("x /*\n  multi\n  line\n*/ + y") == [
            tok("identifier", "x"),
            tok("operator", "plus"),
            tok("identifier", "y"),
        ]

    def test_unterminated_block_comment(self):
        with pytest.raises(DsqlexError, match="Unterminated block comment"):
            tokenize("x /* never closes")

    def test_comment_bodies_may_contain_non_ascii(self):
        expr = (
            "status_id NOT IN (\n"
            "  1,  -- pending review\n"
            "  2,  -- archived – soft-deleted\n"
            "  3,  -- naïve test\n"
            "  4   -- staging\n"
            ")"
        )
        tokens = tokenize(expr)
        assert tok("identifier", "status_id") in tokens
        assert tok("keyword", "not") in tokens
        assert tok("keyword", "in") in tokens
        assert tok("number", "1") in tokens
        assert tok("number", "4") in tokens
        assert tok("operator", "minus") not in tokens

    def test_minus_operator_unaffected_when_not_doubled(self):
        assert tokenize("x - y") == [
            tok("identifier", "x"),
            tok("operator", "minus"),
            tok("identifier", "y"),
        ]

    def test_divide_operator_unaffected_when_not_followed_by_star(self):
        assert tokenize("x / y") == [
            tok("identifier", "x"),
            tok("operator", "divide"),
            tok("identifier", "y"),
        ]


# ---------------------------------------------------------------------------
# Error messages
# ---------------------------------------------------------------------------

class TestErrorMessages:
    def test_non_ascii_character_returns_error(self):
        with pytest.raises(DsqlexError) as exc_info:
            tokenize("ô")
        assert "Unexpected character" in str(exc_info.value)
        assert "ô" in str(exc_info.value)

    def test_unexpected_character_message_format(self):
        with pytest.raises(DsqlexError, match=r"Unexpected character: 'ô'"):
            tokenize("ô")
