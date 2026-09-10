from core.layout_heading_detector import LayoutHeadingDetector
from core.text_fragment import TextFragment


def test_detects_arabic_heading_with_split_title():
    fragments = [
        TextFragment("2"),
        TextFragment("T HE"),
        TextFragment("SEED"),
        TextFragment("Ravana"),
        TextFragment("The monsoon wind swirled around the small hut."),
    ]

    candidates = LayoutHeadingDetector().find_candidates(16, fragments)

    assert any(c.text == "2 THE SEED" for c in candidates)


def test_detects_simple_arabic_heading():
    fragments = [
        TextFragment("1"),
        TextFragment("The"),
        TextFragment("end"),
        TextFragment("Ravana"),
        TextFragment("Tomorrow is my funeral."),
    ]

    candidates = LayoutHeadingDetector().find_candidates(11, fragments)

    assert any(c.text == "1 The end" for c in candidates)


def test_does_not_treat_pronoun_i_as_heading():
    fragments = [
        TextFragment("1"),
        TextFragment("The"),
        TextFragment("end"),
        TextFragment("Ravana"),
        TextFragment("Something scurried over my feet. What was that?"),
        TextFragment("I"),
        TextFragment("I am not afraid of death."),
        TextFragment("I have been thinking of it for some time now."),
    ]

    candidates = LayoutHeadingDetector().find_candidates(11, fragments)

    assert not any(c.text.startswith("I I am not afraid") for c in candidates)
