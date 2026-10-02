from app.core.config import settings
from app.config import settings as app_settings
from app.ai.providers.base import LLMProvider, EmbeddingProvider
from app.ai.providers.anthropic_provider import AnthropicProvider
from app.ai.providers.gemini_provider import GeminiProvider
from app.ai.providers.mock_provider import MockLLMProvider, LocalEmbeddingProvider
from app.ai.providers.groq_provider import GroqProvider

_llm_instance = None
_embedding_instance = None

def get_llm_provider() -> LLMProvider:
    global _llm_instance
    if _llm_instance:
        return _llm_instance

    if app_settings.GROQ_API_KEY:
        _llm_instance = GroqProvider()
        return _llm_instance

    provider_name = settings.DEFAULT_LLM_PROVIDER.lower()
    if provider_name == "anthropic" and settings.ANTHROPIC_API_KEY:
        _llm_instance = AnthropicProvider()
    elif provider_name == "gemini" and settings.GEMINI_API_KEY:
        _llm_instance = GeminiProvider()
    else:
        # Graceful fallback to deterministic mock provider
        _llm_instance = MockLLMProvider()
    
    return _llm_instance

def get_embedding_provider() -> EmbeddingProvider:
    global _embedding_instance
    if _embedding_instance:
        return _embedding_instance
    
    # Default 384-dimension vector provider
    _embedding_instance = LocalEmbeddingProvider()
    return _embedding_instance
