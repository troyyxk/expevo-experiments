from prompt_manager import PromptManager
from util import get_generated_text
from model.local_model import LocalModel


class CondenseModel:
    def __init__(self, model: LocalModel):
        self.model = model
        self.pm = PromptManager()

    def condense(self, txt: str) -> str:
        """
        Input a string and return a condensed, compact version of it using the model.
        """
        prompt = self.pm.get_condence_prompt(txt)
        print("len(prompt): ", len(prompt))
        generate_result = self.model.clean_pipe(prompt)
        condensed_txt = self.pm.retrieve_llama_summarized_content(generate_result)
        return condensed_txt.strip()
