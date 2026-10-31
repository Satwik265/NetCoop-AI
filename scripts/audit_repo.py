"""Repository safety and aesthetics audit script.

Scans tracked git files for:
1. Emojis
2. Saturated bright colors and gradient CSS rules
3. Secrets, API keys, credentials
4. Large files (> 5MB)
"""

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.resolve()

# Precise regex for actual emojis across Unicode standard (excluding box-drawing and standard math/punctuation)
EMOJI_PATTERN = re.compile(
    r"["
    r"\U0001F600-\U0001F64F"  # Emoticons
    r"\U0001F300-\U0001F5FF"  # Misc Symbols and Pictographs
    r"\U0001F680-\U0001F6FF"  # Transport and Map
    r"\U0001F1E0-\U0001F1FF"  # Regional Indicator Symbols (Flags)
    r"\U00002702-\U000027B0"  # Dingbats
    r"\U0001F900-\U0001F9FF"  # Supplemental Symbols and Pictographs
    r"\U0001FA70-\U0001FAFF"  # Symbols and Pictographs Extended-A
    r"\U00002600-\U00002604\U00002614-\U00002615\U00002618\U0000261D\U00002620\U00002622-\U00002623\U0000262E-\U0000262F"
    r"\U00002638-\U0000263A\U00002640\U00002642\U00002648-\U00002653\U00002660\U00002663\U00002665-\U00002666\U00002668"
    r"\U0000267B\U0000267E-\U0000267F\U00002692-\U00002697\U00002699\U0000269B-\U0000269C\U000026A0-\U000026A1\U000026A7"
    r"\U000026AA-\U000026AB\U000026B0-\U000026B1\U000026BD-\U000026BE\U000026C4-\U000026C5\U000026C8\U000026CE-\U000026CF"
    r"\U000026D1\U000026D3-\U000026D4\U000026E9-\U000026EA\U000026F0-\U000026F5\U000026F7-\U000026FA\U000026FD"
    r"]",
    flags=re.UNICODE,
)

# Secret pattern checks
SECRET_PATTERNS = [
    re.compile(r"(AIza[0-9A-Za-z-_]{35})"),  # Google API key
    re.compile(r"sk-[a-zA-Z0-9]{32,}"),      # OpenAI key
    re.compile(r"(ghp_[a-zA-Z0-9]{36})"),    # GitHub personal access token
    re.compile(r"(gho_[a-zA-Z0-9]{36})"),    # GitHub oauth token
    re.compile(r"-----BEGIN (RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"GEMINI_API_KEY\s*=\s*['\"][a-zA-Z0-9_-]{20,}['\"]"),
]

# Gradient patterns
GRADIENT_PATTERN = re.compile(r"(linear-gradient|radial-gradient|conic-gradient)", re.IGNORECASE)


def get_tracked_files():
    cmd = ["git", "ls-files"]
    res = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, check=True)
    return [ROOT / f.strip() for f in res.stdout.splitlines() if f.strip()]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    files = get_tracked_files()
    emoji_hits = []
    gradient_hits = []
    secret_hits = []
    large_files = []

    # Whitelist / ignore patterns
    ignore_extensions = {".joblib", ".png", ".jpg", ".jpeg", ".ico", ".woff", ".woff2", ".ttf"}

    for p in files:
        if not p.exists():
            continue

        # File size check (> 5MB)
        size_mb = p.stat().st_size / (1024 * 1024)
        if size_mb > 5.0:
            large_files.append((str(p.relative_to(ROOT)), f"{size_mb:.2f} MB"))

        if p.suffix.lower() in ignore_extensions:
            continue

        try:
            content = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        # 1. Emoji check
        for line_num, line in enumerate(content.splitlines(), start=1):
            if EMOJI_PATTERN.search(line):
                # Exclude this script itself
                if "audit_repo.py" not in str(p):
                    emoji_hits.append((str(p.relative_to(ROOT)), line_num, line.strip()))

        # 2. Gradient check (in UI / css / docs)
        if p.suffix.lower() in {".css", ".html", ".tsx", ".jsx", ".ts", ".js", ".md"}:
            for line_num, line in enumerate(content.splitlines(), start=1):
                if GRADIENT_PATTERN.search(line):
                    gradient_hits.append((str(p.relative_to(ROOT)), line_num, line.strip()))

        # 3. Secret check
        for line_num, line in enumerate(content.splitlines(), start=1):
            for sp in SECRET_PATTERNS:
                if sp.search(line):
                    if not p.name.endswith(".example"):
                        secret_hits.append((str(p.relative_to(ROOT)), line_num, line.strip()))

    print("=== REPO AUDIT REPORT ===")
    print(f"Total tracked files scanned: {len(files)}")
    print(f"Large files (> 5MB): {len(large_files)}")
    for f, sz in large_files:
        print(f"  [LARGE FILE] {f} ({sz})")

    print(f"Secrets detected: {len(secret_hits)}")
    for f, lnum, line in secret_hits:
        print(f"  [SECRET] {f}:{lnum} -> {line[:40]}...")

    print(f"Emojis detected: {len(emoji_hits)}")
    for f, lnum, line in emoji_hits:
        print(f"  [EMOJI] {f}:{lnum} -> {line[:60]}")

    print(f"Gradients detected: {len(gradient_hits)}")
    for f, lnum, line in gradient_hits:
        print(f"  [GRADIENT] {f}:{lnum} -> {line[:60]}")

    if emoji_hits or secret_hits or large_files or gradient_hits:
        print("Audit findings detected.")
        sys.exit(1)
    else:
        print("Audit PASSED cleanly: zero emojis, zero secrets, zero large files, zero gradients.")
        sys.exit(0)


if __name__ == "__main__":
    main()
