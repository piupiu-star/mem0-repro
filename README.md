# mem0-repro

Reproducibility study for **Mem0** (`mem0ai/mem0`), submitted for
FTEC5660 *Agentic AI for Business and FinTech* — Reproducibility Work.

Name: Xiuling PIAO · Student ID: 1155267871

---

## 1. Reproduction target card (frozen before any experiment)

| item | value |
|---|---|
| Upstream repo | https://github.com/mem0ai/mem0 |
| Eval suite | https://github.com/mem0ai/memory-benchmarks (git submodule of the above) |
| Paper | arXiv:2504.19413v1 (2025-04-28) — **v2 algorithm** |
| Repo HEAD at study time | **v3 "New Memory Algorithm" (Apr 2026)** — *not* the paper's algorithm |
| Benchmark | LOCOMO-10, a fixed subset (conversation 0, first N questions) |
| **R1 (primary, absolute)** | LOCOMO overall LLM-as-a-Judge accuracy → reported **92.5%** (README v3, managed platform) |
| **R2 (primary, relative)** | vs full-context: **>90% token saving**, **91% lower p95 latency** (paper abstract — arithmetic, not judge-based) |
| **R3 (finding)** | paper (v2) vs repo (v3) version drift → absolute numbers are not comparable across code lines |
| Controlled variables | extraction = answerer = judge = `deepseek-chat`, temperature 0; embedder `fastembed:BAAI/bge-small-en-v1.5`; cutoffs {10, 200}; 3 trials at top-200 for the two mem0 arms, 1 for the full-context baseline (its 99.2 % leaves no headroom to vary) |
| **Modification A** | `infer=False` — disable Mem0's LLM fact-extraction stage (ablation of the paper's core mechanism) |
| Fallback ladder | A → embedder swap → rerank off |
| Budget | measured: **$3.80** of tracked answer + judge billing across every run kept here — $1.97 for the three 120-question configurations, $1.74 for trials 2–3, $0.09 for one discarded run. A lower bound: Mem0's extraction calls inside `add()` bypass the tracker |

Why two reference numbers rather than one: the platform score (92.5) and the
paper's claims live on **different code lines**, and the authors state it
themselves:

> "Scores reflect Mem0's managed platform, which includes proprietary
> optimizations **not available in the open-source SDK**; open-source users
> should expect **directionally similar gains but not identical numbers**."

So the interesting question is not "is 92.5 true" but **how large the gap is,
and whether the direction survives**.

---

## 2. Install

Requires Python 3.11+, no Docker, no GPU.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install -r requirements.txt
python -m spacy download en_core_web_sm   # required by mem0ai[nlp]
```

Copy `.env.example` to `.env` and fill in your key:

```powershell
Copy-Item .env.example .env
```

Record the resolved versions — the report must cite them:

```powershell
python -c "import importlib.metadata as m; print('mem0ai', m.version('mem0ai'))"
pip freeze > results/pip-freeze.txt
```

---

## 3. Run

Everything is executed from the repository root.

```powershell
# cost projection only, spends nothing
python -m src.run --estimate --conversations 0 --limit 120

# baseline: Mem0 with LLM extraction ON (official default)
python -m src.run --backend mem0 --infer 1 --conversations 0 --limit 120 --stage all

# modification A: extraction OFF (ingest costs 0 LLM calls, embeddings are local)
python -m src.run --backend mem0 --infer 0 --conversations 0 --limit 120 --stage all

# full-context baseline, needed for the relative token / latency claim
python -m src.run --backend fullctx --conversations 0 --limit 120 --cutoffs 200 --stage all

# trials 2 and 3 at the paper's operating cutoff (ingest is reused)
.\tools\trials.ps1

# aggregate into results/summary.md and results/runs.csv
python -m src.summarize

