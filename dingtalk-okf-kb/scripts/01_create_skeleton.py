#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""01_create_skeleton.py — 在目标钉钉知识库下创建 OKF 目录骨架。

骨架：
  00_MANIFEST / 01_INDEX / 02_PRODUCT / 03_CAPABILITY / 04_RULE
  05_RESOURCE / 06_DECISION / 07_SERVICE / 08_SOURCE
  08_SOURCE/<sub1> / 08_SOURCE/<sub2> / ...

输出 <WORK_DIR>/folder_idx.json：目录名 -> wiki nodeId

可重入：folder_idx.json 已存在的目录跳过创建。
"""
from __future__ import annotations

import argparse
import os
import sys

# 让脚本能 import lib/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib.dws import (
    assert_authenticated,
    load_json,
    run_dws,
    save_json,
    work_paths,
)


TOP_LEVEL = [
    "00_MANIFEST", "01_INDEX",
    "02_PRODUCT", "03_CAPABILITY", "04_RULE", "05_RESOURCE",
    "06_DECISION", "07_SERVICE", "08_SOURCE",
]


def create_folder(workspace: str, name: str, parent: str | None = None) -> str | None:
    args = ["doc", "folder", "create", "--workspace", workspace, "--name", name, "-y"]
    if parent:
        args[-2:-2] = ["--folder", parent]
    r = run_dws(args)
    return r.get("nodeId")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--workspace", required=True, help="目标钉钉知识库 workspaceId")
    ap.add_argument("--work-dir", required=True, help="工作目录（中间产物落地）")
    ap.add_argument(
        "--source-subdirs",
        default="",
        help="08_SOURCE 下的子目录名，逗号分隔。例：'Agent协作平台,DMClaw,PRD归档'",
    )
    ap.add_argument("--dry-run", action="store_true", help="只打印计划不创建")
    args = ap.parse_args()

    assert_authenticated()
    paths = work_paths(args.work_dir)
    os.makedirs(paths["root"], exist_ok=True)

    idx: dict[str, str] = load_json(paths["folder_idx"], {})
    created = 0
    skipped = 0

    # Top-level folders
    for name in TOP_LEVEL:
        if name in idx:
            print(f"[skip] {name} = {idx[name]}")
            skipped += 1
            continue
        if args.dry_run:
            print(f"[dry] would create {name}")
            continue
        nid = create_folder(args.workspace, name)
        if not nid:
            print(f"[FAIL] create {name}")
            continue
        idx[name] = nid
        print(f"[ok] {name} -> {nid}")
        created += 1

    # Source subfolders under 08_SOURCE
    src_parent = idx.get("08_SOURCE")
    if not src_parent:
        if not args.dry_run:
            print("ERROR: 08_SOURCE not in idx, can't create subfolders")
            return 1
    sub_list = [s.strip() for s in args.source_subdirs.split(",") if s.strip()]
    for sub in sub_list:
        key = f"08_SOURCE/{sub}"
        if key in idx:
            print(f"[skip] {key} = {idx[key]}")
            skipped += 1
            continue
        if args.dry_run:
            print(f"[dry] would create {key}")
            continue
        nid = create_folder(args.workspace, sub, parent=src_parent)
        if not nid:
            print(f"[FAIL] create {key}")
            continue
        idx[key] = nid
        print(f"[ok] {key} -> {nid}")
        created += 1

    if not args.dry_run:
        save_json(paths["folder_idx"], idx)
    print(f"\n=== created={created} skipped={skipped} total_keys={len(idx)} ===")
    print(f"Index: {paths['folder_idx']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
