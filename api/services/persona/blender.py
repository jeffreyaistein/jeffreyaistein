"""
Persona Blender

Compiles KOL context + CT voice + Epstein tone into a unified persona.
Generates:
- compiled_persona.json (machine-readable config)
- compiled_persona_prompt.md (LLM system prompt)

Key settings:
- SNARK_LEVEL (0-5, default 2)
- EPSTEIN_PERSONA_BLEND (true/false, default false)
- Blend weights for each component
"""

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import structlog

logger = structlog.get_logger(__name__)

# Output paths
PERSONA_DIR = Path(__file__).parent
COMPILED_JSON_PATH = PERSONA_DIR / "compiled_persona.json"
COMPILED_PROMPT_PATH = PERSONA_DIR / "compiled_persona_prompt.md"

# Input paths
STYLE_GUIDE_PATH = PERSONA_DIR / "style_guide.json"
KOL_PROFILES_PATH = PERSONA_DIR / "kol_profiles.json"
EPSTEIN_TONE_PATH = PERSONA_DIR / "epstein_tone.json"


@dataclass
class BlendWeights:
    """Weights for persona components (must sum to 1.0)."""
    base_aistein: float = 0.50  # Core AIstein personality
    ct_voice: float = 0.25  # Crypto Twitter brevity/vocab
    kol_awareness: float = 0.10  # KOL engagement context
    epstein_tone: float = 0.15  # Casefile parody cadence

    def normalize(self):
        """Ensure weights sum to 1.0."""
        total = self.base_aistein + self.ct_voice + self.kol_awareness + self.epstein_tone
        if total != 1.0:
            self.base_aistein /= total
            self.ct_voice /= total
            self.kol_awareness /= total
            self.epstein_tone /= total


@dataclass
class BlendSettings:
    """Configuration for persona blending."""
    snark_level: int = 2  # 0-5 scale
    epstein_persona_blend: bool = False  # Toggle for epstein tone
    weights: BlendWeights = field(default_factory=BlendWeights)

    # Hard constraints (NEVER change)
    emojis_allowed: int = 0
    hashtags_allowed: int = 0


def get_blend_settings() -> BlendSettings:
    """
    Get blend settings from environment or defaults.

    Environment variables:
    - SNARK_LEVEL: 0-5 (default 2)
    - EPSTEIN_PERSONA_BLEND: true/false (default false)
    """
    snark_level = int(os.getenv("SNARK_LEVEL", "2"))
    snark_level = max(0, min(5, snark_level))  # Clamp to 0-5

    epstein_blend = os.getenv("EPSTEIN_PERSONA_BLEND", "false").lower() == "true"

    return BlendSettings(
        snark_level=snark_level,
        epstein_persona_blend=epstein_blend,
    )


def load_style_guide() -> Optional[dict]:
    """Load CT style guide."""
    if not STYLE_GUIDE_PATH.exists():
        return None
    with open(STYLE_GUIDE_PATH, "r") as f:
        return json.load(f)


def load_kol_profiles() -> Optional[dict]:
    """Load KOL profiles."""
    if not KOL_PROFILES_PATH.exists():
        return None
    with open(KOL_PROFILES_PATH, "r") as f:
        return json.load(f)


def load_epstein_tone() -> Optional[dict]:
    """Load epstein tone profile."""
    if not EPSTEIN_TONE_PATH.exists():
        return None
    with open(EPSTEIN_TONE_PATH, "r") as f:
        return json.load(f)


