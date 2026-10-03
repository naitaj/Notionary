from app.core.config import settings
from app.config import settings as app_settings
from app.ai.providers.base import LLMProvider, EmbeddingProvider
from app.ai.providers.anthropic_provider import AnthropicProvider
from app.ai.providers.gemini_provider import GeminiProvider
from app.ai.providers.mock_provider import MockLLMProvider, LocalEmbeddingProvider
from app.ai.providers.groq_provider import GroqProvider
from app.ai.resilience import ResilientLLMProvider

_llm_instance = None
_embedding_instance = None

def get_llm_provider() -> LLMProvider:
    global _llm_instance
    if _llm_instance:
        return _llm_instance

    raw_provider: LLMProvider
    if app_settings.GROQ_API_KEY:
        raw_provider = GroqProvider()
    else:
        provider_name = settings.DEFAULT_LLM_PROVIDER.lower()
        if provider_name == "anthropic" and settings.ANTHROPIC_API_KEY:
            raw_provider = AnthropicProvider()
        elif provider_name == "gemini" and settings.GEMINI_API_KEY:
            raw_provider = GeminiProvider()
        else:
            raw_provider = MockLLMProvider()

    # Wrap in resilience layer with 15s timeout and cache fallback (Plan §9.3)
    _llm_instance = ResilientLLMProvider(primary=raw_provider, fallback=MockLLMProvider(), timeout_seconds=15.0)
    return _llm_instance

def get_embedding_provider() -> EmbeddingProvider:
    global _embedding_instance
    if _embedding_instance:
        return _embedding_instance
    
    # Default 384-dimension vector provider
    _embedding_instance = LocalEmbeddingProvider()
    return _embedding_instance
