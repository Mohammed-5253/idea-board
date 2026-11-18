"""Print the resource addresses of a Terraform state, like `terraform state list`.

    aws s3 cp s3://<bucket>/<key> - | python3 ci/state_addresses.py

Reads one state file (format version 4) as JSON on stdin and prints one address per
line. Only module paths, modes, types, names and instance keys are read: attribute
values (DB passwords, tokens) never reach stdout, so the output is safe to show an AI.
Standard library only.
"""

from __future__ import annotations

import json
import sys


def _quote(key: str) -> str:
    """HCL-quote a for_each key the way Terraform prints it (["a\\"b"])."""
    out = []
    for ch in key:
        if ch == "\\":
            out.append("\\\\")
        elif ch == '"':
            out.append('\\"')
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\r":
            out.append("\\r")
        elif ch == "\t":
            out.append("\\t")
        elif not ch.isprintable():
            out.append(f"\\u{ord(ch):04x}" if ord(ch) <= 0xFFFF else f"\\U{ord(ch):08x}")
        else:
            out.append(ch)
    return '"' + "".join(out).replace("${", "$${").replace("%{", "%%{") + '"'


def _key(index_key: object) -> str:
    if index_key is None:
        return ""
    if isinstance(index_key, bool) or not isinstance(index_key, (int, str)):
        raise ValueError(f"unsupported instance key type: {type(index_key).__name__}")
    return f"[{index_key}]" if isinstance(index_key, int) else f"[{_quote(index_key)}]"


def addresses(state: dict) -> list[str]:
    version = state.get("version")
    if version != 4:
        raise ValueError(f"unsupported state format version: {version!r}")
    lines = []
    for res in state.get("resources", []):
        prefix = f"{res['module']}." if res.get("module") else ""
        mode = "data." if res.get("mode") == "data" else ""
        for inst in res.get("instances", []):
            lines.append(f"{prefix}{mode}{res['type']}.{res['name']}{_key(inst.get('index_key'))}")
    return sorted(set(lines))


def main() -> int:
    try:
        state = json.load(sys.stdin)
        lines = addresses(state)
    except (ValueError, KeyError, TypeError) as exc:  # message only: never echo the state
        print(f"state_addresses: {exc}", file=sys.stderr)
        return 1
    for line in lines:
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
