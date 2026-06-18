#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""03_upload_sources.py — 把 upload_list.tsv 里的 markdown 上传到 wiki 08_SOURCE 对应子目录。

自动处理超过 10000 字符的文件（钉钉 doc create 上限）：首块 create + 后续 append。

输出 <WORK_DIR>/source_node_index.json：doc_name -> {subdir, nodeId, docUrl, chunks}

可重入：已在 source_node_index.json 里的 doc_name 跳过。
"""
from __future__ import annotations

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib.dws import (
    DOC_CREATE_MAX_CHARS,
    assert_authenticated,
    chunk_markdown,
    create_doc_with_chunks,
    load_json,
    run_dws,
    save_json,
    work_paths,
)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--workspace", required=True, help="目标知识库 workspaceId")
    ap.add_argument("--work-dir", required=True)
    ap.add_argument("--sleep", type=float, default=0.3, help="每份之间 sleep 秒数 (default 0.3)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    assert_authenticated()
    paths = work_paths(args.work_dir)

    folder_idx = load_json(paths["folder_idx"], {})
    src_idx: dict[str, dict] = load_json(paths["source_index"], {})

    if not os.path.exists(paths["upload_list"]):
        print(f"ERROR: upload_list 不存在：{paths['upload_list']}")
        print("请先跑 02_scan_sources.py")
        return 1

    rows: list[tuple[str, str, str]] = []
    with open(paths["upload_list"], encoding="utf-8") as f:
        next(f, None)  # skip header
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) >= 3:
                rows.append((parts[0], parts[1], parts[2]))

    ok = fail = skip = chunked = 0
    for subdir, src_path, doc_name in rows:
        if doc_name in src_idx:
            print(f"[skip] {doc_name}")
            skip += 1
            continue

        folder = folder_idx.get(f"08_SOURCE/{subdir}")
        if not folder:
            print(f"[FAIL no folder] subdir={subdir} doc={doc_name}")
            fail += 1
            continue

        if not os.path.exists(src_path):
            print(f"[FAIL missing] {src_path}")
            fail += 1
            continue

        with open(src_path, encoding="utf-8") as f:
            content = f.read()

        if args.dry_run:
            n = len(chunk_markdown(content))
            print(f"[dry] would upload {doc_name} ({len(content)} chars, {n} chunks)")
            continue

        if len(content) <= DOC_CREATE_MAX_CHARS - 100:
            # 单次 create
            r = run_dws([
                "doc", "create",
                "--workspace", args.workspace,
                "--folder", folder,
                "--name", doc_name,
                "--content-file", src_path,
                "--content-format", "markdown",
                "--fix-jsonml",
                "-y",
            ])
            n_chunks = 1
        else:
            # 分块
            r = create_doc_with_chunks(args.workspace, folder, doc_name, content)
            n_chunks = r.get("chunks_total", 1)
            chunked += 1

        nid = r.get("nodeId")
        if not nid:
            err_msg = (r.get("error") or {}).get("message", str(r)[:200])
            print(f"[FAIL] {doc_name}: {err_msg}")
            fail += 1
            continue

        url = r.get("docUrl") or f"https://alidocs.dingtalk.com/i/nodes/{nid}"
        src_idx[doc_name] = {
            "subdir": subdir,
            "nodeId": nid,
            "docUrl": url,
            "chunks": n_chunks,
        }
        print(f"[ok] {subdir}/{doc_name} -> {nid}" + (f" ({n_chunks} chunks)" if n_chunks > 1 else ""))
        ok += 1

        # 每 10 份 flush 一次索引
        if ok % 10 == 0:
            save_json(paths["source_index"], src_idx)
        time.sleep(args.sleep)

    if not args.dry_run:
        save_json(paths["source_index"], src_idx)

    print(f"\n=== ok={ok} skip={skip} fail={fail} chunked={chunked} total_indexed={len(src_idx)} ===")
    print(f"Index: {paths['source_index']}")
    return 0 if fail == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
