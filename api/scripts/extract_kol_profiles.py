#!/usr/bin/env python3
"""
KOL Profile Extractor

Extracts KOL personality and engagement data from kol_data.json
and generates profile artifacts for persona integration.

Outputs:
- docs/knowledge/KOL_PROFILES_SUMMARY.md (human-readable)
- services/persona/kol_profiles.json (machine-readable)

Usage:
    cd apps/api && python scripts/extract_kol_profiles.py
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def sanitize_cube_refs(text: str) -> str:
    """Replace CUBE references with AIstein in analysis fields."""
    if not text:
        return text
    return re.sub(r"\bCUBE\b", "AIstein", text, flags=re.IGNORECASE)


def extract_key_traits(notes: dict) -> list[str]:
    """Extract 2-3 key traits from personality analysis."""
    traits = []

    # From tone
    tone = notes.get("tone", "")
    tone_parts = [t.strip() for t in tone.split("|") if t.strip()]
    if tone_parts:
        # Take first 2 tone traits
        traits.extend(tone_parts[:2])

    # From category (passed in separately if needed)
    return traits


def extract_engagement_notes(playbook: dict) -> str:
    """Extract short engagement notes from playbook."""
    if not playbook:
        return ""

    best_approach = playbook.get("best_approach", "")
    topics = playbook.get("topics_they_respond_to", [])

    notes = []
    if best_approach:
        # First sentence only
        first_sentence = best_approach.split(".")[0]
        notes.append(sanitize_cube_refs(first_sentence))

    if topics:
        topics_str = ", ".join(topics[:3])
        notes.append(f"Topics: {topics_str}")

    return ". ".join(notes) if notes else ""


def extract_risk_flags(notes: dict, playbook: dict) -> list[str]:
    """Extract risk flags for engagement."""
    flags = []

    # Low credibility
    cred = notes.get("credibility_score", 5)
    if cred <= 3:
        flags.append("low_credibility")
    elif cred >= 8:
        flags.append("high_credibility")

    # Check for controversial indicators
    avoid_topics = playbook.get("avoid_topics", []) if playbook else []
    if any("politic" in t.lower() for t in avoid_topics):
        flags.append("avoid_politics")
    if any("controver" in t.lower() for t in avoid_topics):
        flags.append("avoid_controversy")

    # Collab potential
    collab = playbook.get("collab_potential", "") if playbook else ""
    if collab == "low":
        flags.append("low_collab_potential")
    elif collab == "high":
        flags.append("high_collab_potential")

    return flags


def process_kol_data(input_path: Path) -> list[dict]:
    """Process kol_data.json and extract profile summaries."""
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    profiles = []

    for record in data:
        handle = record.get("handle", "unknown")
        category = record.get("category", "")
        notes_raw = record.get("notes", {})

        # Parse notes
        if isinstance(notes_raw, str):
            try:
                notes = json.loads(notes_raw)
            except json.JSONDecodeError:
                notes = {}
        else:
            notes = notes_raw

        playbook = notes.get("engagement_playbook", {})

        # Extract fields
        profile = {
            "handle": handle,
            "credibility_score": notes.get("credibility_score", 5),
            "influence_reach": notes.get("influence_reach", "unknown"),
            "tone": sanitize_cube_refs(notes.get("tone", "")),
            "key_traits": extract_key_traits(notes),
            "engagement_notes": extract_engagement_notes(playbook),
            "risk_flags": extract_risk_flags(notes, playbook),
            "category": sanitize_cube_refs(category),
            "topics": playbook.get("topics_they_respond_to", [])[:3] if playbook else [],
            "avoid": playbook.get("avoid_topics", [])[:3] if playbook else [],
        }

        profiles.append(profile)

    return profiles


def generate_markdown(profiles: list[dict], output_path: Path):
    """Generate KOL_PROFILES_SUMMARY.md."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Sort by credibility score descending
    sorted_profiles = sorted(profiles, key=lambda p: p["credibility_score"], reverse=True)

    content = f"""# Jeffrey AIstein - KOL Profile Intelligence

> **Generated**: {datetime.now(timezone.utc).isoformat()}
> **Source**: kol_data.json analysis
> **Total Profiles**: {len(profiles)}

---

## High-Credibility KOLs (Score 8-10)

These profiles are highly credible and worth engaging carefully.

| Handle | Score | Influence | Key Traits | Notes |
|--------|-------|-----------|------------|-------|
"""
    high_cred = [p for p in sorted_profiles if p["credibility_score"] >= 8]
    for p in high_cred[:20]:  # Top 20
        traits = ", ".join(p["key_traits"][:2]) if p["key_traits"] else "-"
        notes = p["engagement_notes"][:60] + "..." if len(p["engagement_notes"]) > 60 else p["engagement_notes"]
        content += f"| @{p['handle']} | {p['credibility_score']} | {p['influence_reach']} | {traits} | {notes} |\n"

    content += """
---

## Medium-Credibility KOLs (Score 5-7)

Standard engagement protocols apply.

| Handle | Score | Influence | Risk Flags |
|--------|-------|-----------|------------|
"""
    med_cred = [p for p in sorted_profiles if 5 <= p["credibility_score"] <= 7]
    for p in med_cred[:30]:  # Top 30
        flags = ", ".join(p["risk_flags"]) if p["risk_flags"] else "-"
        content += f"| @{p['handle']} | {p['credibility_score']} | {p['influence_reach']} | {flags} |\n"

    content += """
---

## Low-Credibility KOLs (Score 1-4)

Exercise caution - potential for misinformation or pump-and-dump schemes.

| Handle | Score | Risk Flags |
|--------|-------|------------|
"""
    low_cred = [p for p in sorted_profiles if p["credibility_score"] < 5]
    for p in low_cred[:20]:  # Top 20
        flags = ", ".join(p["risk_flags"]) if p["risk_flags"] else "-"
        content += f"| @{p['handle']} | {p['credibility_score']} | {flags} |\n"

    content += """
---

## Engagement Guidelines

### When Replying to Known KOLs

1. **High credibility (8+)**: Engage substantively, match their expertise level
2. **Medium credibility (5-7)**: Standard engagement, maintain AIstein's sardonic tone
3. **Low credibility (1-4)**: Brief responses, avoid endorsing claims

### Risk Flag Meanings

| Flag | Meaning |
|------|---------|
| `low_credibility` | History of questionable calls or behavior |
| `high_credibility` | Respected voice in the space |
| `avoid_politics` | Don't engage on political topics |
| `avoid_controversy` | Steer clear of drama |
| `low_collab_potential` | Unlikely to respond well to engagement |
| `high_collab_potential` | Open to interaction and collaboration |

---

*Intelligence compiled for Jeffrey AIstein persona system*
"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)

    return output_path


def generate_json(profiles: list[dict], output_path: Path):
    """Generate kol_profiles.json for persona integration."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Compact format for runtime use
    compact_profiles = {}
    for p in profiles:
        compact_profiles[p["handle"].lower()] = {
            "cred": p["credibility_score"],
            "reach": p["influence_reach"],
            "traits": p["key_traits"][:2],
            "notes": p["engagement_notes"][:100] if p["engagement_notes"] else "",
            "flags": p["risk_flags"],
            "topics": p["topics"][:3],
            "avoid": p["avoid"][:3],
        }

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "profile_count": len(profiles),
        "profiles": compact_profiles,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    return output_path


