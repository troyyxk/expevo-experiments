from model.base_model import BaseModel
from model.local_model import LocalModel
from model.openai_model import OpenAIModel

def load_model(model_type: str, model_path: str) -> BaseModel:
    if model_type == "openai":
        return OpenAIModel(model_path)
    elif model_type == "local":
        return LocalModel(model_path)
    else:
        raise Exception(f"In util.py load_model(), model_type ({model_type}) is not recognized.")