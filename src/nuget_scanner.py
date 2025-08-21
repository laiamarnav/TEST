import subprocess, os, fnmatch, xml.etree.ElementTree as ET
from os.path import exists, dirname, join
from src.logger import log, log_summary
from src.parsers import find_csproj_files, uses_packages_config, is_classic_web_app, resolve_whitelist_for_project, version_lt

NUGET_SOURCES = [
    "https://vueling.pkgs.visualstudio.com/_packaging/vy-nuget/nuget/v3/index.json",
    "https://api.nuget.org/v3/index.json"
]

def run_dotnet_restore(target_path):
    cmd = ["dotnet", "restore", target_path]
    for source in NUGET_SOURCES:
        cmd.extend(["--source", source])
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore")
    log(f"\n[RESTORE] {os.path.abspath(target_path)}")
    if r.stdout: log(r.stdout)
    if r.returncode != 0:
        log_summary(f"ERROR: dotnet restore failed for {target_path}")
        if r.stderr: log(f"[stderr]\n{r.stderr}")
        return False
    return True

def check_packages_config(csproj_path, blocked_packages, whitelist_projects, whitelist_nugets, tag_pr):
    pkg_path = join(dirname(csproj_path), "packages.config")
    if not exists(pkg_path):
        return True
    tree = ET.parse(pkg_path)
    root = tree.getroot()
    whitelist = resolve_whitelist_for_project(csproj_path, whitelist_projects)
    allow_all = "*" in whitelist or "*" in whitelist_nugets
    ok = True
    for pkg in root.findall("package"):
        name = pkg.get("id","").lower()
        version = pkg.get("version","")
        for b in blocked_packages:
            if fnmatch.fnmatch(name, b["name"]):
                if b.get("min_version") and version_lt(version, b["min_version"]):
                    if not allow_all:
                        log_summary(f"ERROR: {name} {version} < {b['min_version']} in {csproj_path}")
                        ok = False
    return ok

def run_dotnet_package_check(csproj_path, check_type, blocked_packages, whitelist_projects, whitelist_nugets, tag_pr):
    cmd = ["dotnet", "list", csproj_path, "package", f"--{check_type}", "--include-transitive"]
    for source in NUGET_SOURCES:
        cmd.extend(["--source", source])

    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore")
    if r.returncode != 0:
        log_summary(f"WARNING: dotnet list failed for {csproj_path}")
        return True
    log(r.stdout)
    return True

def check_all_projects(blocked_packages, whitelist_projects, whitelist_nugets, tag_pr):
    csprojs = find_csproj_files()
    if not csprojs:
        log_summary("No .csproj files found")
        return True
    ok = True
    for csproj in csprojs:
        if uses_packages_config(csproj):
            if not check_packages_config(csproj, blocked_packages, whitelist_projects, whitelist_nugets, tag_pr):
                ok = False
            continue
        if is_classic_web_app(csproj):
            log_summary(f"WARNING: Skipping classic ASP.NET project {csproj}")
            continue
        if not run_dotnet_package_check(csproj, "outdated", blocked_packages, whitelist_projects, whitelist_nugets, tag_pr):
            ok = False
    return ok
