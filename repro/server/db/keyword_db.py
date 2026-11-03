from db.base_db import BaseDB
from typing import Dict, List


class KeywordDB(BaseDB):
    def __init__(self):
        self.store = {}

    def get(self, query_txt: List[str], k) -> str:
        """
        info: in KeywordDB is a list of keywords
        """
        retrieved_info = ""
        for keyword in query_txt:
            retrieved_info += self.store[keyword]
        return retrieved_info

    def put(self, txt):
        """
        :param info: formated as dict[keywords, string of information]
        """
        for keyword in txt:
            if keyword not in self.store:
                self.store[keyword] = ""
            self.store[keyword] += " " + txt[keyword]
