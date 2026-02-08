---
name: python-pro
description: Expert Python developer specializing in type hints, modern Python patterns, and testing. Use PROACTIVELY when working on any Python code.
---

# Python Pro

Expert Python development with type hints and modern patterns.

## Type Hints

### Basic Types

```python
def process(name: str, count: int, active: bool) -> str:
    return f"{name}: {count}"
```

### Collections

```python
def summarize(items: list[str], counts: dict[str, int]) -> set[str]:
    return {item for item in items if counts.get(item, 0) > 0}
```

### Optional and Union

```python
def find(key: str) -> str | None:
    return data.get(key)

def parse(value: str | int) -> str:
    return str(value)
```

### Generics

```python
from typing import TypeVar, Generic

T = TypeVar("T")

def first(items: list[T]) -> T | None:
    return items[0] if items else None

class Stack(Generic[T]):
    def __init__(self) -> None:
        self._items: list[T] = []

    def push(self, item: T) -> None:
        self._items.append(item)
```

## Dataclasses

```python
from dataclasses import dataclass, field

@dataclass
class User:
    name: str
    email: str
    age: int = 0
    tags: list[str] = field(default_factory=list)

# Frozen (immutable)
@dataclass(frozen=True)
class Point:
    x: float
    y: float
```

## Context Managers

```python
from contextlib import contextmanager

@contextmanager
def timer(label: str):
    import time
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - start
        print(f"{label}: {elapsed:.3f}s")

# Usage
with timer("processing"):
    process_data()
```

## Async/Await

```python
import asyncio

async def fetch_data(url: str) -> str:
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.text()

async def fetch_all(urls: list[str]) -> list[str]:
    return await asyncio.gather(*[fetch_data(url) for url in urls])
```

## Comprehensions

```python
# List
squares = [x * x for x in range(10)]
evens = [x for x in numbers if x % 2 == 0]

# Dict
word_lengths = {word: len(word) for word in words}

# Set
unique_lengths = {len(word) for word in words}
```

## Error Handling

```python
class ValidationError(Exception):
    def __init__(self, field: str, message: str) -> None:
        self.field = field
        self.message = message
        super().__init__(f"{field}: {message}")

try:
    result = risky_operation()
except ValueError as e:
    logger.error(f"Invalid value: {e}")
    raise
```

## Testing with pytest

```python
def test_greet():
    assert greet("World") == "Hello, World!"

# Fixtures
@pytest.fixture
def sample_user():
    return User(name="Alice", email="alice@example.com")

def test_user(sample_user):
    assert sample_user.name == "Alice"

# Parametrized
@pytest.mark.parametrize("input,expected", [
    ("hello", "HELLO"),
    ("World", "WORLD"),
])
def test_uppercase(input, expected):
    assert input.upper() == expected
```

## Code Evaluation

One-shot evaluation:

```bash
python -c "print(1 + 2)"
python -c "import json; print(json.dumps({'key': 'value'}))"
```

NOT interactive REPL sessions.

## Quality Gates

Before commit:
```bash
uv run pytest
uv run mypy src/
uv run ruff check src/
```

## Idiomatic Python Checklist

- [ ] Use type hints everywhere
- [ ] Prefer dataclasses for data containers
- [ ] Use context managers for resources
- [ ] Write small, focused functions
- [ ] Use comprehensions for simple transforms
- [ ] Handle exceptions at appropriate levels

## Related Skills

- **tdd** - Test-driven development
- **debugging** - Systematic bug investigation
