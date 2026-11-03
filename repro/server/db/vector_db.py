from rank_bm25 import BM25Okapi
from db.base_db import BaseDB
from config import db_hyperparameter, model_parameter
from esprotocol.protocol import ESMsgDelimiter
from util import log_flush
import json
import os
import numpy as np
from collections import defaultdict
from condence_model import CondenseModel
from model.local_model import LocalModel
from util import get_string_len_sum, tokenize_str


class VectorDB(BaseDB):
    def __init__(self, port: int, lm: LocalModel):
        self.port = port
        self.model = CondenseModel(lm)
        self.max_pipe_condense_size = model_parameter["pipe_max_length"] // 2

        # data base
        self.db = []
        self.tokenized_corpus = []

        # bm25 similarity search setting
        self.bm25 = None
        self.k = db_hyperparameter["k"]
        self.return_bm25th = db_hyperparameter["return_bm25th"]
        self.similarity_bm25th = db_hyperparameter["similarity_bm25th"]
        print(f"self.similarity_bm25th: {self.similarity_bm25th}")

        self.condense_threshold = db_hyperparameter["condense_threshold"]

        # set up logger
        self.fileIO = open(f'./log/vector_{self.port}.log', 'a')
        log_flush(self.fileIO, "===============================")

    def put(self, txt):
        log_flush(self.fileIO, "[VectorDB] Adding to db...")
        self.db.append(txt)
        tokenized = tokenize_str(txt)
        self.tokenized_corpus.append(tokenized)
        self._update_bm25()
        log_flush(self.fileIO, f"[VectorDB] save done, cur db size: {len(self.db)}, saved txt: ({txt})")
        # if len(self.db) > self.condense_threshold:
        #     self.group_and_combine_similar()
        #     self.save()

    def get(self, query_txt):
        log_flush(self.fileIO, "[VectorDB] Searching...")
        if not self.db:
            log_flush(self.fileIO, "[VectorDB] db is empty")
            return [], []

        query_tokens = tokenize_str(query_txt)
        scores = self.bm25.get_scores(query_tokens)
        # print(f"[VectorDB] scores: {scores}")
        scored_docs = list(zip(scores, self.db))

        # Filter out documents with score lower than th
        scored_docs = [doc for doc in scored_docs if doc[0] >= self.return_bm25th]
        qualified_size = len(scored_docs)

        # Sort by descending score, then ascending text for determinism
        scored_docs.sort(key=lambda x: (-x[0], x[1]))

        scored_docs = scored_docs[:self.k]
        log_flush(self.fileIO, f"[VectorDB] search done, count of bm25 score higher than ({self.return_bm25th}) is ({qualified_size}), original query: ({query_txt}), scored_docs: ({scored_docs})")

        scores = [sd[0] for sd in scored_docs]
        scores = [float(s) for s in scores]
        docs = [sd[1] for sd in scored_docs]
        return scores, docs
    
    def get_plain(self, query_txt):
        _, docs = self.get(query_txt)
        return docs
    
    def get_with_score_str(self, query_txt):
        scores, docs = self.get(query_txt)
        scores_str = ESMsgDelimiter.ES_SCORE_SEPERATOR.join([str(s) for s in scores])
        return [scores_str] + docs

    def _update_bm25(self):
        self.bm25 = BM25Okapi(self.tokenized_corpus)


    def save(self, path: str = "./storage/"):
        file_path = path + f"vectordb_{self.port}.json"
        log_flush(self.fileIO, f"[VectorDB] Saved db to {file_path}")
        saved_data = {"db": self.db, "tokenized_corpus": self.tokenized_corpus}
        with open(file_path, 'w') as fp:
            json.dump(saved_data, fp)

    def exist_backup(self, path: str = "./storage/"):
        file_path = path + f"vectordb_{self.port}.json"
        return os.path.isfile(file_path)

    def load(self, path: str = "./storage/"):
        if not self.exist_backup(path):
            raise Exception(f"In VectorDB.load(), load file with path {path} and port {self.port} does not exist.")
        file_path = path + f"vectordb_{self.port}.json"
        log_flush(self.fileIO, f"[VectorDB] Load db from {file_path}")
        with open(file_path) as f:
            loaded_data = json.load(f)
            assert len(loaded_data["db"]) == len(loaded_data["tokenized_corpus"])
            if len(loaded_data["db"]) == 0:
                return
            self.db, self.tokenized_corpus = loaded_data["db"], loaded_data["tokenized_corpus"]
        # update bm25
        self._update_bm25()

    def load_external(self, file_path):
        log_flush(self.fileIO, f"[VectorDB] Load db from {file_path}")
        with open(file_path) as f:
            loaded_data = json.load(f)
            assert len(loaded_data["db"]) == len(loaded_data["tokenized_corpus"])
            if len(loaded_data["db"]) == 0:
                return
            self.db, self.tokenized_corpus = loaded_data["db"], loaded_data["tokenized_corpus"]
        # update bm25
        self._update_bm25()

    def load_external_limited(self, file_path, bar):
        log_flush(self.fileIO, f"[VectorDB] Load db from {file_path}")
        with open(file_path) as f:
            loaded_data = json.load(f)
            assert len(loaded_data["db"]) == len(loaded_data["tokenized_corpus"])
            if len(loaded_data["db"]) == 0:
                return
            self.db, self.tokenized_corpus = loaded_data["db"][:bar], loaded_data["tokenized_corpus"][:bar]
        # update bm25
        self._update_bm25()

    def _get_similarity_matrix(self):
        """Calculate similarity matrix between all documents using BM25 scores"""
        n = len(self.db)
        similarity_matrix = np.zeros((n, n))
        
        for i in range(n):
            print(f"_get_similarity_matrix {i}/{n}")
            log_flush(self.fileIO, f"_get_similarity_matrix {i}/{n}")
            query_tokens = self.tokenized_corpus[i]
            scores = self.bm25.get_scores(query_tokens)
            similarity_matrix[i] = scores
            
        return similarity_matrix

    def _find_similar_groups(self):
        """Group similar documents based on similarity threshold"""
        similarity_matrix = self._get_similarity_matrix()
        n = len(self.db)
        groups = []
        used = set()

        for i in range(n):
            log_flush(self.fileIO, f"_find_similar_groups {i}/{n}")
            if i in used:
                continue
                
            # Find all documents similar to current document
            similar_docs = [j for j in range(n) 
                          if similarity_matrix[i][j] >= self.similarity_bm25th 
                          and j not in used]
            
            if len(similar_docs) > 1:  # Only create groups with multiple documents
                groups.append(similar_docs)
                used.update(similar_docs)

        return groups

    def _combine_similar_docs(self, docs):
        """
        Use llm to condence
        """
        combined = " ".join(docs)
        log_flush(self.fileIO, "[_combine_similar_docs] docs:")
        log_flush(self.fileIO, f"{docs}")
        # return combined
        for _ in range(3):
            result = self.model.condense(combined)
            if len(result) > 0:
                break
        log_flush(self.fileIO, "[_combine_similar_docs] result:")
        log_flush(self.fileIO, f"{result}")
        return result
    
    def _safe_combine(self, doc_indices):
        remaining_docs = [self.db[i] for i in doc_indices]
        docs_to_combine = []
        while len(remaining_docs) > 0:
            cur = remaining_docs.pop(0)
            if len(cur) + get_string_len_sum(docs_to_combine) > self.max_pipe_condense_size:
                condensed = self._combine_similar_docs(docs_to_combine)
                docs_to_combine.append(condensed)
                docs_to_combine = []
            docs_to_combine.append(cur)
        if len(docs_to_combine) > 0:
            condensed = self._combine_similar_docs(docs_to_combine)
            return condensed
        log_flush(self.fileIO, "FATAL [_safe_combine] no docs to combine")
        raise Exception("FATAL [_safe_combine] no docs to combine")
                

    def group_and_combine_similar(self):
        """Group similar documents and combine them"""
        log_flush(self.fileIO, "[VectorDB] Grouping and combining similar documents...")
        
        # Find groups of similar documents
        groups = self._find_similar_groups()
        
        if not groups:
            log_flush(self.fileIO, "[VectorDB] No similar documents found to combine")
            return
            
        # Create new database with combined documents
        new_db = []
        new_tokenized = []
        
        # Keep documents that weren't grouped
        used_indices = set()
        for group in groups:
            used_indices.update(group)
            
        # Add ungrouped documents
        for i in range(len(self.db)):
            if i not in used_indices:
                print(f"unused doc {i}")
                new_db.append(self.db[i])
                new_tokenized.append(self.tokenized_corpus[i])
        
        print(f"used_indices: {used_indices}")
        
        # Add combined documents
        for i in range(len(groups)):
            group = groups[i]
            log_flush(self.fileIO, f"[VectorDB] Combining group {i + 1}/{len(groups)}: {group}")
            combined = self._safe_combine(group)
            if len(combined) == 0:
                log_flush(self.fileIO, f"[VectorDB] Combined document is empty for group {i + 1}/{len(groups)}: {group}")
                continue
            new_db.append(combined)
            new_tokenized.append(tokenize_str(combined))
            
        log_flush(self.fileIO, f"[VectorDB] Combined {len(groups)} groups of similar documents. Old db size: {len(self.db)}. New db size: {len(new_db)}")

        # Update database
        self.db = new_db
        self.tokenized_corpus = new_tokenized
        self._update_bm25()
