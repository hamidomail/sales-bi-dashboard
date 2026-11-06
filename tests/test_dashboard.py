"""Run after building the warehouse:  pytest -q"""
from datetime import date

import pytest
from streamlit.testing.v1 import AppTest

from dashboard.queries import Filters, Warehouse


@pytest.fixture(scope="module")
def wh():
    return Warehouse()


def test_breakdowns_add_up_to_the_kpi(wh):
    f = Filters(date(2025, 11, 1), date(2026, 10, 31))
    total = wh.kpis(f)["revenue"]
    for dim in ("category", "region", "channel"):
        assert wh.revenue_by(f, dim)["revenue"].astype(float).sum() == pytest.approx(total, rel=1e-9)


def test_filters_narrow_the_numbers(wh):
    full = Filters(date(2025, 11, 1), date(2026, 10, 31))
    one = Filters(full.start, full.end, regions=("Western Europe",), categories=("Lighting",))
    assert 0 < wh.kpis(one)["revenue"] < wh.kpis(full)["revenue"]
    assert set(wh.revenue_by(one, "category")["label"]) == {"Lighting"}


def test_previous_period_has_same_length():
    f = Filters(date(2026, 4, 1), date(2026, 6, 30))
    p = f.previous()
    assert (p.end - p.start) == (f.end - f.start) and p.end < f.start


def test_marketing_economics_are_sane(wh):
    econ = wh.channel_economics(Filters(date(2025, 11, 1), date(2026, 10, 31)))
    paid = econ[econ["spend"] > 0]
    assert set(paid["channel"]) == {"Paid search", "Social ads", "Marketplace"}
    assert (paid["cac"] > 0).all() and (paid["roas"] > 0).all()


def test_cohort_retention_is_a_share(wh):
    r = wh.cohort_retention(Filters(date(2025, 1, 1), date(2025, 12, 31)))
    assert not r.empty and r["retention"].between(0, 1).all()


@pytest.mark.parametrize("period", ["Last 12 months", "Last 90 days", "Year to date", "Last full quarter", "All time"])
def test_app_renders_without_errors(period):
    at = AppTest.from_file("../app.py", default_timeout=60).run()
    at.selectbox[0].select(period).run()
    assert not at.exception
    assert len(at.metric) == 6


def test_app_with_dimension_filters():
    at = AppTest.from_file("../app.py", default_timeout=60).run()
    at.multiselect[0].select("Southern Europe").run()
    at.multiselect[2].select("Outdoor").run()
    assert not at.exception
