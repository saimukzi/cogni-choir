"""Initializes the third_parties package.

This package groups modules that provide integrations with various third-party
AI services. It makes concrete implementations of AI engines available to the
rest of the application.

Currently available services include:
    - XAI: Integration with xAI's services.
    - AzureOpenAI: Integration with Microsoft Azure OpenAI services.
    - Google: Integration with Google's AI services (e.g., Gemini).
"""
from . import xai as _xai
from . import azure_openai as _azure_openai
from . import google as _google

THIRD_PARTY_CLASSES = [
    _xai.XAI,
    _azure_openai.AzureOpenAI,
    _google.Google,
]
