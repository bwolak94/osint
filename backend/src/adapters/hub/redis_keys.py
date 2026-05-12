"""Centralised Redis key helpers for the Hub module.

All Hub-related Redis keys are defined here to prevent typo bugs and
ensure consistent TTL/namespace conventions across router and workers.
"""
from __future__ import annotations

HUB_TTL = 3600  # 1 hour


def task_status_key(task_id: str) -> str:
    return f"hub:task:{task_id}:status"


def task_result_key(task_id: str) -> str:
    return f"hub:task:{task_id}:result"


def task_state_key(task_id: str) -> str:
    return f"hub:task:{task_id}:state"


def task_events_channel(task_id: str) -> str:
    return f"hub:task:{task_id}:events"
