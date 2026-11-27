#!/usr/bin/env python3
"""Ein-Kommando-Check fuer SePlayer (vor jedem Commit laufen lassen).

Prueft: py_compile + AST aller Python-Dateien, Workflow-YAML (falls PyYAML installiert),
Unit-Tests via unittest (GUI-Test in tests/ laeuft nur mit DISPLAY, sonst skip).
Exit-Code 0 = alles gruen.
"""
import ast
import glob
import os
import py_compile
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
fail = []

files = (sorted(glob.glob("seplayer/*.py")) + sorted(glob.glob("tools/*.py"))
         + sorted(glob.glob("tests/*.py")) + ["se_player.py"])
for f in files:
    try:
        py_compile.compile(f, doraise=True)
        ast.parse(open(f, encoding="utf-8").read())
    except Exception as exc:
        fail.append(f"{f}: {exc}")
print(f"[1/3] py_compile + AST: {len(files)} Dateien ->", "OK" if not fail else "FAIL")

try:
    import yaml
    yaml.safe_load(open(".github/workflows/build.yml", encoding="utf-8"))
    print("[2/3] Workflow-YAML -> OK")
except ImportError:
    print("[2/3] Workflow-YAML -> uebersprungen (PyYAML nicht installiert)")
except Exception as exc:
    fail.append(f".github/workflows/build.yml: {exc}")
    print("[2/3] Workflow-YAML -> FAIL:", exc)

r = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests",
                    "-p", "test_*.py", "-v"], capture_output=True, text=True)
tail = (r.stdout + r.stderr).strip().splitlines()[-12:]
print("[3/3] unittest (GUI-Test nur mit DISPLAY):")
for line in tail:
    print("   ", line)
if r.returncode != 0:
    fail.append("unittest fehlgeschlagen")

if fail:
    print("CHECK FAILED:")
    for f in fail:
        print(" -", f)
    sys.exit(1)
print("ALL CHECKS OK")
