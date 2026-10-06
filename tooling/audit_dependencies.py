#!/usr/bin/env python3
"""Fail if a module imported by this repository is not declared as a dependency.

Why this exists
---------------
``requirements.txt`` declared nine floors while the code imported packages it
never declared. Nothing compared the two, so the file drifted and a clean
install could not run the code. The nine entries were also floors, not pins, so
even the declared set was not reproducible.

What it checks
--------------
1. Collects every top-level module imported by tracked ``*.py`` files using the
   AST, so comments and docstrings cannot produce a finding.
2. Compares that against the declared distributions, mapping import names to
   distribution names explicitly (``dotenv`` -> ``python-dotenv``) rather than
   guessing.
3. Exempts modules this repository provides itself.
4. Fails on an undeclared import.

Known exemption, and why it is an exemption rather than a fix
------------------------------------------------------------
``shared_utils`` is imported by ``risk_scorer.py``, ``alert_dispatcher.py`` and
``sql_extractor.py``, and **no such package exists in this repository or in any
sibling of it**. ``test_sentinel.py`` therefore cannot be collected here either.
That is a real defect and it is not this script's to paper over, so it is listed
explicitly below rather than silently ignored. Remove the entry when the module
is reconstructed; until then the audit reports it as a known gap.

Usage
-----
    python tooling/audit_dependencies.py
    python tooling/audit_dependencies.py --json

Exit codes:
    0  every import is declared (known gaps excluded)
    1  an import is undeclared and not a known gap
    2  bad input
"""

from __future__ import annotations

import argparse
import ast
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
REQUIREMENTS = ROOT / "requirements.txt"

# Imports that resolve to a distribution under a different name. Explicit,
# because a wrong guess produces a false failure.
IMPORT_TO_DISTRIBUTION = {
    "dotenv": "python-dotenv",
    "psycopg2": "psycopg2-binary",
    "yaml": "pyyaml",
    "sklearn": "scikit-learn",
    "PIL": "pillow",
    "bs4": "beautifulsoup4",
}

# Modules this repository provides itself, discovered from the file tree.
def sibling_modules(root: pathlib.Path) -> set[str]:
    skip = {"__pycache__", ".git", ".venv", "venv"}
    return {p.stem for p in root.glob("*.py") if p.stem != "__init__"} | {
        p.stem for p in root.rglob("*.py")
        if p.stem != "__init__" and not any(s in p.parts for s in skip)
    }


# Imports with no matching package anywhere in this repository. Reported, not
# hidden -- see the module docstring.
KNOWN_GAPS = {
    "shared_utils": "absent from this repository and every sibling; imported by "
                    "risk_scorer.py, alert_dispatcher.py, sql_extractor.py. "
                    "Blocks test collection. Reconstruct it, then delete this entry.",
}


def tracked_python(root: pathlib.Path) -> list[pathlib.Path]:
    try:
        out = subprocess.run(["git", "-c", "safe.directory=*", "ls-files", "*.py"],
                             cwd=root, capture_output=True, text=True,
                             timeout=60, check=True)
        files = [root / n for n in out.stdout.splitlines() if n.strip()]
        if files:
            return [f for f in files if f.is_file()]
    except (subprocess.SubprocessError, OSError):
        pass
    return list(root.glob("*.py"))


def declared(req_file: pathlib.Path) -> dict[str, str]:
    if not req_file.exists():
        return {}
    out: dict[str, str] = {}
    for raw in req_file.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        m = re.match(r"^([A-Za-z0-9._-]+)\s*(\[[^\]]*\])?\s*(.*)$", line)
        if m:
            out[m.group(1).strip().lower().replace("_", "-")] = (m.group(3) or "").strip()
    return out


def imports(root: pathlib.Path) -> set[str]:
    found: set[str] = set()
    for path in tracked_python(root):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except (SyntaxError, ValueError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    found.add(a.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                found.add(node.module.split(".")[0])
    return found


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if not REQUIREMENTS.exists():
        print(f"error: {REQUIREMENTS} not found", file=sys.stderr)
        return 2

    decl = declared(REQUIREMENTS)
    sibs = sibling_modules(ROOT)
    mods = imports(ROOT)
    stdlib = set(sys.stdlib_module_names)

    undeclared: list[str] = []
    gaps: list[str] = []
    for m in sorted(mods):
        if m in stdlib or m in sibs:
            continue
        dist = IMPORT_TO_DISTRIBUTION.get(m, m).lower().replace("_", "-")
        if dist in decl:
            continue
        (gaps if m in KNOWN_GAPS else undeclared).append(m)

    floors = [k for k, v in decl.items() if v and not v.startswith("==")]

    result = {
        "declared": sorted(decl),
        "declared_count": len(decl),
        "floors": sorted(floors),
        "undeclared_imports": undeclared,
        "known_gaps": gaps,
    }

    if args.json:
        print(json.dumps(result, indent=2))
        return 1 if undeclared else 0

    print(f"requirements.txt : {REQUIREMENTS}")
    print(f"declared          : {len(decl)}")
    if floors:
        print(f"  WARNING: {len(floors)} entries are floors, not pins: "
              f"{', '.join(sorted(floors))}")
    print(f"imports checked   : {len(mods)}")
    print()

    if undeclared:
        print("FAIL: imported but not declared:")
        for m in undeclared:
            print(f"  - {m}")
    else:
        print("PASS: every import is declared")

    if gaps:
        print()
        print("known gaps (declared in KNOWN_GAPS, not silently ignored):")
        for m in gaps:
            print(f"  - {m}: {KNOWN_GAPS[m]}")

    return 1 if undeclared else 0


if __name__ == "__main__":
    raise SystemExit(main())