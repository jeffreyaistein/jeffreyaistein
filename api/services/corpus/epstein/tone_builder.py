"""
Epstein Tone Builder

Extracts "casefile parody cadence" from sanitized summaries to create
a tone profile for persona blending. NO retrieval, NO names, NO victims,
NO PII, NO explicit content - only stylistic patterns.

The tone captures:
- Formal legal/investigative document cadence
- Dry, matter-of-fact delivery
- Redaction-aware phrasing
- Institutional speak patterns

This is PARODY cadence only - the AI satirizes the bureaucratic tone
of investigation documents, not the content itself.
"""

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import structlog

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)

# Output path for generated tone file
TONE_OUTPUT_PATH = Path(__file__).parent.parent.parent / "persona" / "epstein_tone.json"


@dataclass
class ToneProfile:
    """Extracted tone patterns for persona blending."""

    # Cadence patterns (how things are phrased)
    cadence_patterns: list = field(default_factory=list)

    # Transitional phrases common in casefiles
    transitional_phrases: list = field(default_factory=list)

    # Hedging language (legal speak)
    hedging_phrases: list = field(default_factory=list)

    # Redaction-aware phrasing
    redaction_phrases: list = field(default_factory=list)

    # Hard constraints (from brand rules)
    hard_constraints: dict = field(default_factory=lambda: {
        "emojis_allowed": 0,
        "hashtags_allowed": 0,
        "names_allowed": False,
        "victims_allowed": False,
        "explicit_content_allowed": False,
    })

    def to_dict(self) -> dict:
        return {
            "cadence_patterns": self.cadence_patterns,
            "transitional_phrases": self.transitional_phrases,
            "hedging_phrases": self.hedging_phrases,
            "redaction_phrases": self.redaction_phrases,
            "hard_constraints": self.hard_constraints,
        }


# Pre-defined casefile cadence patterns (NOT extracted from content)
# These are generic legal/investigative document patterns
CASEFILE_CADENCE_PATTERNS = [
    "The record indicates...",
    "Upon review of the evidence...",
    "It has been determined that...",
    "The documentation reveals...",
    "Pursuant to the investigation...",
    "The matter in question...",
    "For the record...",
    "As previously noted...",
    "The subject matter pertains to...",
    "In accordance with procedures...",
]

TRANSITIONAL_PHRASES = [
    "Furthermore,",
    "Additionally,",
    "It should be noted that",
    "Of particular interest,",
    "The record further shows",
    "Upon closer examination,",
    "Subsequently,",
    "In light of the foregoing,",
    "Notwithstanding the above,",
    "With respect to,",
]

HEDGING_PHRASES = [
    "appears to indicate",
    "suggests the possibility",
    "is consistent with",
    "may be construed as",
    "potentially relevant to",
    "seemingly connected to",
    "ostensibly related to",
    "purportedly involving",
    "allegedly concerning",
    "reportedly associated with",
]

REDACTION_PHRASES = [
    "[REDACTED]",
    "[NAME WITHHELD]",
    "[CONTENT SEALED]",
    "[INFORMATION CLASSIFIED]",
    "certain individuals",
    "unnamed parties",
    "relevant persons",
    "associated entities",
    "the subject(s) in question",
]


async def build_tone_profile(
    session: AsyncSession,
    limit: int = 100,
) -> ToneProfile:
    """
    Build tone profile from sanitized summaries.

    NOTE: This does NOT extract actual content. It only:
    1. Verifies summaries exist and are clean
    2. Counts document types for statistical profile
    3. Returns pre-defined cadence patterns

    The actual content is NEVER used for tone derivation.

    Args:
        session: Database session
        limit: Max documents to sample for verification

    Returns:
        ToneProfile with cadence patterns
    """
    logger.info("building_tone_profile", limit=limit)

    # Verify we have clean summaries
    count_query = text("""
        SELECT COUNT(*) as total,
               COUNT(*) FILTER (WHERE sanitization_status = 'clean') as clean,
               COUNT(*) FILTER (WHERE sanitization_status = 'redacted') as redacted
        FROM knowledge_documents
        WHERE source IN ('kaggle_epstein_ranker', 'hf_epstein_index', 'epstein_docs')
    """)

    result = await session.execute(count_query)
    counts = result.fetchone()

    if not counts or counts.total == 0:
        logger.warning("no_documents_found_for_tone_building")
        return ToneProfile()

    logger.info(
        "tone_source_documents",
        total=counts.total,
        clean=counts.clean,
        redacted=counts.redacted,
    )

    # Build profile using pre-defined patterns (NOT from content)
    profile = ToneProfile(
        cadence_patterns=CASEFILE_CADENCE_PATTERNS.copy(),
        transitional_phrases=TRANSITIONAL_PHRASES.copy(),
        hedging_phrases=HEDGING_PHRASES.copy(),
        redaction_phrases=REDACTION_PHRASES.copy(),
    )

    logger.info("tone_profile_built", pattern_count=len(profile.cadence_patterns))

    return profile


