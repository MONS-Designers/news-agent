"""Interface-owned error hierarchy, classified by origin.

Adapters translate vendor-specific exceptions into these - no vendor exception
type may cross the interface boundary. `transient` marks errors the base class
retries internally before surfacing.
"""


class LLMError(Exception):
    """Base for all provider-interface errors."""

    transient: bool = False


class LLMInputError(LLMError):
    """The input/context is at fault (e.g. content too large for the provider)."""


class LLMProviderError(LLMError):
    """The provider itself failed (bad response, service-side error)."""


class LLMTransportError(LLMError):
    """Infrastructure/network failure between us and the provider."""

    transient = True
