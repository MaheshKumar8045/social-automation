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



def test_royal_title_variant_merges_with_bare_name():
    ok, confidence, method, relationship = compatible(
        "King Ravana",
        "Ravana",
    )
    assert ok is True
    assert confidence == 0.98
    assert method == "normalized_exact"
    assert relationship == "IDENTITY_ALIAS"


def test_royal_title_does_not_merge_arbitrary_suffix_variant():
    ok, _, _, relationship = compatible(
        "King Ravana",
        "Ravana Tomorrow",
    )
    assert ok is False
    assert relationship == "UNRESOLVED"
