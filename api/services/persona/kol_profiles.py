"""
Jeffrey AIstein - KOL Profile Loader

Loads KOL profile data for personalized engagement on X.
"""

import json
from pathlib import Path
from typing import Optional

import structlog

logger = structlog.get_logger()

# Profile JSON location
PROFILES_FILE = Path(__file__).parent / "kol_profiles.json"


class KOLProfile:
    """A single KOL profile with engagement context."""

    def __init__(
        self,
        handle: str,
        credibility: int,
        reach: str,
        traits: list[str],
        notes: str,
        flags: list[str],
        topics: list[str],
        avoid: list[str],
    ):
        self.handle = handle
        self.credibility = credibility
        self.reach = reach
        self.traits = traits
        self.notes = notes
        self.flags = flags
        self.topics = topics
        self.avoid = avoid

    @property
    def is_high_credibility(self) -> bool:
        """Check if this is a high-credibility KOL (8+)."""
        return self.credibility >= 8

    @property
    def is_low_credibility(self) -> bool:
        """Check if this is a low-credibility KOL (1-4)."""
        return self.credibility < 5

    def get_engagement_context(self) -> str:
        """
        Get engagement context for prompt injection.

        Returns guidance without exposing private profile data.
        """
        parts = []

        # Credibility tier guidance
        if self.is_high_credibility:
            parts.append(
                f"This is a respected voice in the space (credibility: {self.credibility}/10). "
                "Engage substantively and match their expertise level."
            )
        elif self.is_low_credibility:
            parts.append(
                f"Exercise caution with this account (credibility: {self.credibility}/10). "
                "Keep responses brief and avoid endorsing claims."
            )
        else:
            parts.append(
                f"Standard engagement (credibility: {self.credibility}/10). "
                "Maintain your sardonic tone."
            )

        # Traits context
        if self.traits:
            traits_str = ", ".join(self.traits[:2])
            parts.append(f"Their typical tone: {traits_str}.")

        # Engagement notes
        if self.notes:
            parts.append(f"Engagement tip: {self.notes}")

        # Risk flags
        if "avoid_politics" in self.flags:
            parts.append("Avoid political topics with this account.")
        if "avoid_controversy" in self.flags:
            parts.append("Steer clear of controversial subjects.")

        # Topics context
        if self.topics:
            topics_str = ", ".join(self.topics[:3])
            parts.append(f"Topics they respond well to: {topics_str}.")

        return " ".join(parts)


class KOLProfileLoader:
    """Loads and provides access to KOL profiles."""

    def __init__(self, profiles_path: Optional[Path] = None):
        self.profiles_path = profiles_path or PROFILES_FILE
        self._profiles: dict[str, KOLProfile] = {}
        self._loaded = False
        self._generated_at: Optional[str] = None
        self._load_profiles()

    def _load_profiles(self) -> None:
        """Load profiles from JSON file."""
        if not self.profiles_path.exists():
            logger.warning("kol_profiles_not_found", path=str(self.profiles_path))
            return

        try:
            with open(self.profiles_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Store metadata
            self._generated_at = data.get("generated_at")

            profiles_data = data.get("profiles", {})
            for handle, profile_data in profiles_data.items():
                self._profiles[handle.lower()] = KOLProfile(
                    handle=handle,
                    credibility=profile_data.get("cred", 5),
                    reach=profile_data.get("reach", "unknown"),
                    traits=profile_data.get("traits", []),
                    notes=profile_data.get("notes", ""),
                    flags=profile_data.get("flags", []),
                    topics=profile_data.get("topics", []),
                    avoid=profile_data.get("avoid", []),
                )

            self._loaded = True
            logger.info(
                "kol_profiles_loaded",
                count=len(self._profiles),
                source=str(self.profiles_path),
            )

        except Exception as e:
            logger.error("kol_profiles_load_failed", error=str(e))

    def get_profile(self, handle: str) -> Optional[KOLProfile]:
        """
        Get a KOL profile by handle.

        Args:
            handle: Twitter handle (with or without @)

        Returns:
            KOLProfile if found, None otherwise
        """
        # Normalize handle
        clean_handle = handle.lower().lstrip("@")
        return self._profiles.get(clean_handle)

    def is_known_kol(self, handle: str) -> bool:
        """Check if a handle is a known KOL."""
        return self.get_profile(handle) is not None

    def get_engagement_context(self, handle: str) -> Optional[str]:
        """
        Get engagement context for a handle.

        Args:
            handle: Twitter handle

        Returns:
            Context string for prompt injection, or None if unknown
        """
        profile = self.get_profile(handle)
        if profile:
            return profile.get_engagement_context()
        return None

    def is_available(self) -> bool:
        """Check if profiles were loaded successfully."""
        return self._loaded and len(self._profiles) > 0

    @property
    def profile_count(self) -> int:
        """Get the number of loaded profiles."""
        return len(self._profiles)

    def get_generated_at(self) -> Optional[str]:
        """Get the timestamp when the profiles were generated."""
        return self._generated_at


# Singleton instance
_kol_loader: Optional[KOLProfileLoader] = None


def get_kol_loader() -> KOLProfileLoader:
    """Get the KOL profile loader singleton."""
    global _kol_loader
    if _kol_loader is None:
        _kol_loader = KOLProfileLoader()
    return _kol_loader


def reset_kol_loader() -> None:
    """Reset the KOL loader singleton (for testing)."""
    global _kol_loader
    _kol_loader = None


def get_kol_context(handle: str) -> Optional[str]:
    """
    Convenience function to get KOL engagement context.

    Args:
        handle: Twitter handle

    Returns:
        Context string or None
    """
    loader = get_kol_loader()
    return loader.get_engagement_context(handle)
