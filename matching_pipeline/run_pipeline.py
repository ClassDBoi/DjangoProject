"""AUSME matching pipeline: generate research topics with a local language model and match
researchers to funding opportunities. Run from the repository root.

Steps (each writes to matching_pipeline/runs/<run>/):

  python matching_pipeline/run_pipeline.py prepare-papers           # -> runs/papers/units.jsonl
  python matching_pipeline/run_pipeline.py prepare-opportunities    # -> runs/opportunities/units.jsonl
  python matching_pipeline/run_pipeline.py generate --run papers           (~20 s per paper)
  python matching_pipeline/run_pipeline.py generate --run opportunities    (~30 s per section)
  python matching_pipeline/run_pipeline.py match                    # -> runs/matches/matches.json

Then load the matches into the database (from the Django environment):

  python manage.py import_matches matching_pipeline/runs/matches/matches.json --apply

Generation is resumable: stop with Ctrl+C and run the same command to continue.
--mock checks that everything runs without Ollama or the embedding model (output is meaningless).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from common import RUNS_DIR, load_client_data, load_config  # noqa: E402
import generate  # noqa: E402
import inputs  # noqa: E402
import match  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("step", choices=["prepare-papers", "prepare-opportunities", "generate", "match"])
    parser.add_argument("--run", help="generate: which run to process (papers or opportunities)")
    parser.add_argument("--papers-run", default="papers", help="match: run with the paper keywords")
    parser.add_argument("--opps-run", default="opportunities", help="match: run with the opportunity topics")
    parser.add_argument("--out", default="matches", help="match: output run folder name")
    parser.add_argument("--limit", type=int, help="generate: only the first N units (quick check)")
    parser.add_argument("--mock", action="store_true", help="run without Ollama or the embedding model")
    args = parser.parse_args()

    config = load_config()

    if args.step == "prepare-papers":
        manifest = inputs.prepare_papers(config["generation"], RUNS_DIR / "papers")
        print(f"{manifest['paper_units']} papers prepared "
              f"({manifest['papers_skipped_short_or_missing_abstract']} skipped: abstract missing or too short).")

    elif args.step == "prepare-opportunities":
        result = inputs.prepare_opportunities(config["generation"], RUNS_DIR / "opportunities")
        for doc in result["docs"]:
            print(f"  opp-{doc['opp_id']:>7}  {doc['source']:<44} kept {doc['kept_words']:>5} words  "
                  f"windows {doc['windows']}  {doc['title'][:45]}")
        m = result["manifest"]
        print(f"{m['opportunity_units']} sections from {m['opportunity_docs']} opportunities; "
              f"skipped (too little text): {', '.join(m['skipped_opportunities']) or 'none'}.\n"
              f"Keep/drop decisions: {RUNS_DIR / 'opportunities' / 'sections'}")

    elif args.step == "generate":
        if args.run not in ("papers", "opportunities"):
            sys.exit("generate needs --run papers or --run opportunities")
        generate.run_generation(RUNS_DIR / args.run, config, args.limit, args.mock)

    elif args.step == "match":
        subset, _ = load_client_data()
        out = match.run_matching(RUNS_DIR / args.papers_run, RUNS_DIR / args.opps_run, RUNS_DIR / args.out,
                                 config, subset, args.mock)
        print(f"Matches written to {out / 'matches.json'} (summary: {out / 'match_report.md'}).\n"
              "Load them with:  python manage.py import_matches "
              f"{(out / 'matches.json').relative_to(Path.cwd()) if out.is_relative_to(Path.cwd()) else out} --apply")


if __name__ == "__main__":
    main()
