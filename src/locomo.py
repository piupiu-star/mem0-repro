"""LOCOMO dataset loading and conversation parsing.

Parsing mirrors ``mem0ai/memory-benchmarks`` -> ``benchmarks/locomo/run.py``
so that our subset is constructed identically to the official pipeline.
Any deviation here would silently change the benchmark.

Dataset: snap-research/locomo, ``data/locomo10.json`` (10 conversations).
Per conversation: ``conversation`` (dict of session_N -> turns) + ``qa`` (list).
Category mapping: 1 multi-hop, 2 temporal, 3 open-domain, 4 single-hop,
5 adversarial (excluded from scoring by the official pipeline).
"""

from __future__ import annotations

import json
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from . import config


def download_dataset(dest: Path = config.DATASET_PATH) -> Path:
    """Download locomo10.json once, validating that it has 10 conversations."""
    dest = Path(dest)
    if dest.exists():
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"[dataset] downloading {config.DATASET_URL}")
    urllib.request.urlretrieve(config.DATASET_URL, dest)
    data = json.loads(dest.read_text(encoding="utf-8"))
    if not isinstance(data, list) or len(data) != 10:
        dest.unlink(missing_ok=True)
        raise RuntimeError(f"bad dataset: expected 10 conversations, got {len(data)}")
    print(f"[dataset] ok: {dest} ({len(data)} conversations)")
    return dest


def load_dataset(path: Path = config.DATASET_PATH) -> list[dict]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def parse_session_date(date_str: str) -> datetime | None:
    """Parse LOCOMO session dates: '1:56 pm on 8 May, 2023'."""
    for fmt in ("%I:%M %p on %d %B, %Y", "%I:%M %p on %d %b, %Y"):
        try:
            return datetime.strptime(date_str, fmt)
        except (ValueError, TypeError):
            continue
    return None


def date_to_epoch(date_str: str) -> int | None:
    parsed = parse_session_date(date_str)
    if parsed is None:
        return None
    return int(parsed.replace(tzinfo=timezone.utc).timestamp())


def sorted_sessions(conversation: dict) -> list[tuple[str, str, list[dict]]]:
    """Return [(session_key, date_str, turns)] in chronological order."""
    keys = [k for k in conversation if re.match(r"^session_\d+$", k)]
    paired: list[tuple[str, str, list[dict]]] = []
    for key in keys:
        turns = conversation.get(key) or []
        if isinstance(turns, list):
            paired.append((key, conversation.get(f"{key}_date_time", ""), turns))

    def sort_key(item: tuple[str, str, list[dict]]) -> tuple:
        parsed = parse_session_date(item[1])
        if parsed is not None:
            return (0, parsed)
        num = int(re.search(r"\d+", item[0]).group())  # type: ignore[union-attr]
        return (1, datetime(2000, 1, num))

    paired.sort(key=sort_key)
    return paired


def turn_to_message(turn: dict, speaker_a: str) -> dict | None:
    """Convert one LOCOMO turn into an OpenAI-style chat message."""
    speaker = turn.get("speaker", "")
    text = turn.get("text", "") or ""

    # Multimodal captions are inlined as text, exactly as the official runner does.
    blip = turn.get("blip_caption", "")
    query = turn.get("query", "")
    if query and blip:
        photo_tag = f"[Sharing image - query: {query}. The image shows: {blip}]"
    elif query:
        photo_tag = f"[Sharing image - query for: {query}]"
    elif blip:
        photo_tag = f"[Sharing image that shows: {blip}]"
    else:
        photo_tag = ""
    if photo_tag:
        text = f"{text} {photo_tag}" if text else photo_tag
    if not text.strip():
        return None

    role = "user" if speaker == speaker_a else "assistant"
    return {"role": role, "content": f"{speaker}: {text}"}


def iter_chunks(
    conversation: dict,
    chunk_size: int = config.CHUNK_SIZE,
) -> Iterator[tuple[str, str, int | None, list[dict]]]:
    """Yield (session_key, date_str, epoch, messages_chunk) in order.

    ``chunk_size`` is fixed at 1 by default to match the official runner, which
    issues one ``mem0.add`` call per conversational turn.
    """
    speaker_a = conversation.get("speaker_a", "")
    for session_key, date_str, turns in sorted_sessions(conversation):
        epoch = date_to_epoch(date_str)
        messages: list[dict] = []
        for turn in turns:
            msg = turn_to_message(turn, speaker_a)
            if msg is not None:
                messages.append(msg)
        for i in range(0, len(messages), chunk_size):
            yield session_key, date_str, epoch, messages[i : i + chunk_size]


def questions_in_scope(
    entry: dict,
    categories: list[int],
    limit: int | None = None,
) -> list[tuple[int, dict]]:
    """Return [(qa_index, qa_dict)] for the selected categories."""
    questions = entry.get("qa") or entry.get("qa_pairs") or []
    picked = [(i, qa) for i, qa in enumerate(questions) if qa.get("category") in categories]
    if limit is not None:
        picked = picked[:limit]
    return picked


def reference_date(conversation: dict) -> str:
    """The official runner uses the LAST session's date as the temporal anchor."""
    sessions = sorted_sessions(conversation)
    return sessions[-1][1] if sessions else "2023"


def summarize_dataset(data: list[dict]) -> dict[str, Any]:
    """Cheap inventory used by ``--estimate`` for the cost projection."""
    total_turns = 0
    per_category: dict[int, int] = {c: 0 for c in config.CATEGORIES_TO_EVALUATE}
    for entry in data:
        conv = entry["conversation"]
        total_turns += sum(len(t) for _, _, t in sorted_sessions(conv))
        for _, qa in questions_in_scope(entry, config.CATEGORIES_TO_EVALUATE):
            per_category[qa["category"]] = per_category.get(qa["category"], 0) + 1
    return {"total_turns": total_turns, "per_category": per_category}
