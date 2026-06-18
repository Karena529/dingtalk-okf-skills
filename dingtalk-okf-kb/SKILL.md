---
name: dingtalk-okf-kb
description: 把一组本地 PRD/设计文档整理成 OKF 元数据卡片体系，连同原文上传到钉钉知识库。当用户需要"建产品知识库""把 PRD 整理成 OKF""把文档传进钉钉知识库""产品事实结构化"时使用。需要 dws CLI 已登录、本机有 pandoc。
---

# 钉钉 OKF 产品知识库构建 Skill

把若干本地目录里的 PRD / 设计文档 / 实施计划，转化为：

1. **原文层**（`08_SOURCE/`）：原文 markdown + 可选 docx 附件
2. **OKF 元数据层**（`02_PRODUCT … 07_SERVICE/`）：每个知识对象一张结构化卡片
3. **索引层**（`00_MANIFEST/` + `01_INDEX/`）：总清单 + 产品索引 + 原文索引

整体方案的核心思想见 [references/overview.md](./references/overview.md)（基于 "钉钉 = 权威知识源 + OKF 元数据 = 索引层 + 外部 Agent 通过 dws CLI 检索" 的架构）。

## 何时触发

用户说类似的话：

- "把这些 PRD 整理成 OKF / 进钉钉知识库"
- "建一个产品知识库 / 产品事实库"
- "把 docx 转成结构化卡片传上去"
- "按 OKF 整理产品文档"

## 前置检查（开始前必跑）

```bash
dws auth status         # 必须 authenticated=true
which pandoc            # 必须存在（docx → md）
which jq                # 必须存在（脚本依赖）
```

任一缺失：先告诉用户怎么补上（pandoc：`brew install pandoc`；dws：见 https://github.com/DingTalk-Real-AI/dingtalk-workspace-cli）。

## 必须先和用户确认的参数

- **目标知识库**：`workspaceId`（已存在）或要新建的名字 —— 用 `dws wiki space list` 列出已有
- **源目录列表**：1 个或多个本地路径（绝对路径优先）
- **08_SOURCE 子目录命名**：每个源目录在 wiki 里对应一个子目录名（默认用源目录的 basename）
- **工作目录**：默认 `./kb_build`，所有中间产物（转换后的 md、上传索引、生成的 OKF 卡片）落地于此
- **范围筛选**：是只取标题含 `PRD` 的 / 还是包含 Feature List/实施计划等 / 还是全部 markdown
- **OKF 卡片落地方式**：本地 review 后再传 / 直接生成并写入

## 工作流程（按顺序）

### 步骤 1：建目录骨架

```bash
python3 scripts/01_create_skeleton.py \
    --workspace <WS_ID> \
    --work-dir <WORK_DIR> \
    --source-subdirs "<sub1>,<sub2>,<sub3>"
```

- 在 wiki 下建 9 个一级目录（`00_MANIFEST` … `08_SOURCE`）
- 在 `08_SOURCE` 下建若干源子目录
- 输出 `<WORK_DIR>/folder_idx.json`（目录名 → wiki nodeId）
- **可重入**：已存在的目录会跳过

### 步骤 2：扫描源目录、转换 docx、生成上传清单

```bash
python3 scripts/02_scan_sources.py \
    --work-dir <WORK_DIR> \
    --source <PATH>:<SUBDIR_NAME> \
    --source <PATH2>:<SUBDIR_NAME2> \
    --filter prd_only|prd_plus|all_markdown
```

- 扫描每个源目录下的 `.md` / `.docx` / `.txt`
- docx 用 pandoc 转 markdown，输出到 `<WORK_DIR>/converted/<SUBDIR_NAME>/`
- 生成 `<WORK_DIR>/upload_list.tsv`（subdir / src_path / doc_name）
- 自动去重（相同内容的 .md 和 .txt 只保留一份）
- **再确认一次**：让用户审 upload_list.tsv 是否合理

### 步骤 3：上传原文 markdown 到 08_SOURCE

```bash
python3 scripts/03_upload_sources.py --work-dir <WORK_DIR>
```

- 读 upload_list.tsv 和 folder_idx.json
- 调 `dws doc create` 上传，超过 10000 字符的文件自动分块（首块 create + 后续 append）
- 输出 `<WORK_DIR>/source_node_index.json`（doc_name → nodeId / docUrl）
- **可重入**：已在 source_node_index.json 里的跳过

