#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""05_upload_okf_cards.py — 把 <WORK_DIR>/okf_cards/ 下的本地 OKF 卡片上传到 wiki 02-07 目录。

每张卡片以其 frontmatter 的 `title` 字段作为 wiki 文档名；以 `id` 字段作为去重 key。

输出 <WORK_DIR>/okf_node_index.json：okf_id -> {type_dir, title, filename, nodeId, docUrl}

可重入。
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
    parse_frontmatter,
    run_dws,
    save_json,
    work_paths,
)


CARD_DIRS = ("02_PRODUCT", "03_CAPABILITY", "04_RULE", "05_RESOURCE", "06_DECISION", "07_SERVICE")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--workspace", required=True)
    ap.add_argument("--work-dir", required=True)
    ap.add_argument("--sleep", type=float, default=0.3)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    assert_authenticated()
    paths = work_paths(args.work_dir)
    folder_idx = load_json(paths["folder_idx"], {})
    okf_idx: dict[str, dict] = load_json(paths["okf_index"], {})

    cards_root = paths["okf_cards_dir"]
    if not os.path.isdir(cards_root):
        print(f"ERROR: okf_cards 目录不存在：{cards_root}")
        return 1

    ok = fail = skip = 0

    for type_dir in CARD_DIRS:
        local_dir = os.path.join(cards_root, type_dir)
        folder = folder_idx.get(type_dir)
        if not folder:
            if os.path.isdir(local_dir) and os.listdir(local_dir):
                print(f"WARN: {type_dir} 在 folder_idx 中缺失，但本地有卡片 → 跳过该目录")
            continue
        if not os.path.isdir(local_dir):
            continue

        for fname in sorted(os.listdir(local_dir)):
            if not fname.endswith(".md"):
                continue
            full = os.path.join(local_dir, fname)
            with open(full, encoding="utf-8") as f:
                content = f.read()
            meta = parse_frontmatter(content)
            okf_id = meta.get("id") or fname[:-3]
            title = meta.get("title") or fname[:-3]

            if okf_id in okf_idx:
                print(f"[skip] {okf_id}")
                skip += 1
                continue
            if args.dry_run:
                n = len(chunk_markdown(content))
                print(f"[dry] would upload {okf_id} ({len(content)} chars, {n} chunks) -> {type_dir}")
                continue

            if len(content) <= DOC_CREATE_MAX_CHARS - 100:
                r = run_dws([
                    "doc", "create",
                    "--workspace", args.workspace,
                    "--folder", folder,
                    "--name", title,
                    "--content-file", full,
                    "--content-format", "markdown",
                    "--fix-jsonml",
                    "-y",
                ])
                n_chunks = 1
            else:
                r = create_doc_with_chunks(args.workspace, folder, title, content)
                n_chunks = r.get("chunks_total", 1)

            nid = r.get("nodeId")
            if not nid:
                err = (r.get("error") or {}).get("message", str(r)[:200])
                print(f"[FAIL] {type_dir}/{fname}: {err}")
                fail += 1
                continue
            url = r.get("docUrl") or f"https://alidocs.dingtalk.com/i/nodes/{nid}"
            okf_idx[okf_id] = {
                "type_dir": type_dir,
                "title": title,
                "filename": fname,
                "nodeId": nid,
                "docUrl": url,
                "chunks": n_chunks,
            }
            print(f"[ok] {type_dir}/{okf_id} -> {nid}")
            ok += 1

            if ok % 10 == 0:
                save_json(paths["okf_index"], okf_idx)
            time.sleep(args.sleep)

    if not args.dry_run:
        save_json(paths["okf_index"], okf_idx)

    print(f"\n=== ok={ok} skip={skip} fail={fail} total_indexed={len(okf_idx)} ===")
    print(f"Index: {paths['okf_index']}")
    return 0 if fail == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
