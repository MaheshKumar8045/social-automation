from core.character_identity_normalizer import compatible


def test_titled_epithet_variant_merges_conservatively():
    ok, confidence, method, relationship = compatible(
        "Lord Shiva",
        "Lord Shiva Pasupathi",
    )
    assert ok is True
    assert confidence == 0.88
    assert method == "qualified_identity_variant"
    assert relationship == "IDENTITY_ALIAS"


def test_titled_literal_variant_merges_conservatively():
    ok, confidence, method, relationship = compatible(
        "Lord Shiva",
        "Lord Shiva Pasupathi Literally",
    )
    assert ok is True
    assert confidence == 0.88
    assert method == "qualified_identity_variant"
    assert relationship == "IDENTITY_ALIAS"


def test_unrelated_titled_names_do_not_merge():
    ok, _, _, relationship = compatible("Lord Shiva", "Lord Vishnu")
    assert ok is False
    assert relationship == "UNRESOLVED"
