#!/usr/bin/env python3

import subprocess
import os
import sys
import glob
import json
import fnmatch
import re
from os.path import exists

ANSI = {
    "BOLD_RED": "\033[1;31m",
    "BOLD_YELLOW": "\033[1;33m",
    "RESET": "\033[0m"
}

LOG_FILE = "nugets.log"
summary_lines = []

NUGET_SOURCES = [
    "https://vueling.pkgs.visualstudio.com/_packaging/vy-nuget/nuget/v3/index.json",
    "https://api.nuget.org/v3/index.json"
]

def log(msg):
    print(msg)

def log_summary(msg):
    summary_lines.append(msg)
    if msg.startswith("ERROR"):
        print(f"{ANSI['BOLD_RED']}{msg}{ANSI['RESET']}")
    elif msg.startswith("WARNING"):
        print(f"{ANSI['BOLD_YELLOW']}{msg}{ANSI['RESET']}")
    else:
        print(msg)

def load_blocked_packages(path):
    if not exists(path):
        print(f"File not found: {path}")
        sys.exit(1)

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    blocked = data.get("blocked_packages")
    if not isinstance(blocked, list):
        print(f"Invalid JSON format: missing or invalid 'blocked_packages' list in {path}")
        sys.exit(1)

    result = []
    for entry in blocked:
        if isinstance(entry, str):
            result.append({
                "name": entry.lower(),
                "block_on": ["all"],
                "min_version": None
            })
        elif isinstance(entry, dict) and "name" in entry:
            result.append({
                "name": entry["name"].lower(),
                "block_on": entry.get("block_on", ["all"]),
                "min_version": entry.get("min_version")
            })
        else:
            print(f"Invalid blocked package entry: {entry}")
            sys.exit(1)
    return result

