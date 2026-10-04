#!/usr/bin/env python3
"""Build small, allowlisted Hermes component ZIPs and verification metadata."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import posixpath
import re
import stat
import sys
import zipfile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agent"))
from jevperf import __version__  # noqa: E402


def _files_for(kind: str) -> list[tuple[Path, str]]:
    paths: list[tuple[Path, str]] = []

    def add(source: str, target: str | None = None) -> None:
        src = ROOT / source
        if not src.is_file():
            raise FileNotFoundError(f"Required release file missing: {source}")
        paths.append((src, target or source))

    if kind in ("server", "combined"):
        add("agent/plugin.yaml" if kind == "server" else "plugin.yaml", "plugin.yaml")
        if kind == "combined":
            add("__init__.py")
            add("agent/plugin.yaml")
        for path in sorted((ROOT / "agent" / "jevperf").glob("*.py")):
            source = path.relative_to(ROOT).as_posix()
            add(source, source.removeprefix("agent/") if kind == "server" else source)
        add("agent/__init__.py", "__init__.py" if kind == "server" else "agent/__init__.py")
        if kind == "server":
            add("agent/dashboard/manifest.json", "dashboard/manifest.json")
            add("agent/dashboard/plugin_api.py", "dashboard/plugin_api.py")
            add("agent/dashboard/server-only.js", "dashboard/server-only.js")
        add("agent/after-install.md" if kind == "server" else "after-install.md", "after-install.md")
        add("LICENSE")
        add("THIRD_PARTY_NOTICES.md")
        add("agent/README.md", "README.md")
        if kind == "combined":
            paths = [(source, target) for source, target in paths if target != "README.md"]
            add("README.md")
            add("CHANGELOG.md")
            for guide in sorted((ROOT / "docs").glob("*.md")):
                add(guide.relative_to(ROOT).as_posix())
            add("desktop/plugin.js")
            add("desktop/README.md", "desktop/README.md")
            add("dashboard/manifest.json")
            add("dashboard/plugin_api.py")
            add("dashboard/dist/index.js")
            add("dashboard/dist/style.css")
    elif kind == "desktop":
        add("desktop/plugin.js", "plugin.js")
        add("desktop/README.md", "README.md")
        add("LICENSE")
    else:
        raise ValueError(f"Unknown package kind: {kind}")

    names = [name for _, name in paths]
    if len(names) != len(set(names)):
        raise ValueError("Release file mapping has duplicate paths")
    return sorted([(source, "hermes-jev-performance/" + target) for source, target in paths], key=lambda pair: pair[1])


def _write_zip(kind: str, output: Path) -> tuple[int, str, list[str]]:
    files = _files_for(kind)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for source, target in files:
            if source.is_symlink():
                raise ValueError("Release sources must be regular files, not symlinks")
            info = zipfile.ZipInfo(PurePosixPath(target).as_posix(), date_time=(2020, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, source.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    inventory = [target for _, target in files]
    output.with_suffix(output.suffix + ".sha256").write_text(f"{digest}  {output.name}\n", encoding="utf-8")
    output.with_suffix(output.suffix + ".files.txt").write_text("\n".join(inventory) + "\n", encoding="utf-8")
    return output.stat().st_size, digest, inventory


def build(output_dir: Path) -> dict[str, dict[str, object]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    releases: dict[str, dict[str, object]] = {}
    for kind, label in (("server", "server-only"), ("desktop", "desktop-dashboard"), ("combined", "combined-local")):
        path = output_dir / f"hermes-jev-performance-{label}-{__version__}.zip"
        size, digest, inventory = _write_zip(kind, path)
        releases[kind] = {"path": path.name, "bytes": size, "sha256": digest, "files": inventory}
    metadata = {"plugin": "hermes-jev-performance", "version": __version__, "packages": releases}
    (output_dir / "release-manifest.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return metadata


def verify(metadata: dict[str, dict[str, object]], output_dir: Path) -> None:
    allowed_server_roots = {"jevperf", "dashboard", "README.md", "LICENSE", "THIRD_PARTY_NOTICES.md", "plugin.yaml", "__init__.py", "after-install.md"}
    for kind, entry in metadata["packages"].items():  # type: ignore[union-attr]
        path = output_dir / str(entry["path"])
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            if names != sorted(names) or len(names) != len(set(names)):
                raise ValueError(f"{path.name}: inventory order/uniqueness failure")
            for name in names:
                segments = PurePosixPath(name).parts
                if not segments or segments[0] != "hermes-jev-performance" or ".." in segments or PurePosixPath(name).is_absolute():
                    raise ValueError(f"{path.name}: unsafe extraction layout")
            if names != entry["files"] or hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
                raise ValueError(f"{path.name}: checksum/inventory mismatch")
            prefix = "hermes-jev-performance/"
            relative = [name.removeprefix(prefix) for name in names]
            if kind == "server":
                unexpected = [name for name in relative if name.split("/", 1)[0] not in allowed_server_roots]
                if unexpected or any("dist/" in name or name.startswith("desktop/") for name in relative):
                    raise ValueError(f"Server ZIP includes visual/dev files: {unexpected}")
                if "dashboard/server-only.js" not in relative or "dashboard/dist/index.js" in relative:
                    raise ValueError("Server ZIP is missing its tiny hidden shim or includes the visual bundle")
            if kind == "desktop" and relative != ["LICENSE", "README.md", "plugin.js"]:
                raise ValueError(f"Unexpected Desktop-only package contents: {names}")
            if kind == "combined" and not all(name in relative for name in ("README.md", "docs/INSTALL_LOCAL.md", "desktop/plugin.js")):
                raise ValueError("Combined package is missing its beginner guide or Desktop component")
            for name in names:
                if name.endswith(".md"):
                    text = archive.read(name).decode("utf-8")
                    for target in re.findall(r"\]\(([^)]+)\)", text):
                        if ":" in target or target.startswith("#"):
                            continue
                        destination = posixpath.normpath(posixpath.join(posixpath.dirname(name), target.split("#")[0]))
                        if destination not in names:
                            raise ValueError(f"{path.name}: broken document link in {name}: {target}")
            if "plugin.yaml" in relative:
                manifest = archive.read(prefix + "plugin.yaml").decode("utf-8")
                if not re.search(rf"(?m)^version:\s*['\"]?{re.escape(__version__)}(?:['\"])?\s*$", manifest):
                    raise ValueError(f"Version mismatch in {path.name}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist" / "releases")
    args = parser.parse_args()
    metadata = build(args.output)
    verify(metadata, args.output)
    for kind, item in metadata["packages"].items():  # type: ignore[union-attr]
        print(f"{kind}: {item['path']} ({item['bytes']} bytes, sha256 {item['sha256']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
