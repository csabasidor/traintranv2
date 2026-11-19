"""
Unit tests for the LAU name-matching fallback in enrichment.py.

These only exercise the pure decision helpers (_name_score, _name_contains,
_best_lau_match), which take plain dicts/strings — no geopandas, shapefile,
or Excel I/O — so they cover the Rožňava/Brzotín boundary-mismatch scenario
and the legitimate Bad Schandau suffix-mismatch scenario without needing
real spatial data.
"""

from traintranv2.nb01b_stations import _best_lau_match, _name_contains, _name_score

THRESHOLD = 0.6


def test_boundary_mismatch_is_overridden_by_nearby_candidate():
    # Station "Rožňava"'s point falls inside neighbouring Brzotín's polygon.
    name_by_gisco = {
        "SK_BRZOTIN": "Brzotín",
        "SK_ROZNAVA": "Rožňava",
    }
    gisco_id, overridden, method, score = _best_lau_match(
        "Rožňava", "SK_BRZOTIN", ["SK_BRZOTIN", "SK_ROZNAVA"],
        name_by_gisco, THRESHOLD,
    )
    assert overridden is True
    assert gisco_id == "SK_ROZNAVA"
    assert method == "contains_neighbor"
    assert score == 1.0


def test_legitimate_suffix_mismatch_is_kept():
    # "Bad Schandau" is literally contained in "Bad Schandau, Stadt", so the
    # primary match is kept even though a nearby candidate with an
    # exact-looking name is present.
    name_by_gisco = {
        "DE_BAD_SCHANDAU": "Bad Schandau, Stadt",
        "DE_OTHER_VILLAGE": "Sonstige Ortschaft",
    }
    gisco_id, overridden, method, score = _best_lau_match(
        "Bad Schandau", "DE_BAD_SCHANDAU",
        ["DE_BAD_SCHANDAU", "DE_OTHER_VILLAGE"],
        name_by_gisco, THRESHOLD,
    )
    assert overridden is False
    assert gisco_id == "DE_BAD_SCHANDAU"
    assert method == "contains_primary"


def test_mismatch_with_no_good_candidate_is_kept_unresolved():
    # Primary is a poor match and none of the nearby candidates are any
    # better -> keep the primary rather than guessing.
    name_by_gisco = {
        "SK_BRZOTIN": "Brzotín",
        "SK_SOMEWHERE_ELSE": "Somewhere Else",
    }
    gisco_id, overridden, method, score = _best_lau_match(
        "Rožňava", "SK_BRZOTIN", ["SK_BRZOTIN", "SK_SOMEWHERE_ELSE"],
        name_by_gisco, THRESHOLD,
    )
    assert overridden is False
    assert gisco_id == "SK_BRZOTIN"
    assert method == "unresolved"


def test_candidate_must_beat_threshold_not_just_primary():
    # A candidate that scores higher than the primary but still below
    # threshold must not win.
    name_by_gisco = {
        "SK_BRZOTIN": "Brzotín",
        "SK_ROZNAVICE": "Rožnavice",  # a different, similarly-named village
    }
    gisco_id, overridden, method, score = _best_lau_match(
        "Rimavska Sobota", "SK_BRZOTIN", ["SK_BRZOTIN", "SK_ROZNAVICE"],
        name_by_gisco, THRESHOLD,
    )
    assert overridden is False
    assert gisco_id == "SK_BRZOTIN"
    assert method == "unresolved"


def test_missing_primary_can_still_be_resolved_by_a_candidate():
    # Stop fell entirely outside all DGURBA polygons (primary_gisco_id=None)
    # but a nearby polygon's name matches well -> resolve to it.
    name_by_gisco = {"SK_ROZNAVA": "Rožňava"}
    gisco_id, overridden, method, score = _best_lau_match(
        "Rožňava", None, ["SK_ROZNAVA"], name_by_gisco, THRESHOLD,
    )
    assert overridden is True
    assert gisco_id == "SK_ROZNAVA"
    assert method == "contains_neighbor"


def test_village_name_surviving_as_suffix_of_absorbing_municipality():
    # "Barca" was absorbed into Košice but survives as a suffix in the LAU's
    # display name -> should resolve via containment, not fuzzy score.
    name_by_gisco = {"SK_KOSICE_BARCA": "Košice - mestská časť Barca"}
    gisco_id, overridden, method, score = _best_lau_match(
        "Barca", "SK_KOSICE_BARCA", [], name_by_gisco, THRESHOLD,
    )
    assert overridden is False
    assert gisco_id == "SK_KOSICE_BARCA"
    assert method == "contains_primary"


def test_name_score_handles_missing_names():
    assert _name_score("Rožňava", None) == 0.0
    assert _name_score(None, "Rožňava") == 0.0
    assert _name_score("", "") == 0.0


def test_name_score_is_diacritic_and_case_insensitive():
    assert _name_score("Roznava", "ROŽŇAVA") == 1.0


def test_name_contains_is_diacritic_and_case_insensitive_substring():
    assert _name_contains("barca", "Košice - mestská časť Barca") is True
    assert _name_contains("Kosice", "Barca") is False
    assert _name_contains(None, "Barca") is False
    assert _name_contains("Barca", None) is False
    assert _name_contains("", "Barca") is False
