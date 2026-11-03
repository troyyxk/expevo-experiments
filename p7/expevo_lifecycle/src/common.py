"""Shared helpers: env/config loading, canonical serialization, JSONL IO."""
import hashlib
import json
import os
import re
import time

# --------------------------------------------------------------------------
# canonical payload model (Section 5 of the task spec)
# --------------------------------------------------------------------------
def serialize_item(topic: str, content: str) -> bytes:
    """The ONE serializer used for Raw / Distilled / Refined byte counts."""
    obj = {"topic": topic, "content": content}
    return json.dumps(
        obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# --------------------------------------------------------------------------
# env / config
# --------------------------------------------------------------------------
def load_env(path: str = None) -> dict:
    """Minimal .env loader (KEY=VALUE, ignores blanks/comments)."""
    path = path or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    env = {}
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    for k, v in os.environ.items():
        if k.startswith("LLM_") or k.endswith("_PRICE_USD_PER_1M"):
            env[k] = v
    return env


_VAR = re.compile(r"\$\{([A-Z0-9_]+)\}")


def _expand(value, env):
    if isinstance(value, str):
        return _VAR.sub(lambda m: str(env.get(m.group(1), "")), value)
    if isinstance(value, list):
        return [_expand(v, env) for v in value]
    if isinstance(value, dict):
        return {k: _expand(v, env) for k, v in value.items()}
    return value


def load_config(path: str, env: dict = None) -> dict:
    import yaml

    env = env if env is not None else load_env()
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    return _expand(cfg, env)


# --------------------------------------------------------------------------
# JSONL helpers
# --------------------------------------------------------------------------
def append_jsonl(path: str, record: dict):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
        f.flush()


def write_jsonl(path: str, records):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def read_jsonl(path: str):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_json(path: str, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, sort_keys=True)


def read_json(path: str, default=None):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")
