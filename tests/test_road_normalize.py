"""Tests for road name normalization."""

import sys
from pathlib import Path

# geocode-routes.py isn't a package; add parent dir so we can import it.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from importlib import import_module

geocode_routes = import_module("geocode-routes")
normalize_road_name = geocode_routes.normalize_road_name
make_geo_key = geocode_routes.make_geo_key


# ---------------------------------------------------------------------------
# normalize_road_name() unit tests
# ---------------------------------------------------------------------------


class TestNormalizeRoadName:
    """Test normalize_road_name() in isolation."""

    def test_county_road(self):
        assert normalize_road_name("county road 201") == "cr 201"

    def test_county_rd(self):
        assert normalize_road_name("county rd 201") == "cr 201"

    def test_co_rd(self):
        assert normalize_road_name("co rd 201") == "cr 201"

    def test_farm_to_market_rd(self):
        assert normalize_road_name("farm to market rd 1788") == "fm 1788"

    def test_farm_to_market_road(self):
        assert normalize_road_name("farm to market road 1788") == "fm 1788"

    def test_farm_to_market_bare(self):
        assert normalize_road_name("farm to market 1788") == "fm 1788"

    def test_ranch_to_market_rd(self):
        assert normalize_road_name("ranch to market rd 652") == "rm 652"

    def test_ranch_road(self):
        assert normalize_road_name("ranch road 652") == "rm 652"

    def test_tx_dash_separator(self):
        assert normalize_road_name("tx-115") == "tx 115"

    def test_tx_double_space(self):
        assert normalize_road_name("tx  115") == "tx 115"

    def test_tx_dash_space(self):
        assert normalize_road_name("tx- 115") == "tx 115"

    def test_interstate(self):
        assert normalize_road_name("interstate 20") == "i-20"

    def test_ih_dash(self):
        assert normalize_road_name("ih-20") == "i-20"

    def test_ih_bare(self):
        assert normalize_road_name("ih 20") == "i-20"

    def test_i_space(self):
        assert normalize_road_name("i 20") == "i-20"

    def test_i_dash_space(self):
        assert normalize_road_name("i- 20") == "i-20"

    def test_state_highway(self):
        assert normalize_road_name("state highway 302") == "sh 302"

    def test_state_hwy(self):
        assert normalize_road_name("state hwy 302") == "sh 302"

    def test_st_hwy(self):
        assert normalize_road_name("st hwy 302") == "sh 302"

    def test_highway_becomes_hwy(self):
        assert normalize_road_name("highway 176") == "hwy 176"

    def test_texas_becomes_tx(self):
        assert normalize_road_name("texas 115") == "tx 115"

    def test_business_becomes_bus(self):
        assert normalize_road_name("business 20") == "bus 20"

    def test_park_road(self):
        assert normalize_road_name("park road 4") == "pr 4"

    def test_trailing_rd_stripped(self):
        assert normalize_road_name("ne 100 rd") == "ne 100"

    def test_trailing_road_stripped(self):
        assert normalize_road_name("ne 100 road") == "ne 100"

    def test_us_hwy_no_change(self):
        """Compound prefix 'us hwy' is left alone (ambiguous)."""
        assert normalize_road_name("us hwy 385") == "us hwy 385"

    def test_main_st_no_change(self):
        """Regular street name is left alone."""
        assert normalize_road_name("main st") == "main st"

    def test_empty_string(self):
        assert normalize_road_name("") == ""

    def test_fm_dash_separator(self):
        assert normalize_road_name("fm-1788") == "fm 1788"


# ---------------------------------------------------------------------------
# make_geo_key() equivalence tests
# ---------------------------------------------------------------------------


class TestMakeGeoKeyEquivalence:
    """Verify that known road-name variants produce the same cache key."""

    def test_tx_dash_vs_tx_space(self):
        k1 = make_geo_key("Andrews", "Andrews", "TX-115", "FM 1788", True)
        k2 = make_geo_key("Andrews", "Andrews", "tx 115", "fm 1788", True)
        assert k1 == k2

    def test_state_highway_vs_sh(self):
        k1 = make_geo_key("Ector", "Odessa", "State Highway 302", "", False)
        k2 = make_geo_key("Ector", "Odessa", "SH 302", "", False)
        assert k1 == k2

    def test_county_road_vs_cr(self):
        k1 = make_geo_key("Ward", "Monahans", "County Road 201", "", False)
        k2 = make_geo_key("Ward", "Monahans", "CR 201", "", False)
        assert k1 == k2

    def test_interstate_variants(self):
        k1 = make_geo_key("Midland", "Midland", "Interstate 20", "", False)
        k2 = make_geo_key("Midland", "Midland", "IH-20", "", False)
        k3 = make_geo_key("Midland", "Midland", "I 20", "", False)
        assert k1 == k2 == k3

    def test_farm_to_market_vs_fm(self):
        k1 = make_geo_key("Andrews", "Andrews", "", "Farm to Market Rd 1788", True)
        k2 = make_geo_key("Andrews", "Andrews", "", "FM 1788", True)
        assert k1 == k2

    def test_highway_vs_hwy(self):
        k1 = make_geo_key("Ector", "Odessa", "Highway 176", "", False)
        k2 = make_geo_key("Ector", "Odessa", "Hwy 176", "", False)
        assert k1 == k2
