#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""04_upload_docx.py — 把原始 docx 二进制文件作为附件归档到 wiki 知识库。

可选步骤。如果用户希望"md 进 wiki 文档树 + docx 二进制留档供下载"，跑这一步。

策略：在每个 08_SOURCE/<subdir> 下建一个 _原始docx 子目录，把 docx 上传进去。

可重入：以 docx_attachments_index.json 跟踪已上传 → 跳过。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib.dws import (
    assert_authenticated,
    load_json,
    run_dws,
    save_json,
    work_paths,
)

ATTACH_FOLDER_NAME = "_原始docx"


def docx_index_path(work_dir: str) -> str:
    return os.path.join(os.path.abspath(work_dir), "docx_attachments_index.json")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--workspace", required=True)
    ap.add_argument("--work-dir", required=True)
    ap.add_argument(
        "--source", action="append", required=True, dest="sources",
        help="<PATH>:<SUBDIR> 格式，可重复",
    )
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    assert_authenticated()
    paths = work_paths(args.work_dir)
    folder_idx = load_json(paths["folder_idx"], {})
    attach_idx_file = docx_index_path(args.work_dir)
    attach_idx: dict[str, dict] = load_json(attach_idx_file, {})

    ok = fail = skip = 0

    for src_spec in args.sources:
        if ":" not in src_spec:
            print(f"ERROR: --source must be PATH:SUBDIR")
            return 1
        path, subdir = src_spec.rsplit(":", 1)
        path = os.path.abspath(path)
        parent_key = f"08_SOURCE/{subdir}"
        parent = folder_idx.get(parent_key)
        if not parent:
            print(f"WARN: {parent_key} 不在 folder_idx 中，跳过 {path}")
            continue

        # 在该 subdir 下建 _原始docx 子目录（幂等）
        attach_folder_key = f"{parent_key}/{ATTACH_FOLDER_NAME}"
        attach_folder = folder_idx.get(attach_folder_key)
        if not attach_folder:
            if args.dry_run:
                print(f"[dry] would create folder {attach_folder_key}")
                attach_folder = "<dry-run-folder>"
            else:
                r = run_dws([
                    "doc", "folder", "create",
                    "--workspace", args.workspace,
                    "--folder", parent,
                    "--name", ATTACH_FOLDER_NAME,
                    "-y",
                ])
                attach_folder = r.get("nodeId")
                if not attach_folder:
                    print(f"[FAIL create folder] {attach_folder_key}: {r}")
                    continue
                folder_idx[attach_folder_key] = attach_folder
                save_json(paths["folder_idx"], folder_idx)
                print(f"[ok] folder {attach_folder_key} -> {attach_folder}")

        # 找 docx 文件
        if not os.path.isdir(path):
            print(f"WARN: not a dir: {path}")
            continue
        docxs = [
            os.path.join(path, f) for f in sorted(os.listdir(path))
            if f.lower().endswith(".docx") and not f.startswith(".")
        ]
        for f in docxs:
            base = os.path.basename(f)
            key = f"{subdir}/{base}"
            if key in attach_idx:
                print(f"[skip] {key}")
                skip += 1
                continue
            if args.dry_run:
                print(f"[dry] would upload {f} -> {attach_folder_key}")
                continue
            r = run_dws([
                "doc", "upload",
                "--file", f,
                "--folder", attach_folder,
                "--name", base,
                "-y",
            ])
            nid = r.get("nodeId") or r.get("fileId")
            if not nid:
                print(f"[FAIL] {key}: {(r.get('error') or {}).get('message', str(r)[:200])}")
                fail += 1
                continue
            attach_idx[key] = {"subdir": subdir, "nodeId": nid}
            print(f"[ok] {key} -> {nid}")
            ok += 1
            time.sleep(0.3)

    if not args.dry_run:
        save_json(attach_idx_file, attach_idx)
    print(f"\n=== ok={ok} skip={skip} fail={fail} total={len(attach_idx)} ===")
    print(f"Index: {attach_idx_file}")
    return 0 if fail == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
