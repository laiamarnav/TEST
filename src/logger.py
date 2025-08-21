ANSI = {
    "BOLD_RED": "\033[1;31m",
    "BOLD_YELLOW": "\033[1;33m",
    "RESET": "\033[0m"
}

_summary_lines = []

def log(msg: str):
    print(msg)

def log_summary(msg: str):
    _summary_lines.append(msg)
    if msg.startswith("ERROR"):
        print(f"{ANSI['BOLD_RED']}{msg}{ANSI['RESET']}")
    elif msg.startswith("WARNING"):
        print(f"{ANSI['BOLD_YELLOW']}{msg}{ANSI['RESET']}")
    else:
        print(msg)

def get_summary():
    return _summary_lines
