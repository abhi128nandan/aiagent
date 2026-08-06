"""LLM factory — uses litellm under the hood for universal model support.

The Groq provider now uses RateLimitedGroqLLM which automatically:
  - Rotates across multiple API keys
  - Handles 429 rate limits with exponential backoff
  - Tracks TPM/TPD/RPM per key
"""
import asyncio
import random
from typing import Optional, List, Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.callbacks import CallbackManagerForLLMRun, AsyncCallbackManagerForLLMRun
from langchain_core.messages import BaseMessage, AIMessage
from langchain_core.outputs import ChatResult, ChatGeneration

from core.config import get_settings
from core.logger import get_logger
from services.secrets_service import SecretsService
from models.llm_profile import LLMProfile

settings = get_settings()
logger = get_logger(__name__)


class LLMFactory:
    """Factory for creating LLM instances across providers."""

    def __init__(self, secrets_service: Optional[SecretsService] = None) -> None:
        self.secrets_service = secrets_service or SecretsService()

    def create(
        self,
        provider: Optional[str] = None,
        model_name: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
        role: Optional[str] = None,
    ) -> BaseChatModel:
        provider = provider or settings.DEFAULT_LLM_PROVIDER

        if provider == "groq":
            llm = self._create_groq(model_name, temperature, max_tokens, role)
        elif provider == "ollama":
            llm = self._create_ollama(model_name, temperature, max_tokens, role)
        elif provider == "anthropic":
            llm = self._create_anthropic(model_name, temperature, max_tokens)
        elif provider == "openai":
            llm = self._create_openai(model_name, temperature, max_tokens)
        elif provider == "gemini":
            llm = self._create_gemini(model_name, temperature, max_tokens, role)
        elif model_name:
            llm = self._create_openai(model_name, temperature, max_tokens)
        else:
            raise ValueError(f"Unknown provider: {provider}")

        return self._apply_fallbacks(llm, provider, temperature, max_tokens, role)

    def _apply_fallbacks(
        self, 
        primary_llm: BaseChatModel, 
        primary_provider: str, 
        temperature: float, 
        max_tokens: Optional[int],
        role: Optional[str]
    ) -> BaseChatModel:
        """
        Apply a fallback chain (Gemini -> Claude -> OpenAI -> Ollama) to a primary LLM.
        """
        fallbacks = []
        
        # Order of fallbacks: Anthropic (Claude) -> OpenAI -> Ollama
        providers_to_try = []
        if primary_provider == "gemini":
            providers_to_try = ["anthropic", "openai", "ollama"]
        elif primary_provider == "anthropic":
            providers_to_try = ["openai", "ollama"]
        elif primary_provider == "openai":
            providers_to_try = ["anthropic", "ollama"]
        
        for p in providers_to_try:
            try:
                if p == "anthropic":
                    fallbacks.append(self._create_anthropic(None, temperature, max_tokens))
                elif p == "openai":
                    fallbacks.append(self._create_openai(None, temperature, max_tokens))
                elif p == "ollama":
                    fallbacks.append(self._create_ollama(None, temperature, max_tokens, role))
            except Exception as e:
                logger.warning(f"Failed to initialize fallback provider {p}", error=str(e))
                
        if fallbacks:
            return primary_llm.with_fallbacks(fallbacks)
        return primary_llm

    def create_from_profile(self, profile: LLMProfile) -> BaseChatModel:
        return self.create(
            provider=profile.provider,
            model_name=profile.model,
            temperature=profile.temperature,
            max_tokens=profile.max_tokens,
        )

    def _resolve_secret(self, provider: str, fallback: Optional[str]) -> Optional[str]:
        try:
            secret = self.secrets_service.get_secret(provider)
        except Exception:
            secret = None
        return secret or fallback

    def _build_params(
        self,
        model: str,
        temperature: float,
        max_tokens: Optional[int],
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
    ) -> dict:
        params: dict = {"model": model, "temperature": temperature, "max_retries": 5}
        if max_tokens is not None:
            params["max_tokens"] = max_tokens
        if api_key:
            params["api_key"] = api_key
        if api_base:
            params["api_base"] = api_base
        return params

    def _create_groq(
        self,
        model_name: Optional[str],
        temperature: float,
        max_tokens: Optional[int],
        role: Optional[str] = None,
    ) -> BaseChatModel:
        """
        Create a Groq LLM with automatic multi-key rotation.
        """
        # Respect user selected model or fallback to role-based selection
        if model_name:
            model = model_name
        elif settings.DEFAULT_LLM_MODEL and settings.DEFAULT_LLM_MODEL.startswith("groq/"):
            model = settings.DEFAULT_LLM_MODEL
        elif role == "planner":
            model = "groq/llama-3.3-70b-versatile"
        elif role == "coder":
            model = "groq/meta-llama/llama-4-scout-17b-16e-instruct"
        elif role == "validator":
            model = "groq/llama-3.1-8b-instant"
        else:
            model = "groq/llama-3.3-70b-versatile"

        # Ensure groq/ prefix
        if not model.startswith("groq/"):
            model = f"groq/{model}"

        # Check if we have multiple keys → use RateLimitedGroqLLM
        keys = settings.get_groq_keys()
        if not keys:
            # Try single key from secrets
            single_key = self._resolve_secret("groq", settings.GROQ_API_KEY)
            if single_key:
                keys = [single_key]

        if not keys:
            raise ValueError(
                "No Groq API keys found. Set GROQ_API_KEYS or GROQ_API_KEY in .env"
            )

        # Use the rate-limited wrapper with key pool
        from agent.rate_limited_llm import RateLimitedGroqLLM

        logger.info(
            "groq_llm_created",
            model=model,
            role=role,
            num_keys=len(keys),
            mode="pool" if len(keys) > 1 else "single",
        )

        groq_llm = RateLimitedGroqLLM(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        # Apply fallback chain so rate-limit exhaustion falls through
        # to Gemini/Anthropic/OpenAI/Ollama automatically
        return self._apply_fallbacks(groq_llm, "groq", temperature, max_tokens, role)

    def _create_gemini(
        self,
        model_name: Optional[str],
        temperature: float,
        max_tokens: Optional[int],
        role: Optional[str] = None,
    ) -> BaseChatModel:
        """
        Create a Gemini LLM.
        """
        # Respect user selected model or fallback to role-based selection
        if model_name:
            model = model_name
        elif settings.DEFAULT_LLM_MODEL and (settings.DEFAULT_LLM_MODEL.startswith("gemini/") or settings.DEFAULT_LLM_MODEL.startswith("models/")):
            model = settings.DEFAULT_LLM_MODEL
        elif role == "planner":
            model = "gemini/gemini-2.5-flash"
        elif role == "coder":
            model = "gemini/gemini-2.5-flash"
        elif role == "validator":
            model = "gemini/gemini-2.5-flash"
        else:
            model = "gemini/gemini-2.5-flash"

        # Ensure gemini/ prefix
        if not model.startswith("gemini/") and not model.startswith("models/"):
            model = f"gemini/{model}"

        # Resolve api_keys
        keys = settings.get_gemini_keys()
        if not keys:
            # Fallback to secrets service
            single_key = self._resolve_secret("gemini", settings.GEMINI_API_KEY)
            if single_key:
                keys = [single_key]

        if not keys:
            raise ValueError(
                "No Gemini API keys found. Set GEMINI_API_KEY or GEMINI_API_KEYS in .env"
            )

        logger.info(
            "gemini_llm_created",
            model=model,
            role=role,
            num_keys=len(keys),
            mode="pool" if len(keys) > 1 else "single",
        )

        return ResilientGeminiLLM(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            api_keys=keys,
        )

    def _create_ollama(
        self,
        model_name: Optional[str],
        temperature: float,
        max_tokens: Optional[int],
        role: Optional[str] = None,
    ) -> BaseChatModel:
        # Multi-agent role routing for local Ollama
        num_ctx = 8192
        
        # Respect user selected model or fallback to role-based selection
        if model_name:
            model = model_name
        elif settings.DEFAULT_LLM_MODEL and settings.DEFAULT_LLM_MODEL.startswith("ollama/"):
            model = settings.DEFAULT_LLM_MODEL
        elif role == "planner":
            model = "ollama/llama3.1:8b"
        elif role == "coder":
            model = "ollama/qwen2.5-coder:7b"
        elif role == "validator":
            model = "ollama/mistral:7b"
        else:
            model = "ollama/mistral:7b"

        # Set specific num_ctx based on role (coder always needs a large context)
        if role == "coder":
            num_ctx = 32768
        else:
            num_ctx = 8192

        # Strip "ollama/" prefix if present
        if model.startswith("ollama/"):
            model = model[len("ollama/"):]

        params = self._build_params(
            model,
            temperature,
            max_tokens,
            api_base=settings.OLLAMA_BASE_URL,
        )
        
        # Force keep_alive=0 to prevent VRAM crashes on model switch, and set specific num_ctx
        params["custom_llm_provider"] = "ollama"
        params["num_ctx"] = num_ctx
        params["options"] = {
            "num_ctx": num_ctx
        }
        params["extra_body"] = {
            "keep_alive": 0,
            "options": {
                "num_ctx": num_ctx
            }
        }
        
        return ChatLiteLLM(**params)

    def _create_anthropic(
        self,
        model_name: Optional[str],
        temperature: float,
        max_tokens: Optional[int],
    ) -> BaseChatModel:
        model = model_name or settings.DEFAULT_LLM_MODEL or "claude-3-5-sonnet-20241022"
        api_key = self._resolve_secret("anthropic", settings.ANTHROPIC_API_KEY)
        return ChatLiteLLM(**self._build_params(model, temperature, max_tokens, api_key=api_key))

    def _create_openai(
        self,
        model_name: Optional[str],
        temperature: float,
        max_tokens: Optional[int],
    ) -> BaseChatModel:
        model = model_name or settings.DEFAULT_LLM_MODEL or "gpt-4o"
        api_key = self._resolve_secret("openai", settings.OPENAI_API_KEY)
        return ChatLiteLLM(**self._build_params(model, temperature, max_tokens, api_key=api_key))


class ResilientGeminiLLM(BaseChatModel):
    """
    A LangChain-compatible chat model that wraps Gemini calls with:
      - Automatic retry on 503 (Service Unavailable)
      - Automatic retry on 429 (Rate Limit/Quota Exhaustion)
      - Exponential backoff
      - Automatic rotation across multiple API keys on retry
    """
    model: str
    temperature: float = 0.2
    max_tokens: Optional[int] = None
    api_keys: List[str]
    max_retries: int = 5
    base_delay: float = 2.0
    max_delay: float = 16.0

    class Config:
        arbitrary_types_allowed = True

    @property
    def _llm_type(self) -> str:
        return "resilient_gemini"

    @property
    def _identifying_params(self) -> dict:
        return {"model": self.model, "temperature": self.temperature}

    def _create_inner_llm(self, api_key: str) -> BaseChatModel:
        params: dict[str, Any] = {
            "model": self.model,
            "temperature": self.temperature,
            "api_key": api_key,
            "max_retries": 0,  # We handle retries ourselves
            "timeout": 180,
        }
        if self.max_tokens is not None:
            params["max_tokens"] = self.max_tokens
        return ChatLiteLLM(**params)

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        import asyncio
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(
                    asyncio.run,
                    self._agenerate(messages, stop=stop, run_manager=None, **kwargs),
                )
                return future.result()
        else:
            return asyncio.run(
                self._agenerate(messages, stop=stop, run_manager=None, **kwargs)
            )

    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        last_error = None
        num_keys = len(self.api_keys)

        for attempt in range(self.max_retries):
            current_key = self.api_keys[attempt % num_keys]
            inner_llm = self._create_inner_llm(current_key)
            try:
                result = await inner_llm.agenerate([messages], stop=stop, **kwargs)
                return ChatResult(generations=result.generations[0], llm_output=result.llm_output)
            except Exception as e:
                last_error = e
                error_str = str(e).lower()

                # Catch retryable errors
                is_retryable = any(
                    indicator in error_str
                    for indicator in [
                        "503",
                        "unavailable",
                        "429",
                        "rate_limit",
                        "rate_limited",
                        "too many requests",
                        "resource_exhausted",
                        "quota",
                        "connection",
                        "timeout",
                    ]
                )

                if is_retryable:
                    delay = min(
                        self.base_delay * (2 ** attempt) + random.uniform(0, 1),
                        self.max_delay,
                    )
                    key_suffix = f"...{current_key[-4:]}" if len(current_key) > 4 else "..."
                    logger.warning(
                        "gemini_request_retry",
                        attempt=attempt + 1,
                        model=self.model,
                        key_suffix=key_suffix,
                        error=error_str[:150],
                        retry_in=round(delay, 1),
                    )
                    await asyncio.sleep(delay)
                    continue
                else:
                    # Non-retryable error
                    logger.error(
                        "gemini_non_retryable_error",
                        model=self.model,
                        error=error_str[:200],
                    )
                    raise e

        logger.error(
            "gemini_all_retries_exhausted",
            model=self.model,
            max_retries=self.max_retries,
            error=str(last_error)[:200],
        )
        if last_error is not None:
            raise last_error
        raise RuntimeError("Gemini call failed with unknown error")


def get_llm(
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
    role: Optional[str] = None,
) -> BaseChatModel:
    """Backward-compatible factory function."""
    return LLMFactory().create(provider=provider, model_name=model_name, role=role)
