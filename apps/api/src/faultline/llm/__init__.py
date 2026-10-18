"""Extractor selection."""

from faultline.config import Settings
from faultline.llm.adapter import Extractor
from faultline.llm.fake import FakeExtractor
from faultline.llm.openai_adapter import OpenAIExtractor


def build_extractor(settings: Settings) -> Extractor:
    if settings.openai_api_key.strip():
        return OpenAIExtractor(settings)
    return FakeExtractor()
