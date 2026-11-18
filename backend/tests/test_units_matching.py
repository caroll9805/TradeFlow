from decimal import Decimal

import pytest

from app.services.matching import find_matches
from app.services.text import normalize_text
from app.services.units import UnitConversionError, conversion_factor, resolve_unit


def test_dimension_conversions(db, f):
    assert conversion_factor(db, f.unit("t"), f.unit("kg")) == Decimal(1000)
    assert conversion_factor(db, f.unit("g"), f.unit("kg")) == Decimal("0.001")
    assert conversion_factor(db, f.unit("ml"), f.unit("l")) == Decimal("0.001")
    assert conversion_factor(db, f.unit("m3"), f.unit("l")) == Decimal(1000)


def test_incompatible_units_rejected(db, f):
    with pytest.raises(UnitConversionError):
        conversion_factor(db, f.unit("kg"), f.unit("l"))
    with pytest.raises(UnitConversionError):
        conversion_factor(db, f.unit("bag"), f.unit("kg"))  # package unit without product conversion
    with pytest.raises(UnitConversionError):
        conversion_factor(db, f.unit("piece"), f.unit("m"))


def test_product_specific_conversion_and_chaining(db, f):
    p = f.product("Cement M400", bag_kg=50)
    assert conversion_factor(db, f.unit("bag"), f.unit("kg"), p.id) == Decimal(50)
    assert conversion_factor(db, f.unit("kg"), f.unit("bag"), p.id) == Decimal("0.02")
    # bag -> kg (product) -> t (dimension)
    assert conversion_factor(db, f.unit("bag"), f.unit("t"), p.id) == Decimal("0.05")


def test_resolve_unit_aliases(db):
    assert resolve_unit(db, "кг").code == "kg"
    assert resolve_unit(db, "Dona").code == "piece"
    assert resolve_unit(db, "мешок").code == "bag"
    assert resolve_unit(db, "parsec") is None


def test_normalize_text():
    assert normalize_text("Цемент  М400, 50 кг") == "tsement m400 50kg"
    assert normalize_text("Copper 2,5 mm") == "copper 2.5mm"
    assert normalize_text("Sement M-400 50 kg") == "sement m 400 50kg"
    assert normalize_text("Ўзбек шакар") == "ozbek shakar"
    assert normalize_text(None) == ""


def test_matching_barcode_exact_and_fuzzy(db, f):
    a = f.product("Portland cement M400 50kg", barcode="4780000000017", terms=["sement m400"])
    f.product("Portland cement M500 50kg")
    f.product("Granulated sugar", cat="food")
    m = find_matches(db, "anything", barcode="4780000000017")
    assert m[0].product.id == a.id and m[0].score == 1.0 and m[0].method == "barcode"
    m = find_matches(db, "Portland cement M400 50 kg")
    assert m[0].product.id == a.id and m[0].score >= 0.95
    m = find_matches(db, "cement M400 portland bag")
    assert m and m[0].product.id == a.id
    assert 0.3 < m[0].score < 0.95  # uncertain -> would go to review, not auto-merged
    assert not [x for x in find_matches(db, "Laptop 15 inch") if x.score > 0.6]
