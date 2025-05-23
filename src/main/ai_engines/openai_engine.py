# Attempt to import AI SDKs
try:
    import openai
except ImportError:
    openai = None

from ..ai_bots import AIEngine # Use relative import


class OpenAIEngine(AIEngine):
    def __init__(self, api_key: str = None, model_name: str = "gpt-3.5-turbo"):
        super().__init__(api_key, model_name)
        self.client = None
        if openai and self.api_key:
            try:
                self.client = openai.OpenAI(api_key=self.api_key)
            except Exception as e:
                print(f"Error configuring OpenAI client: {e}")
                self.client = None
        elif openai and not self.api_key:
             print("OpenAIEngine: API key not provided, real calls will fail.")
        elif not openai:
            print("OpenAIEngine: openai SDK not found.")


    def generate_response(self, current_user_prompt: str, conversation_history: list[tuple[str, str]]) -> str:
        if not openai: 
            return "Error: openai SDK not available."
        if not self.api_key or not self.client: 
            return "Error: OpenAI API key not configured or client not initialized."

        openai_history = []
        for sender, text_content in conversation_history:
            role = "user" if sender == "User" else "assistant"
            openai_history.append({"role": role, "content": text_content})
        
        messages = openai_history + [{"role": "user", "content": current_user_prompt}]
        
        try:
            completion = self.client.chat.completions.create(
                model=self.model_name, 
                messages=messages
            )
            return completion.choices[0].message.content
        except Exception as e:
            return f"Error: OpenAI API call failed: {str(e)}"
