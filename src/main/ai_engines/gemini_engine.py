import logging
# Attempt to import AI SDKs
try:
    from google import genai
except ImportError:
    genai = None

from ..ai_base import AIEngine # Use relative import to access AIEngine from its new location
from ..commons import EscapeException

class GeminiEngine(AIEngine):
    def __init__(self, api_key: str = None, model_name: str = "gemini-2.5-flash-preview-05-20"):
        super().__init__(api_key, model_name)
        self.logger = logging.getLogger(__name__ + ".GeminiEngine")
        self.client = None
        self.logger.info(f"Initializing GeminiEngine with model '{model_name}'.")

        try:
            if not genai:
                self.logger.warning("GeminiEngine: google.generativeai SDK not found. Ensure it is installed.")
                raise EscapeException()
            if not self.api_key:
                self.logger.warning("GeminiEngine: API key not provided, real calls will fail.")
                raise EscapeException()
            self.client = genai.Client(api_key=self.api_key)  # Do not log self.api_key
            self.logger.info("Gemini SDK configured successfully.")
        except EscapeException:
            pass


    def generate_response(self, role_name: str, system_prompt: str, conversation_history: list[dict]) -> str:
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
        return True
