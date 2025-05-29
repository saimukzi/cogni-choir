"""AI engine implementation for xAI's Grok.

This module defines the `GrokEngine` class, which interacts with xAI's Grok API
using an OpenAI-compatible client. It allows for generating responses from Grok
based on provided prompts and conversation history.
"""
import logging
import openai
from ..ai_base import AIEngine # Use relative import from new location
from ..message import Message


class GrokEngine(AIEngine):
    """AI engine for xAI's Grok, using an OpenAI-compatible API.

    This class interfaces with xAI's Grok API to generate text responses.
    It uses an OpenAI-compatible client to make requests to the Grok API endpoint.

    Attributes:
        logger: Logger instance for this engine.
        model_name (str): The model name specified for Grok (e.g., "grok-3-latest").
        client (openai.OpenAI): The OpenAI client configured for xAI's Grok API.
    """
    def __init__(self, api_key: str = None, model_name: str = "grok-3-latest"):
        """Initializes the GrokEngine.

        Sets up the logger, validates the API key, and initializes the
        OpenAI client to interact with xAI's Grok API.

        Args:
            api_key (str, optional): The API key for xAI's Grok API.
                                     Defaults to None. If None, a ValueError
                                     is raised.
            model_name (str, optional): The name of the Grok model to use.
                                        Defaults to "grok-3-latest".

        Raises:
            ValueError: If `api_key` is not provided.
        """
        super().__init__(api_key, model_name) # model_name is passed to super
        self.logger = logging.getLogger(__name__ + ".GrokEngine")
        self.logger.info(f"Initializing GrokEngine with model '{self.model_name}'.")

        if not api_key:
            raise ValueError("GrokEngine requires an API key, but none was provided.")

        self.client = openai.OpenAI(
            api_key = self.api_key,
            base_url = "https://api.x.ai/v1",
        )

    def generate_response(self, role_name: str, system_prompt: str, conversation_history: list[Message]) -> str:
        """Generates a response from Grok using the configured API.

        Constructs a list of messages from the system prompt and conversation
        history, then sends a request to the Grok API via the OpenAI client.
        It handles successful responses by returning the generated text and
        logs various API errors if they occur, returning an error message.

        Args:
            role_name (str): The name of the assistant role (e.g., "AI Assistant").
                This is used to label messages from the AI in the API request.
            system_prompt (str): The initial prompt that defines the AI's persona
                or task.
            conversation_history (list[Message]): A list of `Message` objects
                representing the preceding conversation.

        Returns:
            str: The generated text response from Grok, or an error message
                 if an issue occurred during generation or API interaction.
        """
        messages = [{"role": "system", "content": system_prompt}]
        for msg in conversation_history:
            if msg.sender == role_name:
                messages.append({"role": "assistant", "content": msg.content.strip()})
            else:
                messages.append({"role": "user", "content": f'{msg.sender} said:\n{msg.content.strip()}'})

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages
            )
            if response.choices and len(response.choices) > 0:
                generated_text = response.choices[0].message.content.strip()
                # Log the successful generation, possibly with a summary of input if not too verbose
                logging.info(f"Successfully generated response from Grok for role {role_name}.")
                return generated_text
            else:
                logging.error(f"No response choices found from Grok for role {role_name}.")
                return "Error: No response generated."
        except openai.APIConnectionError as e:
            logging.error(f"Grok API connection error for role {role_name}: {e}")
            return f"Error: Could not connect to Grok API. Details: {e}"
        except openai.RateLimitError as e:
            logging.error(f"Grok API rate limit exceeded for role {role_name}: {e}")
            return f"Error: Grok API rate limit exceeded. Details: {e}"
        except openai.AuthenticationError as e:
            logging.error(f"Grok API authentication error for role {role_name}: {e}")
            return f"Error: Grok API authentication failed. Please check your API key and endpoint. Details: {e}"
        except openai.APIError as e:
            logging.error(f"Grok API error for role {role_name}: {e}")
            return f"Error: An unexpected error occurred with the Grok API. Details: {e}"
        except Exception as e:
            logging.error(f"An unexpected error occurred for role {role_name}: {e}")
            return f"Error: An unexpected error occurred. Details: {e}"

    def requires_api_key(self) -> bool:
        """Checks if this AI engine requires an API key.

        Returns:
            bool: True, as the Grok API requires an API key for authentication.
        """
        return True
