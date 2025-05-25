import logging

from ..commons import EscapeException
# Attempt to import AI SDKs
try:
    import openai
except ImportError:
    openai = None

from ..ai_base import AIEngine # Use relative import from new location


class OpenAIEngine(AIEngine):
    def __init__(self, api_key: str = None, model_name: str = "gpt-3.5-turbo"):
        super().__init__(api_key, model_name)
        self.logger = logging.getLogger(__name__ + ".OpenAIEngine")
        self.client = None
        self.logger.info(f"Initializing OpenAIEngine with model '{model_name}'.")

        try:
            if not openai:
                self.logger.warning("OpenAIEngine: openai SDK not found. Ensure it is installed.")
                raise EscapeException()
            if not self.api_key:
                self.logger.warning("OpenAIEngine: API key not provided, real calls will fail.")
                raise EscapeException()
            try:
                self.client = openai.OpenAI(api_key=self.api_key) # Do not log self.api_key
                self.logger.info("OpenAI client configured successfully.")
            except Exception as e:
                self.logger.error(f"Error configuring OpenAI client: {e}", exc_info=True)
                self.client = None
        except EscapeException:
            self.logger.warning("OpenAIEngine: Initialization failed due to missing SDK or API key.")
            self.client = None


    def generate_response(self, role_name: str, system_prompt: str, conversation_history: list[dict]) -> str:
        self.logger.info(f"Generating response for role_name={role_name}, system_prompt={system_prompt}, history_len={len(conversation_history)}")
        if not openai: 
            msg = "Error: openai SDK not available."
            self.logger.error(msg)
            return msg
        if not self.api_key or not self.client: 
            msg = "Error: OpenAI API key not configured or client not initialized."
            self.logger.error(msg)
            return msg

        contents = []
        for msg in conversation_history:
            sender_role = msg['role']
            text_content = msg['text'].strip()
            if sender_role == role_name:
                contents.append({"role": "assistant", "content": text_content})
            else:
                reuse_content = True
                if len(contents) <= 0:
                    reuse_content = False
                if reuse_content and len(contents) >= 1 and contents[-1]["role"] != "user":
                    reuse_content = False

                if reuse_content:
                    text = contents[-1]["content"]
                    text += f'\n\n{sender_role} said:\n{text_content}'
                    contents[-1]["content"] = text
                else:
                    text = f'{sender_role} said:\n{text_content}'
                    content = {"role": "user", "content": text}
                    contents.append(content)

        messages = contents
        
        try:
            self.logger.debug(f"Sending request to OpenAI API. Model: '{self.model_name}'. Prompt (first 50 chars): '{messages[:50]}...'")
            response = self.client.responses.create(
                model=self.model_name, 
                instructions=system_prompt,
                input=messages
            )
            return response.output_text
            # if completion.choices and completion.choices[0].message:
            #     content = completion.choices[0].message.content
            #     if content:
            #         self.logger.info("Successfully received response from OpenAI API.")
            #         # self.logger.debug(f"OpenAI response (first 100 chars): {content[:100]}...")
            #         return content
            #     else:
            #         self.logger.error("OpenAI API call returned an empty message content.")
            #         return "Error: OpenAI API call returned an empty message content."
            # else:
            #     self.logger.error("OpenAI API call did not return expected structure (no choices or message).")
            #     return "Error: OpenAI API call did not return expected structure."
        except Exception as e:
            self.logger.error(f"OpenAI API call failed: {str(e)}", exc_info=True)
            return f"Error: OpenAI API call failed: {str(e)}"

    def requires_api_key(self) -> bool:
        return True
