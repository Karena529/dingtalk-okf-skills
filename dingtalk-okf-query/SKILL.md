---
name: dingtalk-okf-query
description: 查询钉钉 OKF 产品知识库以回答用户的产品事实/规则/能力/版本/决策问题。先读 manifest 找候选 OKF 卡片，再读卡片定位原文，最后生成带引用、能区分当前与历史版本的回答。当用户问产品/能力/版本/决策的具体问题，且数据已经按 OKF 格式入库到钉钉时使用。需要 dws CLI 已登录。
---

# 钉钉 OKF 产品知识库查询 Skill

把"建好的 OKF 知识库"变成"Agent 能稳定回答的产品大脑"。配套 `dingtalk-okf-kb`（建库）使用。

底层架构与字段语义见 [dingtalk-okf-kb 的 references/overview.md](../dingtalk-okf-kb/references/overview.md)。

## 何时触发

用户问的是某个**已入库产品**的具体问题，例如：

- "Skill 命名有什么约束？"
- "DMClaw v1.1 的详情页 Tab 是几个？为什么这么改？"
- "Agent 协作工作台 v3 的核心能力是什么？"
- "国际化 PRD 在英文环境下积分怎么显示？"
- "OctoPush 和 DMClaw 的 Claw 详情页是同一份吗？"

**不要触发**的场景：

- 用户问的是**怎么建库 / 怎么导入 PRD** → 走 `dingtalk-okf-kb`
- 用户问的是**钉钉本身怎么用** → 走 `dws` skill
- 用户问的内容**明显不在已入库范围**（先用 `01_load_manifest.py` 看看有没有相关产品）

## 前置

```bash
dws auth status                  # 必须 authenticated=true
which jq python3                 # 脚本依赖
```

需要知道目标知识库的 `workspaceId`。不知道的话先：

```bash
dws wiki space list --format json
# 或按名字搜：
dws wiki space search --query "<知识库名>" --format json
```

## 标准检索流程（**必须按这个顺序走**）

详见 [references/retrieval-flow.md](./references/retrieval-flow.md)。简版：

```
1. 理解问题 → 抽实体 / 抽问题类型 / 抽时间约束
2. 抽 3-7 个搜索关键词（包含产品名 / 能力名 / 版本号 / 同义词）
3. 加载 manifest（首次拉取，之后用本地缓存）
4. 在 manifest 里按 keywords 命中 id+title+aliases+summary，取 Top-5
5. 读 Top-1 OKF 卡片 → 看 status / effective_from / sources
6. status != active 时降权，但要在回答中注明
7. 沿 sources 里的 doc_id 读原文（最多读 3 篇）
8. 生成回答 + 引用（带 doc_id / status / updated_at / authority）
```

## 调用顺序

### 步骤 1：加载 manifest（首次或缓存过期时）

```bash
python3 scripts/01_load_manifest.py \
    --workspace <WS_ID> \
    [--cache-dir <DIR>]            # 默认 ~/.cache/dingtalk-okf-query
    [--force]                       # 跳过缓存
```

把目标知识库的所有 OKF 卡片元数据（id / title / aliases / summary / status / products / type / nodeId）拉到本地缓存，加速后续匹配。默认缓存 1 小时。

### 步骤 2：匹配候选卡片（核心）

```bash
python3 scripts/02_match_cards.py \
    --workspace <WS_ID> \
    --keywords "<kw1>,<kw2>,<kw3>" \
    [--top-k 5] \
    [--type product,capability,...]   # 可选过滤
    [--status active]                 # 默认只看 active；带 --include-superseded 才包含历史
```

返回 Top-K 候选 JSON，含每条的 `id / title / type / status / matched_via / score / nodeId`。

**关键**：keywords 由调用 Agent **从问题中智力抽取**，不要依赖脚本自动抽。覆盖：
- 产品名（"DMClaw"、"Agent 协作工作台"）
- 能力 / 模块名（"Tab"、"详情页"、"命名"）
- 版本号（"v1.1"、"V3"）
- 同义词扩展（"提前还款 / 提前结清 / 一次性结清"）

