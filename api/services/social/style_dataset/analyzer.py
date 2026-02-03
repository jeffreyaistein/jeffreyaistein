"""
Jeffrey AIstein - KOL Style Analyzer

Analyzes collected tweets to derive style patterns.
Generates STYLE_GUIDE_DERIVED.md and style_guide.json.
"""

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import structlog

logger = structlog.get_logger()

# Output paths
DEFAULT_DATA_DIR = Path(__file__).parent.parent.parent.parent / "data"
DEFAULT_DOCS_DIR = Path(__file__).parent.parent.parent.parent.parent / "docs"
DEFAULT_PERSONA_DIR = Path(__file__).parent.parent.parent / "persona"

# CT vocabulary patterns
CT_VOCAB = {
    "greetings": ["gm", "gn", "wagmi", "ngmi", "lfg"],
    "signals": ["alpha", "nfa", "dyor", "iykyk", "based"],
    "market": ["pump", "dump", "moon", "rekt", "rug", "ape"],
    "tribal": ["fren", "ser", "anon", "degen", "ct"],
}

# Emoji categories
EMOJI_PATTERN = re.compile(
    "["
    "\U0001F600-\U0001F64F"  # emoticons
    "\U0001F300-\U0001F5FF"  # symbols & pictographs
    "\U0001F680-\U0001F6FF"  # transport & map
    "\U0001F700-\U0001F77F"  # alchemical
    "\U0001F780-\U0001F7FF"  # geometric
    "\U0001F800-\U0001F8FF"  # arrows
    "\U0001F900-\U0001F9FF"  # supplemental
    "\U0001FA00-\U0001FA6F"  # chess
    "\U0001FA70-\U0001FAFF"  # symbols
    "\U00002702-\U000027B0"  # dingbats
    "\U000024C2-\U0001F251"
    "]+",
    flags=re.UNICODE,
)


@dataclass
class TweetStats:
    """Statistics for a single tweet."""
    length: int
    word_count: int
    has_emoji: bool
    emoji_count: int
    has_link: bool
    has_hashtag: bool
    has_mention: bool
    ct_vocab_used: list = field(default_factory=list)
    ends_with_link: bool = False
    is_question: bool = False
    is_short: bool = False  # < 50 chars


@dataclass
class StyleProfile:
    """Aggregated style profile from analyzed tweets."""
    # Length patterns
    avg_length: float = 0.0
    median_length: float = 0.0
    short_tweet_pct: float = 0.0  # % under 50 chars

    # Structure patterns
    emoji_usage_pct: float = 0.0
    avg_emoji_per_tweet: float = 0.0
    link_usage_pct: float = 0.0
    hashtag_usage_pct: float = 0.0
    mention_usage_pct: float = 0.0
    question_pct: float = 0.0
    ends_with_link_pct: float = 0.0

    # Vocabulary
    ct_vocab_frequency: dict = field(default_factory=dict)
    top_phrases: list = field(default_factory=list)

    # Derived rules
    rules: list = field(default_factory=list)


