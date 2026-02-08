# Python Makefile - Standard targets for Claude Code starter

.PHONY: setup build test run lint clean help

# Default target
help:
	@echo "Available targets:"
	@echo "  setup  - Create venv and install dependencies with uv"
	@echo "  build  - Build package (if applicable)"
	@echo "  test   - Run pytest"
	@echo "  run    - Run application"
	@echo "  lint   - Run ruff and mypy"
	@echo "  clean  - Remove build artifacts and caches"

# Setup virtual environment and install dependencies
setup:
	@echo "Setting up Python environment..."
	uv venv
	uv pip install -e ".[dev]"
	@echo "Setup complete. Activate with: source .venv/bin/activate"

# Build package
build:
	@echo "Building package..."
	uv build

# Run tests
test:
	uv run pytest

# Run tests with verbose output
test-verbose:
	uv run pytest -v

# Run tests with coverage
test-coverage:
	uv run pytest --cov=src --cov-report=term-missing

# Run application
run:
	uv run python -m starter

# Run linters
lint:
	uv run ruff check src/ tests/
	uv run ruff format --check src/ tests/
	uv run mypy src/

# Fix lint issues automatically
lint-fix:
	uv run ruff check --fix src/ tests/
	uv run ruff format src/ tests/

# Type checking only
typecheck:
	uv run mypy src/

# Clean build artifacts
clean:
	rm -rf __pycache__
	rm -rf .pytest_cache
	rm -rf .mypy_cache
	rm -rf .ruff_cache
	rm -rf .venv
	rm -rf dist
	rm -rf build
	rm -rf *.egg-info
	rm -rf src/*.egg-info
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	@echo "Cleaned build artifacts"