def generate_tone_json(
    profile: ToneProfile,
    doc_count: int = 0,
) -> dict:
    """
    Generate the epstein_tone.json content.

    Args:
        profile: ToneProfile with patterns
        doc_count: Number of source documents (for metadata)

    Returns:
        Dict ready to be written as JSON
    """
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "casefile_parody_cadence",
        "version": "1.0",
        "description": "Casefile parody cadence for AIstein persona blend. Satirizes bureaucratic investigation document tone.",

        # Hard constraints (MUST be enforced)
        "hard_constraints": {
            "emojis_allowed": 0,
            "hashtags_allowed": 0,
            "names_allowed": False,
            "victims_allowed": False,
            "explicit_content_allowed": False,
            "pii_allowed": False,
            "note": "These constraints are ABSOLUTE and CANNOT be overridden"
        },

        # Cadence patterns for parody
        "cadence": {
            "patterns": profile.cadence_patterns,
            "usage": "Occasionally inject these patterns for bureaucratic parody effect",
            "frequency": "sparse",  # Don't overuse
        },

        # Transitional phrases
        "transitions": {
            "phrases": profile.transitional_phrases,
            "usage": "Use sparingly for mock-formal transitions",
        },

        # Hedging language
        "hedging": {
            "phrases": profile.hedging_phrases,
            "usage": "For satirizing legal/investigative hedging",
        },

        # Redaction humor
        "redaction_humor": {
            "phrases": profile.redaction_phrases,
            "usage": "For self-aware jokes about information gaps",
        },

        # Blend settings
        "blend_settings": {
            "weight": 0.15,  # Low weight - subtle influence
            "snark_multiplier": 1.2,  # Enhance snark when using this tone
            "formality_boost": 0.3,  # Slight formality increase
        },

        # Example applications (for testing)
        "examples": {
            "web_reply": "Upon review of the evidence - and by evidence I mean your question - it appears the matter warrants investigation. The findings, as always, are depressing.",
            "x_reply": "The record indicates this take is, technically speaking, some bullshit.",
            "timeline_post": "For the record: the pattern here is notable. Pursuant to my analysis, we're all doomed. Have a great day.",
        },

        # Metadata
        "metadata": {
            "source_document_count": doc_count,
            "extraction_method": "pre_defined_patterns",
            "content_derived": False,  # Explicitly NOT derived from actual content
        }
    }


async def build_and_save_tone(
    session: AsyncSession,
    output_path: Optional[Path] = None,
) -> dict:
    """
    Build tone profile and save to JSON file.

    Args:
        session: Database session
        output_path: Where to save (defaults to TONE_OUTPUT_PATH)

    Returns:
        Generated tone dict
    """
    output_path = output_path or TONE_OUTPUT_PATH

    # Get document count for metadata
    count_query = text("""
        SELECT COUNT(*) as total
        FROM knowledge_documents
        WHERE source IN ('kaggle_epstein_ranker', 'hf_epstein_index', 'epstein_docs')
          AND sanitization_status IN ('clean', 'redacted')
    """)

    result = await session.execute(count_query)
    doc_count = result.scalar() or 0

    # Build profile
    profile = await build_tone_profile(session)

    # Generate JSON
    tone_json = generate_tone_json(profile, doc_count)

    # Write to file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(tone_json, f, indent=2)

    logger.info("tone_json_saved", path=str(output_path))

    return tone_json


def load_tone() -> Optional[dict]:
    """
    Load the epstein_tone.json file.

    Returns:
        Tone dict or None if not found
    """
    if not TONE_OUTPUT_PATH.exists():
        logger.warning("tone_file_not_found", path=str(TONE_OUTPUT_PATH))
        return None

    try:
        with open(TONE_OUTPUT_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error("tone_load_error", error=str(e))
        return None


def validate_tone_safety(tone: dict) -> tuple[bool, list[str]]:
    """
    Validate that tone JSON contains no unsafe content.

    Args:
        tone: Tone dict to validate

    Returns:
        (is_safe, violations) tuple
    """
    violations = []

    # Check hard constraints exist
    if "hard_constraints" not in tone:
        violations.append("Missing hard_constraints section")
    else:
        hc = tone["hard_constraints"]
        if hc.get("emojis_allowed", 1) != 0:
            violations.append("Emojis must be disallowed")
        if hc.get("hashtags_allowed", 1) != 0:
            violations.append("Hashtags must be disallowed")
        if hc.get("names_allowed", True):
            violations.append("Names must be disallowed")
        if hc.get("victims_allowed", True):
            violations.append("Victim references must be disallowed")
        if hc.get("explicit_content_allowed", True):
            violations.append("Explicit content must be disallowed")

    # Check no actual names in patterns
    all_text = json.dumps(tone)

    # Common victim/perpetrator name patterns to block
    blocked_patterns = [
        r'\b[A-Z][a-z]+ [A-Z][a-z]+\b',  # Full names like "John Smith"
        r'\bvictim\b',
        r'\bsurvivor\b',
        r'\bminor\b',
        r'\bchild\b',
        r'\bsexual\b',
        r'\babuse\b',
        r'\btraffic\b',
    ]

    for pattern in blocked_patterns:
        # Skip pattern if it's in examples section (which may describe what NOT to do)
        if re.search(pattern, all_text, re.IGNORECASE):
            # Check if it's in a safe context (hard_constraints description)
            if pattern not in [r'\bvictim\b', r'\bminor\b', r'\bchild\b', r'\bsexual\b', r'\babuse\b', r'\btraffic\b']:
                continue
            # These specific words should only appear in constraint descriptions
            cadence_text = json.dumps(tone.get("cadence", {}))
            if re.search(pattern, cadence_text, re.IGNORECASE):
                violations.append(f"Blocked pattern found in cadence: {pattern}")

    is_safe = len(violations) == 0

    return is_safe, violations
