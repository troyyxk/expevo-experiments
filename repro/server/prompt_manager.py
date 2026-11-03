from util import clean_string, cut_last_appearance


class PromptManager:
    def get_condence_prompt(self, txt: str) -> str:
        prompt = f"""<|begin_of_text|><|start_header_id|>system<|end_header_id|>
                You are a concise and accurate summarization assistant.
                You will condense any given text into a brief summary that:
                - Preserves all essential facts or arguments.
                - Uses plain, accessible language.<|eot_id|>
                <|start_header_id|>user<|end_header_id|>
                Please condense the following text:
                
                "{txt}"
                
                Provide the summary only—no commentary or additional details.<|eot_id|>
                <|start_header_id|>assistant<|end_header_id|>
                Summary:"""
        return prompt 

    def generate_llama_summarize_prompt(self, txt: str) -> str:
        prompt = f"""<|begin_of_text|><|start_header_id|>user<|end_header_id|>
        Summarize this text in less than 3 concise sentences:

        {txt}

        <|eot_id|><|start_header_id|>assistant<|end_header_id|>
        Summary:"""
        return prompt

    def retrieve_llama_summarized_content(self, txt: str) -> str:
        keyword = "Summary:"
        return clean_string(cut_last_appearance(txt, keyword))
