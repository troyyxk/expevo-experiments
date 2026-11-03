"""Shared harness for reproducing Fig.5 / Fig.6 (high-school-biology) of the
Experience Scaling paper with an OpenRouter-hosted Llama-3.x-8B-Instruct.

Design notes
------------
* The *method* code is taken from the paper repo unchanged where possible:
  - server/db/vector_db.py  (BM25 retrieval + similarity grouping + LLM condense)
  - server/condence_model.py + server/prompt_manager.py (condensation prompt)
  - client/prompt_manager.py prompt strings (copied verbatim below, see
    `precise_question_prompt` / `summarize_prompt` / `confidence_prompt`)
* Only the model backend is swapped: `LocalModel` (HF pipeline) -> `ORClient`
  (OpenRouter chat completions). `ORClient.clean_pipe(prompt)` returns
  `prompt + completion`, so the repo's `cut_last_appearance`-style extraction
  keeps working unchanged.
* Two documented deviations (both needed because the served model is a chat
  model, and because OpenRouter no longer serves the original Llama-3-8B):
    D1. one extra instruction line asking the model to end with `#### <option>`
    D2. a lenient answer matcher (strict exact-match is still recorded)
"""

import json
import os
import random
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

BASE = os.path.dirname(os.path.abspath(__file__))
SERVER_DIR = os.path.join(BASE, "server")
OUT_DIR = os.path.join(BASE, "out")
DATA_DIR = os.path.join(BASE, "data")

# the server package must win the module-name race (config/util/prompt_manager)
os.chdir(SERVER_DIR)
PROTO_DIR = os.path.join(BASE, "../ExperienceScaling/experience_scaling_protocol")
sys.path.insert(0, os.path.abspath(PROTO_DIR))
sys.path.insert(0, SERVER_DIR)

from config import db_hyperparameter, model_parameter  # noqa: E402  (server config)
import config as server_config  # noqa: E402
from db.vector_db import VectorDB  # noqa: E402
from util import clean_string, tokenize_str  # noqa: E402  (server util)
from condence_model import CondenseModel  # noqa: E402
from prompt_manager import PromptManager as ServerPromptManager  # noqa: E402

os.makedirs(OUT_DIR, exist_ok=True)
os.makedirs(os.path.join(SERVER_DIR, "log"), exist_ok=True)
os.makedirs(os.path.join(SERVER_DIR, "storage"), exist_ok=True)

KEY = open(os.path.join(BASE, "secret_key.txt")).read().strip()
MODEL = os.environ.get("ES_MODEL", "meta-llama/llama-3.1-8b-instruct")
CONC = int(os.environ.get("ES_CONC", "20"))
TEMPERATURE = 0.7
URL = "https://openrouter.ai/api/v1/chat/completions"

USAGE_PATH = os.path.join(OUT_DIR, "usage.jsonl")
_usage_lock = threading.Lock()
_tls = threading.local()


# --------------------------------------------------------------------------- #
# model backend
# --------------------------------------------------------------------------- #
class Fatal(Exception):
    pass


class Transient(Exception):
    pass


