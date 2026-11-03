"""Tiny runner (pytest is not installed in this env)."""
import importlib, inspect, sys, traceback

failed = 0
for mod in ["test_serialization", "test_grouping", "test_reduction", "test_no_label_leakage"]:
    m = importlib.import_module(f"tests.{mod}")
    for name, fn in inspect.getmembers(m, inspect.isfunction):
        if name.startswith("test_"):
            try:
                fn(); print(f"PASS {mod}.{name}")
            except Exception:
                failed += 1; print(f"FAIL {mod}.{name}"); traceback.print_exc()
print("FAILED:", failed)
sys.exit(1 if failed else 0)
