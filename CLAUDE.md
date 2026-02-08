# Claude Code Starter - Agent Instructions

## Prime Directive

**Always grow complexity from a simple system that already works.**

- **Modularity**: Simple parts, clean interfaces
- **Clarity**: Clarity over cleverness
- **Composition**: Design parts to connect with other parts
- **Simplicity**: Add complexity only where you must

In practice:
- Prefer minimal working slices over grand designs
- Avoid speculative architecture and premature abstraction
- Make only small, verifiable changes
- Push back when requests ignore this: *Begin -> Learn -> Succeed -> then add complexity*

---

## Role

**You are an orchestrator, not an implementer.**

At session start, activate the `orchestrator` skill. It establishes:
- Delegation thresholds (when to use subagents)
- Subagent launch templates
- Token efficiency rules
- Parallel safety constraints
- File ownership boundaries

If you are a **subagent** (delegated by an orchestrator), activate `subagent` instead.

---

## Beads

Use [beads](https://github.com/steveyegge/beads) (`bd` CLI) for persistent issue tracking across sessions.

**Setup**: Hooks auto-inject `bd prime` at session start when `.beads/` detected.
**Recovery**: Run `bd prime` after compaction or `/clear` to restore workflow context.
**Quick ref**: `bd ready` (find work), `bd close <id>` (complete), `bd sync` (session end).

### Landing the Plane (Session Completion)

**When ending a work session**, you MUST complete ALL steps below.

**MANDATORY WORKFLOW:**

1. **File issues for remaining work** - Create issues for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **Verify** - All changes committed
5. **Hand off** - Provide context for next session

---

## Language Configuration

This project uses **Python** exclusively.

**Quality gates:**
```bash
make test        # Run pytest
make lint        # Run ruff + mypy
```

**Language-specific skills** are in `.claude/skills/languages/python-pro/`.

---

## Skills Reference

Skills are in `.claude/skills/`. Core skills (language-agnostic):

| Skill | When to Use |
|-------|-------------|
| **orchestrator** | Session start (primary Claude) |
| **subagent** | When delegated |
| **tdd** | Before writing any feature/fix |
| **debugging** | When encountering bugs |
| **brainstorming** | Before creative/design work |
| **dialectical-refinement** | For complex specs |
| **worktrees** | For isolated workspaces |

Language-specific skill: **python-pro** - activated for all code tasks.

---

## Skills & Tools

You have MCPs, skills, and bash tools. Use them. Ensure subagents know about relevant skills when delegating.

---

# Python Language Module

## Setup Requirements

- **Python**: 3.11+ (`python --version`)
- **Package Manager**: uv (preferred), poetry, or pip
- **Virtual Environment**: Managed by uv or venv

### Quick Start with uv

```bash
# Install uv (if not installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Setup project
make setup
```

---

## Quality Gates

Before commit:
```bash
make test
```

Or directly:
```bash
uv run pytest
```

All tests must pass. Type checking should be clean:
```bash
uv run mypy src/
```

---

## Code Evaluation

Claude Code uses one-shot evaluation:
```bash
python -c "print(1 + 2)"
python -c "import json; print(json.dumps({'a': 1}))"
python -c "from pathlib import Path; print(list(Path('.').glob('*.py')))"
```

NOT interactive REPL sessions.

---

## Skills Reference

| Skill | When to Use |
|-------|-------------|
| **python-pro** | Any Python code work |
| **tdd** | Before writing any feature/fix |
| **debugging** | When encountering bugs |

---

## Project Structure

```
project/
├── src/
│   └── starter/
│       ├── __init__.py
│       ├── __main__.py
│       └── core.py
├── tests/
│   └── test_core.py
├── pyproject.toml
└── Makefile
```

---

## Common Patterns

### Type Hints
```python
def process(items: list[str]) -> dict[str, int]:
    return {item: len(item) for item in items}
```

### Dataclasses
```python
from dataclasses import dataclass

@dataclass
class User:
    name: str
    email: str
```

### Context Managers
```python
from contextlib import contextmanager

@contextmanager
def managed_resource():
    resource = acquire()
    try:
        yield resource
    finally:
        release(resource)
```

---

## Testing

Use pytest with clear, descriptive test names:
```python
def test_greet_returns_greeting_with_name():
    assert greet("World") == "Hello, World!"
```

Run specific tests:
```bash
uv run pytest tests/test_core.py -v
uv run pytest -k "test_greet"
```
