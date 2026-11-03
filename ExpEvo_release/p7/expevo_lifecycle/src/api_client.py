"""OpenAI-compatible chat client with retries, prompt caching, usage logging
and hard budget guards (Section 2 of the task spec)."""
import csv
import json
import os
import threading
import time
import urllib.error
import urllib.request

from .common import now_iso, sha256_text


class BudgetExceeded(RuntimeError):
    pass


class FatalAPIError(RuntimeError):
    pass


class TransientAPIError(RuntimeError):
    pass


class LLMClient:
    def __init__(self, cfg, run_dir):
        api = cfg["api"]
        self.base_url = api["base_url"].rstrip("/")
        self.model = api["model"]
        self.api_key = api["api_key"]
        if not self.api_key or self.api_key.startswith("FILL"):
            raise FatalAPIError("LLM_API_KEY is not configured (put it in .env)")
        self.timeout = float(api.get("timeout", 120))
        self.max_retries = int(api.get("max_retries", 5))
        self.max_calls = int(api.get("max_api_calls", 10**9))
        self.max_cost = float(api.get("max_estimated_cost_usd", 1e9))
        self.price_in = float(api.get("input_price_usd_per_1m", 0) or 0)
        self.price_out = float(api.get("output_price_usd_per_1m", 0) or 0)
        self.cache_dir = os.path.join(run_dir, "..", "cache")
        self.cache_dir = os.path.abspath(self.cache_dir)
        os.makedirs(self.cache_dir, exist_ok=True)
        self.usage_csv = os.path.join(run_dir, "tables", "api_usage.csv")
        os.makedirs(os.path.dirname(self.usage_csv), exist_ok=True)
        self._lock = threading.Lock()
        self.calls = 0
        self.cached_hits = 0
        self.failures = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.cost = 0.0
        self.t_start = time.time()
        if not os.path.exists(self.usage_csv):
            with open(self.usage_csv, "w", newline="") as f:
                csv.writer(f).writerow(
                    ["ts", "tag", "model", "cached", "latency_s", "prompt_tokens",
                     "completion_tokens", "cost_usd", "status", "prompt_hash"]
                )

    # ------------------------------------------------------------------
    def _log(self, row):
        with self._lock:
            with open(self.usage_csv, "a", newline="") as f:
                csv.writer(f).writerow(row)

    def _budget_check(self):
        with self._lock:
            if self.calls >= self.max_calls:
                raise BudgetExceeded(f"MAX_API_CALLS={self.max_calls} reached")
            if self.cost >= self.max_cost:
                raise BudgetExceeded(f"MAX_ESTIMATED_COST_USD={self.max_cost} reached")

    def chat(self, messages, tag, temperature=0.0, max_tokens=256, json_mode=False,
             cache_salt=""):
        """Return dict(text, usage, cached, latency).

        `cache_salt` makes deliberate repeated samples (e.g. the 10 interactions of
        the same question) distinct cache entries while keeping resume-caching:
        pass a stable per-episode id, never a random value.
        """
        self._budget_check()
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        key = sha256_text(
            json.dumps(
                {"model": self.model, "payload": payload, "salt": cache_salt},
                sort_keys=True,
                ensure_ascii=False,
            )
        )
        cache_path = os.path.join(self.cache_dir, f"{key}.json")
        if os.path.exists(cache_path):
            with open(cache_path, encoding="utf-8") as f:
                hit = json.load(f)
            with self._lock:
                self.cached_hits += 1
            self._log([now_iso(), tag, self.model, 1, 0.0,
                       hit["usage"].get("prompt_tokens", 0),
                       hit["usage"].get("completion_tokens", 0),
                       0.0, "cached", key[:16]])
            return {"text": hit["text"], "usage": hit["usage"], "cached": True,
                    "latency": 0.0, "prompt_hash": key}

        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://localhost/expevo-lifecycle",
            "X-Title": "expevo-lifecycle-p7",
        }
        last_err = None
        for attempt in range(self.max_retries):
            self._budget_check()
            t0 = time.time()
            try:
                req = urllib.request.Request(
                    f"{self.base_url}/chat/completions", data=body, headers=headers
                )
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    data = json.load(resp)
                text = data["choices"][0]["message"]["content"] or ""
                usage = data.get("usage") or {}
                latency = time.time() - t0
                pt = int(usage.get("prompt_tokens", 0) or 0)
                ct = int(usage.get("completion_tokens", 0) or 0)
                cost = self.price_in * pt / 1e6 + self.price_out * ct / 1e6
                with self._lock:
                    self.calls += 1
                    self.prompt_tokens += pt
                    self.completion_tokens += ct
                    self.cost += cost
                with open(cache_path, "w", encoding="utf-8") as f:
                    json.dump({"text": text, "usage": usage, "model": self.model}, f,
                              ensure_ascii=False)
                self._log([now_iso(), tag, self.model, 0, f"{latency:.3f}", pt, ct,
                           f"{cost:.8f}", "ok", key[:16]])
                return {"text": text, "usage": usage, "cached": False,
                        "latency": latency, "prompt_hash": key}
            except urllib.error.HTTPError as e:
                code = e.code
                detail = e.read().decode("utf-8", "ignore")[:200]
                last_err = f"HTTP {code}: {detail}"
                if code not in (408, 409, 425, 429, 500, 502, 503, 504):
                    with self._lock:
                        self.failures += 1
                    self._log([now_iso(), tag, self.model, 0, "", 0, 0, "", f"fatal:{last_err}", key[:16]])
                    raise FatalAPIError(last_err)
            except Exception as e:  # timeouts, connection resets, JSON errors
                last_err = f"{type(e).__name__}: {e}"
            time.sleep(min(30, 1.5 * (2**attempt)))
        with self._lock:
            self.failures += 1
        self._log([now_iso(), tag, self.model, 0, "", 0, 0, "", f"failed:{last_err}", key[:16]])
        raise TransientAPIError(last_err)

    # ------------------------------------------------------------------
    def summary(self):
        return {
            "model_id": self.model,
            "base_url": self.base_url,
            "api_calls_billed": self.calls,
            "cache_hits": self.cached_hits,
            "failures": self.failures,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "estimated_cost_usd": round(self.cost, 6),
            "wall_seconds": round(time.time() - self.t_start, 1),
        }
