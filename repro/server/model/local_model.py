from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
from model.base_model import BaseModel
from prompt_manager import PromptManager
from config import model_parameter
from util import get_generated_text
from util import log_flush
import datetime


class LocalModel(BaseModel):
    def __init__(self, model_path: str):
        self.model_path = model_path
        self.tokenizer = AutoTokenizer.from_pretrained(model_path)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_path,
            device_map="auto",
            torch_dtype="auto"
        )
        self.pm = PromptManager()
        self.temperature = model_parameter["temperature"]
        self.pipe = pipeline("text-generation", 
                            model=self.model, 
                            tokenizer=self.tokenizer,
                            do_sample=True,
                            temperature=self.temperature,
                            max_length=model_parameter["pipe_max_length"],
                            )
        # logger setting
        self.fileIO = open('./log/local_model.txt', 'a')
        log_flush(self.fileIO, "===============================")
        log_flush(self.fileIO, "Start teacher model on " + str(datetime.datetime.now()))
        
    def clean_pipe(self, prompt: str) -> str:
        result = get_generated_text(self.pipe(prompt))
        return result

    def generate_distillation(self, txt: str) -> str:
        print("[Local Model] Distilling...")
        summerization_prompt = self.pm.generate_llama_summarize_prompt(txt)
        # print("summerization_prompt: ", summerization_prompt)
        summarized_result = self.clean_pipe(summerization_prompt)
        # print("summarized_result: ", summarized_result)
        summarized_txt = self.pm.retrieve_llama_summarized_content(summarized_result)
        # print("summarized_txt: ", summarized_txt)
        return summarized_txt
    
    def generate_QA_distillation(self, question: str, correct_answers: list, wrong_answers: list) -> str:
        """
        Get the distillation of the multiple choice question.
        """
        print("[Local Model] Multiple choice distilling...")
        log_flush(self.fileIO, "================================")
        log_flush(self.fileIO, f"Input question: {question}; correct answers: {correct_answers}; wrong answers: {wrong_answers}")
        qa_txt = f"{question} "
        if len(correct_answers) > 0:
            # if len(correct_answers) > 1:
            #     raise ValueError(f"ERROR: in generate_QA_distillation() more than 1 correct answers: {question}, correct answers: {correct_answers}, wrong answers: {wrong_answers}.")
            qa_txt += f"The answer is '{correct_answers[0]}'"
        elif len(wrong_answers) > 0:
            wrong_ans_str = " or ".join([f"'{w_ans}'" for w_ans in wrong_answers])
            qa_txt += f"The answer is NOT {wrong_ans_str}"
        else:
            raise ValueError(f"ERROR: in generate_QA_distillation() no answers: {question}, correct answers: {correct_answers}, wrong answers: {wrong_answers}.")
        log_flush(self.fileIO, f"Distillation input: {qa_txt}")
        summerization_prompt = self.pm.generate_llama_summarize_prompt(qa_txt)
        # print("summerization_prompt: ", summerization_prompt)
        summarized_result = self.clean_pipe(summerization_prompt)
        # print("summarized_result: ", summarized_result)
        summarized_txt = self.pm.retrieve_llama_summarized_content(summarized_result)
        log_flush(self.fileIO, f"Distillation output: {summarized_txt}")
        # print("summarized_txt: ", summarized_txt)
        return summarized_txt
    
    def generate_MC_distillation(self, question: str, correct_answers: list, wrong_answers: list) -> str:
        """
        Get the distillation of the multiple choice question.
        """
        print("[Local Model] Multiple choice distilling...")
        summerization_prompt = self.pm.generate_llama_MC_distillation_prompt(question, correct_answers, wrong_answers)
        # print("summerization_prompt: ", summerization_prompt)
        summarized_result = self.clean_pipe(summerization_prompt)
        # print("summarized_result: ", summarized_result)
        summarized_txt = self.pm.retrieve_llama_summarized_content(summarized_result)
        # print("summarized_txt: ", summarized_txt)
        return summarized_txt


    def generate_answer(self, txt: str, context: str) -> str:
        print("[Local Model] Generating answer...")
        generation_prompt = self.pm.generate_llama_generation_prompt(txt, context)
        # print("generation_prompt: ", generation_prompt)
        generation_result = self.clean_pipe(generation_prompt)
        # print("generation_result: ", generation_result)
        answer = self.pm.retrieve_llama_generation_content(generation_result)
        # print("answer: ", answer)
        return answer

    def get_question_type(self, txt: str) -> str:
        print("[Local Model] Classifying question type...")
        classify_type_prompt = self.pm.generate_llama_classify_question_type(txt)
        # print("classify_type_prompt: ", classify_type_prompt)
        classify_type_result = self.clean_pipe(classify_type_prompt)
        # print("classify_type_result: ", classify_type_result)
        result_type = self.pm.retrieve_llama_generation_content(classify_type_result)
        # print("result_type: ", result_type)
        return result_type

