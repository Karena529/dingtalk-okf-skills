#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""03_read_card.py — 读单张 OKF 卡片，返回结构化结果（frontmatter + body + sources）。

可以传 nodeId 或 OKF id（后者会从缓存查 nodeId）。

输出含：
  - frontmatter: 全部解析出来的字段
  - body: 正文（去掉 frontmatter）
  - status_check: 当前状态判断（active / superseded / draft / 已过期等）
  - sources: 引用原文清单
  - hints: 给 Agent 的提示（例如"已超过复核周期"、"effective_from 在未来"等）
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib.dws import (
    extract_doc_text,
    load_json,
    manifest_cache_path,
    parse_frontmatter,
    read_doc,
)


def status_hints(fm: dict, today_str: str | None = None) -> list[str]:
    """根据 frontmatter 字段产出给 Agent 的提示。"""
    hints: list[str] = []
    today = date.fromisoformat(today_str) if today_str else date.today()

    status = fm.get("status")
    if status == "superseded":
        hints.append("⚠️ 该卡片状态为 superseded，已被新版本取代。**不要**作为当前结论使用。")
        if fm.get("supersedes"):
            hints.append(f"  → 应改为查询 supersedes: {fm['supersedes']}")
    elif status == "deprecated":
        hints.append("⚠️ 该卡片状态为 deprecated，能力已废弃。仅作为历史背景，不要当前规则。")
    elif status == "draft":
        hints.append("📝 该卡片状态为 draft，尚未正式确认。回答中必须明确标注'草稿状态'。")
    elif status == "unknown":
        hints.append("❓ 该卡片状态为 unknown，事实可能未确认。建议向 Owner 复核。")

    # 复核过期判断
    verified_at = fm.get("verified_at")
    cycle = fm.get("review_cycle_days")
    try:
        if verified_at and cycle:
            v_date = date.fromisoformat(str(verified_at))
            cycle_int = int(cycle)
            from datetime import timedelta
            if v_date + timedelta(days=cycle_int) < today:
                days_overdue = (today - (v_date + timedelta(days=cycle_int))).days
                hints.append(f"⏰ 该卡片已超过复核周期 {days_overdue} 天（verified_at={verified_at}, cycle={cycle}d）。建议向 Owner 复核。")
    except Exception:
        pass

    # effective_from / to 检查
    eff_from = fm.get("effective_from")
    eff_to = fm.get("effective_to")
    try:
        if eff_from:
            f_date = date.fromisoformat(str(eff_from))
            if f_date > today:
                hints.append(f"📅 effective_from={eff_from} 在未来，该能力尚未上线。")
    except Exception:
        pass
    try:
        if eff_to:
            t_date = date.fromisoformat(str(eff_to))
            if t_date < today:
                hints.append(f"📅 effective_to={eff_to} 已过，该能力已下线（等同 deprecated）。")
    except Exception:
        pass

    return hints


def strip_frontmatter(text: str) -> str:
    return re.sub(r"^---\n.*?\n---\n*", "", text, count=1, flags=re.DOTALL)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--node", help="wiki nodeId")
    g.add_argument("--okf-id", help="OKF id（从缓存查 nodeId）")
    ap.add_argument("--workspace", help="若用 --okf-id 必填（用于定位缓存）")
    ap.add_argument("--cache-dir", default=None)
    ap.add_argument("--today", default=None, help="覆盖今天日期（测试用），格式 YYYY-MM-DD")
    ap.add_argument("--debug", action="store_true", help="同时输出原始 dws read 响应")
    args = ap.parse_args()

    node_id = args.node
    if not node_id:
        if not args.workspace:
            print(json.dumps({"error": "--okf-id 时必须传 --workspace"}), file=sys.stderr)
            return 1
        cache = load_json(manifest_cache_path(args.workspace, args.cache_dir), {})
        for c in (cache.get("cards") or []):
            if c.get("id") == args.okf_id:
                node_id = c.get("nodeId")
                break
        if not node_id:
            print(json.dumps({"error": f"OKF id {args.okf_id} 不在缓存中。先跑 01_load_manifest.py。"}, ensure_ascii=False))
            return 1

    raw = read_doc(node_id)
    text = extract_doc_text(raw)
    if not text:
        out = {"error": "卡片正文为空", "nodeId": node_id}
        if args.debug:
            out["raw"] = raw
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 1

    fm = parse_frontmatter(text)
    body = strip_frontmatter(text).strip()
    hints = status_hints(fm, today_str=args.today)

    result = {
        "nodeId": node_id,
        "frontmatter": fm,
        "body": body,
        "sources": fm.get("sources") or [],
        "hints": hints,
        "is_safe_as_current_truth": fm.get("status") == "active" and not any(
            h.startswith("📅 effective") for h in hints
        ),
    }
    if args.debug:
        result["raw"] = raw

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
