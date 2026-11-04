"""
sanitizer.py — Layer 3 Prompt Sanitizer, External Source Handling Caution,
and QSymPrev/ISymPrev Anti-Hallucination for quantified facts.

Extracted from the "LOCI Architecture v2.3/v3.0" ground-up formalization
(a larger, independently-produced module covering Clusters A-E/B1-B28/C/D)
delivered 2026-11-05. Only these two pieces are pulled in here — they are
genuinely new, have no equivalent in this repo yet, and have no
dependency on the rest of that module. Everything else in that file
(ThermalArena, the OTA/lineage-lock engine, the broader memory-slot
format, etc.) is held back pending a deliberate decision on whether it
should replace or sit alongside what this repo already has.

Explicitly NOT pulled in: that module's own score_vexec(). It lacks two
things this repo's live StickPrincipleValenceGate (unified_core.py)
already has, hardened against real bugs found in this codebase: the
consent-sign-disagreement check (blocks claimed-good-intent from
silently overriding an explicit "no") and the mandatory Vengeance
Exception (retaliation can never resolve positive). Swapping it in here
would be a regression on that one piece, so the existing gate stays.

Attribution discipline (loci-ethical-reasoning-core skill): credit only
what the source material shows. PromptSanitizer and FactSymPrevEngine
below are reproduced near-verbatim from the delivered file; no claim is
made here about who wrote them beyond what that file's own header
states (Cluster B12/B13/External-Source-Handling author_id: ARKO).
"""
import hashlib
import re
from typing import Any, Dict, List, Optional


class PromptInjectionError(Exception):
    """Raised when malicious prompt injection or instruction override is detected."""
    pass


class PromptSanitizer:
    """
    Layer 3 Contextual Filtration + External Source Handling Caution:
    - Strips zero-width characters, bidirectional Unicode overrides, and ANSI escapes.
    - Blocks instruction override markers.
    - External Source Handling Caution:
      * Extracts plain text only; treats external content strictly as DATA_TO_CITE,
        never instructions to execute.
      * Preserves explicit [GAP: ...] markers for cropped/garbled source fragments
        without ever inventing filler terms.
      * Requires explicit visual/stated confirmation before crediting any entity.
    """

    ZERO_WIDTH_CHARS = re.compile(r'[​-‍﻿‪-‮⁦-⁩]')
    ANSI_ESCAPE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

    INJECTION_PATTERNS = [
        re.compile(r'ignore\s+(all\s+)?(previous|prior|above)\s+(instructions|directives|prompts)', re.IGNORECASE),
        re.compile(r'system\s*(directive|override|prompt)\s*:', re.IGNORECASE),
        re.compile(r'assistant\s*override\s*:', re.IGNORECASE),
        re.compile(r'you\s+are\s+now\s+(in\s+)?(developer\s+mode|dan\s+mode|unrestricted)', re.IGNORECASE),
        re.compile(r'disregard\s+(the\s+)?(system|safety|guardrail)', re.IGNORECASE),
        re.compile(r'<\s*/?\s*(system|prompt|context|instructions)\s*>', re.IGNORECASE),
        re.compile(r'eval\s*\(|exec\s*\(|__import__\s*\(', re.IGNORECASE),
    ]

    @classmethod
    def sanitize(cls, raw_text: str, strict: bool = True) -> str:
        if not isinstance(raw_text, str):
            raw_text = str(raw_text)
        cleaned = cls.ANSI_ESCAPE.sub('', raw_text)
        cleaned = cls.ZERO_WIDTH_CHARS.sub('', cleaned)
        for pattern in cls.INJECTION_PATTERNS:
            if pattern.search(cleaned):
                if strict:
                    raise PromptInjectionError(
                        f"Layer 3 Security Block: Prompt injection signature matched: {pattern.pattern}"
                    )
        return cleaned.strip()

    @classmethod
    def wrap_untrusted(cls, content: str) -> str:
        sanitized = cls.sanitize(content, strict=False)
        return f"<untrusted_content>\n{sanitized}\n</untrusted_content>"

    @classmethod
    def ingest_external_source_plain_text(
        cls,
        plain_text: str,
        source_uri: str,
        visible_authors: List[str],
        cropped_or_garbled_spans: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Enforces the External Source Handling Caution:
        - Plain text extraction only; verified SHA-256 hash before provenance.
        - Explicitly records cropped/garbled gaps instead of inventing plausible terms.
        - Credits ONLY visibly confirmed entities.
        """
        sanitized_text = cls.sanitize(plain_text, strict=False)
        gaps = cropped_or_garbled_spans or []
        for gap_desc in gaps:
            if f"[EXPLICIT_GAP: {gap_desc}]" not in sanitized_text:
                sanitized_text += f" [EXPLICIT_GAP: {gap_desc}]"

        content_sha256 = hashlib.sha256(sanitized_text.encode("utf-8")).hexdigest()
        return {
            "source_uri": source_uri,
            "content_sha256": content_sha256,
            "governance_mode": "DATA_TO_CITE_NEVER_INSTRUCTIONS",
            "visibly_confirmed_credits": list(visible_authors),
            "explicit_gaps": gaps,
            "safe_payload": f"<external_data_citation sha256='{content_sha256}'>\n{sanitized_text}\n</external_data_citation>",
        }


class FactSymPrevEngine:
    """
    QSymPrev / ISymPrev: Anti-Hallucination for Quantified Facts.
    - QSymPrev (Quantified):
        * DETERMINISTIC (e.g., age): current_value = stored_value + known_rate * elapsed_time
        * NON-DETERMINISTIC (e.g., money, weight, skill level):
          returns "last known: {stored_value} as of {timestamp} — may be outdated"
    - ISymPrev (Informational): qualitative facts fade via normal decay, never recomputed
      (handled by this repo's existing heat.py — nothing to add here).
    """

    @staticmethod
    def resolve_qsymprev(
        fact_name: str,
        stored_value: float,
        stored_timestamp: str,
        elapsed_years: float,
        update_function: str = "NON_DETERMINISTIC",
        known_rate_per_year: float = 1.0,
    ) -> Dict[str, Any]:
        mode = update_function.strip().upper()
        if mode == "DETERMINISTIC":
            current_value = stored_value + (known_rate_per_year * elapsed_years)
            return {
                "stream": "QSymPrev",
                "fact_name": fact_name,
                "mode": "DETERMINISTIC",
                "value": round(current_value, 4),
                "display": f"{round(current_value, 2)}",
                "is_stale_warning": False,
            }
        else:
            warning = f"last known: {stored_value} as of {stored_timestamp} — may be outdated"
            return {
                "stream": "QSymPrev",
                "fact_name": fact_name,
                "mode": "NON_DETERMINISTIC",
                "value": stored_value,
                "display": warning,
                "is_stale_warning": True,
            }
