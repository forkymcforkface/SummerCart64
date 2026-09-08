#!/usr/bin/env python3
"""Generate or explicitly install/remove the research-only N64 receiver hook."""
import argparse
import difflib
import hashlib
import json
from pathlib import Path

MARKER = "void gpu_init(void)\n{"
HOOK = '    phos_usb_on("gifspanbench", gif_span_bench);'
NAME = "gif_span_bench"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="explicit src/rtk/rtk_gpu_n64.c in an isolated checkout")
    parser.add_argument("output", type=Path, help="ignored patch/backup directory")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--apply", action="store_true", help="modify explicit source, preserving exact backup")
    action.add_argument("--remove", action="store_true", help="restore backup only if installed source is unchanged")
    args = parser.parse_args()
    source = args.source.resolve()
    original = source.read_bytes()
    backup = args.output / "receiver-original.c"
    state_path = args.output / "receiver-state.json"
    if args.remove:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        saved = backup.read_bytes()
        if (state["source"] != str(source) or state["status"] != "installed"
                or digest(original) != state["installed_sha256"]
                or digest(saved) != state["original_sha256"]):
            raise SystemExit("REFUSED: source/backup changed; preserve those edits and review manually")
        source.write_bytes(saved)
        state["status"] = "removed"
        state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
        print("PASS restored exact original source")
        return
    text = original.decode("utf-8").replace("\r\n", "\n")
    if text.count(MARKER) != 1 or NAME in text or '"gifspanbench"' in text:
        raise SystemExit("REFUSED: expected one clean gpu_init and no receiver hook")
    payload = Path(__file__).with_name("receiver.inc").read_text(encoding="utf-8-sig")
    modified = text.replace(MARKER, payload + "\n" + MARKER + "\n" + HOOK, 1)
    if modified.count("static void gif_span_bench(") != 1 or modified.count(HOOK) != 1:
        raise SystemExit("REFUSED: receiver declaration/hook is not unique")
    args.output.mkdir(parents=True, exist_ok=True)
    patch = "".join(difflib.unified_diff(text.splitlines(True), modified.splitlines(True),
                                       fromfile="a/src/rtk/rtk_gpu_n64.c",
                                       tofile="b/src/rtk/rtk_gpu_n64.c"))
    (args.output / "receiver.patch").write_text(patch, encoding="utf-8")
    if args.apply:
        if backup.exists() or state_path.exists():
            raise SystemExit("REFUSED: backup already exists; use a fresh ignored output directory")
        installed = modified.encode("utf-8")
        backup.write_bytes(original)
        state = dict(source=str(source), original_sha256=digest(original),
                     installed_sha256=digest(installed), status="installed")
        state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
        source.write_bytes(installed)
        print("PASS installed research-only receiver; exact source backup retained")
    else:
        print("PASS generated receiver.patch; source unchanged")


if __name__ == "__main__":
    main()
