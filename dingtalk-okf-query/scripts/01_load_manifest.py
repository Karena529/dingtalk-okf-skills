#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""01_load_manifest.py — 把目标钉钉知识库的 OKF 卡片元数据拉到本地缓存。

策略：
  1. 在知识库内按 "00_MANIFEST" 找 MANIFEST 目录的 nodeId
  2. 列出该目录下所有 manifest-* 文档（manifest-all 不读，因为它最长且重复）
  3. 直接遍历 02_PRODUCT…07_SERVICE 目录，逐个读卡片正文，解析 frontmatter
  4. 输出富化清单（id / title / aliases / summary / status / products / type / nodeId）
  5. 写入 <cache_dir>/<ws>/manifest.json

后续 02_match_cards.py / 03_read_card.py 直接读这个缓存文件。

可选：
  --force          忽略缓存，强制重新拉取
  --ttl <秒>       自定义缓存有效期，默认 3600
  --cache-dir <P>  自定义缓存根目录（默认 ~/.cache/dingtalk-okf-query）
"""
from __future__ import annotations

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib.dws import (
    assert_authenticated,
    cache_dir,
    extract_doc_text,
    is_cache_fresh,
    list_folder,
    manifest_cache_path,
    parse_frontmatter,
    read_doc,
    run_dws,
    save_json,
)


CARD_FOLDERS = ["02_PRODUCT", "03_CAPABILITY", "04_RULE", "05_RESOURCE", "06_DECISION", "07_SERVICE"]


def find_top_level_folders(workspace_id: str) -> dict[str, str]:
    """在知识库根目录列出所有 02-07 子目录的 nodeId。"""
    # dws doc list 单页上限实测 50
    r = run_dws(["doc", "list", "--workspace", workspace_id, "--page-size", "50"])
    nodes = r.get("nodes") or r.get("documents") or []
    out = {}
    for n in nodes:
        name = n.get("name", "")
        if name in CARD_FOLDERS:
            out[name] = n.get("nodeId")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workspace", required=True, help="目标钉钉知识库 workspaceId")
    ap.add_argument("--cache-dir", default=None, help="缓存根目录（默认 ~/.cache/dingtalk-okf-query）")
    ap.add_argument("--ttl", type=int, default=3600, help="缓存有效期（秒），默认 3600")
    ap.add_argument("--force", action="store_true", help="强制重新拉取")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    cache_path = manifest_cache_path(args.workspace, args.cache_dir)

    if not args.force and is_cache_fresh(cache_path, args.ttl):
        age = int(time.time() - os.path.getmtime(cache_path))
        print(f"[cache hit] {cache_path} (age={age}s, ttl={args.ttl}s)")
        print(f"使用 --force 跳过缓存重新拉取。")
        return 0

    assert_authenticated()
    print(f"[fetch] workspace={args.workspace}")
    folders = find_top_level_folders(args.workspace)
    if not folders:
        print(f"ERROR: 没找到 02_PRODUCT…07_SERVICE 任一目录，确认 workspaceId 是否正确，并已跑过 dingtalk-okf-kb 建库流程")
        return 1
    print(f"[folders] {len(folders)} found: {sorted(folders.keys())}")

    cards = []
    for fname in CARD_FOLDERS:
        fid = folders.get(fname)
        if not fid:
            if args.verbose:
                print(f"  [skip] {fname} not present")
            continue
        nodes = list_folder(fid, args.workspace)
        print(f"  [{fname}] {len(nodes)} cards")
        for n in nodes:
            if n.get("nodeType") != "file":
                continue
            nid = n.get("nodeId")
            if not nid:
                continue
            r = read_doc(nid)
            text = extract_doc_text(r)
            if not text:
                if args.verbose:
                    print(f"    [WARN no body] {n.get('name')}")
                continue
            meta = parse_frontmatter(text)
            okf_id = meta.get("id") or n.get("name", "").replace(" ", "-").lower()
            cards.append({
                "id": okf_id,
                "type": meta.get("type"),
                "type_dir": fname,
                "title": meta.get("title") or n.get("name"),
                "status": meta.get("status") or "unknown",
                "products": meta.get("product") or [],
                "modules": meta.get("module") or [],
                "aliases": meta.get("aliases") or [],
                "summary": meta.get("summary") or "",
                "verified_at": meta.get("verified_at"),
                "effective_from": meta.get("effective_from"),
                "effective_to": meta.get("effective_to"),
                "review_cycle_days": meta.get("review_cycle_days"),
                "supersedes": meta.get("supersedes") or [],
                "related": meta.get("related") or [],
                "sources": meta.get("sources") or [],
                "nodeId": nid,
                "docUrl": n.get("docUrl") or f"https://alidocs.dingtalk.com/i/nodes/{nid}",
            })

    payload = {
        "workspace": args.workspace,
        "fetched_at": int(time.time()),
        "ttl": args.ttl,
        "card_count": len(cards),
        "cards": cards,
    }
    save_json(cache_path, payload)
    print(f"\n[ok] {len(cards)} cards cached → {cache_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
