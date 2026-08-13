"""Interface-owned error hierarchy, classified by origin.

Mirrors `newsagent.llm.errors` exactly (AD-3 - the two pluggable-provider
sub-patterns share a shape but not a module). Adapters translate
vendor-specific exceptions into these - no vendor exception type may cross the
interface boundary. `transient` marks errors the base class retries
internally before surfacing.
"""


class SuggestionError(Exception):
    """Base for all provider-interface errors."""

    transient: bool = False


class SuggestionInputError(SuggestionError):
    """The input/context is at fault (e.g. content too large for the provider)."""


class SuggestionProviderError(SuggestionError):
    """The provider itself failed (bad response, service-side error)."""


class SuggestionTransportError(SuggestionError):
    """Infrastructure/network failure between us and the provider."""

    transient = True
