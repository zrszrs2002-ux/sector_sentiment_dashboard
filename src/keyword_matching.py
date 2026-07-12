"""Shared, dependency-light keyword matching primitives."""

from __future__ import annotations

import re


def normalize_for_keyword_match(text: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", " ", str(text or "").lower())
    return re.sub(r"\s+", " ", normalized).strip()


def matched_terms_in_sentence(sentence: str, terms: list[str]) -> list[str]:
    haystack = f" {normalize_for_keyword_match(sentence)} "
    matches: list[str] = []
    for term in terms:
        needle = normalize_for_keyword_match(term)
        if needle and f" {needle} " in haystack:
            matches.append(term)
    return matches


def distinct_matched_terms(sentences: list[str], terms: list[str]) -> list[str]:
    matches: list[str] = []
    seen: set[str] = set()
    for sentence in sentences:
        for term in matched_terms_in_sentence(sentence, terms):
            key = normalize_for_keyword_match(term)
            if key and key not in seen:
                seen.add(key)
                matches.append(term)
    return matches


def normalized_sentence_hit_score(
    sentences: list[str],
    terms: list[str],
    multiplier: float,
    blocked_terms: list[str] | None = None,
) -> float:
    """Return a sentence-hit score, optionally excluding direction-reversed hits."""
    clean_sentences = [str(sentence).strip() for sentence in sentences if str(sentence).strip()]
    if not clean_sentences:
        return 0.0
    blockers = blocked_terms or []
    hit_sentence_count = sum(
        1
        for sentence in clean_sentences
        if matched_terms_in_sentence(sentence, terms)
        and not matched_terms_in_sentence(sentence, blockers)
    )
    return min(hit_sentence_count / len(clean_sentences) * multiplier, 1.0)