class ORClient:
    """Minimal replacement for client/model/local_model.LocalModel."""

    def __init__(self, model=MODEL, temperature=TEMPERATURE, tag="run"):
        self.model = model
        self.temperature = temperature
        self.tag = tag
        self.calls = 0
        self._count_lock = threading.Lock()

    # ---- low level --------------------------------------------------------
    def _post(self, messages, max_tokens):
        body = json.dumps(
            {
                "model": self.model,
                "messages": messages,
                "temperature": self.temperature,
                "max_tokens": max_tokens,
            }
        ).encode()
        req = urllib.request.Request(
            URL,
            data=body,
            headers={
                "Authorization": f"Bearer {KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://localhost/es-repro",
                "X-Title": "experience-scaling-repro",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                data = json.load(resp)
        except urllib.error.HTTPError as e:
            code = e.code
            txt = e.read().decode("utf-8", "ignore")[:300]
            if code in (408, 409, 425, 429, 500, 502, 503, 504):
                raise Transient(f"HTTP {code}: {txt}")
            raise Fatal(f"HTTP {code}: {txt}")
        except Exception as e:  # timeouts, connection resets
            raise Transient(f"{type(e).__name__}: {e}")
        if "error" in data and data.get("error"):
            msg = str(data["error"])
            if "rate" in msg.lower() or "overload" in msg.lower():
                raise Transient(msg)
            raise Fatal(msg)
        usage = data.get("usage") or {}
        with _usage_lock:
            with open(USAGE_PATH, "a") as f:
                f.write(
                    json.dumps(
                        {
                            "tag": self.tag,
                            "model": data.get("model"),
                            "provider": data.get("provider"),
                            "pt": usage.get("prompt_tokens"),
                            "ct": usage.get("completion_tokens"),
                            "cost": usage.get("cost"),
                            "ts": time.time(),
                        }
                    )
                    + "\n"
                )
        return data["choices"][0]["message"]["content"] or ""

    def chat(self, messages, max_tokens=300, tries=8):
        last = None
        for attempt in range(tries):
            try:
                with self._count_lock:
                    self.calls += 1
                return self._post(messages, max_tokens)
            except Transient as e:
                last = e
                time.sleep(min(30, 1.5 * (2**attempt)) + random.random())
        raise Fatal(f"giving up after {tries} tries: {last}")

    # ---- repo interface ---------------------------------------------------
    def clean_pipe(self, prompt: str, max_tokens: int = 300) -> str:
        """Mirror LocalModel.clean_pipe: return prompt+completion so that the
        repo's `cut_last_appearance(txt, keyword)` retrievers still work."""
        messages = parse_llama3_prompt(prompt)
        answer = self.chat(messages, max_tokens=max_tokens)
        return prompt + answer

    def generate_distillation(self, txt: str) -> str:
        raw = self.clean_pipe(summarize_prompt(txt), max_tokens=120)
        return clean_string(cut_after_last(raw, "Summary:"))

    def generate_QA_distillation(self, question, correct_answers, wrong_answers) -> str:
        qa_txt = f"{question} "
        if len(correct_answers) > 0:
            qa_txt += f"The answer is '{correct_answers[0]}'"
        elif len(wrong_answers) > 0:
            qa_txt += "The answer is NOT " + " or ".join(
                f"'{w}'" for w in wrong_answers
            )
        else:
            return ""
        return self.generate_distillation(qa_txt)


# --------------------------------------------------------------------------- #
# Llama-3 prompt <-> chat messages
# --------------------------------------------------------------------------- #
def parse_llama3_prompt(prompt: str):
    p = prompt.replace("<|begin_of_text|>", "")
    msgs = []
    for part in p.split("<|start_header_id|>"):
        if "<|end_header_id|>" not in part:
            continue
        role, rest = part.split("<|end_header_id|>", 1)
        role = role.strip()
        rest = rest.split("<|eot_id|>")[0].strip()
        if role in ("system", "user") and rest:
            msgs.append({"role": role, "content": rest})
    return msgs


def cut_after_last(txt: str, keyword: str) -> str:
    i = txt.rfind(keyword)
    if i < 0:
        raise ValueError(f"keyword {keyword!r} not found")
    return txt[i + len(keyword) :].strip()


# --------------------------------------------------------------------------- #
# prompts copied verbatim from client/prompt_manager.py
# --------------------------------------------------------------------------- #
def _answer_header(options, context, force_format=True, extra="") -> str:
    header = (
        "You are a helpful AI assistant. The final answer should be as short "
        "and percise as possible."
    )
    if len(options) > 0:
        header += " Choose the answer from the options."
    if len(context) > 0:
        header += " Use the provided context to answer."
    header += " Answer the final answer in the end after #### "
    if force_format:  # D1
        header += (
            "End your reply with exactly one line of the form: "
            "#### <the chosen option text>. Choose the single best option and "
            "copy its text verbatim as the final line; never list or quote the "
            "other options."
        )
    if extra:
        header += " " + extra
    return header


def precise_question_prompt(query, options, context, force_format=True):
    header = _answer_header(options, context, force_format)
    prompt = f"""<|begin_of_text|><|start_header_id|>system<|end_header_id|>
                {header}<|eot_id|>
                <|start_header_id|>user<|end_header_id|>\n"""
    if len(options) > 0:
        prompt += f"Options: '{str(options)}'\n\n"
    if len(context) > 0:
        prompt += f"Context: '[{context}]'\n\n"
    prompt += f"""Request: {query}<|eot_id|>
                <|start_header_id|>assistant<|end_header_id|>"""
    return prompt


def confidence_prompt(query, target_option, options, context, force_format=True):
    header = _answer_header(
        options,
        context,
        False,
        extra="At the very end write exactly: #### <your confidence as an integer 0-100>.",
    )
    prompt = f"""<|begin_of_text|><|start_header_id|>system<|end_header_id|>
                {header}<|eot_id|>
                <|start_header_id|>user<|end_header_id|>\n"""
    if len(options) > 0:
        prompt += f"Options: '{str(options)}'\n\n"
    if len(context) > 0:
        prompt += f"Context: '[{context}]'\n\n"
    prompt += f"""Request: What is your confidence that '{target_option}' is correct answer to question: {query}<|eot_id|>
                <|start_header_id|>assistant<|end_header_id|>"""
    return prompt


OLD_SUM = os.environ.get("ES_OLD_SUM") == "1"


def summarize_prompt(txt, max_len=3):
    if OLD_SUM:
        # prompt used by the authors for the Fig.5 run (git: residual_scaling_client,
        # prompt_manager.py before 2025-09-12)
        return f"""<|begin_of_text|><|start_header_id|>user<|end_header_id|>
        Summarize this text in less than {max_len} concise sentences:

        {txt}

        <|eot_id|><|start_header_id|>assistant<|end_header_id|>
        Summary:"""
    return f"""<|begin_of_text|><|start_header_id|>user<|end_header_id|>
        This is a conversation between a use and a chatbot. Output only the very key information in less than {max_len} concise sentences:

        {txt}

        <|eot_id|><|start_header_id|>assistant<|end_header_id|>
        Summary:"""


# --------------------------------------------------------------------------- #
# answer extraction / matching
# --------------------------------------------------------------------------- #
_ASSISTANT_MARK = "<|start_header_id|>assistant<|end_header_id|>"


def reply_part(raw: str) -> str:
    if _ASSISTANT_MARK in raw:
        return raw.rsplit(_ASSISTANT_MARK, 1)[-1]
    return raw


def extract_answer(raw: str) -> str:
    rep = reply_part(raw).strip()
    if "####" in rep:
        cand = rep.rsplit("####", 1)[-1]
    else:
        cand = rep
    cand = cand.split("\n")[0].strip()
    return cand


def clean_str(txt: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", txt.lower())


_PREFIX = re.compile(
    r"^(?:final\s+answer|answer|the\s+answer\s+is|correct\s+answer|option)\s*[:\-]?\s*",
    re.I,
)
_LETTER = re.compile(r"^\(?([abcd])\)?\s*[\.\):\-]?\s*$", re.I)


def normalize_answer(cand: str, options):
    c = cand.strip().strip("\"'`").strip()
    c = re.sub(r"\s+", " ", c)
    prev = None
    while prev != c:
        prev = c
        c = _PREFIX.sub("", c).strip()
    c = c.rstrip(".")
    m = _LETTER.match(c.strip())
    if m and options:
        idx = "abcd".index(m.group(1).lower())
        if idx < len(options):
            return options[idx]
    return c


def is_correct(cand_raw: str, options, truth) -> tuple:
    """returns (correct_lenient, correct_strict, normalized_answer)"""
    cand = normalize_answer(cand_raw, options)
    c = clean_str(cand)
    t = clean_str(truth)
    strict = c == t
    lenient = strict
    if not lenient and options:
        hits = [o for o in options if clean_str(o) and clean_str(o) == c]
        lenient = bool(hits)
    if not lenient and options:
        # answer text embedded in a longer sentence
        embedded = [o for o in options if clean_str(o) and clean_str(o) in c]
        if len(embedded) == 1:
            lenient = clean_str(embedded[0]) == t
    return lenient, strict, cand


# --------------------------------------------------------------------------- #
# fast VectorDB (lazy BM25 rebuild + cached similarity matrix)
# --------------------------------------------------------------------------- #
class FastVectorDB(VectorDB):
    def __init__(self, port=4001, lm=None):
        self._dirty = False
        self._S = None
        super().__init__(port, lm)

    def put(self, txt):
        self.db.append(txt)
        self.tokenized_corpus.append(tokenize_str(txt))
        self._dirty = True

    def ensure(self):
        if not self.db:
            return
        if self._dirty or self.bm25 is None:
            self._update_bm25()
            self._dirty = False

    def get(self, query_txt):
        self.ensure()
        return super().get(query_txt)

    def _get_similarity_matrix(self):
        if self._S is None:
            self._S = super()._get_similarity_matrix()
        return self._S


# --------------------------------------------------------------------------- #
# data
# --------------------------------------------------------------------------- #
def clean_str_pair(x):
    return clean_str(x)


def load_mmlu(subject="high_school_biology"):
    import pandas as pd

    base = os.path.join(DATA_DIR, "mmlu", subject)
    out = []
    for split in ("dev", "test", "validation"):
        df = pd.read_parquet(os.path.join(base, f"{split}-00000-of-00001.parquet"))
        for _, row in df.iterrows():
            opts = list(row["choices"])
            out.append(
                {
                    "question": row["question"],
                    "truth": opts[row["answer"]],
                    "options": opts,
                    "reasoning": "",
                }
            )
    return out


def pmap(fn, items, workers=None, label="", every=100):
    workers = workers or CONC
    results = [None] * len(items)
    done = 0
    t0 = time.time()
    lock = threading.Lock()

    def wrapped(i_item):
        i, item = i_item
        r = fn(item)
        nonlocal done
        with lock:
            done += 1
            if label and (done % every == 0 or done == len(items)):
                el = time.time() - t0
                print(
                    f"  [{label}] {done}/{len(items)}  {el:6.1f}s  "
                    f"({el / max(done,1):.2f}s/item)",
                    flush=True,
                )
        return r

    with ThreadPoolExecutor(max_workers=workers) as ex:
        for i, r in enumerate(ex.map(wrapped, list(enumerate(items)))):
            results[i] = r
    return results
