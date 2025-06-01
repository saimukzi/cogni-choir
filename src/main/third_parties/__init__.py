from . import xai as _xai
from . import azure_openai as _azure_openai
from . import google as _google

THIRD_PARTY_CLASSES = [
    _xai.XAI,
    _azure_openai.AzureOpenAI,
    _google.Google,
]
