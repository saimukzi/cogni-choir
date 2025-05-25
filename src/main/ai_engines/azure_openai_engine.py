import logging
import os
import openai
from ..ai_base import AIEngine
from .. import commons


class AzureOpenAIEngine(AIEngine):
    def __init__(self, api_key: str = None, model_name: str = None):
        super().__init__(api_key, model_name)
        self.api_key = api_key
        self.azure_endpoint = commons.read_str(os.path.join('tmp','azure_endpoint.txt'))
        self.api_version = '2024-12-01-preview'
        self.deployment_name = commons.read_str(os.path.join('tmp','azure_model.txt'))
        self.client = openai.AzureOpenAI(
            api_key=api_key,
            azure_endpoint=self.azure_endpoint,
            api_version=self.api_version
        )
        logging.info("AzureOpenAIEngine initialized.")

    def generate_response(self, role_name: str, system_prompt: str, conversation_history: list[dict]) -> str:
        messages = [{"role": "system", "content": system_prompt}]
        for msg in conversation_history:
            if msg['role'] == role_name:
                messages.append({"role": "assistant", "content": msg['text']})
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
                messages[-1]["content"] += f'{msg["role"]} said:\n{msg["text"]}'

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
        return True
