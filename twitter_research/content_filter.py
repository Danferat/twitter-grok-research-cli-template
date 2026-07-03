from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path


DEFAULT_CONTENT_INDEX = Path("content_research_index.md")
DEFAULT_SIMILARITY_THRESHOLD = 0.8


@dataclass(frozen=True)
class ContentIndexEntry:
    added_at: str
    topic: str
    category: str
    summary: str
    source_url: str
    file_path: str
    status: str


@dataclass(frozen=True)
class SimilarSummaryMatch:
    entry: ContentIndexEntry
    score: float


def load_content_index(index_path: Path | str = DEFAULT_CONTENT_INDEX) -> list[ContentIndexEntry]:
    path = Path(index_path)
    if not path.exists():
        return []
    return load_content_index_from_text(path.read_text(encoding="utf-8"))


def load_content_index_from_text(text: str) -> list[ContentIndexEntry]:
    entries: list[ContentIndexEntry] = []
    for line in text.splitlines():
        cells = _parse_table_row(line)
        if cells is None or _is_separator_row(cells) or cells[0] == "Дата добавления":
            continue
        if len(cells) < 7:
            continue
        entries.append(
            ContentIndexEntry(
                added_at=cells[0],
                topic=cells[1],
                category=cells[2],
                summary=cells[3],
                source_url=cells[4],
                file_path=cells[5],
                status=cells[6],
            )
        )
    return entries


def find_similar_summary(
    candidate_summary: str,
    entries: list[ContentIndexEntry],
    threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
) -> SimilarSummaryMatch | None:
    best: SimilarSummaryMatch | None = None
    for entry in entries:
        score = summary_similarity(candidate_summary, entry.summary)
        if best is None or score > best.score:
            best = SimilarSummaryMatch(entry=entry, score=score)

    if best is None or best.score <= threshold:
        return None
    return best


def summary_similarity(left: str, right: str) -> float:
    left_text = _normalize_text(left)
    right_text = _normalize_text(right)
    if not left_text or not right_text:
        return 0.0

    sequence_score = SequenceMatcher(None, left_text, right_text).ratio()
    token_score = _token_f1_score(left_text, right_text)
    return max(sequence_score, token_score)


def _parse_table_row(line: str) -> list[str] | None:
    stripped = line.strip()
    if not stripped.startswith("|") or not stripped.endswith("|"):
        return None
    return [cell.strip() for cell in stripped.strip("|").split("|")]


def _is_separator_row(cells: list[str]) -> bool:
    return all(re.fullmatch(r"[-:\s]+", cell) for cell in cells)


def _normalize_text(text: str) -> str:
    normalized = text.lower().replace("ё", "е")
    normalized = normalized.replace("offline", "офлайн")
    normalized = normalized.replace("online", "онлайн")
    tokens = [_canonical_token(token) for token in re.findall(r"[a-zа-я0-9]+", normalized)]
    return " ".join(tokens)


def _canonical_token(token: str) -> str:
    synonyms = {
        "невозможность": "блокировка",
        "нельзя": "блокировка",
        "невозможно": "блокировка",
        "заблокирован": "блокировка",
        "заблокирована": "блокировка",
        "платежей": "платеж",
        "платежи": "платеж",
        "платеж": "платеж",
        "комиссии": "платеж",
        "комиссий": "платеж",
        "оплатить": "платеж",
        "оплата": "платеж",
        "дополнительные": "новый",
        "дополнительных": "новый",
        "новых": "новый",
        "новые": "новый",
        "средств": "актив",
        "деньги": "актив",
        "денег": "актив",
        "кошелька": "кошелек",
        "кошельков": "кошелек",
        "криптокошелька": "криптокошелек",
        "подписями": "подпись",
        "подписью": "подпись",
        "разрешений": "approval",
        "разрешения": "approval",
        "аппрувы": "approval",
        "аппрувов": "approval",
    }
    if token in synonyms:
        return synonyms[token]

    suffixes = (
        "иями",
        "ями",
        "ами",
        "ого",
        "ему",
        "ому",
        "ыми",
        "ими",
        "ая",
        "яя",
        "ое",
        "ее",
        "ые",
        "ие",
        "ых",
        "их",
        "ой",
        "ей",
        "ам",
        "ям",
        "ах",
        "ях",
        "ов",
        "ев",
        "ом",
        "ем",
        "а",
        "я",
        "ы",
        "и",
        "е",
        "у",
        "ю",
    )
    for suffix in suffixes:
        if len(token) > len(suffix) + 4 and token.endswith(suffix):
            return token[: -len(suffix)]
    return token


def _token_f1_score(left_text: str, right_text: str) -> float:
    left_tokens = left_text.split()
    right_tokens = right_text.split()
    if not left_tokens or not right_tokens:
        return 0.0

    left_counts = Counter(left_tokens)
    right_counts = Counter(right_tokens)
    overlap = sum((left_counts & right_counts).values())
    precision = overlap / len(left_tokens)
    recall = overlap / len(right_tokens)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)
