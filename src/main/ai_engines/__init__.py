"""Initializes the AI engines package.

This package provides various AI engine implementations. This __init__ file
makes the engine classes directly available under the `ai_engines` namespace
and defines a mapping from engine type names to their respective classes.

Attributes:
    ENGINE_TYPE_TO_CLASS_MAP (dict[str, type]): A dictionary mapping engine
        type names (e.g., "GeminiEngine") to their corresponding class objects.
        This is useful for dynamically instantiating engines based on configuration.
"""
from .gemini_engine import GeminiEngine
# from .openai_engine import OpenAIEngine
from .grok_engine import GrokEngine
from .azure_openai_engine import AzureOpenAIEngine

__all__ = [
    "GeminiEngine",
    "OpenAIEngine",
    "GrokEngine",
    "AzureOpenAIEngine",
]

ENGINE_TYPE_TO_CLASS_MAP = {
    "GeminiEngine": GeminiEngine,
    # "OpenAIEngine": OpenAIEngine,
    "GrokEngine": GrokEngine,
    "AzureOpenAIEngine": AzureOpenAIEngine,
}
"""A mapping from engine type names (str) to engine class objects.

This dictionary is used to dynamically instantiate AI engine classes based on
a string identifier, typically loaded from configuration files or user input.
For example, `ENGINE_TYPE_TO_CLASS_MAP["GeminiEngine"]` would return the
`GeminiEngine` class.
"""
