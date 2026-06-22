"""dingtalk-okf-query 公共函数（dws 调用、frontmatter 解析、缓存管理）。

这是一个**精简的只读版**，与 dingtalk-okf-kb/scripts/lib/dws.py 是兄弟关系；
共有的部分（run_dws / dws_bin / parse_frontmatter）在两边都有一份，互不依赖。

无任何硬编码绝对路径。dws 二进制路径解析顺序：
1. 环境变量 DWS_BIN
2. PATH 中的 dws
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


def run_dws(args: Iterable[str], timeout: int = 60) -> dict[str, Any]:
    """调用 dws，返回 JSON 解析后的 dict。dws 偶尔会有 note: 前缀行，本函数会跳过。"""
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
    r = run_dws(["auth", "status"])
    if not r.get("authenticated"):
        raise RuntimeError(
            f"dws not authenticated. Run `dws auth login` first.\n"
            f"Detail: {json.dumps(r, ensure_ascii=False)[:300]}"
        )
    return r


# ---------------- frontmatter 解析 ----------------

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)

# 钉钉 doc read 返回的 markdown 会把若干字符转义（_, >, *, +, -）。
# frontmatter 用 YAML 子集，这些字符在 YAML 里没特殊含义，反转义即可。
_DING_ESCAPE_RE = re.compile(r"\\([_>*+\-])")


def _unescape_ding_md(text: str) -> str:
    """反转义钉钉 doc read 在 markdown 输出中加的反斜杠。"""
    return _DING_ESCAPE_RE.sub(r"\1", text)


def parse_frontmatter(text: str) -> dict[str, Any]:
    """提取 YAML frontmatter 中的常用字段。

    钉钉 doc read 返回的 markdown 会把 `_` `>` 等转义成 `\_` `\>`，
    本函数在解析前先反转义 frontmatter 区段。
    """
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}
    body = _unescape_ding_md(m.group(1))
    out: dict[str, Any] = {}

    # 标量字段
    for key in ("id", "title", "type", "status", "verified_at", "effective_from", "effective_to", "review_cycle_days"):
        mm = re.search(rf"^{key}:\s*(.+)$", body, re.MULTILINE)
        if mm:
            v = mm.group(1).strip().strip('"').strip("'")
            if v.lower() == "null":
                out[key] = None
            else:
                out[key] = v

    # 数组字段
    for key in ("product", "aliases", "module", "related", "supersedes"):
        mm = re.search(rf"^{key}:\s*\n((?:\s+-\s+.+\n?)+)", body, re.MULTILINE)
        if mm:
            out[key] = [
                ln.strip().lstrip("- ").strip().strip('"').strip("'")
                for ln in mm.group(1).strip().split("\n")
                if ln.strip()
            ]
        else:
            out[key] = []

    # summary（折叠多行）
    sm = re.search(r"^summary:\s*>\s*\n((?:\s+.+\n?)+)", body, re.MULTILINE)
    if sm:
        out["summary"] = " ".join(
            ln.strip() for ln in sm.group(1).split("\n") if ln.strip()
        )

    # sources 数组（每项是 dict）
    out["sources"] = parse_sources(body)

    return out


def parse_sources(frontmatter_body: str) -> list[dict[str, Any]]:
    """从 frontmatter 文本里抽出 sources 列表。

    sources 在标准 YAML 里是 list-of-dict，每个 dict 字段缩进 2 空格。但钉钉 doc read
    返回的 markdown 会把缩进吃掉，变成"平铺"形式：

      sources:
      - title: 第一份原文
      doc_id: xxx
      url: https://...
      authority: high
      - title: 第二份原文
      doc_id: yyy
      ...

    所以这里做"宽松解析"：以 `- title:`（或 `- (任意首字段):`）作为 source 分隔点，
    后续 `key: value` 行归到当前 source，直到下一个 `- ...:` 出现或 frontmatter 段
    结束（遇到顶级 key 如 `related:` / `supersedes:`）。
    """
    # 找 sources 段的起始与结束
    start_m = re.search(r"^sources:\s*$", frontmatter_body, re.MULTILINE)
    if not start_m:
        return []
    rest = frontmatter_body[start_m.end():]

    # 段尾：下一个**已知的** frontmatter 顶级 key（不能用 `^\w+:` 通配，因为
    # source 子字段如 doc_id / source_type 也会匹配，会被误判为段尾）。
    SOURCES_TERMINATORS = ("related", "supersedes", "owner", "tags", "external_refs")
    end_pos = len(rest)
    pattern = r"^(?:" + "|".join(SOURCES_TERMINATORS) + r"):\s*$"
    for m in re.finditer(pattern, rest, re.MULTILINE):
        end_pos = m.start()
        break
    section = rest[:end_pos]

    sources: list[dict[str, Any]] = []
    cur: dict[str, Any] | None = None
    for ln in section.split("\n"):
        if not ln.strip():
            continue
        # 新 source（以 `- key: value` 开头，可能有也可能没有缩进）
        m = re.match(r"^\s*-\s+(\w+):\s*(.*)$", ln)
        if m:
            if cur is not None:
                sources.append(cur)
            cur = {m.group(1): m.group(2).strip().strip('"').strip("'")}
            continue
        # 同 source 的下一字段
        m = re.match(r"^\s*(\w+):\s*(.*)$", ln)
        if m and cur is not None:
            cur[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    if cur is not None:
        sources.append(cur)
    return sources


# ---------------- index 文件读写 ----------------

def load_json(path: str, default: Any = None) -> Any:
    if not os.path.exists(path):
        return default if default is not None else {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path: str, data: Any) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ---------------- 缓存路径 ----------------

def cache_dir(workspace_id: str, base: str | None = None) -> str:
    """返回 ~/.cache/dingtalk-okf-query/<ws>/ （或自定义 base）。"""
    base = base or os.path.expanduser("~/.cache/dingtalk-okf-query")
    return os.path.join(os.path.expanduser(base), workspace_id)


def manifest_cache_path(workspace_id: str, base: str | None = None) -> str:
    return os.path.join(cache_dir(workspace_id, base), "manifest.json")


def is_cache_fresh(path: str, ttl_seconds: int) -> bool:
    if not os.path.exists(path):
        return False
    age = time.time() - os.path.getmtime(path)
    return age < ttl_seconds


# ---------------- 文档读取 ----------------

def read_doc(node_id: str) -> dict[str, Any]:
    """读取一篇钉钉文档，返回 dws raw 响应。"""
    return run_dws(["doc", "read", "--node", node_id])


def extract_doc_text(read_response: dict[str, Any]) -> str:
    """从 dws doc read 响应里抽出纯文本/markdown 内容。

    dws 不同版本字段不一样：尝试 markdown / content / data.content / docContent 几个 key。
    """
    for key in ("markdown", "content", "docContent"):
        v = read_response.get(key)
        if isinstance(v, str) and v.strip():
            return v
    data = read_response.get("data")
    if isinstance(data, dict):
        for key in ("markdown", "content", "text"):
            v = data.get(key)
            if isinstance(v, str) and v.strip():
                return v
    if isinstance(data, str):
        return data
    return ""


# ---------------- 列文档 ----------------

def list_folder(folder_node_id: str, workspace_id: str | None = None, page_size: int = 50) -> list[dict[str, Any]]:
    """列出某个文件夹下的所有节点（自动翻页直到读完）。

    钉钉 doc list 单页上限实测 50；超过会报 'pageSize 超过最大允许值'。
    """
    out: list[dict[str, Any]] = []
    cursor: str | None = None
    while True:
        args = ["doc", "list", "--folder", folder_node_id, "--page-size", str(page_size)]
        if workspace_id:
            args += ["--workspace", workspace_id]
        if cursor:
            args += ["--page-token", cursor]
        r = run_dws(args)
        nodes = r.get("nodes") or r.get("documents") or []
        out.extend(nodes)
        if not r.get("hasMore"):
            break
        cursor = r.get("nextPageToken")
        if not cursor:
            break
    return out
