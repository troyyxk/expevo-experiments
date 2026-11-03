"""Verify that the prompt strings in engine.py match the paper repo verbatim
(modulo the documented D1 extra line)."""
import json
import os
import subprocess
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
CLIENT = os.path.join(BASE, "../ExperienceScaling/experience_scaling_client")

SNIP = r"""
import json, sys
sys.path.insert(0, ".")
from prompt_manager import PromptManager
pm = PromptManager()
out = {
  "q_noctx": pm.generate_llama_percise_question_prompt("What is X?", ["a", "b"], ""),
  "q_ctx":   pm.generate_llama_percise_question_prompt("What is X?", ["a", "b"], "ctx here"),
  "q_noopt": pm.generate_llama_percise_question_prompt("What is X?", [], "ctx here"),
  "sum":     pm.generate_llama_summarize_prompt("Some conversation text."),
  "conf":    pm.generate_llama_percise_confidence_prompt("What is X?", "a", ["a","b"], ""),
}
print(json.dumps(out))
"""

ref = json.loads(
    subprocess.check_output([sys.executable, "-c", SNIP], cwd=CLIENT).decode().strip().splitlines()[-1]
)

sys.path.insert(0, BASE)
import engine  # noqa: E402

mine = {
    "q_noctx": engine.precise_question_prompt("What is X?", ["a", "b"], "", force_format=False),
    "q_ctx": engine.precise_question_prompt("What is X?", ["a", "b"], "ctx here", force_format=False),
    "q_noopt": engine.precise_question_prompt("What is X?", [], "ctx here", force_format=False),
    "sum": engine.summarize_prompt("Some conversation text."),
    "conf": engine.confidence_prompt("What is X?", "a", ["a", "b"], "", force_format=False),
}

ok = True
for k in ref:
    if k == "conf":
        known = " At the very end write exactly: #### <your confidence as an integer 0-100>."
        same = mine[k].replace(known, "") == ref[k]
        print(f"{k:<8} exact_match_after_removing_documented_line={same}")
    else:
        same = ref[k] == mine[k]
        print(f"{k:<8} exact_match={same}")
        if not same:
            print("  REF :", repr(ref[k][:220]))
            print("  MINE:", repr(mine[k][:220]))
    ok &= same
print("PROMPT FIDELITY OK (expected deviations only):", ok)

# show the D1 variant diff
d1 = engine.precise_question_prompt("What is X?", ["a", "b"], "")
print("\nD1 variant header line:")
print(" ", [m for m in engine.parse_llama3_prompt(d1) if m["role"] == "system"][0]["content"][-160:])
