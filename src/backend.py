"""The two memory backends under test.

``Mem0Backend``     : the authors' open-source SDK, driven directly.
``FullContextBackend`` : the paper's main efficiency baseline (feed the whole
                     conversation to the model), needed to test the relative
                     claim ">90% fewer tokens than full-context".

Neither backend needs Docker. The official OSS evaluation path in
``memory-benchmarks`` wraps Mem0 in a FastAPI service started by
``docker compose``; since this machine has no Docker, we call the same SDK
directly. That deviation is recorded in the report's debug diary and is the
only structural difference from the official harness.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from . import config


class Mem0Backend:
    name = "mem0"

    def __init__(self, vector_dir: Path, infer: bool = True) -> None:
        self.infer = infer
        self.vector_dir = Path(vector_dir)
        self.vector_dir.mkdir(parents=True, exist_ok=True)
        self._instances: dict[int, Any] = {}
        self._memory_cls: Any = None
        # Signatures that had to be adapted are surfaced in the run report,
        # because they are evidence about which mem0 version is running.
        self.adaptations: list[str] = []

    def user_id(self, conv_idx: int) -> str:
        tag = "ext" if self.infer else "raw"
        return f"locomo_{conv_idx}_{tag}"

    def _memory(self, conv_idx: int) -> Any:
        if self._memory_cls is None:
            from mem0 import Memory  # lazy: keeps --estimate usable without deps

            self._memory_cls = Memory
        if conv_idx not in self._instances:
            self._instances[conv_idx] = self._memory_cls.from_config(
                config.mem0_config(self.vector_dir, f"locomo_conv{conv_idx}")
            )
        return self._instances[conv_idx]

    # -- write side ---------------------------------------------------------
    def add(self, conv_idx: int, messages: list[dict], metadata: dict) -> Any:
        memory = self._memory(conv_idx)
        uid = self.user_id(conv_idx)
        # ``timestamp`` is what anchors relative expressions ("last week") to the
        # conversation's own clock, and the official runner passes the session
        # epoch. In mem0ai 2.x the OSS SDK *refuses* it: "The timestamp parameter
        # is not supported by the OSS Memory SDK" (mem0/memory/notices.py). The
        # fallback below therefore drops ``timestamp`` but keeps ``metadata`` --
        # dropping metadata too would lose the session label for no reason.
        attempts: list[dict] = []
        if metadata.get("epoch") is not None:
            attempts.append({"user_id": uid, "metadata": metadata, "timestamp": metadata["epoch"]})
        attempts.append({"user_id": uid, "metadata": metadata})
        attempts.append({"user_id": uid})
        if not self.infer:
            # Modification A: disable the LLM fact-extraction stage entirely.
            # ``infer`` is carried into every fallback so that a signature change
            # can never silently re-enable extraction mid-run.
            attempts = [{**kwargs, "infer": False} for kwargs in attempts]

        last: Exception | None = None
        for kwargs in attempts:
            try:
                return memory.add(messages, **kwargs)
            except (TypeError, ValueError) as exc:
                last = exc
                self._note(f"add({sorted(kwargs)}): {type(exc).__name__}: {exc}")
                continue
        raise RuntimeError(f"memory.add() rejected every known signature: {last}")

    def _note(self, message: str) -> None:
        """Record each distinct adaptation once (419 identical lines are noise)."""
        if message not in self.adaptations:
            self.adaptations.append(message)

    # -- read side ---------------------------------------------------------
    def search(self, conv_idx: int, query: str, limit: int = config.OFFICIAL_TOP_K) -> list[dict]:
        memory = self._memory(conv_idx)
        uid = self.user_id(conv_idx)
        # mem0ai >= 2.x rejects top-level entity params in search() with a
        # ValueError (not TypeError): "Use filters={'user_id': '...'} instead."
        # The filters form is therefore tried first, with the older signatures
        # kept as fallbacks so the harness survives a version pin change.
        attempts = (
            {"filters": {"user_id": uid}, "top_k": limit},
            {"filters": {"user_id": uid}, "limit": limit},
            {"user_id": uid, "top_k": limit},
            {"user_id": uid, "limit": limit},
        )
        last: Exception | None = None
        for index, kwargs in enumerate(attempts):
            try:
                return _normalize(memory.search(query, **kwargs))
            except (TypeError, ValueError) as exc:
                last = exc
                if index == 0:
                    self.adaptations.append(f"search filters signature: {type(exc).__name__}: {exc}")
                continue
        raise RuntimeError(f"memory.search() rejected every known signature: {last}")

    def count(self, conv_idx: int) -> int | None:
        """Number of stored memories, for the ingest diagnostics only.

        ``Memory.get_all`` defaults to ``top_k=20`` in mem0ai 2.x, so a bare call
        reports 20 for any store larger than that. The cap has to be lifted
        explicitly or the ingest log understates the store by orders of magnitude.
        """
        memory = self._memory(conv_idx)
        uid = self.user_id(conv_idx)
        for kwargs in (
            {"filters": {"user_id": uid}, "top_k": 100_000},
            {"user_id": uid, "top_k": 100_000},
        ):
            try:
                return len(memory.get_all(**kwargs).get("results", []))
            except (TypeError, ValueError):
                continue
        return None


class FullContextBackend:
    """Baseline that keeps the entire transcript and stuffs it into the prompt."""

    name = "fullctx"
    infer = True
    # In-process only: there is no vector store to restart into, so the ingest
    # marker must never be written for this backend (see ``run._ingest``).
    persistent = False

    def __init__(self, vector_dir: Path | None = None, infer: bool = True) -> None:
        self._transcripts: dict[int, list[str]] = {}
        self.adaptations: list[str] = []

    def user_id(self, conv_idx: int) -> str:
        return f"fullctx_{conv_idx}"

    def add(self, conv_idx: int, messages: list[dict], metadata: dict) -> None:
        bucket = self._transcripts.setdefault(conv_idx, [])
        stamp = metadata.get("date", "")
        for msg in messages:
            bucket.append(f"[{stamp}] {msg['content']}" if stamp else msg["content"])
        return None

    def search(self, conv_idx: int, query: str, limit: int = config.OFFICIAL_TOP_K) -> list[dict]:
        lines = self._transcripts.get(conv_idx, [])
        if not lines:
            return []
        return [{"memory": "\n".join(lines), "created_at": "", "score": 1.0}]

    def count(self, conv_idx: int) -> int:
        return len(self._transcripts.get(conv_idx, []))


def build_backend(name: str, vector_dir: Path, infer: bool):
    if name == "mem0":
        return Mem0Backend(vector_dir, infer=infer)
    if name == "fullctx":
        return FullContextBackend()
    raise ValueError(f"unknown backend: {name}")


def _normalize(result: Any) -> list[dict]:
    """Accept the several shapes mem0 has returned across versions."""
    if isinstance(result, dict):
        items = result.get("results", [])
    elif isinstance(result, list):
        items = result
    else:
        items = []
    normalized: list[dict] = []
    for item in items:
        if isinstance(item, str):
            normalized.append({"memory": item, "created_at": "", "score": None})
        elif isinstance(item, dict):
            normalized.append(
                {
                    "memory": item.get("memory") or item.get("text") or str(item),
                    "created_at": item.get("created_at") or "",
                    "score": item.get("score"),
                    "id": item.get("id"),
                    "metadata": item.get("metadata") or {},
                }
            )
    return normalized