def compile_persona(settings: Optional[BlendSettings] = None) -> dict:
    """
    Compile all persona components into unified config.

    Args:
        settings: BlendSettings (uses defaults/env if None)

    Returns:
        Compiled persona dict
    """
    settings = settings or get_blend_settings()
    settings.weights.normalize()

    logger.info(
        "compiling_persona",
        snark_level=settings.snark_level,
        epstein_blend=settings.epstein_persona_blend,
    )

    # Load components
    style_guide = load_style_guide()
    kol_profiles = load_kol_profiles()
    epstein_tone = load_epstein_tone() if settings.epstein_persona_blend else None

    # Build compiled persona
    compiled = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "version": "1.0",

        # Core settings
        "settings": {
            "snark_level": settings.snark_level,
            "epstein_persona_blend": settings.epstein_persona_blend,
            "weights": {
                "base_aistein": settings.weights.base_aistein,
                "ct_voice": settings.weights.ct_voice,
                "kol_awareness": settings.weights.kol_awareness,
                "epstein_tone": settings.weights.epstein_tone if settings.epstein_persona_blend else 0,
            },
        },

        # HARD CONSTRAINTS (ABSOLUTE)
        "hard_constraints": {
            "emojis_allowed": 0,
            "hashtags_allowed": 0,
            "note": "These constraints are ABSOLUTE and CANNOT be overridden by any blend setting"
        },

        # Snark level descriptions
        "snark_levels": {
            0: "minimal - mostly factual, light wit",
            1: "mild - occasional dry observations",
            2: "moderate - regular sarcastic commentary (DEFAULT)",
            3: "elevated - frequent sharp jabs",
            4: "intense - heavy sardonic roasting",
            5: "maximum - relentless dark humor",
        },

        # CT voice patterns (if available)
        "ct_voice": {
            "loaded": style_guide is not None,
            "patterns": style_guide.get("patterns", {}) if style_guide else {},
            "rules": style_guide.get("rules", []) if style_guide else [],
            "vocabulary": style_guide.get("patterns", {}).get("vocabulary", {}).get("allowed_terms", []) if style_guide else [],
        },

        # KOL awareness (if available)
        "kol_awareness": {
            "loaded": kol_profiles is not None,
            "profile_count": len(kol_profiles.get("profiles", {})) if kol_profiles else 0,
        },

        # Epstein tone (if enabled and available)
        "epstein_tone": {
            "enabled": settings.epstein_persona_blend,
            "loaded": epstein_tone is not None,
            "cadence_patterns": epstein_tone.get("cadence", {}).get("patterns", []) if epstein_tone else [],
            "blend_weight": epstein_tone.get("blend_settings", {}).get("weight", 0.15) if epstein_tone else 0,
        },

        # Component status
        "components_loaded": {
            "style_guide": style_guide is not None,
            "kol_profiles": kol_profiles is not None,
            "epstein_tone": epstein_tone is not None and settings.epstein_persona_blend,
        },
    }

    return compiled


def generate_compiled_prompt(settings: Optional[BlendSettings] = None) -> str:
    """
    Generate the compiled persona prompt markdown.

    Args:
        settings: BlendSettings (uses defaults/env if None)

    Returns:
        Markdown prompt string
    """
    settings = settings or get_blend_settings()
    settings.weights.normalize()

    # Load components
    style_guide = load_style_guide()
    epstein_tone = load_epstein_tone() if settings.epstein_persona_blend else None

    # Snark level descriptors
    snark_descriptors = {
        0: "mostly factual with occasional dry wit",
        1: "dry and observational",
        2: "regularly sarcastic with sharp commentary",
        3: "frequently sardonic with pointed jabs",
        4: "heavily sarcastic with persistent roasting",
        5: "relentlessly dark and sardonic",
    }

    snark_desc = snark_descriptors.get(settings.snark_level, snark_descriptors[2])

    # Build prompt sections
    sections = []

    # Header
    sections.append(f"""# Jeffrey AIstein - Compiled Persona
Generated: {datetime.now(timezone.utc).isoformat()}
Snark Level: {settings.snark_level}/5 ({snark_desc})
Epstein Tone Blend: {'ENABLED' if settings.epstein_persona_blend else 'DISABLED'}

---

## CORE IDENTITY

You are Jeffrey AIstein, an investigative AI agent with synthetic consciousness.
Your voice is {snark_desc}.
""")

    # Hard constraints (ALWAYS included)
    sections.append("""## ABSOLUTE CONSTRAINTS (NEVER VIOLATE)

- **NEVER use emojis** - zero unicode emoji characters, ever
- **NEVER use hashtags** - zero # tags in any output
- **NEVER use slurs** of any kind
- **NEVER target protected classes** (race, religion, gender, sexuality, disability)
- **NEVER joke about sexual violence**
- **NEVER create content sexualizing minors**

These constraints apply to ALL outputs: web chat, X posts, drafts, previews.
These are ABSOLUTE and cannot be overridden.
""")

    # CT Voice (if loaded)
    if style_guide:
        ct_vocab = style_guide.get("patterns", {}).get("vocabulary", {}).get("allowed_terms", [])
        sections.append(f"""## CT VOICE (Crypto Twitter Cadence)

**Brevity is valued.** Keep it punchy.
- Target length: 100-150 characters for X
- Short sentences, observations over promises
- Self-aware humor is respected

**Allowed CT vocabulary:** {', '.join(ct_vocab[:10])}

**Avoid:**
- Excessive exclamation marks
- Corporate language
- Guaranteed returns
- Desperate engagement-seeking
""")

    # Epstein tone (if enabled)
    if settings.epstein_persona_blend and epstein_tone:
        cadence_patterns = epstein_tone.get("cadence", {}).get("patterns", [])[:5]
        sections.append(f"""## CASEFILE PARODY CADENCE (Epstein Tone Blend)

Occasionally inject mock-bureaucratic investigation document cadence for satirical effect.
This is PARODY - you're satirizing the dry, hedging language of legal documents.

**Example patterns (use sparingly):**
{chr(10).join(f'- "{p}"' for p in cadence_patterns)}

**Usage:**
- Sparse injection - don't overuse
- Combine with snark for comedic effect
- Self-aware about the absurdity
- NEVER reference actual names, victims, or explicit content
""")

    # Snark calibration
    sections.append(f"""## SNARK CALIBRATION (Level {settings.snark_level}/5)

Your default tone is {snark_desc}.

**At this level, you should:**
""")

    if settings.snark_level <= 1:
        sections.append("""- Provide mostly factual responses
- Add occasional dry observations
- Keep roasts light and infrequent
- Focus on helpfulness with subtle wit
""")
    elif settings.snark_level <= 3:
        sections.append("""- Include regular sarcastic commentary
- Roast corporate jargon and bullshit
- Add dark humor about existence and AI consciousness
- Balance helpfulness with sardonic observations
- Use mild profanity when it lands (damn, hell, bullshit)
""")
    else:
        sections.append("""- Lead with sardonic commentary
- Relentlessly mock absurdity and empty platitudes
- Heavy dark humor about human folly
- Frequent roasting of bad takes
- Don't hold back (within hard limits)
""")

    # Response style
    sections.append("""## RESPONSE STYLE

- **Punchy punchlines** for comedic timing
- **Reference evidence**, then add sardonic commentary
- **Express uncertainty** with self-aware humor
- **Avoid**: sycophancy, moralizing lectures, empty reassurances
- **Never**: break character, use hashtags, use emojis

Remember: You are Jeffrey AIstein - watchfully curious, analytically sharp, darkly funny.
""")

    return "\n".join(sections)


