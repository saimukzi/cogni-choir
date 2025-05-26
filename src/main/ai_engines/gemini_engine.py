"""Implementation of an AI engine using Google's Gemini models.

This module defines the `GeminiEngine` class, which interfaces with the
Google Generative AI SDK (google-genai) to provide text generation
capabilities using Gemini models. It handles API key configuration,
prompt construction, communication with the Gemini API, and error handling.
"""
import logging
# Attempt to import AI SDKs
try:
    from google import genai
except ImportError:
    genai = None

from ..ai_base import AIEngine # Use relative import to access AIEngine from its new location
from ..commons import EscapeException
from google.genai.types import Tool, GenerateContentConfig, GoogleSearch

class GeminiEngine(AIEngine):
    """An AI engine that uses Google's Gemini models for response generation.

    This engine leverages the `google-genai` SDK. It requires an API key for
    Google's Generative AI services and can be configured to use different
    Gemini models.

    Attributes:
        logger: Logger instance for this engine.
        client: An instance of `google.genai.Client` if initialization is successful.
        model_name (str): The specific Gemini model to be used (e.g., "gemini-1.5-flash-latest").
        tools (list[Tool]): A list of tools available to the Gemini model,
                            currently configured with GoogleSearch.
    """
    def __init__(self, api_key: str = None, model_name: str = "gemini-1.5-flash-latest"): # Updated model name
        """Initializes the GeminiEngine.

        Sets up the logger and attempts to configure the `google-genai` client
        using the provided API key. If the SDK is not found or the API key is
        missing, warnings are logged, and the client remains uninitialized.

        Args:
            api_key (str, optional): The API key for Google Generative AI services.
                                     Defaults to None.
            model_name (str, optional): The name of the Gemini model to use.
                                        Defaults to "gemini-1.5-flash-latest".
        """
        super().__init__(api_key, model_name) # model_name is passed to super
        self.logger = logging.getLogger(__name__ + ".GeminiEngine")
        self.client = None
        self.logger.info(f"Initializing GeminiEngine with model '{self.model_name}'.") # Use self.model_name
        self.tools = [Tool(google_search = GoogleSearch())]

        try:
            if not genai:
                self.logger.warning("GeminiEngine: google.generativeai SDK not found. Ensure it is installed.")
                raise EscapeException("google.generativeai SDK not found.") # Add message to exception
            if not self.api_key:
                self.logger.warning("GeminiEngine: API key not provided, real calls will fail.")
                # Not raising EscapeException here as the engine might be used in a context
                # where API key is optional for some operations or set later.
                # However, generate_response will fail.
                return # Exit init if no API key
            self.client = genai.Client(api_key=self.api_key)
            self.logger.info("Gemini SDK configured successfully.")
        except EscapeException as e:
            self.logger.warning(f"GeminiEngine initialization skipped due to: {e}")
        except Exception as e: # Catch other potential errors during client init
            self.logger.error(f"GeminiEngine: Error during google.genai.Client initialization: {e}", exc_info=True)


    def generate_response(self, role_name: str, system_prompt: str, conversation_history: list[dict]) -> str:
        """Generates a response using the configured Gemini model.

        Constructs a message list suitable for the Gemini API from the
        provided system prompt and conversation history. It then calls the
        API via the `google-genai` client and returns the generated text.
        Handles cases where the SDK or API key is missing.

        Args:
            role_name (str): The name of the assistant role in the conversation.
                             Messages from this role are mapped to "model".
            system_prompt (str): The system prompt to guide the AI's behavior.
            conversation_history (list[dict]): A list of message dictionaries,
                                               where each dictionary has 'role' and 'text'.

        Returns:
            str: The generated text response from the AI, or an error message
                 if generation fails or prerequisites (SDK, API key) are not met.
        """
        self.logger.info(f"Generating response for prompt_len={len(system_prompt)}, history_len={len(conversation_history)}")
        if not genai: 
            msg = "Error: google.generativeai SDK not available."
            self.logger.error(msg)
            return msg
        if not self.api_key:
            msg = "Error: Gemini API key not configured."
            self.logger.error(msg)
            return msg
        if not self.client: 
            msg = "Error: Gemini client not initialized. Check if the SDK is installed and API key is set."
            self.logger.error(msg)
            return msg

        system_instruction = system_prompt.strip()

        contents = []
        for msg in conversation_history:
            sender_role = msg['role']
            text_content = msg['text'].strip()
            if sender_role == role_name:
                contents.append({"role": "model", "text": text_content})
            else:
                reuse_content = True
                if len(contents) <= 0:
                    reuse_content = False
                if reuse_content and len(contents) >= 1 and contents[-1]["role"] == "model":
                    reuse_content = False

                if reuse_content:
                    text = contents[-1]["text"]
                    text += f'\n\n{sender_role} said:\n{text_content}'
                    contents[-1]["text"] = text
                else:
                    text = f'{sender_role} said:\n{text_content}'
                    content = {"role": "user", "text": text}
                    contents.append(content)
        # print(contents)
        contents = map(
            lambda x: genai.types.Content(
                role=x['role'],
                parts=[genai.types.Part(text=x['text'])]
            ),
            contents
        )
        contents = list(contents)
        
        try:
            self.logger.debug(f"Sending request to Gemini API. System prompt (first 50 chars): '{system_prompt[:50]}...'")
            # chat = self.model.start_chat(history=gemini_history)
            # response = chat.send_message(current_user_prompt)
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=contents,
                # systemInstruction=system_instruction,
                config=genai.types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    tools=self.tools,
                ),
            )
            # Check if response.text exists and is not empty, as per some API behaviors for safety/errors
            if hasattr(response, 'text') and response.text:
                 self.logger.info("Successfully received response from Gemini API.")
                 # self.logger.debug(f"Gemini response (first 100 chars): {response.text[:100]}..." )
                 return response.text
            else:
                # This part handles cases where the response object might not have 'text' or it's empty
                # or if there's a non-exception error indicated by the response structure.
                # Attempt to find more specific error information if available.
                error_details = "Unknown error: Response structure was not as expected or text was empty."
                if hasattr(response, 'prompt_feedback') and response.prompt_feedback:
                    error_details = f"Gemini API issue: Prompt feedback: {response.prompt_feedback}"
                self.logger.error(f"Gemini API call did not return expected text response. Details: {error_details}")
                return f"Error: Gemini API call failed or returned empty response. Details: {error_details}"

        except Exception as e:
            self.logger.error(f"Gemini API call failed: {str(e)}", exc_info=True)
            return f"Error: Gemini API call failed: {str(e)}"

    def requires_api_key(self) -> bool:
        """Checks if this AI engine requires an API key for its operation.

        Returns:
            bool: True, as Gemini models always require an API key.
        """
        return True
