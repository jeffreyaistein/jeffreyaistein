#!/usr/bin/env python3
"""
KOL Profile Generator

Generates knowledge artifacts from kol_data.json:
- docs/knowledge/KOL_PROFILES_SUMMARY.md (human-readable)
- apps/api/services/persona/kol_profiles.json (machine-readable)

Usage:
    python scripts/generate_kol_profiles.py
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from collections import Counter


def sanitize_cube_references(text) -> str:
    """Replace CUBE references with AIstein."""
    if not text:
        return ""
    if isinstance(text, list):
        text = ", ".join(str(t) for t in text)
    if not isinstance(text, str):
        text = str(text)
    return re.sub(r'\bCUBE\b', 'AIstein', text, flags=re.IGNORECASE)


def extract_risk_flags(notes: dict) -> list[str]:
    """Extract risk flags from profile notes."""
    flags = []

    # Check personality summary for warning signs
    personality = notes.get("personality_summary", "").lower()
    tone = notes.get("tone", "").lower()

    if "controversial" in personality or "controversial" in tone:
        flags.append("controversial_content")
    if "aggressive" in tone:
        flags.append("aggressive_tone")
    if "shill" in personality:
        flags.append("potential_shill")
    if "scam" in personality or "rug" in personality:
        flags.append("mentioned_scams")

    # Check engagement playbook for avoid topics
    playbook = notes.get("engagement_playbook", {})
    avoid = playbook.get("avoid_topics", "")
    if isinstance(avoid, list):
        avoid = " ".join(str(a) for a in avoid)
    if avoid and "politic" in avoid.lower():
        flags.append("political_sensitivity")

    return flags


def generate_profiles(input_path: Path) -> tuple[list[dict], dict]:
    """Generate profile data from kol_data.json."""
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    profiles = []
    category_counts = Counter()
    credibility_sum = 0
    credibility_count = 0

    for record in data:
        handle = record.get("handle", "unknown")
        category = record.get("category", "unknown")

        # Parse notes
        notes_raw = record.get("notes", {})
        if isinstance(notes_raw, str):
            try:
                notes = json.loads(notes_raw)
            except json.JSONDecodeError:
                notes = {}
        else:
            notes = notes_raw

        # Extract key fields
        credibility = notes.get("credibility_score", 5)
        credibility_sum += credibility
        credibility_count += 1

        # Categorize
        for cat in category.split("|"):
            category_counts[cat.strip()] += 1

        # Build profile
        profile = {
            "handle": handle,
            "category": category,
            "credibility_score": credibility,
            "tone": sanitize_cube_references(notes.get("tone", "")),
            "personality_summary": sanitize_cube_references(notes.get("personality_summary", ""))[:200],
            "engagement_notes": {
                "best_approach": sanitize_cube_references(
                    notes.get("engagement_playbook", {}).get("best_approach", "")
                )[:150],
                "topics_respond_to": sanitize_cube_references(
                    notes.get("engagement_playbook", {}).get("topics_they_respond_to", "")
                )[:100],
                "avoid_topics": sanitize_cube_references(
                    notes.get("engagement_playbook", {}).get("avoid_topics", "")
                )[:100],
                "reply_style": sanitize_cube_references(
                    notes.get("engagement_playbook", {}).get("ideal_reply_style", "")
                )[:100],
            },
            "risk_flags": extract_risk_flags(notes),
            "influence_reach": notes.get("influence_reach", "unknown"),
        }

        profiles.append(profile)

    # Sort by credibility (highest first)
    profiles.sort(key=lambda x: x["credibility_score"], reverse=True)

    stats = {
        "total_profiles": len(profiles),
        "avg_credibility": round(credibility_sum / credibility_count, 1) if credibility_count else 0,
        "category_breakdown": dict(category_counts.most_common(10)),
        "high_credibility_count": sum(1 for p in profiles if p["credibility_score"] >= 8),
    }

    return profiles, stats


def generate_markdown(profiles: list[dict], stats: dict, output_path: Path):
    """Generate KOL_PROFILES_SUMMARY.md."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    content = f"""# Jeffrey AIstein - KOL Profiles Summary

> **Generated**: {datetime.now(timezone.utc).isoformat()}
> **Total Profiles**: {stats['total_profiles']}
> **Average Credibility**: {stats['avg_credibility']}/10

---

## Overview

