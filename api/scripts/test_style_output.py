#!/usr/bin/env python3
"""
Jeffrey AIstein - Style Output Test Harness

Tests that the style guide and KOL context are being applied correctly.
This is a deterministic test - does NOT call the LLM.

Usage:
    python scripts/test_style_output.py --handle frankdegods --text "gm how are you doing today"
    python scripts/test_style_output.py --handle unknown_user --text "hello world"
    python scripts/test_style_output.py --text "testing without handle"

Output:
    - Final rewritten text
    - Character count (confirms <= 280)
    - No emoji confirmation
    - No hashtag confirmation
    - KOL context (if handle is known)
"""

import argparse
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.persona.style_rewriter import get_style_rewriter, StyleRewriter
from services.persona.kol_profiles import get_kol_loader


def test_style_output(handle: str | None, text: str) -> dict:
    """
    Test style output for given handle and text.

    Args:
        handle: Optional KOL handle (e.g., "frankdegods")
        text: Input text to process

    Returns:
        Dict with test results
    """
    results = {
        "input_text": text,
        "handle": handle,
        "output_text": "",
        "char_count": 0,
        "max_length": 280,
        "under_max_length": False,
        "contains_emoji": False,
        "contains_hashtag": False,
        "no_emoji": False,
        "no_hashtag": False,
        "kol_known": False,
        "kol_context": None,
        "style_guide_loaded": False,
        "all_checks_passed": False,
    }

    # Get rewriter and loader
    rewriter = get_style_rewriter()
    kol_loader = get_kol_loader()

    # Check style guide loaded
    results["style_guide_loaded"] = rewriter.is_available()

    # Rewrite text for X
    output_text = rewriter.rewrite_for_x(text)
    results["output_text"] = output_text
    results["char_count"] = len(output_text)
    results["under_max_length"] = len(output_text) <= 280

    # Check for emoji and hashtag
    results["contains_emoji"] = StyleRewriter.contains_emoji(output_text)
    results["contains_hashtag"] = StyleRewriter.contains_hashtag(output_text)
    results["no_emoji"] = not results["contains_emoji"]
    results["no_hashtag"] = not results["contains_hashtag"]

    # Check KOL context if handle provided
    if handle:
        results["kol_known"] = kol_loader.is_known_kol(handle)
        if results["kol_known"]:
            results["kol_context"] = kol_loader.get_engagement_context(handle)

    # All checks passed?
    results["all_checks_passed"] = (
        results["style_guide_loaded"]
        and results["under_max_length"]
        and results["no_emoji"]
        and results["no_hashtag"]
    )

    return results


def print_results(results: dict):
    """Print test results in a readable format."""
    print("=" * 60)
    print("STYLE OUTPUT TEST RESULTS")
    print("=" * 60)
    print()

    print(f"Input text:  {results['input_text']}")
    print(f"Handle:      {results['handle'] or '(none)'}")
    print()

    print("-" * 60)
    print("OUTPUT")
    print("-" * 60)
    print(f"Final text:  {results['output_text']}")
    print(f"Char count:  {results['char_count']} / {results['max_length']}")
    print()

    print("-" * 60)
    print("CHECKS")
    print("-" * 60)

    # Style guide
    status = "PASS" if results["style_guide_loaded"] else "FAIL"
    print(f"[{status}] Style guide loaded: {results['style_guide_loaded']}")

    # Length check
    status = "PASS" if results["under_max_length"] else "FAIL"
    print(f"[{status}] Under max length (280): {results['char_count']} chars")

    # Emoji check
    status = "PASS" if results["no_emoji"] else "FAIL"
    print(f"[{status}] No emoji: {results['no_emoji']}")

    # Hashtag check
    status = "PASS" if results["no_hashtag"] else "FAIL"
    print(f"[{status}] No hashtag: {results['no_hashtag']}")

    # KOL context
    if results["handle"]:
        status = "INFO"
        known_str = "YES" if results["kol_known"] else "NO"
        print(f"[{status}] KOL known: {known_str}")
        if results["kol_context"]:
            print()
            print("-" * 60)
            print("KOL CONTEXT (for prompt injection)")
            print("-" * 60)
            print(results["kol_context"])

    print()
    print("=" * 60)
    overall = "ALL CHECKS PASSED" if results["all_checks_passed"] else "SOME CHECKS FAILED"
    print(f"RESULT: {overall}")
    print("=" * 60)

    return results["all_checks_passed"]


def main():
    parser = argparse.ArgumentParser(
        description="Test style output for Jeffrey AIstein"
    )
    parser.add_argument(
        "--handle",
        type=str,
        default=None,
        help="KOL handle to test (e.g., frankdegods, rajgokal)"
    )
    parser.add_argument(
        "--text",
        type=str,
        required=True,
        help="Input text to process"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON instead of formatted text"
    )

    args = parser.parse_args()

    # Run test
    results = test_style_output(args.handle, args.text)

    if args.json:
        import json
        print(json.dumps(results, indent=2, default=str))
        sys.exit(0 if results["all_checks_passed"] else 1)
    else:
        passed = print_results(results)
        sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
