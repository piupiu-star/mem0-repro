"""Export curated raw excerpts so the report's claims can be checked by eye.

The aggregate tables say *how often* a configuration was wrong. This tool says
*what the model actually saw*, which is the only way to tell a retrieval failure
from an answering failure from a judging failure:

    python -m tools.evidence --tag repro_mem0_ext --category temporal --want wrong

Writes ``results/evidence/<tag>_<category>_<want>.md``. Nothing here calls an
API: it only re-reads the per-question JSON written by ``src/run.py``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"


def load(tag: str, trial: int, cutoff: int) -> list[dict]:
    out: list[dict] = []
    for path in sorted((RESULTS / tag).glob(f"conv*_q*_t{trial}.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        payload = (data.get("cutoffs") or {}).get(str(cutoff)) or {}
        if "error" in payload:
            continue
        out.append(
            {
                "qid": data["qid"],
                "category": data.get("category_name", "?"),
                "question": data["question"],
                "gold": data.get("gold_answer", ""),
                "answer": payload.get("generated_answer", ""),
                "correct": bool(payload.get("correct")),
                "reason": payload.get("reason", ""),
                "retrieved": data.get("retrieved") or [],
            }
        )
    return out


def render(rows: list[dict], tag: str, category: str, want: str, cutoff: int, limit: int) -> str:
    keep = [r for r in rows if r["category"] == category and (r["correct"] == (want == "right"))]
    lines = [
        f"# Evidence — {tag}, {category}, cutoff {cutoff}, showing {want} answers",
        "",
        f"{len(keep)} matching questions out of {len(rows)} in this configuration.",
        "Everything below is copied verbatim from the per-question JSON; nothing is paraphrased.",
        "",
    ]
    for r in keep[:limit]:
        lines.append(f"## {r['qid']} — {'CORRECT' if r['correct'] else 'WRONG'}")
        lines.append("")
        lines.append(f"**Question.** {r['question']}")
        lines.append("")
        lines.append(f"**Gold.** {r['gold']}")
        lines.append("")
        lines.append(f"**Generated.** {r['answer']}")
        lines.append("")
        lines.append(f"**Judge.** {r['reason']}")
        lines.append("")
        lines.append(f"**Retrieved memories (top 5 of {len(r['retrieved'])}).**")
        lines.append("")
        for mem in r["retrieved"][:5]:
            text = str(mem.get("memory", ""))
            created = mem.get("created_at") or "?"
            lines.append(f"- `{created}` {text}")
        lines.append("")
        lines.append("---")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", default="repro_mem0_ext")
    parser.add_argument("--trial", type=int, default=1)
    parser.add_argument("--cutoff", type=int, default=200)
    parser.add_argument("--category", default="temporal")
    parser.add_argument("--want", choices=["wrong", "right"], default="wrong")
    parser.add_argument("--limit", type=int, default=3)
    args = parser.parse_args()

    rows = load(args.tag, args.trial, args.cutoff)
    if not rows:
        raise SystemExit(f"no per-question files under results/{args.tag} for trial {args.trial}")

    out_dir = RESULTS / "evidence"
    out_dir.mkdir(parents=True, exist_ok=True)
    text = render(rows, args.tag, args.category, args.want, args.cutoff, args.limit)
    path = out_dir / f"{args.tag}_{args.category}_{args.want}.md"
    path.write_text(text, encoding="utf-8")
    print(f"{len(rows)} questions read -> {path}")


if __name__ == "__main__":
    main()
