"""DeepSeek client with token accounting, retries and a budget guard.

Why not use mem0's internal LLM for the answerer/judge: we need exact
per-call token counts and latencies to reproduce the paper's efficiency
claims ("90% fewer tokens", "91% lower p95 latency"). Those numbers are the
relative targets, and they are only defensible if measured precisely here.
"""

from __future__ import annotations

import json
import os
import time
import urllib.request
from dataclasses import dataclass, field

from . import config


class BudgetExceeded(RuntimeError):
    pass


@dataclass
class CostTracker:
    """Accumulates token usage across a run and enforces the spend cap."""

    label: str = ""
    calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latencies_s: list[float] = field(default_factory=list)
    per_stage: dict[str, int] = field(default_factory=dict)

    def record(self, stage: str, prompt_tokens: int, completion_tokens: int, latency_s: float) -> None:
        self.calls += 1
        self.prompt_tokens += prompt_tokens
        self.completion_tokens += completion_tokens
        self.latencies_s.append(latency_s)
        self.per_stage[stage] = self.per_stage.get(stage, 0) + prompt_tokens + completion_tokens
        if self.cost_usd > config.BUDGET_CAP_USD:
            raise BudgetExceeded(
                f"spend ${self.cost_usd:.2f} exceeded cap ${config.BUDGET_CAP_USD:.2f} "
                f"after {self.calls} calls ({self.label})"
            )

    @property
    def cost_usd(self) -> float:
        return (
            self.prompt_tokens / 1_000_000 * config.PRICE_IN_PER_MTOK
            + self.completion_tokens / 1_000_000 * config.PRICE_OUT_PER_MTOK
        )

    def as_dict(self) -> dict:
        return {
            "label": self.label,
            "calls": self.calls,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "cost_usd": round(self.cost_usd, 4),
            "per_stage_tokens": self.per_stage,
        }


class LLM:
    """Thin OpenAI-compatible wrapper around DeepSeek."""

    def __init__(self, model: str | None = None, max_tokens: int | None = None) -> None:
        from openai import OpenAI

        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise SystemExit(
                "DEEPSEEK_API_KEY is not set. Create .env from .env.example, then re-run."
            )
        self.model = model or config.LLM_MODEL
        self.max_tokens = max_tokens or config.ANSWER_MAX_TOKENS
        self._client = OpenAI(api_key=api_key, base_url=config.LLM_BASE_URL)

    def chat(
        self,
        user: str,
        system: str = "",
        json_mode: bool = False,
        max_tokens: int | None = None,
        retries: int = 5,
    ) -> tuple[str, int, int, float]:
        """Return (text, prompt_tokens, completion_tokens, latency_seconds)."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": user})

        kwargs: dict = {
            "model": self.model,
            "messages": messages,
            "temperature": config.TEMPERATURE,
            "max_tokens": max_tokens or self.max_tokens,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        last_error: Exception | None = None
        for attempt in range(retries):
            started = time.monotonic()
            try:
                response = self._client.chat.completions.create(**kwargs)
                latency = time.monotonic() - started
                usage = response.usage
                text = (response.choices[0].message.content or "").strip()
                return (
                    text,
                    int(getattr(usage, "prompt_tokens", 0) or 0),
                    int(getattr(usage, "completion_tokens", 0) or 0),
                    latency,
                )
            except Exception as exc:  # noqa: BLE001 - retried below
                last_error = exc
                time.sleep(1.5 * (attempt + 1))
        raise RuntimeError(f"LLM call failed after {retries} attempts: {last_error}")

    def chat_json(self, user: str, system: str = "", retries: int = 2) -> tuple[dict, int, int, float]:
        """Chat with JSON output, tolerant to code fences and stray prose."""
        prompt_tokens = completion_tokens = 0
        latency = 0.0
        text = ""
        for _ in range(retries):
            text, pt, ct, lat = self.chat(
                user, system=system, json_mode=True, max_tokens=config.JUDGE_MAX_TOKENS
            )
            prompt_tokens += pt
            completion_tokens += ct
            latency += lat
            parsed = _loose_json(text)
            if parsed is not None:
                return parsed, prompt_tokens, completion_tokens, latency
        return {"label": "ERROR", "reasoning": f"unparseable judge output: {text[:120]}"}, (
            prompt_tokens,
            completion_tokens,
            latency,
        )


def _loose_json(text: str) -> dict | None:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1] if "```" in cleaned[3:] else cleaned[3:]
        cleaned = cleaned.lstrip("json").strip("`").strip()
    try:
        value = json.loads(cleaned)
        return value if isinstance(value, dict) else None
    except json.JSONDecodeError:
        pass
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start != -1 and end > start:
        try:
            value = json.loads(cleaned[start : end + 1])
            return value if isinstance(value, dict) else None
        except json.JSONDecodeError:
            return None
    return None


def balance_usd() -> float | None:
    """Current DeepSeek account balance, or None if it cannot be read."""
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        return None
    request = urllib.request.Request(
        f"{config.LLM_BASE_URL.rstrip('/')}/user/balance",
        headers={"Authorization": f"Bearer {api_key}"},
    )
    try:
        payload = json.loads(urllib.request.urlopen(request, timeout=20).read().decode())
        return float(payload["balance_infos"][0]["total_balance"])
    except Exception:  # noqa: BLE001 - best effort only
        return None


def percentile(values: list[float], pct: float) -> float:
    """Simple nearest-rank percentile (no numpy dependency)."""
    if not values:
        return 0.0
    ordered = sorted(values)
    k = max(0, min(len(ordered) - 1, int(round((pct / 100) * (len(ordered) - 1)))))
    return ordered[k]
