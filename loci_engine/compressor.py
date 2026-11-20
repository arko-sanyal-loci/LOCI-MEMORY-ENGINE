"""
loci_engine/compressor.py
=========================
TF-IDF context compression with no secondary model (Efficiency pillar).

What it does
------------
Shrinks an LLM's input context by keeping only the sentences that carry the
most query-relevant, document-distinctive information, scored by TF-IDF.
It is pure deterministic text processing: no neural model, no fine-tuning,
no API call, so it costs nothing to run and gives the same output for the
same input every time.

Source
------
Defensive publication Claim 4, "TF-IDF Context Compression Without
Secondary Model" (draft prompt in Dropbox ``Claude Artifacts/Part 2/
defensepub 5 claims check.txt``, 2026-07-02). The published claim states a
measured **8.89× compression and 39% API cost reduction on Claude Sonnet
4.6**. No implementation was ever committed to any LOCI repository; this
module is a fresh implementation of the described method.

**This code does not reproduce the 8.89× figure.** The ratio depends
entirely on the corpus, the query and the budget. ``CompressionResult``
reports the ratio actually achieved so any claim can be re-measured
(``benchmarks/compression_ratio.py`` runs it over this repository's own
docs). Until that number is re-measured on the original workload, cite the
8.89× as "reported", not "reproduced".

Method
------
1. Split each document into sentences.
2. Treat every sentence as a "document" for IDF, so a term that appears in
   every sentence (boilerplate) scores ~0 and a rare, specific term scores
   high.
3. Score each sentence = mean TF-IDF of its terms, plus a query bonus
   (``query_weight`` × summed IDF of the query terms it contains).
4. Greedily keep the highest-scoring sentences until the token budget (or
   target ratio) is met, then emit them in their **original order** so the
   compressed text still reads coherently.
5. Always keep sentences that contain an exact value the reader may need
   (numbers, ports, versions, IDs) when ``keep_exact_values`` is set: these
   are value-bus content (see ``value_bus.py``) and must never be lost to
   summarisation.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import List, Optional, Sequence

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n{2,}|\n(?=[-*•#]|\d+\.)")
_TOKEN = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.\-]*")
_EXACT_VALUE = re.compile(
    r"\b\d+(?:\.\d+)+\b"          # versions, IPs, decimals
    r"|\b\d{2,}\b"                # ports, counts, years
    r"|\b[0-9a-f]{7,40}\b"        # hashes
    r"|\b[A-Z]{2,}-\d+\b"         # ticket ids
)

STOPWORDS = frozenset(
    "a an and are as at be been but by can do does for from had has have he her his "
    "i if in into is it its me my no not of on or our she so than that the their them "
    "then there these they this to was we were what when where which who will with "
    "would you your".split()
)


def approx_tokens(text: str) -> int:
    """Cheap token estimate (~4 characters per token, never below word count / 1.3)."""
    return max(1, int(max(len(text) / 4.0, len(text.split()) / 1.3)))


def _terms(text: str) -> List[str]:
    return [t for t in (m.group(0).lower().strip(".-") for m in _TOKEN.finditer(text))
            if t and t not in STOPWORDS]


def split_sentences(text: str) -> List[str]:
    return [s.strip() for s in _SENTENCE_SPLIT.split(text) if s and s.strip()]


@dataclass(frozen=True)
class CompressionResult:
    text: str
    original_tokens: int
    compressed_tokens: int
    kept_sentences: int
    total_sentences: int

    @property
    def ratio(self) -> float:
        """original / compressed tokens (8.89 means 8.89× smaller)."""
        return self.original_tokens / max(1, self.compressed_tokens)

    @property
    def savings(self) -> float:
        """Fraction of input tokens removed (0.39 = 39% fewer tokens)."""
        return 1.0 - self.compressed_tokens / max(1, self.original_tokens)


class TfidfCompressor:
    """Deterministic, model-free context compressor.

    Parameters
    ----------
    query_weight      : how strongly query-term overlap boosts a sentence.
    keep_exact_values : never drop a sentence that contains an exact value
                        (number, version, hash, ticket id) that also appears
                        in the query.
    """

    def __init__(self, query_weight: float = 2.0, keep_exact_values: bool = True):
        self.query_weight = query_weight
        self.keep_exact_values = keep_exact_values

    def _score(self, sentences: Sequence[str], query: Optional[str]) -> List[float]:
        term_lists = [_terms(s) for s in sentences]
        n = len(sentences)
        df: Counter = Counter()
        for terms in term_lists:
            df.update(set(terms))
        idf = {t: math.log((1 + n) / (1 + c)) + 1.0 for t, c in df.items()}
        q_terms = set(_terms(query)) if query else set()

        scores = []
        for terms in term_lists:
            if not terms:
                scores.append(0.0)
                continue
            tf = Counter(terms)
            base = sum((c / len(terms)) * idf[t] for t, c in tf.items())
            bonus = sum(idf.get(t, 0.0) for t in q_terms if t in tf)
            scores.append(base + self.query_weight * bonus)
        return scores

    def compress(
        self,
        text: str | Sequence[str],
        query: Optional[str] = None,
        *,
        max_tokens: Optional[int] = None,
        target_ratio: Optional[float] = None,
    ) -> CompressionResult:
        """Compress ``text`` (a string or a list of chunks).

        Give either ``max_tokens`` (absolute budget) or ``target_ratio``
        (e.g. 4.0 keeps about a quarter). With neither, the default target
        ratio is 3.0.
        """
        if not isinstance(text, str):
            text = "\n\n".join(text)
        sentences = split_sentences(text)
        original = approx_tokens(text) if text else 0
        if not sentences:
            return CompressionResult("", original, 0, 0, 0)

        if max_tokens is None:
            max_tokens = max(1, int(original / (target_ratio or 3.0)))

        scores = self._score(sentences, query)
        order = sorted(range(len(sentences)), key=lambda i: (-scores[i], i))

        must_keep: set[int] = set()
        if self.keep_exact_values and query:
            q_values = {m.group(0) for m in _EXACT_VALUE.finditer(query)}
            if q_values:
                must_keep = {i for i, s in enumerate(sentences)
                             if any(v in s for v in q_values)}

        kept: set[int] = set(must_keep)
        used = sum(approx_tokens(sentences[i]) for i in kept)
        for i in order:
            if i in kept:
                continue
            cost = approx_tokens(sentences[i])
            if used + cost > max_tokens and kept:
                continue
            kept.add(i)
            used += cost
            if used >= max_tokens:
                break

        out = " ".join(sentences[i] for i in sorted(kept))
        return CompressionResult(out, original, approx_tokens(out), len(kept), len(sentences))


def compress(text: str | Sequence[str], query: Optional[str] = None, **kw) -> CompressionResult:
    """Module-level shortcut for ``TfidfCompressor().compress``."""
    return TfidfCompressor().compress(text, query, **kw)


__all__ = ["CompressionResult", "TfidfCompressor", "approx_tokens", "compress", "split_sentences"]
