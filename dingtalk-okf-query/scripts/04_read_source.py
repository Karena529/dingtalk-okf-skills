#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""04_read_source.py — 读 sources 引用的原文 PRD/技术文档。

从 03_read_card.py 输出的 sources 列表里挑 1-3 篇读：
  - 优先按 authority 排序（high > medium > low）
  - 多块拼成完整 markdown
  - 默认截断到 12000 字符（避免回答 prompt 过长）

支持：
  --node <doc_id>     读单个原文
  --max-chars N       截断字符数（默认 12000）
  --head-only         只读首 N 字符（不分块拼接）
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib.dws import (
    extract_doc_text,
    read_doc,
)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--node", required=True, help="原文 nodeId（来自 OKF 卡片 sources[].doc_id）")
    ap.add_argument("--max-chars", type=int, default=12000, help="截断字符数（默认 12000）")
    ap.add_argument("--head-only", action="store_true", help="只取头部，不警告 truncate")
    ap.add_argument("--format", choices=["json", "raw"], default="json")
    ap.add_argument("--debug", action="store_true")
    args = ap.parse_args()

    raw = read_doc(args.node)
    text = extract_doc_text(raw)
    if not text:
        out = {"error": "原文正文为空", "nodeId": args.node}
        if args.debug:
            out["raw"] = raw
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 1

    truncated = False
    full_chars = len(text)
    if full_chars > args.max_chars:
        text = text[:args.max_chars]
        truncated = True

    if args.format == "raw":
        sys.stdout.write(text)
        if truncated and not args.head_only:
            sys.stderr.write(f"\n[truncated: {full_chars - args.max_chars} chars omitted]\n")
        return 0

    out = {
        "nodeId": args.node,
        "chars": len(text),
        "full_chars": full_chars,
        "truncated": truncated,
        "content": text,
    }
    if args.debug:
        out["raw_keys"] = list(raw.keys()) if isinstance(raw, dict) else None
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
