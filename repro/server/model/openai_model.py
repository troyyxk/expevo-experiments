import os
import openai
from openai import OpenAI
from model.base_model import BaseModel


class OpenAIModel(BaseModel):
    def __init__(self, model_name: str, temperature: float = 0.7):
        self.model_name = model_name
        self.openai_api_key = os.environ["OPENAI_API_KEY"]
        openai.api_key = self.openai_api_key
        self.temperature = temperature
        # self.client = OpenAI(api_key=self.openai_api_key)

    def generate_distillation(self, txt: str) -> str:
        # TODO fine-tune prompt later
        prompt = txt
        messages = [{"role": "user", "content": prompt}]

        response = openai.ChatCompletion.create(
            model=self.model_name,
            messages=messages,
            temperature=self.temperature,
            # max_tokens=max_tokens,
        )

        return response.choices[0].message['content'].strip()

    def generate_answer(self, txt: str) -> str:
        # TODO fine-tune prompt later
        prompt = txt
        messages = [{"role": "user", "content": prompt}]

        response = openai.ChatCompletion.create(
            model=self.model_name,
            messages=messages,
            temperature=self.temperature,
            # max_tokens=max_tokens,
        )

        return response.choices[0].message['content'].strip()

