"""Offline tests for the lexical sentiment scorer (no SDK/network)."""
from __future__ import annotations

from sentiment.sentiment_scorer import LexicalSentimentScorer
from session.session_state import SessionUserData

scorer = LexicalSentimentScorer()


def test_three_negative_turns_recommend_escalation() -> None:
    ud = SessionUserData()
    scorer.score("this is unacceptable, I am furious", ud)
    scorer.score("ridiculous, the worst service ever", ud)
    scorer.score("this is completely useless", ud)
    assert ud.consecutive_negative_turns >= 3
    assert ud.should_offer_escalation is True


def test_positive_turn_resets_the_counter() -> None:
    ud = SessionUserData()
    scorer.score("this is terrible", ud)
    scorer.score("thanks, that is perfect and helpful", ud)
    assert ud.consecutive_negative_turns == 0
    assert ud.should_offer_escalation is False


def test_neutral_turn_does_not_flag() -> None:
    ud = SessionUserData()
    scorer.score("I would like to check my invoice please", ud)
    assert ud.should_offer_escalation is False