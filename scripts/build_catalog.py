#!/usr/bin/env python3
"""Build the stable public catalog for the framepack-video-skill repository."""

from __future__ import annotations

import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"
NAMES = ["framepack-video"]
PURPOSE = {
    "framepack-video": "审查并控制已安装的本地 FramePack 模型下载与图生视频 WebUI",
}
NETWORK = {"framepack-video"}
WRITES = {"framepack-video"}
CREDENTIALS = set()
COST = {"framepack-video"}
EXTERNAL_STATE = {"framepack-video"}
DEPENDENCIES = {
    "framepack-video": [
        "Windows",
        "Python 3.10+",
        "PowerShell",
        "用户已自行安装并审查的 FramePack",
        "约 43 GB 可用磁盘空间（仅在用户批准模型下载时）",
    ],
}


def display_name(name: str) -> str:
    text = (SKILLS / name / "agents" / "openai.yaml").read_text(encoding="utf-8")
    match = re.search(r'^\s*display_name:\s*["\']?(.+?)["\']?\s*$', text, re.M)
    return match.group(1) if match else name


def main() -> int:
    provenance = json.loads((ROOT / "provenance.json").read_text(encoding="utf-8"))
    approved = {row["name"] for row in provenance.get("skills", [])}
    planned = set(NAMES)
    directories = {path.name for path in SKILLS.iterdir() if path.is_dir()}
    if approved != planned or directories != approved:
        raise ValueError(
            "publication set differs from provenance approval: "
            f"unplanned={sorted(directories - approved)}, "
            f"missing={sorted(approved - directories)}, "
            f"metadata_gap={sorted(approved ^ planned)}"
        )
    rows = []
    for name in NAMES:
        rows.append({
            "name": name,
            "display_name_zh": display_name(name),
            "purpose_zh": PURPOSE[name],
            "release": "v0.1.0",
            "platforms": ["Windows"],
            "risk_level": "high",
            "permissions": {
                "network": name in NETWORK,
                "filesystem_read": True,
                "filesystem_write": name in WRITES,
                "credentials": name in CREDENTIALS,
                "external_state": name in EXTERNAL_STATE,
                "cost_or_quota": name in COST,
            },
            "dependencies": DEPENDENCIES[name],
            "invocation_policy": "explicit-only",
            "license": "MIT",
            "version": "0.1.0",
            "archive_sha256": None,
        })
    payload = {
        "schema_version": 1,
        "repository": "ranveerankhira-gif/framepack-video-skill",
        "skills": rows,
    }
    target = ROOT / "catalog.json"
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {target} with {len(rows)} skills")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
