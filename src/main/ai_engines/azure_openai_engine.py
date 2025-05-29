"""Implementation of an AI engine using Microsoft Azure OpenAI services.

This module defines the `AzureOpenAIEngine` class, which interfaces with
Azure OpenAI to provide text generation capabilities. It handles the
construction of prompts, communication with the Azure OpenAI API, and
error handling specific to the service.

Configuration for the Azure endpoint and deployment name (model) is expected
to be found in `tmp/azure_endpoint.txt` and `tmp/azure_model.txt` respectively.
"""
import logging
import os
import openai
from ..ai_base import AIEngine
from .. import commons
from ..message import Message


class AzureOpenAIEngine(AIEngine):
    """An AI engine that uses Azure OpenAI for response generation.

    This engine connects to an Azure OpenAI deployment to generate text-based
    responses. It requires an API key, an Azure endpoint, and a deployment name
    (model) for its operation.

    Attributes:
        api_key (str): The API key for accessing Azure OpenAI services.
        azure_endpoint (str): The specific Azure endpoint URL for the OpenAI service.
        api_version (str): The API version string for the Azure OpenAI service.
        deployment_name (str): The name of the deployed model on Azure to be used.
        client (openai.AzureOpenAI): The Azure OpenAI client instance.
    """
    def __init__(self, api_key: str = None, model_name: str = None):
        """Initializes the AzureOpenAIEngine.

        Args:
            api_key (str, optional): The Azure OpenAI API key. Defaults to None.
                                     If not provided, it must be available through
                                     other means (e.g., environment variables)
                                     for the client to authenticate.
            model_name (str, optional): This parameter is not directly used for
                                        selecting the Azure model in this implementation,
                                        as `deployment_name` is read from a file.
                                        It is present for compatibility with the base class.
                                        Defaults to None.

        Raises:
            commons.EscapeException: If configuration files for Azure endpoint or
                                     model cannot be read.
        """
        super().__init__(api_key, model_name)
        self.api_key = api_key
        # Configuration for azure_endpoint and deployment_name is critical.
        # Consider adding more robust error handling or configuration management here.
        self.azure_endpoint = commons.read_str(os.path.join('tmp','azure_endpoint.txt'))
        self.api_version = '2024-12-01-preview' # This could be configurable
        self.deployment_name = commons.read_str(os.path.join('tmp','azure_model.txt'))
        
        self.client = openai.AzureOpenAI(
            api_key=self.api_key,
            azure_endpoint=self.azure_endpoint,
            api_version=self.api_version
        )
        logging.info(f"AzureOpenAIEngine initialized with deployment: {self.deployment_name}, endpoint: {self.azure_endpoint}")

    def generate_response(self, role_name: str, system_prompt: str, conversation_history: list[Message]) -> str:
        """Generates a response using the configured Azure OpenAI model.

        Constructs a message list suitable for the Azure OpenAI API from the
        provided system prompt and conversation history. It then calls the
        API and returns the generated text. Error handling is included for
        common API issues.

        Args:
            role_name (str): The name of the assistant role in the conversation.
                             Messages from this role are mapped to "assistant".
            system_prompt (str): The system prompt to guide the AI's behavior.
            conversation_history (list[Message]): A Message list
                                                        containing the current
                                                        conversation.

        Returns:
            str: The generated text response from the AI, or an error message
                 if generation fails.
        """
        messages = [{"role": "system", "content": system_prompt}]
        for msg in conversation_history:
            if msg.sender == role_name:
                messages.append({"role": "assistant", "content": msg.content.strip()})
            else:
                # messages.append({"role": "user", "content": msg['text']})
                reuse_content = True
                if len(messages) <= 0:
                    reuse_content = False
                if reuse_content and len(messages) >= 1 and messages[-1]["role"] != "user":
                    reuse_content = False

                if reuse_content:
                    messages[-1]["content"] += '\n\n'
                else:
                    messages.append({"role": "user", "content": ""})
                messages[-1]["content"] += f'{msg.sender} said:\n{msg.content.strip()}'

        # Log the constructed messages list for debugging, if necessary (optional)
        # logging.debug(f"Constructed messages for Azure OpenAI: {messages}")

        try:
            response = self.client.chat.completions.create(
                model=self.deployment_name,
                messages=messages
            )
            if response.choices and len(response.choices) > 0:
                generated_text = response.choices[0].message.content.strip()
                # Log the successful generation, possibly with a summary of input if not too verbose
                logging.info(f"Successfully generated response from Azure OpenAI for role {role_name}.")
                return generated_text
            else:
                logging.error(f"No response choices found from Azure OpenAI for role {role_name}.")
                return "Error: No response generated."
        except openai.APIConnectionError as e:
            logging.error(f"Azure OpenAI API connection error for role {role_name}: {e}")
            return f"Error: Could not connect to Azure OpenAI API. Details: {e}"
        except openai.RateLimitError as e:
            logging.error(f"Azure OpenAI API rate limit exceeded for role {role_name}: {e}")
            return f"Error: Azure OpenAI API rate limit exceeded. Details: {e}"
        except openai.AuthenticationError as e:
            logging.error(f"Azure OpenAI API authentication error for role {role_name}: {e}")
            return f"Error: Azure OpenAI API authentication failed. Please check your API key and endpoint. Details: {e}"
        except openai.APIError as e:
            logging.error(f"Azure OpenAI API error for role {role_name}: {e}")
            return f"Error: An unexpected error occurred with the Azure OpenAI API. Details: {e}"
        except Exception as e:
            logging.error(f"An unexpected error occurred for role {role_name}: {e}")
            return f"Error: An unexpected error occurred. Details: {e}"

    def requires_api_key(self) -> bool:
        """Checks if this AI engine requires an API key for its operation.

        Returns:
            bool: True, as Azure OpenAI always requires an API key.
        """
        return True