def main():
    """Run profile extraction."""
    # Paths
    script_dir = Path(__file__).parent.parent  # apps/api
    apps_dir = script_dir.parent  # apps

    input_path = apps_dir / "data" / "raw" / "kol_data.json"
    md_output = apps_dir / "docs" / "knowledge" / "KOL_PROFILES_SUMMARY.md"
    json_output = script_dir / "services" / "persona" / "kol_profiles.json"

    print("=" * 60)
    print("KOL PROFILE EXTRACTOR")
    print("=" * 60)
    print()
    print(f"Input: {input_path}")
    print(f"MD Output: {md_output}")
    print(f"JSON Output: {json_output}")
    print()

    # Check input exists
    if not input_path.exists():
        print(f"ERROR: {input_path} not found")
        print("Run raw data setup first. See docs/RAW_DATA_SETUP.md")
        return 1

    # Process
    print("Processing profiles...")
    profiles = process_kol_data(input_path)
    print(f"  Profiles extracted: {len(profiles)}")

    # Stats
    high_cred = sum(1 for p in profiles if p["credibility_score"] >= 8)
    med_cred = sum(1 for p in profiles if 5 <= p["credibility_score"] <= 7)
    low_cred = sum(1 for p in profiles if p["credibility_score"] < 5)
    print(f"  High credibility (8+): {high_cred}")
    print(f"  Medium credibility (5-7): {med_cred}")
    print(f"  Low credibility (1-4): {low_cred}")
    print()

    # Generate outputs
    print("Generating markdown...")
    generate_markdown(profiles, md_output)
    print(f"  Created: {md_output}")
    print(f"  Size: {md_output.stat().st_size:,} bytes")
    print()

    print("Generating JSON...")
    generate_json(profiles, json_output)
    print(f"  Created: {json_output}")
    print(f"  Size: {json_output.stat().st_size:,} bytes")
    print()

    print("=" * 60)
    print("EXTRACTION COMPLETE")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    exit(main())
