"""Entry point for running the starter package as a module."""

from starter.core import greet


def main() -> None:
    """Run the main application."""
    print(greet("World"))


if __name__ == "__main__":
    main()
