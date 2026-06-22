# 标准检索流程（10 步）

每个问题 Agent 必须按此顺序走，跳步会显著降低准确率。

## 步骤 1：理解问题

读用户问题，识别：
- **问题类型**：事实查询 / 规则查询 / 决策追溯 / 版本对比 / 能力概览 / 跨产品对比
- **实体**：产品名（DMClaw / DM Skill / OctoPush / ...）、模块名、版本号
- **时间约束**：最新版？历史版？某个具体时间点？
- **回答深度**：只要结论 / 要带原文细节 / 要列所有适用条件

## 步骤 2：抽取 3-7 个搜索关键词

**这是召回率的决定性步骤**。覆盖：

| 维度 | 例子 |
|---|---|
| 产品名 | `DMClaw` `Agent 协作工作台` `DM Skill` `OctoPush` |
| 能力名 | `Tab` `详情页` `命名` `异步任务` `提前还款` |
| 版本号 | `v1.1` `V3` `第二期` |
| 同义词 | `提前还款 → 提前结清 / 提前清贷 / 一次性结清` |
| 中英混用 | `WorkItem 任务驱动` `dashboard 概览` |
| 用户口语 | `Skill 重名 / Skill name 校验` |

不要只填 1-2 个词。**每个问题至少 3 个关键词**，2 个不够拓宽召回面。

## 步骤 3：加载 manifest（如未缓存）

```bash
python3 scripts/01_load_manifest.py --workspace <WS_ID>
```

首次拉取会读 `00_MANIFEST` 目录下所有 manifest-* 文档（manifest-all、manifest-products 等），合并解析后缓存到本地。1 小时内重复调用直接读本地缓存。

如果你怀疑缓存过期（例如刚有新 PRD 入库），加 `--force` 重新拉。

## 步骤 4：在 manifest 里匹配候选

```bash
python3 scripts/02_match_cards.py \
    --workspace <WS_ID> \
    --keywords "<kw1>,<kw2>,..." \
    --top-k 5
```

匹配规则：
- 关键词在 entry 的 `id / title / aliases / summary / modules` 任一字段中作为子串出现 → +1 分
- 同时命中多个字段 → 累加
- 同一关键词多字段命中 → 只计 1 分（避免被 alias 撞重复计）
- `status == active` 加 0.5 分（默认权重）
- 输出 Top-K 含 `score / matched_via`

**默认 `--status active`**：只返回当前有效卡片，避免误用历史。如果用户明确问历史版本，加 `--include-superseded`。

## 步骤 5：读 Top-1 OKF 卡片

```bash
python3 scripts/03_read_card.py --node <Top-1 nodeId>
```

返回 frontmatter + body + sources 的结构化字典。

**重点检查**：
- `status` 字段：`active` 才作为当前结论；`superseded`/`deprecated` 视为历史
- `effective_from` / `effective_to`：是否在生效期内
- `verified_at` + `review_cycle_days`：是否过期未复核（超期要在回答中提示）
- `aliases`：是否包含用户问题里的关键词（不在 → 可能是误命中）

## 步骤 6：决策"是否要继续读 sources"

| 情况 | 决策 |
|---|---|
| 卡片正文已包含完整结论 + 适用范围 | 直接进入步骤 8 生成回答 |
| 卡片是简短摘要，需要原文细节 | 进入步骤 7 |
| 用户明确问"为什么 / 怎么实现" | 进入步骤 7（多读 1-2 篇高 authority 原文）|
| 卡片有多张相互冲突 | 步骤 7 + 在回答中标记冲突 |

## 步骤 7：读 sources 引用的原文

按 sources 列表里的 `authority` 优先级（high > medium > low）选 1-3 篇读：

```bash
python3 scripts/04_read_source.py --node <source_doc_id> --max-chars 12000
```

读完后检查：
- 原文是否与 OKF 卡片结论一致
- 有没有卡片漏掉的边界条件 / 例外
- `updated_at` 时间戳是否更新（如果 sources 比卡片 verified_at 还新，提示用户）

## 步骤 8：检查冲突与去重

如果读了多份原文：
- 它们结论是否一致？
- 有冲突 → 不要自行决定，**在回答里同时展示，并标注各自的更新时间和权威等级**
- 没冲突 → 取 `authority: high` 那份 + `updated_at` 最新的为主

## 步骤 9：生成回答

按 [answer-format.md](./answer-format.md) 的模板组织。**每条事实必须有引用**。

## 步骤 10：自检与返回

返回前检查：

- [ ] 每条事实都有引用（没引用的事实必须删除或标"待确认"）
- [ ] superseded/deprecated 内容没被当成当前结论使用
- [ ] 回答里说明了 status / 更新时间 / authority
- [ ] 知识库没收录的部分坦诚说"未收录"，不编造
- [ ] 适用范围 / 已知限制 / 待确认事项 三栏齐全（如卡片里有）

## 检索成本预算

| 操作 | 预算 |
|---|---|
| `01_load_manifest.py`（首次） | 1 次（约 5-15 次 API 调用，缓存后 0 次） |
| `02_match_cards.py` | 0 次（纯本地） |
| `03_read_card.py` | 1-2 次（Top-1 必读，必要时 Top-2 也读） |
| `04_read_source.py` | 1-3 次（按需） |
| **合计** | 3-6 次 API 调用 / 问题 |

如果一个问题需要读超过 5 篇原文才能回答 —— **大概率是问题落在了 OKF 知识库未覆盖的范围**，应该停下来告诉用户而不是硬拼。
