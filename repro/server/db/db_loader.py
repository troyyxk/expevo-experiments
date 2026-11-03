from db.base_db import BaseDB
from db.keyword_db import KeywordDB
from db.vector_db import VectorDB
from condence_model import CondenseModel


def load_db(db_type: str, port: int, model: CondenseModel) -> BaseDB:
    if db_type == "vector":
        return VectorDB(port, model)
    elif db_type == "keyword":
        return KeywordDB()
    else:
        raise Exception("In util.py load_db(), model_type is not recognized.")
    