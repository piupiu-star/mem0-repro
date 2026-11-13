"""Paired comparison between two configurations on the same questions.

A 10-point gap on 40 questions is not self-evidently real. Because both
configurations answer the *same* questions, the correct test is paired, not a
two-sample proportion test: only the questions that flip carry information.

Reports the 2x2 discordance table, the exact McNemar p-value, and the paired
bootstrap 95% interval for the accuracy difference.

Usage:
    python -m tools.paired --a repro_mem0_ext --b repro_mem0_raw --cutoff 200
"""

from __future__ import annotations

import argparse
import glob
import json
import math
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"


def _load(tag: str, cutoff: str) -> dict[str, bool]:
    cells: dict[str, bool] = {}
    for path in sorted(glob.glob(str(RESULTS / tag / "conv*_q*_t1.json"))):
        record = json.loads(Path(path).read_text(encoding="utf-8"))
        score = (record.get("cutoffs") or {}).get(cutoff) or {}
        if "error" in score:
            continue
        cells[record["qid"]] = bool(score.get("correct"))
    return cells


def _binom_two_sided(b: int, c: int) -> float:
    """Exact McNemar p-value (binomial test on the discordant pairs)."""
    n = b + c
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, k) for k in range(0, min(b, c) + 1)) / 2**n
    return min(1.0, 2 * tail)


def _bootstrap_ci(diffs: list[int], rounds: int = 20000, seed: int = 0) -> tuple[float, float]:
    rng = random.Random(seed)
    n = len(diffs)
    stats = []
    for _ in range(rounds):
        sample = [diffs[rng.randrange(n)] for _ in range(n)]
        stats.append(100 * sum(sample) / n)
    stats.sort()
    return stats[int(0.025 * rounds)], stats[int(0.975 * rounds)]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--a", required=True, help="baseline tag")
    parser.add_argument("--b", required=True, help="modified tag")
    parser.add_argument("--cutoff", default="200")
    args = parser.parse_args()

    a = _load(args.a, args.cutoff)
    b = _load(args.b, args.cutoff)
    common = sorted(set(a) & set(b))
    if not common:
        raise SystemExit("no overlapping questions - check the tags and cutoff")

    both_right = sum(1 for q in common if a[q] and b[q])
    a_only = sum(1 for q in common if a[q] and not b[q])
    b_only = sum(1 for q in common if b[q] and not a[q])
    both_wrong = sum(1 for q in common if not a[q] and not b[q])
    n = len(common)

    acc_a = 100 * (both_right + a_only) / n
    acc_b = 100 * (both_right + b_only) / n
    diffs = [int(b[q]) - int(a[q]) for q in common]
    low, high = _bootstrap_ci(diffs)
    p = _binom_two_sided(a_only, b_only)

    print(f"cutoff top_{args.cutoff}, n = {n} paired questions\n")
    print(f"  {'':22s} {'right':>6s} {'wrong':>6s} {'accuracy':>10s}")
    print(f"  {args.a:22s} {both_right + a_only:6d} {both_wrong + b_only:6d} {acc_a:9.1f}%")
    print(f"  {args.b:22s} {both_right + b_only:6d} {both_wrong + a_only:6d} {acc_b:9.1f}%")
    print(f"\n  both correct      : {both_right}")
    print(f"  both wrong        : {both_wrong}")
    print(f"  only '{args.a}'   : {a_only}   <- {args.b} lost these")
    print(f"  only '{args.b}'   : {b_only}   <- {args.b} gained these")
    print(f"\n  delta accuracy    : {acc_b - acc_a:+.1f} pp")
    print(f"  bootstrap 95% CI  : [{low:+.1f}, {high:+.1f}] pp")
    print(f"  McNemar exact p   : {p:.3f}  (discordant pairs = {a_only + b_only})")
    verdict = "difference is NOT established at this sample size" if p >= 0.05 else "difference is statistically supported"
    print(f"  reading           : {verdict}")


if __name__ == "__main__":
    main()
