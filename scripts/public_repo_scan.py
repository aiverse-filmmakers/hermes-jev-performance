#!/usr/bin/env python3
"""Conservative public-repository secret/private-data scan.

Designed for CI. It scans text-like project files and never prints matched secret
values, only file paths and rule identifiers.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import re


SKIP_DIRS = {
    ".git", ".venv", "venv", "__pycache__", ".pytest_cache",
    "node_modules", "dist-info", "egg-info",
}
TEXT_SUFFIXES = {
    ".py", ".md", ".json", ".yaml", ".yml", ".toml", ".txt",
    ".js", ".css", ".html", ".sh",
}
RULES = (
    ("private_key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("openrouter_token", re.compile(r"\bsk-or-v1-[A-Za-z0-9_-]{16,}\b")),
    ("github_classic_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    ("github_fine_grained_token", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b")),
    ("slack_token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{16,}\b")),
    ("telegram_bot_token", re.compile(r"\b\d{8,12}:[A-Za-z0-9_-]{30,}\b")),
    ("linux_user_path", re.compile(r"(?<![A-Za-z0-9_])/home/[A-Za-z0-9._-]+/")),
    ("mac_user_path", re.compile(r"(?<![A-Za-z0-9_])/Users/[A-Za-z0-9._-]+/")),
    ("windows_user_path", re.compile(r"(?i)\b[A-Z]:\\\\Users\\\\[^\\\\\r\n]+\\\\")),
)

EMAIL_RE = re.compile(
    r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b"
)
IPV4_RE = re.compile(
    r"(?<![0-9])(?:\d{1,3}\.){3}\d{1,3}(?![0-9])"
)
SAFE_EMAIL_DOMAINS = {"example.com", "example.org", "example.net"}
SAFE_IPV4 = {"0.0.0.0", "127.0.0.1", "255.255.255.255"}
SAFE_IPV4_PREFIXES = ("192.0.2.", "198.51.100.", "203.0.113.")

ASSIGNMENT_RE = re.compile(
    r"(?m)^\s*(?:export\s+)?"
    r"(OPENROUTER(?:_JEV)?_API_(?:KEY|TOKEN)|GITHUB_TOKEN|GH_TOKEN)"
    r"\s*=\s*([^\s#]+)"
)
PLACEHOLDER_VALUES = {
    '""', "''", "<TOKEN>", "<API_KEY>", "<KEY>", "YOUR_TOKEN",
    "YOUR_API_KEY", "\${TOKEN}", "\${API_KEY}",
}


def iter_files(root: Path):
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() in TEXT_SUFFIXES or path.name == "LICENSE":
            yield path


def scan_text(text: str) -> set[str]:
    findings: set[str] = set()
    for rule_id, pattern in RULES:
        if pattern.search(text):
            findings.add(rule_id)

    for match in EMAIL_RE.finditer(text):
        address = match.group(0)
        domain = address.rsplit("@", 1)[-1].lower()
        if domain not in SAFE_EMAIL_DOMAINS:
            findings.add("email_address")

    for match in IPV4_RE.finditer(text):
        value = match.group(0)
        try:
            octets = [int(part) for part in value.split(".")]
        except ValueError:
            continue
        if len(octets) != 4 or any(part > 255 for part in octets):
            continue
        if value in SAFE_IPV4 or value.startswith(SAFE_IPV4_PREFIXES):
            continue
        findings.add("ipv4_address")

    for match in ASSIGNMENT_RE.finditer(text):
        value = match.group(2).strip()
        if value not in PLACEHOLDER_VALUES and not value.startswith("\${"):
            findings.add("credential_assignment")
    return findings


def scan_repository(root: Path) -> list[tuple[str, str]]:
    findings: list[tuple[str, str]] = []
    for path in iter_files(root):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for rule_id in sorted(scan_text(text)):
            findings.append((path.relative_to(root).as_posix(), rule_id))
    return findings


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    findings = scan_repository(root)
    if findings:
        print("Public-repository scan FAILED")
        for path, rule_id in findings:
            print(f"{path}: {rule_id}")
        return 1
    print("Public-repository scan PASS: no blocked patterns found")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
