"""Tests for purge_stale_cache module."""

import sys
from pathlib import Path

# Allow importing from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from purge_stale_cache import is_geocode_ok, is_new_format, purge_cache


def _old_format_entry():
    return {
        "geo_key": "SE 8000 RD|Farm to Market Road 1788|ANDREWS|ANDREWS",
        "norm_street": "SE 8000 RD",
        "norm_intersection": "Farm to Market Road 1788",
        "city": "ANDREWS",
        "county": "ANDREWS",
        "lat": None,
        "lon": None,
        "status": "REQUEST_DENIED",
        "strategy": None,
    }


def _new_format_ok():
    return {
        "geo_key": "andrews|andrews17|intersection|ne 100|tx-176",
        "county": "ANDREWS",
        "city": "ANDREWS17",
        "street": "NE 100",
        "intersection": "TX-176",
        "is_intersection": True,
        "raw_line": "TX-176",
        "normalized_line": "TX-176",
        "validation": {
            "status": "ok",
            "raw_address": "TX-176",
            "validated_address": "TX-176",
        },
        "geocode": {
            "status": "OK",
            "lat": 32.32,
            "lng": -102.28,
            "formatted_address": "TX-176, Texas, USA",
            "place_id": "abc",
        },
    }


def _new_format_zero_results():
    return {
        "geo_key": "winkler|wink|intersection|cr 999|cr 888",
        "county": "WINKLER",
        "city": "WINK",
        "street": "CR 999",
        "intersection": "CR 888",
        "is_intersection": True,
        "raw_line": "CR 888",
        "normalized_line": "CR 888",
        "validation": {
            "status": "ok",
            "raw_address": "CR 888",
            "validated_address": "CR 888",
        },
        "geocode": {
            "status": "ZERO_RESULTS",
            "lat": None,
            "lng": None,
            "formatted_address": "",
            "place_id": "",
        },
    }


def _new_format_exception():
    return {
        "geo_key": "ward|monahans|intersection|i-20|hwy 18",
        "county": "WARD",
        "city": "MONAHANS",
        "street": "I-20",
        "intersection": "HWY 18",
        "is_intersection": True,
        "raw_line": "HWY 18",
        "normalized_line": "HWY 18",
        "validation": {
            "status": "error",
            "raw_address": "HWY 18",
            "validated_address": "HWY 18",
        },
        "geocode": {
            "status": "exception",
            "lat": None,
            "lng": None,
            "formatted_address": "",
            "place_id": "",
        },
    }


def test_is_new_format_detects_old():
    assert is_new_format(_old_format_entry()) is False


def test_is_new_format_detects_new():
    assert is_new_format(_new_format_ok()) is True


def test_is_geocode_ok_true_for_ok():
    assert is_geocode_ok(_new_format_ok()) is True


def test_is_geocode_ok_false_for_old_format():
    assert is_geocode_ok(_old_format_entry()) is False


def test_is_geocode_ok_false_for_zero_results():
    assert is_geocode_ok(_new_format_zero_results()) is False


def test_is_geocode_ok_false_for_exception():
    assert is_geocode_ok(_new_format_exception()) is False


def test_purge_cache_keeps_only_ok():
    cache = {
        "old_key": _old_format_entry(),
        "ok_key": _new_format_ok(),
        "zero_key": _new_format_zero_results(),
        "exc_key": _new_format_exception(),
    }
    result = purge_cache(cache)
    assert list(result.keys()) == ["ok_key"]
    assert result["ok_key"]["geocode"]["status"] == "OK"


def test_purge_cache_empty_input():
    assert purge_cache({}) == {}