# curated raw excerpts for the report's evidence section
python -m tools.evidence --tag repro_mem0_ext --category temporal --want wrong
```

`--limit 120` is not arbitrary: conversation 0 puts its single-hop block after
the multi-hop, temporal and open-domain blocks, so at `--limit 40` the single-hop
row simply cannot be reported. 120 questions covers all four scored categories.

### What the harness does

```
ingest (once per configuration)  ->  search -> answer -> judge (per trial)
```

| file | responsibility |
|---|---|
| `src/config.py` | every disclosed knob: models, temperature, prices, caps, reported numbers |
| `src/locomo.py` | dataset download + session parsing, mirroring the official runner (chunk size 1) |
| `src/prompts.py` | answer + judge prompts, **copied verbatim** from `mem0ai/memory-benchmarks` |
| `src/llm.py` | DeepSeek client, per-call token accounting, retries, budget guard |
| `src/backend.py` | `mem0` SDK backend and the `fullctx` baseline |
| `src/run.py` | orchestration, checkpointing, per-question JSON |
| `src/summarize.py` | `runs.csv` + `summary.md` (mean ± std, p50/p95, reported-vs-measured) |

Ingest runs **once per configuration**; trials 2–3 reuse the same vector store
and vary only the stochastic answer/judge stage. This keeps the 3-trial
variance estimate affordable and is disclosed as a design choice.

---

## 4. Deviations from the official pipeline

Each of these is a controlled, documented departure — not an accident.

| # | Official | Here | Why |
|---|---|---|---|
| 1 | Mem0 served over HTTP via `docker compose` (FastAPI + Qdrant) | `mem0.Memory.from_config` called directly | machine has no Docker; the SDK is the same code |
| 2 | `--answerer-model` default `gpt-5`, provider `openai` | `deepseek-chat` via `https://api.deepseek.com` | repo targets a paid/closed model; the brief explicitly permits substitution under Edge case A |
| 3 | `--judge-model` default `gpt-5` | `deepseek-chat` | **this changes the metric, not just the answerer**: the judge *is* the measuring instrument. The judge prompt text is byte-identical; the grader is not. See `REPORT.md` §2 |
| 4 | `text-embedding-3-small` | local `fastembed bge-small-en-v1.5` (384 dims) | DeepSeek exposes **no** embeddings endpoint, so this swap is forced rather than chosen |
| 5 | `benchmarks/locomo/run.py` (the authors' script) | `src/run.py`, a re-implementation of the same loop | the official entry point requires the Docker service (#1). Prompts and `preprocess_answer` are byte-identical copies and the memory-rendering glue was diffed against `get_answer_prompt`; that diff is the evidence of fidelity |
| 6 | cutoffs `10,20,50,200` | `10,200` | budget; the endpoint of the trade-off curve is what R2 needs |
| 7 | all 10 conversations, 1540 questions | conversation 0, first 120 questions | time budget; the subset is fixed, not sampled at random, and covers all four scored categories |

Consequence, stated in the report: **absolute scores are not directly
comparable to the paper because the underlying LLM differs.**

### 4.1 Controlled-variable record (required by the brief, "When you swap models")

> **Results are not directly comparable to the paper because the underlying LLM
> differs.**

| item | value | declared in |
|---|---|---|
| model name | `deepseek-chat` | `config.LLM_MODEL` |
| judge model | also `deepseek-chat` — one model serves extraction, answering **and** judging. The authors' `run.py` defaults the judge to `gpt-5`, so the grader differs even though the rubric does not | `config.LLM_MODEL` |
| provider | `deepseek` (OpenAI-compatible endpoint) | `config.mem0_config()` → `llm.provider` |
| base URL | `https://api.deepseek.com` | `config.LLM_BASE_URL` |
| temperature | `0.0`, identical for extraction, answering and judging | `config.TEMPERATURE` |
| max tokens | answer `600`, judge `120`, extraction `600` | `config.ANSWER_MAX_TOKENS`, `config.JUDGE_MAX_TOKENS` |
| top_p | **not set** — provider default. It is unset identically in every configuration, so it is a constant of the study rather than a controlled knob; this is an omission to note, not a hidden setting | — |
| embedder | `fastembed:BAAI/bge-small-en-v1.5` (384 dims) | `config.EMBEDDER_*` |
| prompt / template changes | **none to any prompt text.** `ANSWER_GENERATION_PROMPT`, the judge template, `JUDGE_SYSTEM_PROMPT`, `ANSWERER_MEMORY_LIMIT = 200` and `preprocess_answer` are byte-identical copies of `memory-benchmarks/benchmarks/locomo/prompts.py` | `src/prompts.py` |

The *glue* that renders retrieved memories into the answer prompt was
re-implemented, so that glue (not the prompt text) is where a silent divergence
could hide. It has been diffed against the authors' `get_answer_prompt`: the
`[:ANSWERER_MEMORY_LIMIT]` slice, the `created_at` sort, the
`"(<date>) <memory>"` line format and the date formatter all match, and no
`user_profile` is passed, matching the official call path. One mismatch was in
fact found this way and is recorded as diary row 9.

**Temperature 0 does not make the answer/judge stage deterministic** (batching,
float nondeterminism, MoE routing), which is why 3 trials are run rather than 1.

---

## 5. Results

**The report is [`REPORT.md`](REPORT.md).** Everything in it is generated here,
not typed by hand.

`python -m src.summarize` writes:

- `results/runs.csv` — one row per (configuration, trial, question, cutoff)
- `results/summary.md` — Table 1 accuracy, Table 1b by question type,
  Table 2 cost/latency, Table 3 reported vs measured, Table 4 paired test for the
  modification, plus the measured-subset decomposition
- `results/evidence/*.md` — curated raw excerpts (gold answer, generated answer,
  judge reason, retrieved memories) so the tables can be checked by eye

Headline, at top-200 (the authors' operating depth) on 120 questions, pooled over
three trials:

| | reported | measured |
|---|---|---|
| LoCoMo overall | 92.5 % | 65.3 % (± 0.5) |
| single-hop | 91.2 % | 96.5 % |
| multi-hop | 91.3 % | 84.4 % |
| open-domain | 72.7 % | 97.4 % |
| temporal | 92.0 % | **5.4 %** |
| token saving vs full-context | >90 % | 58.9 % |

The category figures are the top-200 rows of `runs.csv`. Table 1b in
`results/summary.md` averages the two cutoffs instead, so its per-category
percentages sit slightly lower than these.

The temporal collapse is traced to `mem0/memory/notices.py`: the OSS SDK refuses
the `timestamp` anchor that the authors' runner passes, so extraction resolves
every relative date against the wall clock. Set that one category aside and the
remaining 249 question instances score **92.0 % (229/249)**, against 92.5 %
reported. That subset is measured rather than reconstructed, so it assumes none
of the reported values it is being compared with.

The modification (`infer=False`) raises overall accuracy to **77.5 %**
(+12.2 pp; paired McNemar p < 0.001, 95 % CI [+8.3, +16.4] pooled over three
trials, and +12.5 / +12.5 / +11.7 per trial). 35 of the 44 extra correct answers
are temporal; open-domain moves by one question the wrong way (38/39 → 37/39),
which is noise at that n. See `REPORT.md` §5.

---

## 6. Data and licensing

- LOCOMO dataset: `snap-research/locomo`, downloaded automatically to
  `datasets/locomo10.json` (gitignored).
- Prompts and parsing logic: adapted from `mem0ai/memory-benchmarks`
  (Apache-2.0), attributed in `src/prompts.py` and `src/locomo.py`.
- API keys: never committed. `.env` is gitignored; only `.env.example` is
  tracked.

---

## 7. Debug diary — blockers already hit (verified on this machine)

These were found while wiring the harness up. They go straight into report
section 6, and each one is a generalisable lesson.

| # | Symptom | Root cause | Resolution |
|---|---|---|---|
| 1 | `RuntimeError: Storage folder ~/.mem0/migrations_qdrant is already accessed by another instance of Qdrant client` | mem0 v3 opens a **global** telemetry Qdrant store, so a process may only hold **one** `Memory` instance | one configuration per process; enforced in `src/run.py` |
| 2 | `search()` raised `ValueError: Top-level entity parameters frozenset({'user_id'}) are not supported` | mem0ai 2.2.1 changed the calling convention; note it raises `ValueError`, not `TypeError`, so a naive `except TypeError` fallback never fires | call `search(query, filters={"user_id": ...}, top_k=...)`; the adapter tries the new form first with old forms as fallback |
| 3 | `Failed to load spaCy lemma model: spaCy is not installed` | the plain `mem0ai` wheel silently degrades v3's multi-signal retrieval to dense-only | install `mem0ai[nlp]` + `python -m spacy download en_core_web_sm`; documented as **required** |
| 4 | no Docker on this machine, official OSS eval path is `docker compose`-only | official harness wraps Mem0 in a FastAPI service | drive the SDK directly (deviation #1 above) |
| 5 | DeepSeek exposes no `/embeddings` endpoint | model substitution cannot be a single variable | embedder replaced by local `fastembed`; recorded as a **forced** confounding variable |
| 6 | Temporal accuracy collapsed to **2/20 (10%)** while multi-hop scored 14/15 | the official runner passes `timestamp=<session epoch>` to `add()`, but `mem0ai==2.2.1` **refuses** it — `ValueError: The timestamp parameter is not supported by the OSS Memory SDK.`, gated in `mem0/memory/notices.py` (same for `reference_date`). My adapter catches the refusal and retries without it, so ingestion succeeds and every relative expression is then resolved against the **wall clock**: a 2023 conversation gets stored as "November 2026" evidence | **not patched** — reported as the main finding. It is a platform-only feature gate, and the `infer=False` ablation in `REPORT.md` §5 exists to measure its damage |
| 7 | ingest log printed `stored=20` for a 419-turn conversation | `Memory.get_all()` defaults to **`top_k=20`**, so any bare call truncates to 20 and reports a fabricated total. The store behind that log held several hundred memories (503 in the run behind the reported numbers — see `REPORT.md` §5) | pass `top_k=100_000`; count is cross-checked against `QdrantClient.count(exact=True)` |
| 8 | first run exited with code 1 although every artefact was written | PostHog/Qdrant shutdown noise on the stderr stream; PowerShell promotes stderr output to a terminating error | run with `*> results/runN.log` and judge success by artefact count, not by exit code |
| 9 | every retrieved memory was prefixed `(2026-11-12)` where the authors' pipeline renders `(Thursday, November 12, 2026)` | my `_human_date` carried a shortened `strptime` format tuple. mem0 writes `created_at` as `2026-11-12T15:31:07.809868+00:00`, which matches the authors' second candidate `%Y-%m-%dT%H:%M:%S.%f%z` only after the `[:26]` truncation *and* `%z` removal; mine skipped that candidate and fell through to the bare `YYYY-MM-DD` fallback | copied `_to_human_date` verbatim, verified byte-identical output on 8 input shapes, and archived (not patched) every answer produced under the old prefix to `results/_archive_v1_datefmt/` |

Bug 6 is the instructive one: the harness ran end-to-end, produced 40 valid
files, and reported a plausible-looking accuracy -- **yet it was measuring the
wrong thing**. Only a per-question dump (gold vs generated answer, sorted by
category) exposed it. An aggregate score alone would have been reported as
"mem0 reproduces poorly", which would have been a false conclusion about the
authors' system rather than a true conclusion about my own pipeline.

Measured facts after a successful smoke test (`mem0ai 2.2.1`):

```
add()     -> {'results': [{'memory': 'Alice loves hiking in the Alps every summer', 'event': 'ADD'}]}
search()  -> 2 hits, correct facts
infer=False -> 1 raw turn stored, retrievable   <- modification A is viable
```

