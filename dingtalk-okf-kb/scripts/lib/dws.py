"""dws / OKF 知识库构建脚本的公共函数。

可由 scripts/*.py 通过 `from lib.dws import ...` 引入。

无任何硬编码绝对路径。dws 二进制路径解析顺序：
1. 环境变量 DWS_BIN
2. PATH 中的 `dws`
3. ~/.local/bin/dws
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from typing import Any, Iterable


# ---------------- dws 调用 ----------------

def dws_bin() -> str:
    env = os.environ.get("DWS_BIN")
    if env and os.path.isfile(env):
        return env
    p = shutil.which("dws")
    if p:
        return p
    fallback = os.path.expanduser("~/.local/bin/dws")
    if os.path.isfile(fallback):
        return fallback
    raise RuntimeError(
        "dws CLI not found. Install via "
        "https://github.com/DingTalk-Real-AI/dingtalk-workspace-cli "
        "or set DWS_BIN env to its path."
    )


def run_dws(args: Iterable[str], timeout: int = 120) -> dict[str, Any]:
    """调用 dws，返回 JSON 解析后的 dict。

    dws 偶尔会在 JSON 前加 note: 行（例如 "正文首行与 --name 相同的一级标题已自动移除"），
    本函数会跳过这些非 JSON 行。
    """
    proc = subprocess.run(
        [dws_bin(), *args],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    out = proc.stdout
    json_start = out.find("{")
    if json_start < 0:
        return {
            "error": {
                "type": "no_json",
                "raw_stdout": out[:500],
                "stderr": proc.stderr[:500],
                "returncode": proc.returncode,
            }
        }
    try:
        return json.loads(out[json_start:])
    except json.JSONDecodeError as e:
        return {
            "error": {
                "type": "parse_error",
                "message": str(e),
                "raw_stdout_head": out[:500],
            }
        }


def assert_authenticated() -> dict[str, Any]:
    """确保 dws 已登录。失败时抛错。"""
    r = run_dws(["auth", "status"])
    if not r.get("authenticated"):
        raise RuntimeError(
            f"dws not authenticated. Run `dws auth login` first.\n"
            f"Detail: {json.dumps(r, ensure_ascii=False)[:300]}"
        )
    return r


# ---------------- 内容分块 ----------------

DOC_CREATE_MAX_CHARS = 10000  # 钉钉 doc create 的硬上限
DEFAULT_CHUNK = 9000          # 留 1000 字符安全边际


def chunk_markdown(text: str, max_size: int = DEFAULT_CHUNK) -> list[str]:
    """按段落（双换行）边界切块。每块不超过 max_size 字符。"""
    parts = re.split(r"(\n\n+)", text)  # 保留分隔符
    chunks: list[str] = []
    current = ""
    for part in parts:
        if len(current) + len(part) <= max_size:
            current += part
            continue
        if current:
            chunks.append(current)
        if len(part) > max_size:
            # 单段就超长，硬切
            for i in range(0, len(part), max_size):
                chunks.append(part[i:i + max_size])
            current = ""
        else:
            current = part
    if current:
        chunks.append(current)
    return chunks


def create_doc_with_chunks(
    workspace: str,
    folder: str,
    name: str,
    content: str,
    *,
    fix_jsonml: bool = True,
    sleep_between: float = 0.3,
) -> dict[str, Any]:
    """创建文档，自动处理超长内容分块。

    返回首块 create 的 result（含 nodeId）。后续 append 失败时在 result["chunks_failed"] 记录。
    """
    chunks = chunk_markdown(content)
    if not chunks:
        return {"error": {"type": "empty_content"}}

    # Step 1: create
    first_path = _tmp_md(name + "_0", chunks[0])
    args = [
        "doc", "create",
        "--workspace", workspace,
        "--folder", folder,
        "--name", name,
        "--content-file", first_path,
        "--content-format", "markdown",
        "-y",
    ]
    if fix_jsonml:
        args.append("--fix-jsonml")
    result = run_dws(args)
    os.unlink(first_path)
    node_id = result.get("nodeId")
    if not node_id:
        return result

    # Step 2: append remaining chunks
    chunks_failed: list[int] = []
    for i, chunk in enumerate(chunks[1:], start=1):
        time.sleep(sleep_between)
        chunk_path = _tmp_md(f"{name}_{i}", chunk)
        args = [
            "doc", "update",
            "--node", node_id,
            "--content-file", chunk_path,
            "--content-format", "markdown",
            "--mode", "append",
            "-y",
        ]
        if fix_jsonml:
            args.append("--fix-jsonml")
        r = run_dws(args)
        os.unlink(chunk_path)
        # update 返回结构可能没有 success 字段，看是否有 error
        if r.get("error") or (r.get("success") is False):
            chunks_failed.append(i)

    if chunks_failed:
        result["chunks_failed"] = chunks_failed
    result["chunks_total"] = len(chunks)
    return result


def _tmp_md(suffix: str, content: str) -> str:
    """写一个临时 md 文件返回路径。"""
    safe = re.sub(r"[^a-zA-Z0-9_-]", "_", suffix)[:40]
    path = f"/tmp/dws_kb_{abs(hash(suffix))}_{safe}.md"
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


# ---------------- frontmatter ----------------

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)


def parse_frontmatter(text: str) -> dict[str, Any]:
    """简易 YAML frontmatter 解析。

    只提取常用字段：id / title / type / status / product (list) / aliases (list) /
    summary (folded scalar) / module (list) / verified_at。

    需要更完整解析时使用 PyYAML。
    """
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}
    body = m.group(1)
    out: dict[str, Any] = {}

    # 标量字段
    for key in ("id", "title", "type", "status", "verified_at"):
        mm = re.search(rf"^{key}:\s*(.+)$", body, re.MULTILINE)
        if mm:
            out[key] = mm.group(1).strip().strip('"').strip("'")

    # 数组字段
    for key in ("product", "aliases", "module"):
        mm = re.search(rf"^{key}:\s*\n((?:\s+-\s+.+\n?)+)", body, re.MULTILINE)
        if mm:
            out[key] = [
                ln.strip().lstrip("- ").strip().strip('"').strip("'")
                for ln in mm.group(1).strip().split("\n")
                if ln.strip()
            ]
        else:
            out[key] = []

    # summary 折叠多行
    sm = re.search(r"^summary:\s*>\s*\n((?:\s+.+\n?)+)", body, re.MULTILINE)
    if sm:
        out["summary"] = " ".join(
            ln.strip() for ln in sm.group(1).split("\n") if ln.strip()
        )

    return out


# ---------------- index 文件读写 ----------------

def load_json(path: str, default: Any = None) -> Any:
    if not os.path.exists(path):
        return default if default is not None else {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path: str, data: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ---------------- 工作目录约定 ----------------

def work_paths(work_dir: str) -> dict[str, str]:
    """返回工作目录下各约定文件的绝对路径。"""
    work_dir = os.path.abspath(work_dir)
    return {
        "root": work_dir,
        "folder_idx": os.path.join(work_dir, "folder_idx.json"),
        "upload_list": os.path.join(work_dir, "upload_list.tsv"),
        "source_index": os.path.join(work_dir, "source_node_index.json"),
        "okf_index": os.path.join(work_dir, "okf_node_index.json"),
        "converted_dir": os.path.join(work_dir, "converted"),
        "okf_cards_dir": os.path.join(work_dir, "okf_cards"),
    }


CARD_DIR_TYPES = {
    "02_PRODUCT": "product",
    "03_CAPABILITY": "capability",
    "04_RULE": "product_rule",
    "05_RESOURCE": "resource",
    "06_DECISION": "decision",
    "07_SERVICE": "service",
}


def ensure_card_dirs(work_dir: str) -> None:
    base = work_paths(work_dir)["okf_cards_dir"]
    for d in CARD_DIR_TYPES:
        os.makedirs(os.path.join(base, d), exist_ok=True)
