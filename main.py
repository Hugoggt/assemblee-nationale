"""
Entry point — runs all three data fetch scripts in sequence.
Outputs are saved to the output/ folder.
"""

import sys
import traceback

import fetch_deputes
import fetch_scrutins
import fetch_dossiers
import classify_themes


def run_step(label: str, fn):
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    try:
        fn()
        print(f"  ✓ Done")
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        traceback.print_exc()
        sys.exit(1)


def main():
    run_step("1/4 — Deputies (députés)", fetch_deputes.main)
    run_step("2/4 — Votes (scrutins)", fetch_scrutins.main)
    run_step("3/4 — Legislative dossiers", fetch_dossiers.main)
    run_step("4/4 — Theme classification", classify_themes.main)

    print("\n" + "="*60)
    print("  All done! Files saved to output/")
    print("="*60)


if __name__ == "__main__":
    main()
