"""Audit tool: inspect stored memories and per-question records.

Two questions it answers, both of which must be settled before any accuracy
number is trusted:

1. How many memories are actually in the vector store?
   (``Memory.get_all()`` reports far fewer than ``search(top_k=200)`` returns,
   so the store is counted directly with the Qdrant client.)

2. When a question is scored WRONG, is the failure in retrieval, in answering,
   or in judging? Printing the retrieved slice next to the generated answer
   makes that visible without re-running anything.

Usage:
    python -m tools.inspect count
    python -m tools.inspect show --n 3
    python -m tools.inspect wrong --n 3
"""

from __future__ import annotations

import argparse
import glob
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN_DIR = ROOT / "results" / "repro_mem0_ext"
VECTOR_DIR = ROOT / "results" / "vectorstore" / "repro_mem0_ext"


def _records() -> list[dict]:
    return [json.loads(Path(p).read_text(encoding="utf-8")) for p in sorted(glob.glob(str(RUN_DIR / "conv0_q*_t1.json")))]


def cmd_count(_: argparse.Namespace) -> None:
    from qdrant_client import QdrantClient

    client = QdrantClient(path=str(VECTOR_DIR))
    for name in ("locomo_conv0", "locomo_conv0_entities"):
        try:
            print(f"{name}: {client.count(name, exact=True).count} points")
        except Exception as exc:  # noqa: BLE001
            print(f"{name}: unavailable ({type(exc).__name__}: {exc})")

    users: Counter = Counter()
    offset = None
    seen = 0
    while True:
        batch, offset = client.scroll("locomo_conv0", limit=256, offset=offset, with_payload=True)
        for point in batch:
            payload = point.payload or {}
            users[payload.get("user_id")] += 1
            seen += 1
            if seen <= 3:
                print(f"\n-- point {seen - 1} payload keys: {sorted(payload)}")
                print(f"   user_id={payload.get('user_id')!r}")
                print(f"   data={str(payload.get('data'))[:220]!r}")
        if offset is None:
            break
    client.close()
    print(f"\npayload user_id distribution over {seen} points: {dict(users)}")


def _print_record(record: dict, cutoff: str = "200") -> None:
    score = record["cutoffs"].get(cutoff, {})
    print("=" * 100)
    print(f"[{record['qid']}] cat={record['category_name']} correct={score.get('correct')} "
          f"memories_evaluated={score.get('memories_evaluated')}")
    print(f"Q : {record['question']}")
    print(f"G : {record['gold_answer']}")
    print(f"A : {score.get('generated_answer')}")
    print(f"J : {score.get('judgment')} -- {str(score.get('reason'))[:300]}")
    recalled = [m.get("memory", "") for m in record["retrieved"][:6]]
    print(f"retrieved top-6 ({record['retrieved_count']} total):")
    for text in recalled:
        print(f"   - {text[:160]}")


def cmd_show(args: argparse.Namespace) -> None:
    for record in _records()[: args.n]:
        _print_record(record, args.cutoff)


def cmd_wrong(args: argparse.Namespace) -> None:
    wrong = [r for r in _records() if not r["cutoffs"].get(args.cutoff, {}).get("correct")]
    print(f"{len(wrong)} wrong out of {len(_records())} at top-{args.cutoff}\n")
    for record in wrong[: args.n]:
        _print_record(record, args.cutoff)


def cmd_stats(_: argparse.Namespace) -> None:
    records = _records()
    by_cat: dict[str, Counter] = defaultdict(Counter)
    for record in records:
        for cutoff, score in record["cutoffs"].items():
            by_cat[record["category_name"]][cutoff] += int(bool(score.get("correct")))
            by_cat[record["category_name"]]["n"] += 1
    for name, counter in by_cat.items():
        n = counter["n"] // max(1, len({len(r["cutoffs"]) for r in records}))
        print(f"{name:12s} n~{n:3d} " + "  ".join(
            f"top{k}: {100 * counter[k] / max(1, n):5.1f}%" for k in sorted(counter, key=str) if k != "n"))
    errors = [(r["qid"], k, v.get("error")) for r in records for k, v in r["cutoffs"].items() if "error" in v]
    print(f"\nstage errors: {len(errors)}")
    for item in errors[:5]:
        print("  ", item)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("count").set_defaults(func=cmd_count)
    sub.add_parser("stats").set_defaults(func=cmd_stats)
    for name, func in (("show", cmd_show), ("wrong", cmd_wrong)):
        p = sub.add_parser(name)
        p.add_argument("--n", type=int, default=3)
        p.add_argument("--cutoff", default="200")
        p.set_defaults(func=func)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
