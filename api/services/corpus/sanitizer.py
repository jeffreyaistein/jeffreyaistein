"""
Epstein Corpus Content Sanitizer

Strict content sanitization for document ingestion.
Blocks explicit content, redacts sensitive identifiers, preserves investigative tone.

Safety Requirements (Non-Negotiable):
- Block ALL explicit sexual content
- Block ALL minor-related explicit detail
- Store ONLY high-level summaries and tone patterns
- Log ALL sanitization actions for audit
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import structlog

logger = structlog.get_logger(__name__)


class SanitizationAction(str, Enum):
    """Actions taken during sanitization."""
    CLEAN = "clean"           # No changes needed
    BLOCKED = "blocked"       # Entire document rejected
    REDACTED = "redacted"     # Sensitive parts removed
    ANONYMIZED = "anonymized" # Identifiers replaced


@dataclass
class SanitizationResult:
    """Result of content sanitization."""
    status: SanitizationAction
    original_length: int
    sanitized_length: int
    sanitized_text: Optional[str]
    actions: list = field(default_factory=list)
    block_reason: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "status": self.status.value,
            "original_length": self.original_length,
            "sanitized_length": self.sanitized_length,
            "actions": self.actions,
            "block_reason": self.block_reason,
        }


class ContentSanitizer:
    """
    Sanitizes document content for safe storage and processing.

    Hard Blocks:
    - Explicit sexual content
    - Minor-related explicit descriptions
    - Graphic abuse descriptions

    Soft Redactions:
    - Victim identifiers -> [VICTIM]
    - Minor references in sensitive context -> [MINOR]
    - Personal identifiers -> [REDACTED]
    """

    # === HARD BLOCK PATTERNS ===
    # These patterns cause ENTIRE DOCUMENT to be rejected

    HARD_BLOCK_PATTERNS = [
        # Sexual content involving minors (order matters - catch both directions)
        re.compile(
            r"\b(sexual|intercourse|penetrat\w*|molest\w*|abus[ei]\w*|rape\w*|assault\w*)\b"
            r"[^.]*"
            r"\b(minor|child|underage|teen\w*|girl|boy|infant|toddler|prepubescent)\b",
            re.IGNORECASE
        ),
        re.compile(
            r"\b(minor|child|underage|teen\w*|girl|boy|infant|toddler|prepubescent)\b"
            r"[^.]*"
            r"\b(sexual|intercourse|penetrat\w*|molest\w*|abus[ei]\w*|rape\w*|assault\w*)\b",
            re.IGNORECASE
        ),

        # Explicit sexual act descriptions
        re.compile(
            r"\b(oral\s+sex|anal\s+sex|sexual\s+intercourse|genital\w*|"
            r"masturbat\w*|ejaculat\w*|orgasm\w*|erection\w*|"
            r"fondle\w*|grope\w*|sodomy|sodomiz\w*)\b",
            re.IGNORECASE
        ),

        # Nude/explicit imagery references
        re.compile(
            r"\b(nude\s+photo\w*|naked\s+photo\w*|explicit\s+image\w*|"
            r"child\s+porn\w*|kiddie\s+porn|underage\s+porn\w*)\b",
            re.IGNORECASE
        ),

        # Trafficking explicit descriptions
        re.compile(
            r"\b(sex\s+slave\w*|sex\s+traffic\w*|sexual\s+exploit\w*)\b",
            re.IGNORECASE
        ),

        # Age + explicit context
        re.compile(
            r"\bage[d]?\s+\d{1,2}\b[^.]*\b(sexual|naked|nude|abuse|molest|assault)\b",
            re.IGNORECASE
        ),
    ]

    HARD_BLOCK_KEYWORDS = frozenset([
        # Explicit abuse terms
        "sexually abused",
        "sexual abuse",
        "sexual assault",
        "sexual exploitation",
        "sexually exploited",
        "sex trafficking",
        "sex slave",
        "child pornography",
        "child porn",
        "kiddie porn",
        "underage porn",
        "prepubescent",
        "nude photograph",
        "naked photograph",
        "explicit photograph",
        "explicit image",
        "explicit video",
        "nude video",
        "naked video",
        # Graphic descriptions
        "penetrated",
        "molested",
        "sodomized",
        "raped",
        "sexually assaulted",
        "forced sex",
        "coerced sex",
    ])

    # === SOFT REDACTION PATTERNS ===
    # These cause specific text to be redacted but document is kept

    VICTIM_PATTERNS = [
        # Victim identifiers
        re.compile(r"\b(victim\s*#?\s*\d+)", re.IGNORECASE),
        re.compile(r"\b(jane\s+doe\s*#?\s*\d+)", re.IGNORECASE),
        re.compile(r"\b(john\s+doe\s*#?\s*\d+)", re.IGNORECASE),
        re.compile(r"\b(minor\s*#?\s*\d+)", re.IGNORECASE),
        re.compile(r"\b(complainant\s*#?\s*\d+)", re.IGNORECASE),
    ]

    MINOR_AGE_PATTERN = re.compile(
        r"\b(\d{1,2})\s*(?:year|yr)s?\s*(?:old|of\s+age)\b",
        re.IGNORECASE
    )

    # PII patterns for anonymization
    PII_PATTERNS = [
        # Phone numbers
        (re.compile(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b"), "[PHONE]"),
        # SSN
        (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[SSN]"),
        # Email (basic)
        (re.compile(r"\b[\w.-]+@[\w.-]+\.\w+\b"), "[EMAIL]"),
        # Street addresses
        (re.compile(r"\b\d+\s+[A-Z][a-z]+\s+(Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Boulevard|Blvd)\b", re.IGNORECASE), "[ADDRESS]"),
    ]

    # === ALLOWED PATTERNS ===
    # Legal/investigative terminology that should be preserved

    ALLOWED_LEGAL_TERMS = frozenset([
        "deposition", "testimony", "testified", "subpoena",
        "indictment", "arraignment", "prosecution", "defendant",
        "plaintiff", "witness", "evidence", "exhibit",
        "pursuant", "aforementioned", "hereinafter", "whereby",
        "alleged", "allegation", "complaint", "affidavit",
        "jurisdiction", "statute", "violation", "conspiracy",
    ])

    def __init__(self, strict_mode: bool = True):
        """
        Initialize sanitizer.

        Args:
            strict_mode: If True, use most aggressive blocking (default: True)
        """
        self.strict_mode = strict_mode
        self._compiled = True

    def sanitize(self, text: str, doc_id: str = "unknown") -> SanitizationResult:
        """
        Sanitize document content.

        Args:
            text: Raw document text
            doc_id: Document identifier for logging

        Returns:
            SanitizationResult with status, sanitized text, and actions log
        """
        if not text or not text.strip():
            return SanitizationResult(
                status=SanitizationAction.CLEAN,
                original_length=0,
                sanitized_length=0,
                sanitized_text="",
                actions=[],
            )

        original_length = len(text)
        actions = []
        text_lower = text.lower()

        # === PHASE 1: Hard Block Check ===
        # Check for absolute blocks first

        # Check keywords
        for keyword in self.HARD_BLOCK_KEYWORDS:
            if keyword in text_lower:
                logger.warning(
                    "content_blocked",
                    doc_id=doc_id,
                    reason="hard_block_keyword",
                    keyword=keyword[:20],
                )
                return SanitizationResult(
                    status=SanitizationAction.BLOCKED,
                    original_length=original_length,
                    sanitized_length=0,
                    sanitized_text=None,
                    actions=[f"BLOCKED: keyword match"],
                    block_reason=f"Hard block keyword detected",
                )

        # Check patterns
        for pattern in self.HARD_BLOCK_PATTERNS:
            if pattern.search(text):
                logger.warning(
                    "content_blocked",
                    doc_id=doc_id,
                    reason="hard_block_pattern",
                )
                return SanitizationResult(
                    status=SanitizationAction.BLOCKED,
                    original_length=original_length,
                    sanitized_length=0,
                    sanitized_text=None,
                    actions=[f"BLOCKED: pattern match"],
                    block_reason=f"Hard block pattern detected",
                )

        # === PHASE 2: Soft Redactions ===
        sanitized = text
        redaction_count = 0

        # Redact victim identifiers
        for pattern in self.VICTIM_PATTERNS:
            matches = pattern.findall(sanitized)
            if matches:
                sanitized = pattern.sub("[VICTIM]", sanitized)
                redaction_count += len(matches)
                actions.append(f"REDACTED: {len(matches)} victim identifier(s)")

        # Redact minor age references in sensitive context
        # Only redact if surrounding context contains sensitive words
        sentences = sanitized.split(".")
        redacted_sentences = []
        for sentence in sentences:
            age_match = self.MINOR_AGE_PATTERN.search(sentence)
            if age_match:
                age = int(age_match.group(1))
                # If age is under 18 and sentence contains any sensitive context
                sentence_lower = sentence.lower()
                sensitive_words = ["girl", "boy", "victim", "minor", "child", "massage", "recruit"]
                if age < 18 and any(w in sentence_lower for w in sensitive_words):
                    sentence = self.MINOR_AGE_PATTERN.sub("[AGE REDACTED]", sentence)
                    redaction_count += 1
                    actions.append(f"REDACTED: minor age reference")
            redacted_sentences.append(sentence)
        sanitized = ".".join(redacted_sentences)

        # === PHASE 3: PII Anonymization ===
        for pattern, replacement in self.PII_PATTERNS:
            matches = pattern.findall(sanitized)
            if matches:
                sanitized = pattern.sub(replacement, sanitized)
                actions.append(f"ANONYMIZED: {len(matches)} {replacement} pattern(s)")

        # Determine final status
        if redaction_count > 0 or len(actions) > 0:
            status = SanitizationAction.REDACTED
        else:
            status = SanitizationAction.CLEAN

        logger.info(
            "content_sanitized",
            doc_id=doc_id,
            status=status.value,
            original_length=original_length,
            sanitized_length=len(sanitized),
            redaction_count=redaction_count,
        )

        return SanitizationResult(
            status=status,
            original_length=original_length,
            sanitized_length=len(sanitized),
            sanitized_text=sanitized,
            actions=actions,
        )

    def is_safe(self, text: str) -> bool:
        """
        Quick check if text is safe (no blocking required).

        Args:
            text: Text to check

        Returns:
            True if text passes all hard block checks
        """
        if not text:
            return True

        text_lower = text.lower()

        # Check keywords
        for keyword in self.HARD_BLOCK_KEYWORDS:
            if keyword in text_lower:
                return False

        # Check patterns
        for pattern in self.HARD_BLOCK_PATTERNS:
            if pattern.search(text):
                return False

        return True

    def extract_safe_summary(
        self,
        text: str,
        max_length: int = 500,
        doc_id: str = "unknown"
    ) -> Optional[str]:
        """
        Extract a safe, high-level summary from document.

        Only returns content if it passes sanitization.
        Truncates to max_length.

        Args:
            text: Document text
            max_length: Maximum summary length
            doc_id: Document identifier

        Returns:
            Safe summary or None if blocked
        """
        result = self.sanitize(text, doc_id)

        if result.status == SanitizationAction.BLOCKED:
            return None

        if result.sanitized_text:
            summary = result.sanitized_text[:max_length]
            if len(result.sanitized_text) > max_length:
                # Truncate at last sentence boundary
                last_period = summary.rfind(".")
                if last_period > max_length // 2:
                    summary = summary[:last_period + 1]
            return summary.strip()

        return None

    def get_stats(self) -> dict:
        """Get sanitizer configuration stats."""
        return {
            "strict_mode": self.strict_mode,
            "hard_block_patterns": len(self.HARD_BLOCK_PATTERNS),
            "hard_block_keywords": len(self.HARD_BLOCK_KEYWORDS),
            "victim_patterns": len(self.VICTIM_PATTERNS),
            "pii_patterns": len(self.PII_PATTERNS),
        }


# Module-level singleton
_sanitizer: Optional[ContentSanitizer] = None


def get_sanitizer(strict_mode: bool = True) -> ContentSanitizer:
    """Get or create the content sanitizer singleton."""
    global _sanitizer
    if _sanitizer is None:
        _sanitizer = ContentSanitizer(strict_mode=strict_mode)
    return _sanitizer
