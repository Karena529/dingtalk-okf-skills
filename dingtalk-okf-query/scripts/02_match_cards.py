#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""02_match_cards.py — 在 manifest 缓存里按 keywords 命中候选 OKF 卡片。

打分规则：
  关键词 kw 在卡片的 id / title / aliases / summary / modules / products 任一字段
  作为子串出现 → +1 分（同卡片多字段命中累计，不同关键词命中同字段也累计）
  status == active → 加 0.5 分（默认权重；可关）

输出 Top-K 候选 JSON，含 score / matched_via。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib.dws import (
    is_cache_fresh,
    load_json,
    manifest_cache_path,
)


SEARCHABLE_FIELDS = ("id", "title", "summary")
SEARCHABLE_LIST_FIELDS = ("aliases", "modules", "products")


def score_card(card: dict, keywords: list[str], active_bonus: float = 0.5) -> tuple[float, list[str]]:
    """计算单张卡片得分 + 命中字段列表。"""
    matched: list[str] = []
    score = 0.0
    seen_kw_field = set()

    for kw in keywords:
        kw_low = kw.lower()
        if not kw_low:
            continue

        # 标量字段
        for f in SEARCHABLE_FIELDS:
            v = (card.get(f) or "").lower()
            if not v:
                continue
            if kw_low in v:
                key = (kw_low, f)
                if key not in seen_kw_field:
                    seen_kw_field.add(key)
                    score += 1
                    snippet = card.get(f) or ""
                    short = snippet[:30] + ("..." if len(snippet) > 30 else "")
                    matched.append(f"{f}:{short}")

        # 数组字段
        for f in SEARCHABLE_LIST_FIELDS:
            arr = card.get(f) or []
            for item in arr:
                if isinstance(item, str) and kw_low in item.lower():
                    key = (kw_low, f)
                    if key not in seen_kw_field:
                        seen_kw_field.add(key)
                        score += 1
                        matched.append(f"{f}:{item}")
                    break

    # active 加分
    if card.get("status") == "active":
        score += active_bonus

    return score, matched


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workspace", required=True, help="目标知识库 workspaceId（用于定位缓存）")
    ap.add_argument("--keywords", required=True, help="逗号分隔的搜索关键词，例 'DMClaw,Tab,详情'")
    ap.add_argument("--top-k", type=int, default=5)
    ap.add_argument("--type", default=None, help="按 type 过滤：product,capability,product_rule,decision,service,resource（多个用逗号分隔）")
    ap.add_argument("--status", default="active", help="按 status 过滤，默认 active；'all' 表示不过滤")
    ap.add_argument("--include-superseded", action="store_true", help="status=all 的快捷别名")
    ap.add_argument("--cache-dir", default=None)
    ap.add_argument("--ttl", type=int, default=3600)
    ap.add_argument("--no-active-bonus", action="store_true", help="禁用 active 状态加分")
    ap.add_argument("--format", choices=["json", "table"], default="json")
    args = ap.parse_args()

    cache_path = manifest_cache_path(args.workspace, args.cache_dir)
    if not os.path.exists(cache_path):
        print(json.dumps({"error": "缓存不存在，请先跑 01_load_manifest.py", "expected_path": cache_path}, ensure_ascii=False))
        return 1
    if not is_cache_fresh(cache_path, args.ttl):
        print(f"[warn] 缓存已过期（>{args.ttl}s），建议跑 01_load_manifest.py --force", file=sys.stderr)

    payload = load_json(cache_path, {})
    cards = payload.get("cards") or []
    if not cards:
        print(json.dumps({"error": "缓存为空", "path": cache_path}, ensure_ascii=False))
        return 1

    keywords = [k.strip() for k in args.keywords.split(",") if k.strip()]
    if not keywords:
        print(json.dumps({"error": "未提供有效 keywords"}, ensure_ascii=False))
        return 1

    # 过滤
    type_filter = None
    if args.type:
        type_filter = {t.strip() for t in args.type.split(",") if t.strip()}

    status_filter: set[str] | None
    if args.include_superseded or args.status == "all":
        status_filter = None
    else:
        status_filter = {s.strip() for s in args.status.split(",") if s.strip()}

    candidates = []
    for c in cards:
        if type_filter and c.get("type") not in type_filter:
            continue
        if status_filter and c.get("status") not in status_filter:
            continue
        active_bonus = 0.0 if args.no_active_bonus else 0.5
        score, matched = score_card(c, keywords, active_bonus=active_bonus)
        if score <= 0:
            continue
        candidates.append({
            "id": c["id"],
            "title": c.get("title"),
            "type": c.get("type"),
            "status": c.get("status"),
            "products": c.get("products") or [],
            "score": round(score, 2),
            "matched_via": matched,
            "nodeId": c.get("nodeId"),
            "docUrl": c.get("docUrl"),
            "verified_at": c.get("verified_at"),
            "summary": c.get("summary"),
        })

    candidates.sort(key=lambda x: -x["score"])
    top = candidates[:args.top_k]

    result = {
        "workspace": args.workspace,
        "keywords": keywords,
        "filter": {
            "type": list(type_filter) if type_filter else None,
            "status": list(status_filter) if status_filter else None,
        },
        "candidates_count": len(candidates),
        "returned": len(top),
        "candidates": top,
    }

    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        # table
        print(f"\n{'#':3} {'score':6} {'type':12} {'status':12} {'id'}")
        print("-" * 100)
        for i, c in enumerate(top, 1):
            print(f"{i:3} {c['score']:6.2f} {(c['type'] or '-'):12} {c['status']:12} {c['id']}")
            if c.get("matched_via"):
                print(f"     ↳ {', '.join(c['matched_via'][:3])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
