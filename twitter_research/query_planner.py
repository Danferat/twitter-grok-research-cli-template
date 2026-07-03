from __future__ import annotations

import re
import shlex
from dataclasses import dataclass


@dataclass(frozen=True)
class QueryPlan:
    question: str
    query: str
    days: int
    limit: int

    def command(self) -> str:
        return (
            "python3 -m twitter_research ask "
            f"{shlex.quote(self.question)} --provider PROVIDER --days {self.days} --limit {self.limit}"
        )


DECLINE_TERMS = "dump OR down OR bearish OR selloff OR unlock OR scam OR volume OR whale"
GROWTH_TERMS = "pump OR rally OR bullish OR listing OR launch OR volume OR whale"
GENERAL_TERMS = "news OR thread OR analysis OR sentiment OR market"


def plan_query(question: str) -> QueryPlan:
    cleaned = " ".join(question.strip().split())
    days = _infer_days(cleaned)
    topic = _infer_topic(cleaned)
    intent_terms = _infer_intent_terms(cleaned)
    query = f"{topic} ({intent_terms})" if topic else f"{cleaned} ({intent_terms})"
    return QueryPlan(question=cleaned, query=query, days=days, limit=100)


def _infer_days(question: str) -> int:
    lowered = question.lower()
    if any(token in lowered for token in ("today", "сегодня")):
        return 1
    if any(token in lowered for token in ("week", "недел")):
        return 7
    if any(token in lowered for token in ("month", "месяц", "30 д")):
        return 30
    return 7


def _infer_topic(question: str) -> str:
    ticker = _first_ticker(question)
    english_phrase = _english_phrase(question)

    if ticker and _mentions_token(question):
        return f"{ticker} token"
    if ticker and english_phrase and english_phrase != ticker:
        return english_phrase
    if ticker:
        return ticker
    return english_phrase


def _first_ticker(question: str) -> str:
    for match in re.finditer(r"\b[A-Z0-9]{2,12}\b", question):
        token = match.group(0)
        if token not in {"OR", "API", "X"}:
            return token
    return ""


def _english_phrase(question: str) -> str:
    words = re.findall(r"\b[A-Za-z0-9][A-Za-z0-9.$_-]*\b", question)
    stop_words = {"why", "is", "are", "the", "a", "an", "what", "about", "on", "in"}
    kept = [word for word in words if word.lower() not in stop_words]
    return " ".join(kept[:8])


def _mentions_token(question: str) -> bool:
    lowered = question.lower()
    return "token" in lowered or "токен" in lowered


def _infer_intent_terms(question: str) -> str:
    lowered = question.lower()
    decline_markers = ("пада", "снижа", "упал")
    growth_markers = ("раст", "вырос")

    has_decline = any(marker in lowered for marker in decline_markers) or _has_lowercase_word(
        question,
        ("dump", "down", "bearish", "selloff"),
    )
    has_growth = any(marker in lowered for marker in growth_markers) or _has_lowercase_word(
        question,
        ("pump", "pamp", "rally", "bullish"),
    )

    if has_decline and has_growth:
        return f"{GROWTH_TERMS} OR {DECLINE_TERMS}"
    if has_decline:
        return DECLINE_TERMS
    if has_growth:
        return GROWTH_TERMS
    return GENERAL_TERMS


def _has_lowercase_word(question: str, words: tuple[str, ...]) -> bool:
    return any(re.search(rf"\b{re.escape(word)}\b", question) for word in words)