### 步骤 4（可选）：上传 docx 二进制做附件归档

如果用户选择保留原 docx：

```bash
python3 scripts/04_upload_docx.py --work-dir <WORK_DIR> --source <PATH>:<SUBDIR_NAME>
```

- 在每个对应的 wiki 子目录下建 `_原始docx` 子目录
- 用 `dws doc upload` 上传 docx 二进制

### 步骤 5：生成 OKF 卡片（**LLM 任务，不是脚本**）

这一步**由调用 skill 的 orchestrator LLM 来做**，按以下方式：

1. 读 `references/okf-spec.md`（卡片字段规范）
2. 读 `references/extraction-prompt.md`（子 Agent 提示词模板）
3. 把 upload_list.tsv 按产品聚类（一般 3-6 组）
4. 对每组派一个 sub-agent，输入：
   - 卡片规范（references/okf-spec.md）
   - 该组源文件清单 + 对应的 wiki nodeId（从 source_node_index.json 取）
   - 输出目录：`<WORK_DIR>/okf_cards/{02_PRODUCT,03_CAPABILITY,04_RULE,06_DECISION,07_SERVICE}/`
5. 各 sub-agent 完成后，主线程检查 `<WORK_DIR>/okf_cards/` 下文件数量和分布

**Prompt 模板**见 [references/extraction-prompt.md](./references/extraction-prompt.md) —— orchestrator 把模板里的占位符填上即可。

### 步骤 6：上传 OKF 卡片

```bash
python3 scripts/05_upload_okf_cards.py --work-dir <WORK_DIR>
```

- 扫描 `<WORK_DIR>/okf_cards/<TYPE_DIR>/` 下所有 .md
- 解析每张卡片的 frontmatter 取 `id` 和 `title`
- 上传到 wiki 对应目录（02-07）
- 文档名用 frontmatter 里的 `title`
- 输出 `<WORK_DIR>/okf_node_index.json`
- **可重入**

### 步骤 7：生成 Manifest 与 Index

```bash
python3 scripts/06_build_manifest.py --work-dir <WORK_DIR>
```

输出并上传：

- `00_MANIFEST/manifest-all`：所有卡片总清单
- `00_MANIFEST/manifest-{products,capabilities,rules,decisions,services}`：按类型拆分
- `01_INDEX/产品总索引`：按产品组织所有卡片（从 frontmatter `product` 字段聚合）
- `01_INDEX/原始证据索引`：所有 08_SOURCE 原文清单

超长 manifest 自动分块。

### 步骤 8：（可选）跑评测

向用户提供：

- 拟 6-10 个真实业务问题
- 跑 `scripts/07_evaluate.py`（如提供）
- 比较"路径 A 钉钉原生搜索" vs "路径 B Manifest 路径" 的 Top-1/3/5 命中率

## 失败重试与可重入

每个脚本都设计为**幂等**：通过 `*_index.json` 跟踪已完成项；网络中断或 API 限流后重跑只补缺，不会重复上传。

如果上传过程中产生了"自动加 (1) 后缀"的重复文档，用 `dws doc delete` 清理。

## 限制与已知坑

- **钉钉 doc create 单次内容上限 10000 字符**：脚本里默认按 9000 字符切块，留 1000 字符安全边际。
- **CLI 访问需要组织管理员开启**：报错 "CLI data access is not enabled" 时，让用户去 https://open-dev.dingtalk.com → CLI 访问管理 开启。
- **个人钉钉账号无法用**：必须有组织（即使是免费团队）。
- **同名文档不会失败而是加 `(1) 后缀`**：可重入逻辑保证重跑不再叠加。
- **文档树不支持嵌套太深**：`08_SOURCE/<subdir>/<sub_subdir>` 三层基本能用，但实测最稳还是两层。
- **frontmatter 用 YAML 子集**：脚本只解析 `id` / `title` / `type` / `status` / `product` 等关键字段，复杂语法可能解析不出。

## 公共库

[scripts/lib/dws.py](./scripts/lib/dws.py) 提供：

- `run_dws(args)` — 统一调用 dws，去除 note: 前缀，返回 dict
- `chunk_markdown(text, max_size)` — 按段落边界切块
- `parse_frontmatter(md_text)` — 提取 YAML frontmatter 关键字段
- `create_doc_chunked(workspace, folder, name, content)` — 带自动分块的 create
- `dws_bin()` — 解析 dws 可执行路径（支持 `DWS_BIN` 环境变量覆盖）
