from core.entity_extractor import EntityExtractor


def test_title_candidate_does_not_cross_sentence_boundary():
    text = (
        "The Professor. And thus it was decided. "
        "The Professor. He must have taken notes. "
        "The Professor. Human instincts succumbed to science. "
        "The Professor. It was evident that we were lost. "
        "The Professor. The Icelander went back to the raft. "
        "The Professor. Then he quietly returned. "
        "Professor. Well, was I serious? "
        "Professor Hardwigg explained the plan."
    )

    candidates = EntityExtractor._character_candidates(text)

    assert "Professor Hardwigg" in candidates
    assert "Professor. And" not in candidates
    assert "Professor. He" not in candidates
    assert "Professor. Human" not in candidates
    assert "Professor. It" not in candidates
    assert "Professor. The Icelander" not in candidates
    assert "Professor. Then" not in candidates
    assert "Professor. Well" not in candidates
