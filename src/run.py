"""Single-run driver: ingest -> search -> answer -> judge.

Usage (from the repository root, Windows PowerShell):

    # 0) sanity check the environment and the cost projection, spends nothing
    python -m src.run --estimate --conversations 0 --limit 40

    # 1) baseline: Mem0 with LLM fact extraction ON (official default)
    python -m src.run --backend mem0 --infer 1 --conversations 0 --limit 40 --stage all

    # 2) two more trials for variance (ingest is reused, only answer+judge repeat)
    python -m src.run --backend mem0 --infer 1 --conversations 0 --limit 40 --trial 2 --stage eval
    python -m src.run --backend mem0 --infer 1 --conversations 0 --limit 40 --trial 3 --stage eval

    # 3) modification A: extraction OFF (cheap ingest: embeddings only)
    python -m src.run --backend mem0 --infer 0 --conversations 0 --limit 40 --stage all

    # 4) full-context baseline for the relative token/latency claim
    python -m src.run --backend fullctx --conversations 0 --limit 40 --stage all

    # 5) aggregate everything into results/summary.md
    python -m src.summarize
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

from tqdm import tqdm

from . import config, locomo, prompts
from .backend import build_backend
from .llm import BudgetExceeded, CostTracker, LLM, balance_usd, percentile


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Mem0 / LOCOMO reproducibility harness")
    parser.add_argument("--project", default="repro", help="run namespace, used in result paths")
    parser.add_argument("--backend", default="mem0", choices=["mem0", "fullctx"])
    parser.add_argument("--infer", type=int, default=1, help="1 = LLM extraction ON (baseline), 0 = OFF (modification A)")
    parser.add_argument("--conversations", default="0", help="comma separated LOCOMO conversation indices")
    parser.add_argument("--limit", type=int, default=40, help="max questions per conversation")
    parser.add_argument("--categories", default="1,2,3,4")
    parser.add_argument("--cutoffs", default="10,200", help="retrieval cuts evaluated, official default is 10,20,50,200")
    parser.add_argument("--top-k", type=int, default=config.OFFICIAL_TOP_K)
    parser.add_argument("--trial", type=int, default=1)
    parser.add_argument("--stage", default="all", choices=["all", "ingest", "eval"])
    parser.add_argument("--reuse-trial", type=int, default=None, help="reuse retrieval from this trial (saves cost, keeps comparability)")
    parser.add_argument("--out", default=str(config.ROOT / "results"))
    parser.add_argument("--force-ingest", action="store_true")
    parser.add_argument("--estimate", action="store_true", help="print cost projection and exit")
    return parser.parse_args()


def tag_for(args: argparse.Namespace) -> str:
    if args.backend == "fullctx":
        return f"{args.project}_fullctx"
    return f"{args.project}_mem0_{'ext' if args.infer else 'raw'}"


# ---------------------------------------------------------------------------
# cost projection (uses no API quota)
# ---------------------------------------------------------------------------
def estimate(args: argparse.Namespace, dataset: list[dict]) -> None:
    conv_ids = [int(c) for c in args.conversations.split(",")]
    categories = [int(c) for c in args.categories.split(",")]
    cutoffs = [int(c) for c in args.cutoffs.split(",")]

    turns = 0
    questions = 0
    for conv_idx in conv_ids:
        entry = dataset[conv_idx]
        turns += sum(len(t) for _, _, t in locomo.sorted_sessions(entry["conversation"]))
        questions += len(locomo.questions_in_scope(entry, categories, args.limit))

    # Rough per-call token model, documented so the numbers can be audited.
    ingest_calls = turns if args.backend == "mem0" and args.infer else 0
    ingest_in = ingest_calls * 1400
    ingest_out = ingest_calls * 150
    eval_calls = questions * len(cutoffs) * 2  # answer + judge
    eval_in = eval_calls * 1600
    eval_out = eval_calls * 90

    total_in = ingest_in + eval_in
    total_out = ingest_out + eval_out
    cost = (
        total_in / 1_000_000 * config.PRICE_IN_PER_MTOK
        + total_out / 1_000_000 * config.PRICE_OUT_PER_MTOK
    )

    print("=" * 66)
    print(f"PROJECTION  backend={args.backend} infer={args.infer} trial={args.trial}")
    print(f"  conversations   : {conv_ids}")
    print(f"  turns to ingest : {turns}  -> {ingest_calls} mem0.add() calls")
    print(f"  questions       : {questions}  x cutoffs {cutoffs}")
    print(f"  LLM calls       : ~{ingest_calls + eval_calls}")
    print(f"  tokens          : ~{total_in/1000:.0f}K in / {total_out/1000:.0f}K out")
    print(f"  est. cost       : ~${cost:.2f}   cap=${config.BUDGET_CAP_USD:.2f}")
    balance = balance_usd()
    if balance is not None:
        print(f"  balance now     : ${balance:.2f}")
        print(f"  balance after   : ~${balance - cost:.2f}")
    print("=" * 66)
    print("Per-call token figures are modelled, not measured; they are printed so")
    print("the projection itself can be audited against the first real run.")


# ---------------------------------------------------------------------------
# main pipeline
# ---------------------------------------------------------------------------
def main() -> None:
    args = parse_args()
    dataset = locomo.load_dataset(locomo.download_dataset())

    if args.estimate:
        estimate(args, dataset)
        return

    categories = [int(c) for c in args.categories.split(",")]
    conv_ids = [int(c) for c in args.conversations.split(",")]
    cutoffs = [int(c) for c in args.cutoffs.split(",")]
    tag = tag_for(args)

    # Hard limit discovered during the smoke test: mem0 v3 opens a global
    # telemetry Qdrant store at ~/.mem0/migrations_qdrant, so a second
    # ``Memory`` instance in the same process dies with
    # "Storage folder ... is already accessed by another instance of Qdrant
    # client". One configuration per process is therefore a hard constraint,
    # not a style choice.
    if args.backend == "mem0" and len(conv_ids) > 1:
        raise SystemExit(
            "mem0 allows only ONE Memory instance per process (global Qdrant store).\n"
            "Run one conversation per invocation, e.g. --conversations 0, then --conversations 1."
        )

    # full-context returns one giant blob: extra cutoffs would only repeat it
    if args.backend == "fullctx":
        cutoffs = [max(cutoffs)]

    out_dir = Path(args.out) / tag
    out_dir.mkdir(parents=True, exist_ok=True)
    vector_dir = Path(args.out) / "vectorstore" / tag

    backend = build_backend(args.backend, vector_dir, infer=bool(args.infer))
    answerer = LLM()
    judge = LLM()
    tracker = CostTracker(label=f"{tag}_t{args.trial}")
    balance_before = balance_usd()

    run_meta = {
        "tag": tag,
        "backend": args.backend,
        "infer": bool(args.infer) if args.backend == "mem0" else None,
        "trial": args.trial,
        "conversations": conv_ids,
        "limit": args.limit,
        "categories": categories,
        "cutoffs": cutoffs,
        "top_k": args.top_k,
        "llm_model": config.LLM_MODEL,
        "embedder": f"{config.EMBEDDER_PROVIDER}:{config.EMBEDDER_MODEL}",
        "temperature": config.TEMPERATURE,
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "mem0_version": _mem0_version(),
    }
    (out_dir / f"run_t{args.trial}.json").write_text(json.dumps(run_meta, indent=2), encoding="utf-8")

    try:
        for conv_idx in conv_ids:
            entry = dataset[conv_idx]
            conversation = entry["conversation"]
            ref_date = locomo.reference_date(conversation)

            if args.stage in ("all", "ingest"):
                _ingest(args, backend, out_dir, conv_idx, conversation)

            if args.stage in ("all", "eval"):
                # Preflight: an empty store does not raise, it scores 0 for every
                # question and yields a perfectly plausible-looking table. That
                # happened once (``fullctx`` keeps its transcript in process
                # memory, so ``--stage eval`` alone evaluated 120 questions
                # against nothing). Fail loudly instead of measuring a vacuum.
                stored = backend.count(conv_idx)
                if not stored:
                    raise SystemExit(
                        f"refusing to evaluate conv {conv_idx}: the store reports {stored} memories.\n"
                        f"Run '{backend.name}' with --stage all (or ingest first). Scoring an empty\n"
                        "store produces numbers that look like a finding but are an artefact."
                    )
                _evaluate(
                    args=args,
                    backend=backend,
                    answerer=answerer,
                    judge=judge,
                    tracker=tracker,
                    entry=entry,
                    conv_idx=conv_idx,
                    ref_date=ref_date,
                    categories=categories,
                    cutoffs=cutoffs,
                    out_dir=out_dir,
                )
    except BudgetExceeded as exc:
        print(f"\n[STOP] budget guard: {exc}")
    finally:
        cost_path = out_dir / f"cost_t{args.trial}.json"
        payload = {
            "run": run_meta,
            "usage": tracker.as_dict(),
            "balance_before_usd": balance_before,
            "balance_after_usd": balance_usd(),
            "backend_adaptations": getattr(backend, "adaptations", []),
        }
        cost_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"\n[cost] ${tracker.cost_usd:.3f} | {tracker.calls} calls -> {cost_path}")
        if payload["backend_adaptations"]:
            print("[warn] backend signature adaptations were needed:")
            for note in payload["backend_adaptations"]:
                print("   -", note)


def _ingest(args, backend, out_dir: Path, conv_idx: int, conversation: dict) -> None:
    marker = out_dir / f"ingest_conv{conv_idx}.json"
    # The marker is a promise that the store survives the process. ``fullctx``
    # holds its transcript in memory only, so for that backend the marker would
    # be a lie: a restart would skip ingest and then evaluate an empty store.
    persistent = getattr(backend, "persistent", True)
    if persistent and marker.exists() and not args.force_ingest:
        print(f"[ingest] conv {conv_idx}: already ingested, skipping ({marker.name})")
        return

    chunks = list(locomo.iter_chunks(conversation, config.CHUNK_SIZE))
    started = time.monotonic()
    failed = 0
    for session_key, date_str, epoch, messages in tqdm(chunks, desc=f"ingest conv{conv_idx}", leave=True):
        try:
            backend.add(conv_idx, messages, {"session": session_key, "date": date_str, "epoch": epoch})
        except Exception as exc:  # noqa: BLE001 - counted, then reported
            failed += 1
            if failed <= 3:
                print(f"\n[ingest] failure ({session_key}): {type(exc).__name__}: {exc}")
    elapsed = time.monotonic() - started

    payload = {
        "conversation": conv_idx,
        "chunks": len(chunks),
        "failed": failed,
        "seconds": round(elapsed, 1),
        "stored": backend.count(conv_idx),
        "user_id": backend.user_id(conv_idx),
    }
    if persistent:
        marker.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"[ingest] conv {conv_idx}: {len(chunks)} chunks, {failed} failed, {elapsed:.0f}s, stored={payload['stored']}")


def _evaluate(args, backend, answerer, judge, tracker, entry, conv_idx, ref_date, categories, cutoffs, out_dir) -> None:
    pairs = locomo.questions_in_scope(entry, categories, args.limit)
    for qi, qa in tqdm(pairs, desc=f"eval conv{conv_idx}", leave=True):
        qid = f"conv{conv_idx}_q{qi}"
        qpath = out_dir / f"{qid}_t{args.trial}.json"
        if qpath.exists():
            continue

        reuse_path = out_dir / f"{qid}_t{args.reuse_trial}.json" if args.reuse_trial else None
        if reuse_path and reuse_path.exists():
            memories = json.loads(reuse_path.read_text(encoding="utf-8")).get("retrieved", [])
            search_latency_ms = None
        else:
            started = time.monotonic()
            try:
                memories = backend.search(conv_idx, qa["question"], limit=args.top_k)
            except Exception as exc:  # noqa: BLE001 - a failed query scores 0, it must not abort
                print(f"\n[eval] {qid} search failed: {type(exc).__name__}: {exc}")
                memories = []
            search_latency_ms = round((time.monotonic() - started) * 1000, 1)

        category = qa["category"]
        gold = prompts.preprocess_answer(category, qa.get("answer", ""))
        record = {
            "qid": qid,
            "conversation": conv_idx,
            "category": category,
            "category_name": config.CATEGORY_NAMES.get(category, "unknown"),
            "question": qa["question"],
            "gold_answer": gold,
            "evidence": qa.get("evidence", []),
            "reference_date": ref_date,
            "retrieved_count": len(memories),
            "search_latency_ms": search_latency_ms,
            "retrieved": memories,
            "cutoffs": {},
        }

        for cutoff in cutoffs:
            sliced = memories[:cutoff]
            try:
                answer_text, pt, ct, latency = answerer.chat(
                    prompts.get_answer_prompt(qa["question"], sliced, ref_date)
                )
            except Exception as exc:  # noqa: BLE001
                record["cutoffs"][str(cutoff)] = {"error": f"{type(exc).__name__}: {exc}"}
                continue
            tracker.record("answer", pt, ct, latency)

            if "ANSWER:" in answer_text:
                answer_text = answer_text.rsplit("ANSWER:", 1)[-1].strip()

            # A transient transport failure here used to abort the whole run and
            # lose every remaining question, so the judge is guarded per cutoff.
            try:
                verdict, jpt, jct, jlatency = judge.chat_json(
                    prompts.get_judge_prompt(qa["question"], gold, answer_text),
                    system=prompts.JUDGE_SYSTEM_PROMPT,
                )
            except Exception as exc:  # noqa: BLE001
                record["cutoffs"][str(cutoff)] = {
                    "generated_answer": answer_text,
                    "error": f"judge {type(exc).__name__}: {exc}",
                }
                continue
            tracker.record("judge", jpt, jct, jlatency)
            label = str(verdict.get("label", "")).upper()
            record["cutoffs"][str(cutoff)] = {
                "generated_answer": answer_text,
                "judgment": label or "ERROR",
                "correct": label == "CORRECT",
                "reason": verdict.get("reasoning", ""),
                "memories_evaluated": len(sliced),
                "answer_prompt_tokens": pt,
                "answer_completion_tokens": ct,
                "judge_prompt_tokens": jpt,
                "judge_completion_tokens": jct,
                "answer_latency_s": round(latency, 3),
                "judge_latency_s": round(jlatency, 3),
            }

        qpath.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")


def _mem0_version() -> str:
    try:
        import importlib.metadata as md

        return md.version("mem0ai")
    except Exception:  # noqa: BLE001
        return "unknown"


if __name__ == "__main__":
    main()