This document summarizes the {stats['total_profiles']} KOL (Key Opinion Leader) profiles analyzed from Crypto Twitter.
These profiles inform AIstein's engagement strategy when replying to or mentioning these accounts.

---

## Category Breakdown

| Category | Count |
|----------|-------|
"""
    for cat, count in stats["category_breakdown"].items():
        content += f"| {cat} | {count} |\n"

    content += f"""
---

## High Credibility KOLs (8+/10)

These accounts are considered highly credible and influential:

| Handle | Score | Tone | Key Approach |
|--------|-------|------|--------------|
"""

    for p in profiles:
        if p["credibility_score"] >= 8:
            tone = p["tone"][:20] + "..." if len(p["tone"]) > 20 else p["tone"]
            approach = p["engagement_notes"]["best_approach"][:40] + "..." if len(p["engagement_notes"]["best_approach"]) > 40 else p["engagement_notes"]["best_approach"]
            content += f"| @{p['handle']} | {p['credibility_score']} | {tone} | {approach} |\n"

    content += """
---

## Engagement Guidelines

When interacting with known KOLs:

1. **Check credibility first** - Higher credibility = more careful engagement
2. **Match their tone** - Aggressive accounts expect directness, chill accounts prefer casual
3. **Respect avoid topics** - Each profile has topics to avoid
4. **Use their preferred style** - Reply style varies by account

---

## Risk Flags Legend

| Flag | Meaning |
|------|---------|
| `controversial_content` | Account posts controversial takes |
| `aggressive_tone` | Expect direct/confrontational replies |
| `potential_shill` | May promote projects aggressively |
| `mentioned_scams` | Has discussed scams/rugs |
| `political_sensitivity` | Avoid political topics |

---

## Sample Profiles

"""

    # Add top 5 profiles as detailed examples
    for i, p in enumerate(profiles[:5], 1):
        content += f"""### {i}. @{p['handle']}

- **Credibility**: {p['credibility_score']}/10
- **Category**: {p['category']}
- **Tone**: {p['tone']}
- **Personality**: {p['personality_summary']}
- **Best Approach**: {p['engagement_notes']['best_approach']}
- **Risk Flags**: {', '.join(p['risk_flags']) if p['risk_flags'] else 'None'}

"""

    content += """---

## Integration

This data is available programmatically at:
- `services/persona/kol_profiles.json`

Use `get_kol_profile(handle)` to look up a specific account before replying.

---

*Generated by Jeffrey AIstein KOL Pipeline*
"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"Generated: {output_path}")


def generate_json(profiles: list[dict], stats: dict, output_path: Path):
    """Generate kol_profiles.json."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Create lookup-friendly structure
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "version": "1.0",
        "stats": stats,
        "profiles_by_handle": {p["handle"]: p for p in profiles},
        "high_credibility": [p["handle"] for p in profiles if p["credibility_score"] >= 8],
        "handles_by_category": {},
    }

    # Group by category
    for p in profiles:
        for cat in p["category"].split("|"):
            cat = cat.strip()
            if cat not in output["handles_by_category"]:
                output["handles_by_category"][cat] = []
            output["handles_by_category"][cat].append(p["handle"])

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"Generated: {output_path}")


def main():
    """Generate KOL profile artifacts."""
    # Paths
    script_dir = Path(__file__).parent.parent  # apps/api
    apps_dir = script_dir.parent  # apps/

    input_path = apps_dir / "data" / "raw" / "kol_data.json"
    md_output = apps_dir / "docs" / "knowledge" / "KOL_PROFILES_SUMMARY.md"
    json_output = script_dir / "services" / "persona" / "kol_profiles.json"

    print("=" * 60)
    print("JEFFREY AISTEIN - KOL PROFILE GENERATOR")
    print("=" * 60)
    print()

    if not input_path.exists():
        print(f"ERROR: {input_path} not found")
        print("Run build_style_guide.py first or place raw data files.")
        return

    print(f"Reading: {input_path}")
    profiles, stats = generate_profiles(input_path)

    print(f"Profiles parsed: {stats['total_profiles']}")
    print(f"Avg credibility: {stats['avg_credibility']}/10")
    print(f"High credibility (8+): {stats['high_credibility_count']}")
    print()

    # Generate outputs
    generate_markdown(profiles, stats, md_output)
    generate_json(profiles, stats, json_output)

    print()
    print("=" * 60)
    print("COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
