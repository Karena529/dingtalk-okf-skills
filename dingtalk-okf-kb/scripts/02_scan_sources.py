#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""02_scan_sources.py — 扫描源目录、转换 docx、生成 upload_list.tsv。

源目录可指定多个，每个用 `--source <PATH>:<SUBDIR_NAME>` 格式：
  --source /home/me/PRD归档:PRD归档
  --source /home/me/Agent协作平台/PRD:Agent协作平台

SUBDIR_NAME 必须与 01_create_skeleton.py 的 --source-subdirs 中一致。

输出：
  <WORK_DIR>/upload_list.tsv     # subdir / src_path / doc_name
  <WORK_DIR>/converted/<SUBDIR>/*.md   # docx 转换后的 markdown
"""
from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib.dws import work_paths

INCLUDE_EXT_MAP = {
    "prd_only": {".md", ".docx"},
    "prd_plus": {".md", ".docx", ".txt"},
    "all_markdown": {".md", ".docx", ".txt"},
}


def list_files(src_dir: str, exts: set[str]) -> list[str]:
    out: list[str] = []
    for root, _, files in os.walk(src_dir):
        # 跳过隐藏目录
        if "/." in root + "/":
            continue
        for f in files:
            if f.startswith("."):
                continue
            ext = os.path.splitext(f)[1].lower()
            if ext in exts:
                out.append(os.path.join(root, f))
    return sorted(out)


def filter_prd_only(files: list[str]) -> list[str]:
    """筛选标题中含 PRD / Feature_List 的文件。"""
    out = []
    for f in files:
        base = os.path.basename(f).lower()
        if "prd" in base or "feature_list" in base:
            out.append(f)
    return out


def filter_prd_plus(files: list[str]) -> list[str]:
    """筛选 PRD + 配套（实施计划/方案/规划/Feature/管理操作 等）。"""
    keywords = [
        "prd", "feature_list", "实施计划", "实施方案", "mvp",
        "v2规划", "规划", "管理页", "操作逻辑", "配置流程",
        "定位", "功能结构化梳理", "核心功能", "交互设计",
        "implementation", "plan",
    ]
    out = []
    for f in files:
        base = os.path.basename(f).lower()
        if any(kw in base for kw in keywords):
            out.append(f)
    return out


def convert_docx(src: str, dst_md: str) -> bool:
    if not shutil.which("pandoc"):
        print("ERROR: pandoc not found; install via `brew install pandoc`")
        return False
    media_dir = dst_md + "_media"
    proc = subprocess.run(
        ["pandoc", "-f", "docx", "-t", "gfm", src, "-o", dst_md, f"--extract-media={media_dir}"],
        capture_output=True, text=True,
    )
    return os.path.exists(dst_md)


def file_sha(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def doc_name_for(path: str) -> str:
    return os.path.splitext(os.path.basename(path))[0]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--work-dir", required=True)
    ap.add_argument(
        "--source", action="append", required=True, dest="sources",
        help="格式 <PATH>:<SUBDIR_NAME>，可重复指定。SUBDIR_NAME 必须与 01 step 一致",
    )
    ap.add_argument(
        "--filter", default="prd_plus", choices=list(INCLUDE_EXT_MAP),
        help="文件筛选策略 (default: prd_plus)",
    )
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    paths = work_paths(args.work_dir)
    os.makedirs(paths["converted_dir"], exist_ok=True)

    rows: list[tuple[str, str, str]] = []
    seen_sha: dict[str, str] = {}
    exts = INCLUDE_EXT_MAP[args.filter]

    for src_spec in args.sources:
        if ":" not in src_spec:
            print(f"ERROR: --source 格式必须是 <PATH>:<SUBDIR>，收到 {src_spec}")
            return 1
        path, subdir = src_spec.rsplit(":", 1)
        path = os.path.abspath(path)
        if not os.path.isdir(path):
            print(f"WARN: source not a directory: {path}")
            continue

        files = list_files(path, exts)
        if args.filter == "prd_only":
            files = filter_prd_only(files)
        elif args.filter == "prd_plus":
            files = filter_prd_plus(files)
        # else all_markdown: keep all

        print(f"\n# {path} -> SUBDIR={subdir}: {len(files)} candidates")

        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext == ".docx":
                # 转换到 converted/<subdir>/<basename>.md
                dst_dir = os.path.join(paths["converted_dir"], subdir)
                os.makedirs(dst_dir, exist_ok=True)
                dst = os.path.join(dst_dir, doc_name_for(f) + ".md")
                if not os.path.exists(dst):
                    if args.dry_run:
                        print(f"  [dry] convert {f} -> {dst}")
                    else:
                        ok = convert_docx(f, dst)
                        if not ok:
                            print(f"  [FAIL convert] {f}")
                            continue
                src_for_upload = dst
            else:
                src_for_upload = f

            # 去重（按 sha 内容）
            try:
                sha = file_sha(src_for_upload) if os.path.exists(src_for_upload) else None
            except Exception:
                sha = None
            if sha and sha in seen_sha:
                print(f"  [dup] {f} 与 {seen_sha[sha]} 内容相同，跳过")
                continue
            if sha:
                seen_sha[sha] = f

            rows.append((subdir, src_for_upload, doc_name_for(f)))
            print(f"  [+] {subdir} | {os.path.basename(src_for_upload)} | {doc_name_for(f)}")

    if args.dry_run:
        print(f"\n[dry] would write {len(rows)} rows to {paths['upload_list']}")
        return 0

    with open(paths["upload_list"], "w", encoding="utf-8") as f:
        f.write("subdir\tsource_path\tdoc_name\n")
        for r in rows:
            f.write("\t".join(r) + "\n")

    print(f"\n=== {len(rows)} rows written to {paths['upload_list']} ===")
    print("请人工 review 这份清单，必要时增删，再跑 03_upload_sources.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
