"""Geo gazetteer tests — commuter scope around Beer Sheva."""

from arch_job_bot.matching.geo import classify_location, passes_geo


def test_commuter_towns_match():
    assert classify_location("המשרה בבאר שבע").city == "באר שבע"
    assert classify_location("עבודה באופקים").city == "אופקים"
    assert classify_location("מיקום: קריית גת").city == "קריית גת"
    assert classify_location("ב\"ש מרכז").city == "באר שבע"


def test_excluded_cities():
    g = classify_location("המשרה בתל אביב")
    assert g.city is None
    assert g.excluded_city is not None


def test_strict_general_board_requires_signal():
    # general board: no in-scope signal → drop
    ok, _ = passes_geo("דרוש אדריכל ללא ציון מיקום", arch_only_source=False)
    assert ok is False
    ok, _ = passes_geo("דרוש אדריכל בבאר שבע", arch_only_source=False)
    assert ok is True


def test_arch_only_source_keeps_unless_excluded():
    # arch-only/geo-trusted: keep even without a signal...
    ok, _ = passes_geo("דרוש אדריכל ללא ציון מיקום", arch_only_source=True)
    assert ok is True
    # ...but drop when a non-commuter city is explicitly named
    ok, _ = passes_geo("דרוש אדריכל בתל אביב", arch_only_source=True)
    assert ok is False


def test_remote_in_scope():
    ok, res = passes_geo("דרוש אדריכל לעבודה מהבית / היברידי", arch_only_source=False)
    assert ok is True
    assert res.remote is True


def test_region_word_in_scope():
    ok, _ = passes_geo("דרוש אדריכל באזור הדרום", arch_only_source=False)
    assert ok is True
