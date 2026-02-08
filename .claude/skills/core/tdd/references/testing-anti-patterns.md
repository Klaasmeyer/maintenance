# Testing Anti-Patterns

**Load this reference when:** writing or changing tests, adding mocks, or tempted to add test-only methods to production code.

## Overview

Tests must verify real behavior, not mock behavior. Mocks are a means to isolate, not the thing being tested.

**Core principle:** Test what the code does, not what the mocks do.

**Following strict TDD prevents these anti-patterns.**

## The Iron Laws

```
1. NEVER test mock behavior
2. NEVER add test-only methods to production code
3. NEVER mock without understanding dependencies
```

## Anti-Pattern 1: Testing Mock Behavior

**The violation:**
```python
# BAD: Testing that the mock exists
def test_render_page_renders_sidebar():
    mock_sidebar = "<div class='mock-sidebar'/>"
    result = render_page(mock_sidebar)
    assert "mock-sidebar" in result
```

**Why this is wrong:**
- You're verifying the mock works, not that the component works
- Test passes when mock is present, fails when it's not
- Tells you nothing about real behavior

**The fix:**
```python
# GOOD: Test real component or don't mock it
def test_render_page_renders_sidebar():
    result = render_page(real_sidebar_component)
    assert "<nav" in result
```

### Gate Function

```
BEFORE asserting on any mock element:
  Ask: "Am I testing real behavior or just mock existence?"

  IF testing mock existence:
    STOP - Delete the assertion or unmock the component

  Test real behavior instead
```

## Anti-Pattern 2: Test-Only Functions in Production

**The violation:**
```python
# BAD: destroy only used in tests
class Session:
    def create(self): ...

    def destroy(self):
        """Only exists for test cleanup."""
        self._state = None
        self._close_connections()
```

**Why this is wrong:**
- Production code polluted with test-only functions
- Dangerous if accidentally called in production
- Violates separation of concerns

**The fix:**
```python
# GOOD: Test utilities handle test cleanup
# Session has no destroy - it's stateless in production

# In tests/conftest.py
def cleanup_session(session):
    if session.connection:
        close_test_connection(session.connection)
```

### Gate Function

```
BEFORE adding any function to production module:
  Ask: "Is this only used by tests?"

  IF yes:
    STOP - Don't add it
    Put it in test utilities instead
```

## Anti-Pattern 3: Mocking Without Understanding

**The violation:**
```python
# BAD: Mock breaks test logic
def test_detect_duplicate_server():
    with patch("discover_server", return_value=None):
        add_server(config)  # Works
        add_server(config)  # Won't throw! Mock prevented config write
```

**Why this is wrong:**
- Mocked function had side effect test depended on
- Over-mocking to "be safe" breaks actual behavior
- Test passes for wrong reason or fails mysteriously

**The fix:**
```python
# GOOD: Mock at correct level
def test_detect_duplicate_server():
    with patch("start_server", return_value=ServerHandle(started=True)):
        add_server(config)  # Config written
        with pytest.raises(DuplicateServerError):
            add_server(config)
```

### Gate Function

```
BEFORE mocking any function:
  STOP - Don't mock yet

  1. Ask: "What side effects does the real function have?"
  2. Ask: "Does this test depend on any of those side effects?"
  3. Ask: "Do I fully understand what this test needs?"

  IF depends on side effects:
    Mock at lower level (the actual slow/external operation)
    NOT the high-level function the test depends on
```

## Anti-Pattern 4: Incomplete Mocks

**The violation:**
```python
# BAD: Partial mock - only fields you think you need
mock_response = Response(
    status=Status.SUCCESS,
    data=UserData(id="123", name="Alice"),
)
# Missing: metadata that downstream code uses

# Later: breaks when code accesses response.metadata.request_id
```

**Why this is wrong:**
- Partial mocks hide structural assumptions
- Downstream code may depend on fields you didn't include
- Tests pass but integration fails

**The fix:**
```python
# GOOD: Mirror real API completeness
mock_response = Response(
    status=Status.SUCCESS,
    data=UserData(id="123", name="Alice"),
    metadata=Metadata(request_id="req-789", timestamp=1234567890),
)
# All fields real API returns
```

### Gate Function

```
BEFORE creating mock data:
  Check: "What fields does the real response contain?"

  Actions:
    1. Examine actual response from docs/examples
    2. Include ALL fields system might consume downstream
    3. Verify mock matches real response schema completely
```

## Anti-Pattern 5: Integration Tests as Afterthought

**The violation:**
```
Implementation complete
No tests written
"Ready for testing"
```

**Why this is wrong:**
- Testing is part of implementation, not optional follow-up
- TDD would have caught this
- Can't claim complete without tests

**The fix:**
```
TDD cycle:
1. Write failing test
2. Implement to pass
3. Refactor
4. THEN claim complete
```

## TDD Prevents These Anti-Patterns

**Why TDD helps:**
1. **Write test first** - Forces you to think about what you're actually testing
2. **Watch it fail** - Confirms test tests real behavior, not mocks
3. **Minimal implementation** - No test-only functions creep in
4. **Real dependencies** - You see what the test actually needs before mocking

**If you're testing mock behavior, you violated TDD** - you added mocks without watching test fail against real code first.

## Quick Reference

| Anti-Pattern | Fix |
|--------------|-----|
| Assert on mock elements | Test real component or unmock it |
| Test-only functions in production | Move to test utilities |
| Mock without understanding | Understand dependencies first, mock minimally |
| Incomplete mocks | Mirror real API completely |
| Tests as afterthought | TDD - tests first |
| Over-complex mocks | Consider integration tests |

## Red Flags

- Assertion checks for mock data markers
- Functions only called in test files
- Mock setup is >50% of test
- Test fails when you remove mock
- Can't explain why mock is needed
- Mocking "just to be safe"

## The Bottom Line

**Mocks are tools to isolate, not things to test.**

If TDD reveals you're testing mock behavior, you've gone wrong.

Fix: Test real behavior or question why you're mocking at all.
