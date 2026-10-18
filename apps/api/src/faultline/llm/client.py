"""OpenAI SDK client pointed at OpenAI or an OpenAI-compatible host such as Kimi."""

from __future__ import annotations

from openai import OpenAI

from faultline.config import Settings


def openai_client(settings: Settings) -> OpenAI:
    kwargs: dict[str, str] = {"api_key": settings.openai_api_key}
    base_url = settings.openai_base_url.strip()
    if base_url:
        kwargs["base_url"] = base_url
    return OpenAI(**kwargs)


def kimi_extra_body(settings: Settings) -> dict[str, str] | None:
    if settings.openai_model.startswith("kimi"):
        return {"reasoning_effort": "low"}
    return None
