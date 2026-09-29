"""LLM 调用计量：token / 耗时 / 成败落盘

每次调用记录一条行级 JSON 到 data/metrics/llm_usage.jsonl（O_APPEND 单次 write，原子追加）。
汇总供 GET /api/v1/metrics/summary 使用；计量失败不得影响主调用链路。
"""
from __future__ import annotations

import contextvars
import json
import os
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_METRICS_PATH = ROOT / "data" / "metrics" / "llm_usage.jsonl"

_lock = threading.Lock()

# 当前分析任务 ID（由 analyzer 在 run_analysis 入口设置，计量自动关联）
_current_analysis_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "llm_analysis_id", default=""
)


def set_analysis_id(analysis_id: str) -> contextvars.Token:
    return _current_analysis_id.set(analysis_id or "")


def reset_analysis_id(token: contextvars.Token) -> None:
    try:
        _current_analysis_id.reset(token)
    except ValueError:
        _current_analysis_id.set("")


def get_analysis_id() -> str:
    return _current_analysis_id.get()


@dataclass
class LLMUsageRecord:
    ts: float
    model: str
    provider: str = ""
    call_kind: str = "chat"          # chat / vlm / image_gen
    task_type: str = ""
    analysis_id: str = ""
    latency_ms: float = 0.0
    success: bool = True
    error_type: str = ""
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    extra: dict = field(default_factory=dict)


def _percentile(sorted_values: list[float], q: float) -> float:
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return round(sorted_values[0], 2)
    pos = (len(sorted_values) - 1) * q
    low = int(pos)
    high = min(low + 1, len(sorted_values) - 1)
    frac = pos - low
    return round(sorted_values[low] * (1 - frac) + sorted_values[high] * frac, 2)


class LLMMeter:
    """轻量调用计量器：写入 JSONL 并提供最近 N 条汇总。"""

    def __init__(self, path: Path | str | None = None):
        self.path = Path(path) if path else DEFAULT_METRICS_PATH

    def record(
        self,
        model: str,
        latency_ms: float,
        success: bool = True,
        provider: str = "",
        call_kind: str = "chat",
        task_type: str = "",
        analysis_id: str = "",
        error_type: str = "",
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        total_tokens: int | None = None,
        extra: dict | None = None,
    ) -> LLMUsageRecord:
        rec = LLMUsageRecord(
            ts=time.time(),
            model=model or "",
            provider=provider or "",
            call_kind=call_kind,
            task_type=task_type or "",
            analysis_id=analysis_id or get_analysis_id(),
            latency_ms=round(float(latency_ms), 2),
            success=bool(success),
            error_type=error_type or "",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            extra=extra or {},
        )
        line = json.dumps(asdict(rec), ensure_ascii=False) + "\n"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with _lock:
            fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
            try:
                os.write(fd, line.encode("utf-8"))
            finally:
                os.close(fd)
        return rec

    def read_records(self, n: int | None = None) -> list[dict]:
        if not self.path.exists():
            return []
        rows: list[dict] = []
        with _lock:
            with open(self.path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rows.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        if n is not None and n > 0:
            return rows[-n:]
        return rows

    def summarize(self, n: int = 50) -> dict:
        """最近 n 次分析（无 analysis_id 时按最近 n 条调用）的汇总；无记录时返回 available=False。"""
        n = max(1, int(n or 50))
        rows = self.read_records()
        if not rows:
            return {
                "available": False,
                "window": n,
                "window_unit": "analyses",
                "records": 0,
                "calls": 0,
                "failures": 0,
                "failure_rate": None,
                "latency_ms": None,
                "tokens": None,
                "by_model": {},
                "analyses": {"count": 0, "calls": 0, "failure_rate": None, "latency_ms": None},
            }

        # 优先按 analysis_id 分组取最近 n 次分析；无分组标记时退化为最近 n 条调用
        grouped: dict[str, list[dict]] = {}
        ungrouped: list[dict] = []
        for r in rows:
            aid = r.get("analysis_id") or ""
            if aid:
                grouped.setdefault(aid, []).append(r)
            else:
                ungrouped.append(r)

        if grouped:
            # 按组内最后一条记录的时间排序，取最近 n 组
            ordered_ids = sorted(
                grouped.keys(),
                key=lambda k: max(float(x.get("ts") or 0) for x in grouped[k]),
            )[-n:]
            window_rows = [r for aid in ordered_ids for r in grouped[aid]]
            window_unit = "analyses"
            analyses_count = len(ordered_ids)
        else:
            window_rows = rows[-n:]
            window_unit = "calls"
            analyses_count = 0

        calls = len(window_rows)
        failures = sum(1 for r in window_rows if not r.get("success", True))
        latencies = sorted(float(r.get("latency_ms") or 0.0) for r in window_rows)
        prompt_sum = sum(int(r["prompt_tokens"]) for r in window_rows if r.get("prompt_tokens") is not None)
        completion_sum = sum(int(r["completion_tokens"]) for r in window_rows if r.get("completion_tokens") is not None)
        token_rows = [r for r in window_rows if r.get("prompt_tokens") is not None or r.get("completion_tokens") is not None]

        by_model: dict[str, dict] = {}
        for r in window_rows:
            mk = r.get("model") or "unknown"
            slot = by_model.setdefault(mk, {"calls": 0, "failures": 0, "latencies": []})
            slot["calls"] += 1
            if not r.get("success", True):
                slot["failures"] += 1
            slot["latencies"].append(float(r.get("latency_ms") or 0.0))
        for mk, slot in by_model.items():
            vals = sorted(slot.pop("latencies"))
            slot["failure_rate"] = round(slot["failures"] / slot["calls"], 4) if slot["calls"] else None
            slot["latency_ms"] = {
                "p50": _percentile(vals, 0.5),
                "p90": _percentile(vals, 0.9),
                "p99": _percentile(vals, 0.99),
                "mean": round(sum(vals) / len(vals), 2) if vals else 0.0,
            }

        analyses_block: dict = {
            "count": analyses_count,
            "calls": calls,
            "failure_rate": round(failures / calls, 4) if calls else None,
            "latency_ms": {
                "p50": _percentile(latencies, 0.5),
                "p90": _percentile(latencies, 0.9),
                "p99": _percentile(latencies, 0.99),
                "mean": round(sum(latencies) / len(latencies), 2) if latencies else 0.0,
            },
        }
        if window_unit == "calls":
            analyses_block["note"] = "records_without_analysis_id"

        return {
            "available": True,
            "window": n,
            "window_unit": window_unit,
            "records": calls,
            "calls": calls,
            "failures": failures,
            "failure_rate": round(failures / calls, 4) if calls else None,
            "latency_ms": {
                "p50": _percentile(latencies, 0.5),
                "p90": _percentile(latencies, 0.9),
                "p99": _percentile(latencies, 0.99),
                "mean": round(sum(latencies) / len(latencies), 2) if latencies else 0.0,
            },
            "tokens": {
                "prompt": prompt_sum if token_rows else None,
                "completion": completion_sum if token_rows else None,
                "usage_reported_calls": len(token_rows),
            },
            "by_model": by_model,
            "analyses": analyses_block,
        }


meter = LLMMeter()
