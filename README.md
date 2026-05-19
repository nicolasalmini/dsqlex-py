# dsqlex-py

A pure-Python implementation of the DSQLEX expression evaluator. Zero dependencies. Uses Python's built-in `decimal.Decimal` for arbitrary-precision arithmetic.

## Usage

```python
from dsqlex import eval, parse, evaluate_ast
from decimal import Decimal

# One-shot: parse + evaluate
result = eval("(price * quantity) + tax", {
    "price": Decimal("100.00"),
    "quantity": Decimal("5"),
    "tax": Decimal("50.00"),
})
# result = Decimal("550.00")

# Parse once, evaluate many
ast = parse("amount * rate")
for record in records:
    result = evaluate_ast(ast, record)
```

## Installation

```bash
pip install .
```

Or for development:

```bash
pip install -e ".[dev]"
```

## Running Tests

```bash
pytest
```

## Dependencies

None. Pure Python, standard library only.

## Supported Features

| Feature | Syntax |
|---------|--------|
| Arithmetic | `+`, `-`, `*`, `/` (decimal precision) |
| Comparison | `=`, `!=`, `<`, `>`, `<=`, `>=` |
| Logical | `AND`, `OR` (same-op chaining; mixing requires parens) |
| Conditionals | `CASE WHEN ... THEN ... ELSE ... END` |
| Functions | `ROUND()`, `COALESCE()`/`NVL()`, `UPPER()`, `LOWER()`, `ABS()`, `CONCAT()`, `EVENT()` |
| Membership | `IN (...)`, `NOT IN (...)` |
| Pattern | `LIKE`, `NOT LIKE` (case-insensitive) |
| Null check | `IS NULL`, `IS NOT NULL`, `IS TRUE`, `IS FALSE` |
| Literals | Numbers, strings (`'...'`), `TRUE`, `FALSE`, `NULL` |
| Dot-paths | `config.pricing.margin` (nested context access) |
| Comments | `--`, `#`, `/* ... */` |

## API

```python
from dsqlex import tokenize, parse, evaluate_ast, eval

# Tokenize expression into token list
tokens = tokenize("price * quantity")

# Parse expression into AST
ast = parse("price * quantity")

# Evaluate a pre-parsed AST with context
result = evaluate_ast(ast, {"price": Decimal("10"), "quantity": Decimal("5")})

# Parse and evaluate in one call
result = eval("price * quantity", {"price": Decimal("10"), "quantity": Decimal("5")})
```

### Options

```python
# Custom field resolver
def my_resolver(name, visited):
    return some_external_lookup(name)

result = eval("amount * external_rate", context, resolver=my_resolver)

# Event resolver for cross-event references
def my_event_resolver(type, subtype, ctx, opts):
    return lookup_event(type, subtype, ctx)

result = eval("EVENT('pricing', 'base')", context, event_resolver=my_event_resolver)
```

## Design Decisions

- **Pure Python**: No C extensions, no FFI. Runs anywhere Python runs.
- **`decimal.Decimal`**: Arbitrary-precision arithmetic. No floating-point surprises.
- **Frozen dataclass AST**: Immutable nodes, safe to share and cache.
- **Explicit parentheses**: `a + b * c` is rejected. Use `(a + b) * c`.

## Related

- [dsqlex-c](https://github.com/nicolasalmini/dsqlex-c) — C/C++ implementation (mpdecimal)
- [dsqlex-rs](https://github.com/nicolasalmini/dsqlex-rs) — Rust implementation (rust_decimal)
- [dsqlex-go](https://github.com/nicolasalmini/dsqlex-go) — Go implementation (govalues/decimal)
- [dsqlex-ts](https://github.com/nicolasalmini/dsqlex-ts) — TypeScript implementation
- [dsqlex-bench](https://github.com/nicolasalmini/dsqlex-bench) — Cross-language benchmark suite
