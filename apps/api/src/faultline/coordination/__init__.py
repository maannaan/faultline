"""Versioned task handoffs. Blocked and failed transitions are not built."""

from faultline.coordination.handoff import CoordinationService

__all__ = ["CoordinationService"]
