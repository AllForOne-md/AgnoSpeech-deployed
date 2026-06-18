"""One-CLI reproducibility entry point.

    python -m agnospeech.cli reproduce --csv <corpus.csv> --out web/public/scorecard.json

Regenerates the entire scorecard JSON from one invocation, with pinned seeds and
single-threaded BLAS. No number lives only in a notebook.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .repro import GLOBAL_SEED, pin
from .scorecard import write_scorecard

_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_FIXTURES = _ROOT / "fixtures" / "fixtures.json"
_DEFAULT_OUT = _ROOT / "web" / "public" / "scorecard.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agnospeech")
    sub = parser.add_subparsers(dest="cmd", required=True)

    rep = sub.add_parser("reproduce", help="regenerate the scorecard JSON")
    rep.add_argument("--csv", required=True, help="path to the corpus CSV")
    rep.add_argument("--fixtures", default=str(_DEFAULT_FIXTURES))
    rep.add_argument("--out", default=str(_DEFAULT_OUT))
    rep.add_argument("--seed", type=int, default=GLOBAL_SEED)
    rep.add_argument("--bootstrap", type=int, default=2000)
    rep.add_argument("--quiet", action="store_true")

    con = sub.add_parser("conformance", help="run the hard-rule conformance suite")
    con.add_argument("--check", action="store_true", help="run all assertions")
    con.add_argument("--allow-cloud-on-raw", action="store_true",
                     help="break a rule live: route raw text to a cloud endpoint")

    args = parser.parse_args(argv)
    if args.cmd == "conformance":
        from .conformance import run as run_conformance

        results = run_conformance(allow_cloud_on_raw=args.allow_cloud_on_raw)
        all_pass = all(a.passed for a in results)
        for a in results:
            tag = "GREEN" if a.passed else "RED"
            print(f"[{tag}] {a.name}\n        {a.detail}")
        print(f"\n{'PASSED' if all_pass else 'FAILED'} · "
              f"{sum(a.passed for a in results)}/{len(results)} green")
        return 0 if all_pass else 1
    if args.cmd == "reproduce":
        pin(args.seed)
        card = write_scorecard(
            args.csv, args.fixtures, args.out,
            seed=args.seed, bootstrap_b=args.bootstrap,
        )
        if not args.quiet:
            lv = card["levels"]
            rec = card["dominance"]["recommended_level"]
            print(f"wrote {args.out}")
            print(f"corpus: {card['corpus']['n_posts']} posts, "
                  f"{card['corpus']['n_authors']} authors (closed-world)")
            print(f"baseline F1 raw={card['baselines']['f1_raw']}, "
                  f"majority={card['baselines']['f1_majority']}, "
                  f"attack acc={card['baselines']['privacy_original_acc']}")
            for code in card["level_order"]:
                d = lv[code]
                print(f"  {code}: F1={d['macro_f1']:.3f}  "
                      f"attack(static/adaptive)={d['attack_acc_static']:.3f}/"
                      f"{d['attack_acc_adaptive']:.3f}  "
                      f"TO(optimistic/honest)={d['to_optimistic']:.3f}/{d['to_honest']:.3f}")
            op = card["operating_point"]
            print(f"operating point: L3 @ intensity={op['intensity']} "
                  f"(recommended level {rec})")
            print(f"degenerate optimum refused: "
                  f"{card['curve']['degenerate_optimum_is_refused']} "
                  f"(global max TO={card['curve']['global_max_to']['to']})")
            print(json.dumps(card["dominance"]["win_prob"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