class StyleAnalyzer:
    """
    Analyzes collected tweets to derive style patterns.

    Produces:
    - STYLE_GUIDE_DERIVED.md: Human-readable style guide
    - style_guide.json: Machine-readable for persona integration
    """

    def __init__(
        self,
        data_dir: Optional[Path] = None,
        docs_dir: Optional[Path] = None,
        persona_dir: Optional[Path] = None,
    ):
        self.data_dir = data_dir or DEFAULT_DATA_DIR
        self.docs_dir = docs_dir or DEFAULT_DOCS_DIR
        self.persona_dir = persona_dir or DEFAULT_PERSONA_DIR

    def _analyze_tweet(self, text: str) -> TweetStats:
        """Analyze a single tweet and extract stats."""
        text_clean = text.strip()

        # Basic stats
        length = len(text_clean)
        words = text_clean.split()
        word_count = len(words)

        # Emoji detection
        emojis = EMOJI_PATTERN.findall(text_clean)
        has_emoji = len(emojis) > 0
        emoji_count = len(emojis)

        # Link detection
        has_link = "http" in text_clean.lower() or "t.co" in text_clean.lower()
        ends_with_link = bool(re.search(r'https?://\S+$', text_clean))

        # Hashtag detection
        has_hashtag = "#" in text_clean

        # Mention detection
        has_mention = "@" in text_clean

        # CT vocabulary
        text_lower = text_clean.lower()
        ct_vocab_used = []
        for category, terms in CT_VOCAB.items():
            for term in terms:
                # Word boundary match
                if re.search(rf'\b{term}\b', text_lower):
                    ct_vocab_used.append(term)

        # Question detection
        is_question = "?" in text_clean

        # Short tweet
        is_short = length < 50

        return TweetStats(
            length=length,
            word_count=word_count,
            has_emoji=has_emoji,
            emoji_count=emoji_count,
            has_link=has_link,
            has_hashtag=has_hashtag,
            has_mention=has_mention,
            ct_vocab_used=ct_vocab_used,
            ends_with_link=ends_with_link,
            is_question=is_question,
            is_short=is_short,
        )

    def analyze_dataset(self, input_file: Path) -> StyleProfile:
        """
        Analyze a JSONL dataset of tweets.

        Args:
            input_file: Path to style_tweets.jsonl

        Returns:
            StyleProfile with aggregated patterns
        """
        tweets_stats: list[TweetStats] = []
        ct_vocab_counter: Counter = Counter()

        with open(input_file, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    record = json.loads(line)
                    text = record.get("text", "")
                    if text:
                        stats = self._analyze_tweet(text)
                        tweets_stats.append(stats)
                        ct_vocab_counter.update(stats.ct_vocab_used)
                except json.JSONDecodeError:
                    continue

        if not tweets_stats:
            logger.warning("no_tweets_analyzed")
            return StyleProfile()

        total = len(tweets_stats)

        # Calculate aggregates
        lengths = [s.length for s in tweets_stats]
        avg_length = sum(lengths) / total
        sorted_lengths = sorted(lengths)
        median_length = sorted_lengths[total // 2]

        short_count = sum(1 for s in tweets_stats if s.is_short)
        emoji_count = sum(1 for s in tweets_stats if s.has_emoji)
        total_emojis = sum(s.emoji_count for s in tweets_stats)
        link_count = sum(1 for s in tweets_stats if s.has_link)
        hashtag_count = sum(1 for s in tweets_stats if s.has_hashtag)
        mention_count = sum(1 for s in tweets_stats if s.has_mention)
        question_count = sum(1 for s in tweets_stats if s.is_question)
        ends_link_count = sum(1 for s in tweets_stats if s.ends_with_link)

        # Build profile
        profile = StyleProfile(
            avg_length=round(avg_length, 1),
            median_length=median_length,
            short_tweet_pct=round(short_count / total * 100, 1),
            emoji_usage_pct=round(emoji_count / total * 100, 1),
            avg_emoji_per_tweet=round(total_emojis / total, 2),
            link_usage_pct=round(link_count / total * 100, 1),
            hashtag_usage_pct=round(hashtag_count / total * 100, 1),
            mention_usage_pct=round(mention_count / total * 100, 1),
            question_pct=round(question_count / total * 100, 1),
            ends_with_link_pct=round(ends_link_count / total * 100, 1),
            ct_vocab_frequency=dict(ct_vocab_counter.most_common(20)),
        )

        # Derive rules from patterns
        profile.rules = self._derive_rules(profile)

        logger.info(
            "analysis_complete",
            tweets_analyzed=total,
            avg_length=profile.avg_length,
            emoji_pct=profile.emoji_usage_pct,
        )

        return profile

    def _derive_rules(self, profile: StyleProfile) -> list[str]:
        """Derive style rules from profile patterns."""
        rules = []

        # Length rules
        if profile.avg_length < 100:
            rules.append("Keep tweets SHORT - average under 100 characters")
        elif profile.avg_length < 150:
            rules.append("Moderate tweet length - aim for 100-150 characters")

        if profile.short_tweet_pct > 30:
            rules.append(f"{profile.short_tweet_pct:.0f}% of tweets are under 50 chars - brevity is valued")

        # Emoji rules
        if profile.emoji_usage_pct > 50:
            rules.append(f"Emojis are common ({profile.emoji_usage_pct:.0f}% of tweets) - use sparingly but appropriately")
        elif profile.emoji_usage_pct < 20:
            rules.append(f"Emojis are rare ({profile.emoji_usage_pct:.0f}%) - minimal emoji usage")

        # Link rules
        if profile.link_usage_pct > 40:
            rules.append(f"Links are frequent ({profile.link_usage_pct:.0f}%) - sharing content is valued")
        if profile.ends_with_link_pct > 20:
            rules.append("Tweets often END with links - link-last pattern")

        # Hashtag rules
        if profile.hashtag_usage_pct < 20:
            rules.append("Hashtags are RARE - avoid hashtag spam")

        # Question rules
        if profile.question_pct > 15:
            rules.append(f"Questions are common ({profile.question_pct:.0f}%) - engage with questions")

        # CT vocab rules
        if profile.ct_vocab_frequency:
            top_terms = list(profile.ct_vocab_frequency.keys())[:5]
            rules.append(f"Common CT vocabulary: {', '.join(top_terms)}")

        return rules

    def generate_markdown(
        self,
        profile: StyleProfile,
        output_path: Optional[Path] = None,
    ) -> Path:
        """
        Generate STYLE_GUIDE_DERIVED.md from profile.

        Args:
            profile: Analyzed style profile
            output_path: Optional custom output path

        Returns:
            Path to generated file
        """
        output = output_path or (self.docs_dir / "STYLE_GUIDE_DERIVED.md")
        output.parent.mkdir(parents=True, exist_ok=True)

        content = f"""# Jeffrey AIstein - Derived Style Guide

> **Generated**: {datetime.now(timezone.utc).isoformat()}
> **Source**: KOL Tweet Analysis
> **Purpose**: Output rewriting rules for X platform

---

## HARD BRAND RULES (Non-Negotiable)

These rules OVERRIDE any dataset statistics. They apply to ALL outputs:
- Web chat
- X timeline posts
- X replies
- Drafts and previews

| Rule | Allowed | Enforcement |
|------|---------|-------------|
| **Emojis** | **0% - NEVER** | Stripped at post-processing, validated |
| **Hashtags** | **0% - NEVER** | Stripped at post-processing, validated |

These are enforced at three layers:
1. **Persona prompt**: Explicit instruction to never use
2. **Post-processing**: `StyleRewriter.enforce_brand_rules()` strips any that appear
3. **Validation**: `StyleRewriter.validate_brand_rules()` fails if any remain

---

## Tweet Length Patterns

| Metric | Value |
|--------|-------|
| Average length | {profile.avg_length} chars |
| Median length | {profile.median_length} chars |
| Short tweets (<50 chars) | {profile.short_tweet_pct}% |

---

## Structure Patterns (Dataset Statistics)

| Pattern | Dataset Frequency | AIstein Rule |
|---------|-------------------|--------------|
| Uses emoji | {profile.emoji_usage_pct}% | **0% (FORBIDDEN)** |
| Avg emoji per tweet | {profile.avg_emoji_per_tweet} | **0 (FORBIDDEN)** |
| Contains link | {profile.link_usage_pct}% | Allowed |
| Ends with link | {profile.ends_with_link_pct}% | Allowed |
| Uses hashtag | {profile.hashtag_usage_pct}% | **0% (FORBIDDEN)** |
| Uses mention | {profile.mention_usage_pct}% | Allowed |
| Is question | {profile.question_pct}% | Allowed |

**Note**: Dataset statistics are for reference only. Hard brand rules override all derived patterns.

---

## CT Vocabulary Frequency

| Term | Count |
|------|-------|
"""
        for term, count in profile.ct_vocab_frequency.items():
            content += f"| {term} | {count} |\n"

        content += """
---

## Derived Style Rules

"""
        for i, rule in enumerate(profile.rules, 1):
            content += f"{i}. {rule}\n"

        content += """
---

## Application Guidelines

When generating ANY content (X or web), apply these rules:

1. **Brevity first** - If the message can be shorter, make it shorter
2. **No corporate speak** - Avoid formal language, buzzwords, marketing speak
3. **Tribal vocabulary** - Use CT terms naturally when appropriate
4. **Observations over promises** - Share insights, don't make guarantees
5. **Self-aware tone** - Acknowledge being AI with sardonic humor
6. **NEVER emojis** - Not a single one, ever, on any platform
7. **NEVER hashtags** - Not a single one, ever, on any platform

---

## Integration

This style guide is loaded by the persona system at:
`services/persona/loader.py`

The `style_guide.json` file contains machine-readable rules for output rewriting.

---

*Generated by Jeffrey AIstein Style Dataset Pipeline*
"""

        with open(output, "w", encoding="utf-8") as f:
            f.write(content)

        logger.info("markdown_generated", path=str(output))
        return output

    def generate_json(
        self,
        profile: StyleProfile,
        output_path: Optional[Path] = None,
    ) -> Path:
        """
        Generate style_guide.json from profile.

        Args:
            profile: Analyzed style profile
            output_path: Optional custom output path

        Returns:
            Path to generated file
        """
        output = output_path or (self.persona_dir / "style_guide.json")
        output.parent.mkdir(parents=True, exist_ok=True)

        guide = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": "kol_tweet_analysis",
            "version": "1.0",
            "patterns": {
                "length": {
                    "average": profile.avg_length,
                    "median": profile.median_length,
                    "target_max": 200,  # Derived target
                    "short_pct": profile.short_tweet_pct,
                },
                "structure": {
                    "emoji_pct": profile.emoji_usage_pct,
                    "avg_emoji": profile.avg_emoji_per_tweet,
                    "link_pct": profile.link_usage_pct,
                    "ends_with_link_pct": profile.ends_with_link_pct,
                    "hashtag_pct": profile.hashtag_usage_pct,
                    "question_pct": profile.question_pct,
                },
                "vocabulary": {
                    "ct_terms": profile.ct_vocab_frequency,
                    "allowed_terms": list(CT_VOCAB.get("greetings", [])) + list(CT_VOCAB.get("signals", [])),
                },
            },
            "rules": profile.rules,
            "rewriting": {
                "max_length": 280,
                "target_length": int(profile.avg_length * 1.2),  # Allow 20% more than average
                "avoid": [
                    "excessive hashtags",
                    "corporate language",
                    "guaranteed returns",
                    "excessive exclamation marks",
                ],
                "prefer": [
                    "short sentences",
                    "observations over promises",
                    "self-aware humor",
                    "tribal vocabulary when natural",
                ],
            },
        }

        with open(output, "w", encoding="utf-8") as f:
            json.dump(guide, f, indent=2)

        logger.info("json_generated", path=str(output))
        return output

    def run(self, input_file: Optional[Path] = None) -> dict:
        """
        Run full analysis pipeline.

        Args:
            input_file: Path to style_tweets.jsonl (default: data/style_tweets.jsonl)

        Returns:
            Dict with generated file paths
        """
        input_path = input_file or (self.data_dir / "style_tweets.jsonl")

        if not input_path.exists():
            raise FileNotFoundError(f"Dataset not found: {input_path}")

        logger.info("analysis_started", input=str(input_path))

        # Analyze
        profile = self.analyze_dataset(input_path)

        # Generate outputs
        md_path = self.generate_markdown(profile)
        json_path = self.generate_json(profile)

        return {
            "profile": profile,
            "markdown_path": str(md_path),
            "json_path": str(json_path),
        }


# CLI entry point
def main():
    """Run analyzer from command line."""
    import argparse

    parser = argparse.ArgumentParser(description="Analyze KOL tweets and generate style guide")
    parser.add_argument(
        "--input",
        type=Path,
        help="Input JSONL file (default: data/style_tweets.jsonl)",
    )

    args = parser.parse_args()

    analyzer = StyleAnalyzer()

    try:
        result = analyzer.run(args.input)
        print(f"\nAnalysis complete:")
        print(f"  Markdown: {result['markdown_path']}")
        print(f"  JSON: {result['json_path']}")
        print(f"\nKey patterns:")
        profile = result['profile']
        print(f"  Avg length: {profile.avg_length} chars")
        print(f"  Emoji usage: {profile.emoji_usage_pct}%")
        print(f"  Link usage: {profile.link_usage_pct}%")
        print(f"\nRules derived: {len(profile.rules)}")
    except FileNotFoundError as e:
        print(f"Error: {e}")
        print("Run the collector first to generate the dataset.")


if __name__ == "__main__":
    main()
