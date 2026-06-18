#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""06_build_manifest.py — 生成并上传 MANIFEST 与 INDEX 文档。

产出（上传到 00_MANIFEST 和 01_INDEX 目录）：
  - manifest-all                所有 OKF 卡片总清单
  - manifest-products
  - manifest-capabilities
  - manifest-rules
  - manifest-decisions
  - manifest-services
  - manifest-resources          （仅当存在 resource 卡片时）
  - 产品总索引                  按 product 字段聚合
  - 原始证据索引                所有 08_SOURCE 原文清单

超长文档自动分块。

可重入：通过 manifest_node_index.json 跟踪已上传，重跑会先删除旧版本再创建新版本（保证内容更新）。
"""
from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib.dws import (
    CARD_DIR_TYPES,
    DOC_CREATE_MAX_CHARS,
    assert_authenticated,
    create_doc_with_chunks,
    load_json,
    parse_frontmatter,
    run_dws,
    save_json,
    work_paths,
)


def collect_cards(work_dir: str) -> list[dict]:
    paths = work_paths(work_dir)
    okf_idx = load_json(paths["okf_index"], {})
    cards: list[dict] = []
    cards_root = paths["okf_cards_dir"]
    for type_dir, type_name in CARD_DIR_TYPES.items():
        local_dir = os.path.join(cards_root, type_dir)
        if not os.path.isdir(local_dir):
            continue
        for fname in sorted(os.listdir(local_dir)):
            if not fname.endswith(".md"):
                continue
            with open(os.path.join(local_dir, fname), encoding="utf-8") as f:
                meta = parse_frontmatter(f.read())
            okf_id = meta.get("id") or fname[:-3]
            ni = okf_idx.get(okf_id)
            if not ni:
                continue
            cards.append({
                "id": okf_id,
                "type": type_name,
                "type_dir": type_dir,
                "title": meta.get("title") or okf_id,
                "status": meta.get("status") or "unknown",
                "products": meta.get("product") or [],
                "aliases": meta.get("aliases") or [],
                "nodeId": ni["nodeId"],
                "docUrl": ni["docUrl"],
            })
    return cards


def build_main_manifest(cards: list[dict]) -> str:
    today = date.today().isoformat()
    by_type: dict[str, list[dict]] = defaultdict(list)
    for c in cards:
        by_type[c["type"]].append(c)
    lines = [
        "---",
        "type: manifest",
        "version: 1",
        f"updated_at: {today}",
        f"total: {len(cards)}",
        "---",
        "",
        f"# 产品知识库 OKF 卡片总清单（{today}）",
        "",
        f"共 **{len(cards)}** 张 OKF 卡片，按类型分布：",
        "",
    ]
    for t in ("product", "capability", "product_rule", "resource", "decision", "service"):
        if by_type[t]:
            lines.append(f"- {t}: {len(by_type[t])}")
    lines.append("")
    lines.append("## documents")
    lines.append("")
    for t in ("product", "capability", "product_rule", "resource", "decision", "service"):
        if not by_type[t]:
            continue
        lines.append(f"### {t}")
        lines.append("")
        for c in sorted(by_type[t], key=lambda x: x["id"]):
            lines.append(f"- `{c['id']}` — [{c['title']}]({c['docUrl']}) — status: `{c['status']}` — nodeId: `{c['nodeId']}`")
        lines.append("")
    return "\n".join(lines)


def build_per_type_manifest(cards: list[dict], ftype: str) -> str:
    today = date.today().isoformat()
    rows = [c for c in cards if c["type"] == ftype]
    lines = [
        "---",
        f"type: manifest-{ftype}",
        "version: 1",
        f"updated_at: {today}",
        f"total: {len(rows)}",
        "---",
        "",
        f"# {ftype} 卡片清单",
        "",
    ]
    for c in sorted(rows, key=lambda x: x["id"]):
        prods = ", ".join(c["products"]) if c["products"] else "—"
        aliases = ", ".join(c["aliases"][:5]) if c["aliases"] else "—"
        lines.append(f"- `{c['id']}` — [{c['title']}]({c['docUrl']}) — status: `{c['status']}` — products: {prods}")
        lines.append(f"  - aliases: {aliases}")
        lines.append(f"  - nodeId: `{c['nodeId']}`")
    return "\n".join(lines)


def build_product_index(cards: list[dict]) -> str:
    today = date.today().isoformat()
    by_prod: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for c in cards:
        for p in (c["products"] or ["未分类"]):
            by_prod[p][c["type"]].append(c)
    lines = [
        f"# 产品知识总索引（{today}）",
        "",
        f"共收录 {len(by_prod)} 个产品维度。",
        "",
    ]
    for prod in sorted(by_prod):
        lines.append(f"## {prod}")
        lines.append("")
        for t in ("product", "capability", "product_rule", "resource", "decision", "service"):
            if not by_prod[prod][t]:
                continue
            lines.append(f"### {t}")
            for c in sorted(by_prod[prod][t], key=lambda x: x["id"]):
                tag = "" if c["status"] == "active" else f" *({c['status']})*"
                lines.append(f"- [{c['title']}]({c['docUrl']}) — `{c['id']}`{tag}")
            lines.append("")
    return "\n".join(lines)


def build_source_index(work_dir: str) -> str:
    today = date.today().isoformat()
    src_idx = load_json(work_paths(work_dir)["source_index"], {})
    by_subdir: dict[str, list[tuple[str, dict]]] = defaultdict(list)
    for name, info in src_idx.items():
        by_subdir[info["subdir"]].append((name, info))
    lines = [
        f"# 原始证据索引（{today}）",
        "",
        f"08_SOURCE 目录下共 **{len(src_idx)}** 篇原始文档。",
        "",
    ]
    for sd in sorted(by_subdir):
        rows = sorted(by_subdir[sd], key=lambda x: x[0])
        lines.append(f"## {sd}（{len(rows)} 篇）")
        lines.append("")
        for name, info in rows:
            chunks = f" *(分 {info['chunks']} 块)*" if info.get("chunks", 1) > 1 else ""
            lines.append(f"- [{name}]({info['docUrl']}) — nodeId: `{info['nodeId']}`{chunks}")
        lines.append("")
    return "\n".join(lines)


def upload_manifest(workspace: str, folder: str, name: str, content: str, dry_run: bool) -> str | None:
    if dry_run:
        print(f"[dry] would upload {name} ({len(content)} chars)")
        return None
    if len(content) <= DOC_CREATE_MAX_CHARS - 100:
        from lib.dws import _tmp_md
        path = _tmp_md(name, content)
        r = run_dws([
            "doc", "create",
            "--workspace", workspace,
            "--folder", folder,
            "--name", name,
            "--content-file", path,
            "--content-format", "markdown",
            "--fix-jsonml",
            "-y",
        ])
        os.unlink(path)
    else:
        r = create_doc_with_chunks(workspace, folder, name, content)
    return r.get("nodeId")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--workspace", required=True)
    ap.add_argument("--work-dir", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    assert_authenticated()
    paths = work_paths(args.work_dir)
    folder_idx = load_json(paths["folder_idx"], {})

    manifest_folder = folder_idx.get("00_MANIFEST")
    index_folder = folder_idx.get("01_INDEX")
    if not manifest_folder or not index_folder:
        print("ERROR: folder_idx 中缺少 00_MANIFEST / 01_INDEX")
        return 1

    cards = collect_cards(args.work_dir)
    print(f"Collected {len(cards)} cards")

    # MANIFEST
    main_doc = build_main_manifest(cards)
    upload_manifest(args.workspace, manifest_folder, "manifest-all", main_doc, args.dry_run)

    types_have_cards = {c["type"] for c in cards}
    type_to_name = {
        "product": "manifest-products",
        "capability": "manifest-capabilities",
        "product_rule": "manifest-rules",
        "resource": "manifest-resources",
        "decision": "manifest-decisions",
        "service": "manifest-services",
    }
    for t, name in type_to_name.items():
        if t not in types_have_cards:
            continue
        body = build_per_type_manifest(cards, t)
        upload_manifest(args.workspace, manifest_folder, name, body, args.dry_run)

    # INDEX
    upload_manifest(args.workspace, index_folder, "产品总索引", build_product_index(cards), args.dry_run)
    upload_manifest(args.workspace, index_folder, "原始证据索引", build_source_index(args.work_dir), args.dry_run)

    # 本地保存 manifest-all 副本以便审阅
    if not args.dry_run:
        save_path = os.path.join(paths["root"], "manifest-all.md")
        with open(save_path, "w", encoding="utf-8") as f:
            f.write(main_doc)
        print(f"\nLocal copy saved: {save_path}")

    print(f"\n=== {len(cards)} cards summarized into manifest+index ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
