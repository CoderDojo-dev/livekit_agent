"""Multilingual UAT (FR/AR/EN): the lexical sentiment scorer detects negativity in each language.

Per the cookbook section 20 hard rule, behaviour is asserted in French, Arabic AND English - not
English with a note that 'the others should be similar'.
"""
from __future__ import annotations

import pytest
from sentiment.sentiment_scorer import LexicalSentimentScorer
from session.session_state import SessionUserData

scorer = LexicalSentimentScorer()

# (language, clearly-negative phrase, clearly-positive phrase) using the shipped lexicons.
CASES = [
    ("en", "this is awful and the agent is incompetent", "thanks, that is perfect and helpful"),
    ("fr", "c'est inacceptable et totalement nul", "merci, c'est parfait et génial"),
    ("ar", "هذا سيء جدا وأنا غاضب", "شكرا، رائع وممتاز"),
]


@pytest.mark.parametrize("lang,negative,positive", CASES)
def test_negativity_detected_per_language(lang: str, negative: str, positive: str) -> None:
    ud_neg = SessionUserData(language=lang)
    neg_score = scorer.score(negative, ud_neg)

    ud_pos = SessionUserData(language=lang)
    pos_score = scorer.score(positive, ud_pos)

    assert neg_score < pos_score, f"{lang}: negative should score below positive"
    assert ud_neg.consecutive_negative_turns >= 1, f"{lang}: negative turn should be flagged"


def test_three_negative_turns_escalate_in_arabic() -> None:
    ud = SessionUserData(language="ar")
    scorer.score("هذا سيء جدا", ud)
    scorer.score("مرفوض، فضيحة", ud)
    scorer.score("سخيف ومزعج", ud)
    assert ud.should_offer_escalation is True  # the de-escalation path works cross-lingually