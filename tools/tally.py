"""Print raw per-category tallies so the summary tables can be cross-checked."""

from __future__ import annotations

import glob
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = sorted(glob.glob(str(ROOT / "results" / "repro_mem0_ext" / "conv*_q*_t*.json")))


def main() -> None:
    records = [json.loads(Path(p).read_text(encoding="utf-8")) for p in FILES]
    print(f"files: {len(records)}")
    print("category id  ->", dict(Counter(r["category"] for r in records)))
    print("category name->", dict(Counter(r["category_name"] for r in records)))

    for cutoff in sorted({k for r in records for k in r["cutoffs"]}, key=int):
        buckets: dict[str, list[int]] = defaultdict(lambda: [0, 0])
        for record in records:
            score = record["cutoffs"].get(cutoff, {})
            if "error" in score:
                continue
            cell = buckets[f"{record['category']}:{record['category_name']}"]
            cell[1] += 1
            cell[0] += int(bool(score.get("correct")))
        ok = sum(v[0] for v in buckets.values())
        n = sum(v[1] for v in buckets.values())
        print(f"\n-- top_{cutoff}: {ok}/{n} = {100 * ok / max(1, n):.1f}%")
        for key, (correct, total) in sorted(buckets.items()):
            print(f"   {key:20s} {correct:3d}/{total:3d} = {100 * correct / max(1, total):5.1f}%")

    print("\nper-question at top_200:")
    for record in records:
        score = record["cutoffs"].get("200", {})
        mark = "OK " if score.get("correct") else "BAD"
        print(f"  {mark} {record['qid']:12s} cat={record['category']} {record['category_name']:12s} "
              f"gold={str(record['gold_answer'])[:40]!r} got={str(score.get('generated_answer'))[:40]!r}")


if __name__ == "__main__":
    main()
