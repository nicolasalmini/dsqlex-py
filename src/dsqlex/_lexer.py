from ._errors import DsqlexError
from ._tokens import Token

# Maps uppercase word → (token_type, token_value)
_WORD_MAP: dict[str, tuple[str, str]] = {
    "SELECT":   ("keyword",  "select"),
    "CASE":     ("keyword",  "case"),
    "WHEN":     ("keyword",  "when"),
    "THEN":     ("keyword",  "then"),
    "ELSE":     ("keyword",  "else"),
    "END":      ("keyword",  "end"),
    "AND":      ("keyword",  "and"),
    "OR":       ("keyword",  "or"),
    "NOT":      ("keyword",  "not"),
    "NULL":     ("keyword",  "null"),
    "TRUE":     ("keyword",  "true"),
    "FALSE":    ("keyword",  "false"),
    "IS":       ("keyword",  "is"),
    "IN":       ("keyword",  "in"),
    "LIKE":     ("keyword",  "like"),
    "UPPER":    ("function", "upper"),
    "LOWER":    ("function", "lower"),
    "ROUND":    ("function", "round"),
    "COALESCE": ("function", "coalesce"),
    "NVL":      ("function", "coalesce"),  # alias
    "ABS":      ("function", "abs"),
    "CONCAT":   ("function", "concat"),
    "LEAST":    ("function", "least"),
    "GREATEST": ("function", "greatest"),
    "EVENT":    ("function", "event"),
}

_SINGLE_OPS: dict[str, str] = {
    "+": "plus",
    "-": "minus",
    "*": "multiply",
    "/": "divide",
    "=": "eq",
    "<": "lt",
    ">": "gt",
}


def tokenize(expr: str) -> list[Token]:
    tokens: list[Token] = []
    i = 0
    n = len(expr)

    while i < n:
        c = expr[i]

        # --- whitespace ---
        if c in " \t\n\r":
            i += 1
            continue

        # --- comma ---
        if c == ",":
            tokens.append(Token("comma"))
            i += 1
            continue

        # --- single-quoted string ---
        if c == "'":
            i += 1
            start = i
            while i < n and expr[i] != "'":
                i += 1
            if i >= n:
                raise DsqlexError("Unterminated string")
            tokens.append(Token("string", expr[start:i]))
            i += 1  # skip closing quote
            continue

        # --- parentheses ---
        if c == "(":
            tokens.append(Token("lparen"))
            i += 1
            continue
        if c == ")":
            tokens.append(Token("rparen"))
            i += 1
            continue

        # --- number literal (starts with a digit) ---
        if c.isdigit():
            start = i
            while i < n and expr[i].isdigit():
                i += 1
            # optional decimal portion: '.' followed by at least one digit
            if i + 1 < n and expr[i] == "." and expr[i + 1].isdigit():
                i += 1  # consume '.'
                while i < n and expr[i].isdigit():
                    i += 1
            tokens.append(Token("number", expr[start:i]))
            continue

        # --- identifier / keyword / function (ASCII letters and underscore only) ---
        if c.isascii() and (c.isalpha() or c == "_"):
            start = i
            while i < n and expr[i].isascii() and (expr[i].isalnum() or expr[i] == "_"):
                i += 1
            # dot-path: consume '.' only when followed by an ASCII letter or '_'
            while (i + 1 < n and expr[i] == "."
                   and expr[i + 1].isascii()
                   and (expr[i + 1].isalpha() or expr[i + 1] == "_")):
                i += 1  # consume '.'
                while i < n and expr[i].isascii() and (expr[i].isalnum() or expr[i] == "_"):
                    i += 1
            if i < n and expr[i] == "?":
                i += 1
            word = expr[start:i]
            upper = word.upper()
            # Keywords and functions are only matched on plain words (no dots)
            if "." not in word and upper in _WORD_MAP:
                ttype, tval = _WORD_MAP[upper]
                tokens.append(Token(ttype, tval))
            else:
                tokens.append(Token("identifier", word))
            continue

        # --- SQL line comment: -- … <newline or EOF> ---
        if expr[i : i + 2] == "--":
            while i < n and expr[i] != "\n":
                i += 1
            continue

        # --- MySQL-style line comment: # … <newline or EOF> ---
        if c == "#":
            while i < n and expr[i] != "\n":
                i += 1
            continue

        # --- block comment: /* … */ ---
        if expr[i : i + 2] == "/*":
            i += 2
            closed = False
            while i < n:
                if expr[i : i + 2] == "*/":
                    i += 2
                    closed = True
                    break
                i += 1
            if not closed:
                raise DsqlexError("Unterminated block comment")
            continue

        # --- multi-character operators (checked before single-char) ---
        if expr[i : i + 2] == "!=":
            tokens.append(Token("operator", "neq"))
            i += 2
            continue
        if expr[i : i + 2] == "<=":
            tokens.append(Token("operator", "lte"))
            i += 2
            continue
        if expr[i : i + 2] == ">=":
            tokens.append(Token("operator", "gte"))
            i += 2
            continue

        # --- single-character operators ---
        if c in _SINGLE_OPS:
            tokens.append(Token("operator", _SINGLE_OPS[c]))
            i += 1
            continue

        # --- unexpected character ---
        raise DsqlexError(f"Unexpected character: '{c}'")

    return tokens
