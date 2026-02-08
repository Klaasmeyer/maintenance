"""Tests for geocode query construction logic."""

import sys
from pathlib import Path

# geocode-routes.py isn't a package; add parent dir so we can import it.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from importlib import import_module

# Module name contains a hyphen, so use importlib.
geocode_routes = import_module("geocode-routes")
build_geocode_query = geocode_routes.build_geocode_query


def test_intersection_with_both_roads():
    """Both street and intersection populated → combined query."""
    result = build_geocode_query(
        street="TX 302", intersection="FM 1232", is_intersection=True
    )
    assert result == "TX 302 and FM 1232"


def test_intersection_only_intersection_populated():
    """Only intersection populated, street empty → just intersection."""
    result = build_geocode_query(
        street="", intersection="FM 1232", is_intersection=True
    )
    assert result == "FM 1232"


def test_intersection_street_none():
    """Street is None with intersection → just intersection."""
    result = build_geocode_query(
        street=None, intersection="FM 1232", is_intersection=True
    )
    assert result == "FM 1232"


def test_not_intersection_uses_street():
    """Non-intersection record → uses street."""
    result = build_geocode_query(
        street="Main St", intersection="", is_intersection=False
    )
    assert result == "Main St"


def test_not_intersection_ignores_intersection_field():
    """Non-intersection record ignores intersection even if populated."""
    result = build_geocode_query(
        street="Main St", intersection="FM 1232", is_intersection=False
    )
    assert result == "Main St"