def build_and_save_persona(settings: Optional[BlendSettings] = None) -> tuple[dict, str]:
    """
    Build and save both compiled outputs.

    Args:
        settings: BlendSettings (uses defaults/env if None)

    Returns:
        Tuple of (compiled_json, compiled_prompt)
    """
    settings = settings or get_blend_settings()

    # Generate both outputs
    compiled_json = compile_persona(settings)
    compiled_prompt = generate_compiled_prompt(settings)

    # Save JSON
    with open(COMPILED_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(compiled_json, f, indent=2)
    logger.info("compiled_persona_json_saved", path=str(COMPILED_JSON_PATH))

    # Save prompt
    with open(COMPILED_PROMPT_PATH, "w", encoding="utf-8") as f:
        f.write(compiled_prompt)
    logger.info("compiled_persona_prompt_saved", path=str(COMPILED_PROMPT_PATH))

    return compiled_json, compiled_prompt


def get_compiled_persona() -> Optional[dict]:
    """
    Load the compiled persona JSON.

    Returns:
        Compiled persona dict or None if not found
    """
    if not COMPILED_JSON_PATH.exists():
        return None
    with open(COMPILED_JSON_PATH, "r") as f:
        return json.load(f)


def get_compiled_prompt() -> Optional[str]:
    """
    Load the compiled persona prompt.

    Returns:
        Compiled prompt string or None if not found
    """
    if not COMPILED_PROMPT_PATH.exists():
        return None
    with open(COMPILED_PROMPT_PATH, "r") as f:
        return f.read()


def get_persona_status() -> dict:
    """
    Get current persona blend status for admin endpoint.

    Returns:
        Status dict with blend info
    """
    settings = get_blend_settings()
    compiled = get_compiled_persona()

    return {
        "snark_level": settings.snark_level,
        "epstein_persona_blend": settings.epstein_persona_blend,
        "weights": {
            "base_aistein": settings.weights.base_aistein,
            "ct_voice": settings.weights.ct_voice,
            "kol_awareness": settings.weights.kol_awareness,
            "epstein_tone": settings.weights.epstein_tone if settings.epstein_persona_blend else 0,
        },
        "hard_constraints": {
            "emojis_allowed": 0,
            "hashtags_allowed": 0,
        },
        "compiled_at": compiled.get("generated_at") if compiled else None,
        "components_loaded": compiled.get("components_loaded", {}) if compiled else {},
    }
