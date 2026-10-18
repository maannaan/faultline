"""Replay Lab is the as-of answer and evidence diff. Handoffs are not built yet."""

from faultline.config import Settings
from faultline.replay.answer import DeterministicAnswerer
from faultline.replay.openai_answer import OpenAIAnswerer


def build_answerer(settings: Settings) -> DeterministicAnswerer | OpenAIAnswerer:
    if settings.openai_api_key:
        return OpenAIAnswerer(settings)
    return DeterministicAnswerer()


__all__ = ["DeterministicAnswerer", "OpenAIAnswerer", "build_answerer"]
