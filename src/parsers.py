import os, re, glob, fnmatch
from os.path import exists, dirname, join

def find_csproj_files():
    return glob.glob("**/*.csproj", recursive=True)

def _version_nums(v: str):
    main = v.split('-', 1)[0] if v else ""
    parts = re.split(r"[._]", main) if main else []
    nums = []
    for p in parts:
        try:
            nums.append(int(p))
        except ValueError:
            nums.append(0)
    return nums

def version_lt(v1: str, v2: str) -> bool:
    try:
        a = _version_nums(v1)
        b = _version_nums(v2)
        L = max(len(a), len(b))
        if len(a) < L: a += [0] * (L - len(a))
        if len(b) < L: b += [0] * (L - len(b))
        return a < b
    except Exception:
        return False

def is_classic_web_app(csproj_path: str) -> bool:
    try:
        with open(csproj_path, encoding="utf-8", errors="ignore") as f:
            text = f.read().lower()
        return "microsoft.webapplication.targets" in text
    except Exception:
        return False

def uses_packages_config(csproj_path: str) -> bool:
    if exists(join(dirname(csproj_path), "packages.config")):
        return True
    try:
        with open(csproj_path, encoding="utf-8", errors="ignore") as f:
            txt = f.read().lower()
        return ("<packagereference" not in txt) and ("\\packages\\" in txt or "/packages/" in txt or "<hintpath>" in txt)
    except Exception:
        return False

def resolve_whitelist_for_project(csproj_path, whitelist_projects):
    project_name = os.path.basename(csproj_path)
    project_key = project_name.lower()
    project_stem = os.path.splitext(project_key)[0]

    merged = list(whitelist_projects.get(project_key, []))

    for k, allowed in whitelist_projects.items():
        if k == project_key:
            continue
        if fnmatch.fnmatch(project_key, k) or fnmatch.fnmatch(project_stem, k):
            merged.extend(allowed)

    return merged
