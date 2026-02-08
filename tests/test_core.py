"""Tests for the core module."""

from starter.core import greet


def test_greet_returns_greeting_with_name():
    """Test that greet returns a properly formatted greeting."""
    assert greet("World") == "Hello, World!"


def test_greet_with_different_name():
    """Test that greet works with different names."""
    assert greet("Alice") == "Hello, Alice!"


def test_greet_with_empty_string():
    """Test that greet handles empty string."""
    assert greet("") == "Hello, !"