def load_whitelist_data(path):
    if not exists(path):
        print(f"File not found: {path}")
        sys.exit(1)

    with open(path, encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as e:
            print(f"Invalid JSON in {path}: {e}")
            sys.exit(1)

    project_whitelist = data.get("whitelist_projects", {})
    if not isinstance(project_whitelist, dict):
        print(f"Expected 'whitelist_projects' key with a dictionary value in {path}")
        sys.exit(1)

    nuget_whitelist = data.get("whitelist_nugets", [])
    if not isinstance(nuget_whitelist, list):
        print(f"Expected 'whitelist_nugets' to be a list in {path}")
        sys.exit(1)

    def _norm_list(lst):
        return [str(x).strip().lower() for x in lst]

    project_whitelist = {str(k).strip().lower(): _norm_list(v) for k, v in project_whitelist.items()}
    nuget_whitelist = _norm_list(nuget_whitelist)

    return project_whitelist, nuget_whitelist

def find_csproj_files():
    return glob.glob("**/*.csproj", recursive=True)

def _version_nums(v):
    main = v.split('-', 1)[0] if v else ""
    parts = re.split(r"[._]", main) if main else []
    nums = []
    for p in parts:
        try:
            nums.append(int(p))
        except ValueError:
            nums.append(0)
    return nums

def version_lt(v1, v2):
    try:
        a = _version_nums(v1)
        b = _version_nums(v2)
        L = max(len(a), len(b))
        if len(a) < L: a += [0] * (L - len(a))
        if len(b) < L: b += [0] * (L - len(b))
        return a < b
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

def run_dotnet_package_check(csproj_path, check_type, blocked_packages, whitelist_projects, whitelist_nugets, tag_pull_request):
    cmd = [
        "dotnet", "list", csproj_path, "package",
        f"--{check_type}", "--include-transitive"
    ]
    for source in NUGET_SOURCES:
        cmd.extend(["--source", source])

    whitelist_for_project = resolve_whitelist_for_project(csproj_path, whitelist_projects)
    allow_all = ("*" in whitelist_for_project) or ("*" in whitelist_nugets)

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
        log(f"\n [{check_type.upper()} PACKAGES] ")
        log("-" * 60)
        log(f"\nChecking packages for {os.path.abspath(csproj_path)}")
        log(result.stdout)

        if result.returncode != 0:
            log_summary(f"ERROR: Could not check packages for {csproj_path}. dotnet command failed.")
            return False

        output_lines = result.stdout.splitlines()
        blocked_found = False

        for line in output_lines:
            if not line.strip().startswith("> "):
                continue

            parts = line.strip().split()
            if len(parts) < 4:
                continue

            package_name = parts[1].lower()
            installed_version = parts[2]

            if "-beta" in installed_version:
                is_whitelisted_beta = (
                    any(fnmatch.fnmatch(package_name, wl) for wl in whitelist_for_project) or
                    any(fnmatch.fnmatch(package_name, wl) for wl in whitelist_nugets) or
                    allow_all
                )
                if is_whitelisted_beta:
                    continue
                if not any(x in tag_pull_request for x in ("ephemeral", "mocked", "ephemeral_mocked")):
                    log_summary(f"ERROR: Found '-beta' package '{package_name}' do not allow it.")
                    blocked_found = True
                    continue
                continue

            matched_block_rule = None
            for blocked in blocked_packages:
                if fnmatch.fnmatch(package_name, blocked["name"]):
                    matched_block_rule = blocked
                    break

            if matched_block_rule:

                if matched_block_rule.get("min_version"):
                    if version_lt(installed_version, matched_block_rule["min_version"]):
                        # ¿Whitelist?
                        is_whitelisted = (
                            any(fnmatch.fnmatch(package_name, wl) for wl in whitelist_for_project) or
                            any(fnmatch.fnmatch(package_name, wl) for wl in whitelist_nugets) or
                            allow_all
                        )
                        if is_whitelisted:
                            log_summary(f"WARNING: Package '{package_name}' below min_version but allowed by whitelist.")
                            continue
                        log_summary(
                            f"ERROR: Package '{package_name}' has version '{installed_version}' "
                            f"which is lower than the allowed '{matched_block_rule['min_version']}' in {csproj_path}."
                        )
                        blocked_found = True
                        continue

                if "all" in matched_block_rule.get("block_on", []) or check_type in matched_block_rule.get("block_on", []):
                    is_whitelisted = (
                        any(fnmatch.fnmatch(package_name, wl) for wl in whitelist_for_project) or
                        any(fnmatch.fnmatch(package_name, wl) for wl in whitelist_nugets) or
                        allow_all
                    )
                    if is_whitelisted:
                        log_summary(f"WARNING: Package '{package_name}' would be blocked but is allowed by whitelist.")
                        continue
                    log_summary(f"ERROR: Found blocked package '{package_name}' in {csproj_path}.")
                    blocked_found = True
                    continue

            continue

        return not blocked_found
    except Exception as e:
        log_summary(f"Exception running dotnet command: {e}")
        return False

def check_packages(check_type, blocked_packages, whitelist_projects, whitelist_nugets, tag_pull_request):
    csproj_files = find_csproj_files()
    if not csproj_files:
        log_summary("No .csproj files found. Exiting...")
        sys.exit(0)

    error_count = 0
    for csproj in csproj_files:
        ok = run_dotnet_package_check(
            csproj,
            check_type,
            blocked_packages,
            whitelist_projects,
            whitelist_nugets,
            tag_pull_request
        )
        if not ok:
            error_count += 1

    if error_count > 0:
        log_summary(f"Found issues during {check_type} package check.")
        return False

    return True

def main():
    if len(sys.argv) < 5:
        print("Usage: script.py <working_dir> <blocked_packages_json> <whitelist_projects_json> <tag_pull_request>")
        sys.exit(1)

    working_dir = sys.argv[1]
    blocked_packages_json = sys.argv[2]
    whitelist_projects_json = sys.argv[3]
    tag_pull_request = sys.argv[4]

    try:
        os.chdir(working_dir)
        log(f"Changed to directory: {working_dir}")
    except FileNotFoundError:
        print(f"Directory not found: {working_dir}")
        sys.exit(1)

    blocked_packages = load_blocked_packages(blocked_packages_json)
    whitelist_projects, whitelist_nugets = load_whitelist_data(whitelist_projects_json)

    open(LOG_FILE, "w", encoding="utf-8").close()
    log(f"Logging output to: {LOG_FILE}")

    vulnerable_ok = check_packages("vulnerable", blocked_packages, whitelist_projects, whitelist_nugets, tag_pull_request)
    outdated_ok   = check_packages("outdated",   blocked_packages, whitelist_projects, whitelist_nugets, tag_pull_request)
    deprecated_ok = check_packages("deprecated", blocked_packages, whitelist_projects, whitelist_nugets, tag_pull_request)

    log("\nSUMMARY REPORT")
    log("-" * 60)

    if summary_lines:
        for line in summary_lines:
            log(line)
    else:
        log("No blocked packages or issues found.")

    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write("SUMMARY REPORT\n")
        f.write("-" * 60 + "\n")
        if summary_lines:
            f.write("\n".join(summary_lines) + "\n")
        else:
            f.write("No blocked packages or issues found.\n")

    errors = [line for line in summary_lines if line.startswith("ERROR")]
    warnings = [line for line in summary_lines if line.startswith("WARNING")]

    if errors:
        log("Errors found in package checks. Failing pipeline.")
        sys.exit(1)
    elif warnings:
        log("Warnings found in package checks. Marking pipeline as warning.")
        print("##vso[task.complete result=SucceededWithIssues;]Warnings found in package checks.")
        sys.exit(0)
    else:
        log("All checks passed without issues.")
        sys.exit(0)

if __name__ == "__main__":
    main()
