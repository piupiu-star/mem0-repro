"""Central configuration for the Mem0 reproducibility study.

Every knob that the report must disclose lives here, so that the exact
experimental setup is a single reviewable file rather than scattered
constants.

Reference points
----------------
Upstream repo : https://github.com/mem0ai/mem0  (v3 "New Memory Algorithm")
Eval suite    : https://github.com/mem0ai/memory-benchmarks (git submodule of the above)
Paper         : arXiv:2504.19413v1 (2025-04-28)  <- v2 algorithm, NOT this code line
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

# ---------------------------------------------------------------------------
# Controlled variables (report section 2 "Setup notes")
# ---------------------------------------------------------------------------
# The paper and the managed platform use OpenAI models. We substitute DeepSeek
# as ONE documented change (assignment, "Edge case A"). This is a confounder for
# absolute scores and must be stated verbatim in the report:
#   "Results are not directly comparable to the paper because the underlying
#    LLM differs."
LLM_MODEL = os.getenv("REPRO_LLM_MODEL", "deepseek-chat")
LLM_BASE_URL = os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com")

# DeepSeek exposes no /embeddings endpoint, therefore a local embedder is
# FORCED, not chosen. That makes it a second unavoidable confounder.
EMBEDDER_PROVIDER = os.getenv("REPRO_EMBEDDER_PROVIDER", "fastembed")
EMBEDDER_MODEL = os.getenv("REPRO_EMBEDDER_MODEL", "BAAI/bge-small-en-v1.5")
EMBEDDER_DIMS = int(os.getenv("REPRO_EMBEDDER_DIMS", "384"))

# Decoding parameters, kept identical across extraction / answer / judge so that
# the only difference between configurations is the one we are testing.
TEMPERATURE = float(os.getenv("REPRO_TEMPERATURE", "0.0"))
ANSWER_MAX_TOKENS = int(os.getenv("REPRO_ANSWER_MAX_TOKENS", "600"))
JUDGE_MAX_TOKENS = int(os.getenv("REPRO_JUDGE_MAX_TOKENS", "120"))

# ---------------------------------------------------------------------------
# Budget guard
# ---------------------------------------------------------------------------
# USD per 1M tokens. Update from https://api-docs.deepseek.com/quick_start/pricing
PRICE_IN_PER_MTOK = float(os.getenv("REPRO_PRICE_IN", "0.27"))
PRICE_OUT_PER_MTOK = float(os.getenv("REPRO_PRICE_OUT", "1.10"))
BUDGET_CAP_USD = float(os.getenv("REPRO_BUDGET_CAP", "2.50"))
BUDGET_FLOOR_USD = float(os.getenv("REPRO_BUDGET_FLOOR", "1.00"))

# ---------------------------------------------------------------------------
# Benchmark scope (report section 3 "Reproduction target")
# ---------------------------------------------------------------------------
DATASET_URL = "https://raw.githubusercontent.com/snap-research/locomo/main/data/locomo10.json"
DATASET_PATH = ROOT / "datasets" / "locomo10.json"

# Official defaults from memory-benchmarks/benchmarks/locomo/run.py
OFFICIAL_TOP_K = 200
OFFICIAL_CUTOFFS = [10, 20, 50, 200]
CHUNK_SIZE = 1  # turns per ingest call (official value)

# Categories scored by the official pipeline (5 = adversarial is excluded).
CATEGORIES_TO_EVALUATE = [1, 2, 3, 4]
CATEGORY_NAMES = {1: "multi-hop", 2: "temporal", 3: "open-domain", 4: "single-hop", 5: "adversarial"}

# Reference numbers we compare against. Keep the provenance explicit.
REPORTED = {
    "readme_v3_platform_locomo_overall": 92.5,   # README table, managed platform, v3
    "readme_v3_platform_locomo_by_type": {
        "single-hop": 91.2,
        "multi-hop": 91.3,
        "open-domain": 72.7,
        "temporal": 92.0,
    },
    "readme_v3_platform_tokens_per_query": 7.0,  # K tokens
    "readme_v3_platform_p50_latency_s": 0.88,
    # Relative claims from the 2025 paper abstract (arXiv:2504.19413v1).
    # These are reproducible without the platform: arithmetic on token counts.
    "paper_relative_token_saving_vs_fullctx": 0.90,
    "paper_relative_p95_latency_reduction_vs_fullctx": 0.91,
    "paper_relative_improvement_over_openai_memory": 0.26,
}


def mem0_config(vector_path: Path, collection: str) -> dict:
    """Config dict handed to ``mem0.Memory.from_config``."""
    return {
        "llm": {
            "provider": "deepseek",
            "config": {
                "model": LLM_MODEL,
                "temperature": TEMPERATURE,
                "max_tokens": ANSWER_MAX_TOKENS,
                "deepseek_base_url": LLM_BASE_URL,
            },
        },
        "embedder": {
            "provider": EMBEDDER_PROVIDER,
            "config": {"model": EMBEDDER_MODEL},
        },
        "vector_store": {
            "provider": "qdrant",
            "config": {
                "path": str(vector_path),
                "collection_name": collection,
                "embedding_model_dims": EMBEDDER_DIMS,
            },
        },
    }
