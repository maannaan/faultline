"""Task transitions. blocked and failed are named and unused."""

from __future__ import annotations

from faultline.constants import (
    TASK_CLAIMED,
    TASK_COMPLETED,
    TASK_HANDED_OFF,
    TASK_IN_PROGRESS,
    TASK_QUEUED,
)
from faultline.errors import FaultlineError

_HANDOFF_FROM = {TASK_QUEUED, TASK_CLAIMED, TASK_IN_PROGRESS}
_COMPLETE_FROM = {TASK_CLAIMED, TASK_IN_PROGRESS}
_REVALIDATE_FROM = {TASK_HANDED_OFF, TASK_CLAIMED}


def require_version(current: int, expected: int) -> None:
    if current != expected:
        raise FaultlineError("version_conflict", "Task version does not match", 409)


def transition_handoff(status: str) -> str:
    if status not in _HANDOFF_FROM:
        raise FaultlineError(
            "validation_error",
            "Task cannot be handed off from this status",
            400,
        )
    return TASK_HANDED_OFF


def transition_accept(status: str, actor_id: str, recipient_id: str) -> str:
    if status != TASK_HANDED_OFF:
        raise FaultlineError(
            "validation_error",
            "Task cannot be accepted from this status",
            400,
        )
    if actor_id != recipient_id:
        raise FaultlineError(
            "validation_error",
            "Only the recipient can accept the handoff",
            400,
        )
    return TASK_CLAIMED


def transition_complete(status: str) -> str:
    if status not in _COMPLETE_FROM:
        raise FaultlineError(
            "validation_error",
            "Task cannot be completed from this status",
            400,
        )
    return TASK_COMPLETED


def transition_revalidate(status: str) -> str:
    if status not in _REVALIDATE_FROM:
        raise FaultlineError(
            "validation_error",
            "Task cannot be revalidated from this status",
            400,
        )
    return status
