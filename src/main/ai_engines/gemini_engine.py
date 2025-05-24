# Attempt to import AI SDKs
try:
    import google.generativeai as genai
except ImportError:
    genai = None

from ..ai_bots import AIEngine # Use relative import to access AIEngine from parent directory


class GeminiEngine(AIEngine):
    def __init__(self, api_key: str = None, model_name: str = "gemini-pro"):
        super().__init__(api_key, model_name)
        self.model = None
        if genai and self.api_key:
            try:
                genai.configure(api_key=self.api_key)
                self.model = genai.GenerativeModel(self.model_name)
            except Exception as e:
                print(f"Error configuring Gemini: {e}") 
                self.model = None 
        elif genai and not self.api_key:
            print("GeminiEngine: API key not provided, real calls will fail.")
        elif not genai:
            print("GeminiEngine: google.generativeai SDK not found.")


    def generate_response(self, current_user_prompt: str, conversation_history: list[tuple[str, str]]) -> str:
        if not genai: 
            return "Error: google.generativeai SDK not available."
        if not self.api_key:
            return "Error: Gemini API key not configured."
        if not self.model: 
            return "Error: Gemini model not initialized. Check API key and SDK installation."

        gemini_history = []
        for sender, text_content in conversation_history:
            role = "user" if sender == "User" else "model"
            gemini_history.append({"role": role, "parts": [{"text": text_content}]})
        
        try:
            chat = self.model.start_chat(history=gemini_history)
            response = chat.send_message(current_user_prompt)
            return response.text
        except Exception as e:
            return f"Error: Gemini API call failed: {str(e)}"

    def requires_api_key(self) -> bool:
        return True