### 步骤 3：读 Top-1 OKF 卡片

```bash
python3 scripts/03_read_card.py \
    --node <nodeId>            # 或 --okf-id <id>，会从缓存查 nodeId
    [--workspace <WS_ID>]
```

返回结构化结果：
```json
{
  "frontmatter": {"id": "...", "status": "active", ...},
  "body": "# 当前结论\n...",
  "sources": [{"title": "...", "doc_id": "...", "url": "...", "authority": "high", "updated_at": "..."}, ...]
}
```

### 步骤 4：读 sources 引用的原文（按需）

```bash
python3 scripts/04_read_source.py \
    --node <doc_id_from_sources>
    [--max-chars 12000]            # 默认截断到 12k 字符
```

按权威等级（authority: high > medium > low）优先读，控制在 1-3 篇之内。

### 步骤 5：生成回答

调用 Agent 综合 OKF 卡片 + 原文片段，按 [references/answer-format.md](./references/answer-format.md) 的模板组织答案。**每条事实必须带引用**。

## 三条铁律（**违反即视为回答失败**）

1. **❌ 不要直接 `dws doc search` 找答案**：直接搜钉钉原生搜索，Top-1 命中率 33%（PoC 实测），偏向召回原文 PRD。**必须**先走 manifest。

2. **❌ status: superseded / deprecated 不能作为当前结论**：
   - 看到 superseded → 要么忽略，要么仅作为历史背景引用，**永远不要**说成"现在的规则是 X"
   - 必须读 OKF 卡片的 `status` 字段后再写回答

3. **❌ 不要回答超出 OKF 卡片 + 原文以外的内容**：
   - 知识库里没有 → 老老实实说"知识库未收录"，并建议用户去原始 PRD 或问 Owner
   - 不要靠模型先验补全 / 编造细节

详见 [references/known-pitfalls.md](./references/known-pitfalls.md)。

## 缓存策略

- 缓存位置：`~/.cache/dingtalk-okf-query/<workspace_id>/manifest.json`
- 默认 TTL：1 小时（命中即用）
- 可重新拉取：`--force`
- 可禁用：`--no-cache`

## 期望性能

| 指标 | PoC 实测 |
|---|---|
| Top-1 命中率（盲评 Agent）| 83% |
| Top-3 命中率 | 100% |
| 过期事实误用率 | 0% |
| 平均 CLI 调用次数/问题 | 3 次（manifest 加载缓存后）|
| 平均耗时/问题 | < 5 秒 |

## 失败排查

| 症状 | 原因 | 解决 |
|---|---|---|
| `01_load_manifest.py` 报 `00_MANIFEST not found` | 知识库还没建好 manifest | 先跑 `dingtalk-okf-kb/scripts/06_build_manifest.py` |
| `02_match_cards.py` Top-5 都不相关 | keywords 抽得太窄 / 太宽 | 重抽：覆盖产品名 + 能力 + 同义词 |
| `03_read_card.py` 卡片正文为空 | wiki API 返回结构变化 | 先看 `--debug` 输出原始 JSON 结构 |
| 回答里出现 v1 旧规则 | 没看 status 字段 | 强制只看 active 卡片 |

## 与 dingtalk-okf-kb 的协作

```
dingtalk-okf-kb（建）              dingtalk-okf-query（用）
  ↓                                  ↑
扫源目录                           生成回答
转 docx → md                       读原文 (read_source)
建目录骨架                          读 OKF 卡片 (read_card)
上传原文 (08_SOURCE)                匹配候选 (match_cards)
提炼 OKF 卡片                       加载 manifest (load_manifest)
上传卡片 (02-07)
生成 manifest+index (00_MANIFEST/01_INDEX)
```

两个 skill 共享 lib（dws 调用、frontmatter 解析等），但**互相独立部署**，没有依赖关系。
