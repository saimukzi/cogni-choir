import logging
# Attempt to import AI SDKs
try:
    import google.generativeai as genai
except ImportError:
    genai = None

from ..ai_bots import AIEngine # Use relative import to access AIEngine from parent directory


class GeminiEngine(AIEngine):
    def __init__(self, api_key: str = None, model_name: str = "gemini-pro"):
        super().__init__(api_key, model_name)
        self.logger = logging.getLogger(__name__ + ".GeminiEngine")
        self.model = None
        self.logger.info(f"Initializing GeminiEngine with model '{model_name}'.")
        if genai and self.api_key:
            try:
                genai.configure(api_key=self.api_key) # Do not log self.api_key
                self.model = genai.GenerativeModel(self.model_name)
                self.logger.info("Gemini SDK configured successfully.")
            except Exception as e:
                self.logger.error(f"Error configuring Gemini SDK: {e}", exc_info=True)
                self.model = None 
        elif genai and not self.api_key:
            self.logger.warning("GeminiEngine: API key not provided, real calls will fail.")
        elif not genai:
            self.logger.warning("GeminiEngine: google.generativeai SDK not found.")


    def generate_response(self, current_user_prompt: str, conversation_history: list[tuple[str, str]]) -> str:
        self.logger.info(f"Generating response for prompt_len={len(current_user_prompt)}, history_len={len(conversation_history)}")
        if not genai: 
            msg = "Error: google.generativeai SDK not available."
            self.logger.error(msg)
            return msg
        if not self.api_key:
            msg = "Error: Gemini API key not configured."
            self.logger.error(msg)
            return msg
        if not self.model: 
            msg = "Error: Gemini model not initialized. Check API key and SDK installation."
            self.logger.error(msg)
            return msg

        gemini_history = []
        for sender, text_content in conversation_history:
            role = "user" if sender == "User" else "model"
            gemini_history.append({"role": role, "parts": [{"text": text_content}]})
        
        try:
            self.logger.debug(f"Sending request to Gemini API. Prompt (first 50 chars): '{current_user_prompt[:50]}...'")
            chat = self.model.start_chat(history=gemini_history)
            response = chat.send_message(current_user_prompt)
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
        return True
