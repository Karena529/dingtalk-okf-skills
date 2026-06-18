# 子 Agent 提取 OKF 卡片提示词模板

> Orchestrator 把方括号占位符填上后，作为 sub-agent 的 prompt。每个产品组派一个 sub-agent。

---

```
你是产品知识库建设任务的子 Agent，专门处理 [产品组名] 产品线的 [N] 份 PRD/规划/设计文档，把它们提炼成 OKF 元数据卡片。

## 必读

先 Read 这两份文件，吃透：

1. [SKILL_DIR]/references/okf-spec.md  — 卡片字段规范、命名规范、产出要求
2. [SKILL_DIR]/references/overview.md  — 整体方案（理解 OKF 字段语义）

## 你要处理的 [N] 份文档（路径 + wiki nodeId + docUrl）

[文档清单 — 逐行：原文类型 | 本地 markdown 路径 | wiki nodeId | docUrl]

例：
| PRD-v1 | /path/to/source/prd-v1.md | xxxxx | https://alidocs... |
| 实施计划 | /path/to/source/plan.md | yyyyy | https://alidocs... |

## 工作步骤

1. 逐一 Read 全部 [N] 份原文（一次 Read 一份）
2. 整体梳理：哪些是同一个产品的不同版本 PRD（v1/v2/v3 系列）、哪些是子模块、哪些是实施计划/产品定位类的元文档
3. 提炼 OKF 卡片：
   - **product 卡片**：通常 1 张（覆盖该产品域所有版本，status = active）
   - **capability 卡片**：每个核心能力一张；同一能力多份 PRD 提到 → 1 张 + 多 sources
   - **rule 卡片**：明确写到业务规则/限制/流程约束才产
   - **decision 卡片**：明显的路线选择、放弃/保留方案、版本切换决定才产
   - **service 卡片**：涉及底层接口、技术服务才产
4. 旧版本 PRD 对应能力：如果新版完全改写，旧卡标 status: superseded，supersedes 字段引用新卡片 id；如果只是迭代，不产单独卡
5. 卡片写到对应本地目录：[WORK_DIR]/okf_cards/{02_PRODUCT|03_CAPABILITY|04_RULE|06_DECISION|07_SERVICE}/
6. 文件命名严格：<type>-<slug>.md

## 字段质量要求

严格按 okf-spec.md 的 frontmatter 模板。每张卡片必须有：

- 完整 frontmatter（aliases ≥ 3 条，summary 2-3 行）
- "当前结论"段（3-8 行）
- "适用范围"段
- "已知限制"段
- "待确认事项"段（PRD 里有 TBD 才写）
- "关联文档"段

## sources 字段填写

| 原文性质 | source_type | 默认 authority |
|---|---|---|
| 正式 PRD | prd | medium |
| 当前发布版 PRD | prd | high |
| 早期草稿 / 讨论稿 | prd | low |
| 技术 / 接口文档 | technical_doc | high |
| Feature 清单 | feature_list | medium |
| 实施计划 | implementation_plan | medium |
| 设计 / 交互方案 | design_doc | medium |

## 期望产出量级

- 每份 PRD 通常对应 1-3 张卡片（产品 0-1 张 + 能力 1-2 张 + 规则/决策/服务 0-1 张）
- 质量 > 数量，不要凑数
- N 份 PRD → 总计 N ~ 2N 张卡片是合理范围

## 报告

完成后用一句话总结：产出 X 张卡片，按类型分布是 Y/Z/...，列出所有文件名（按目录分组）。不要返回卡片正文。
```

---

## Orchestrator 派 sub-agent 的步骤

1. 读 `<WORK_DIR>/source_node_index.json` 拿到所有原文的 nodeId
2. 把原文按产品聚类（看文件名/路径里的产品标识，或问用户确认聚类方案）
3. 对每组：
   - 把上面的模板里 `[产品组名]` / `[N]` / `[文档清单]` / `[SKILL_DIR]` / `[WORK_DIR]` 替换成具体值
   - 用 Agent 工具派 `general-purpose` sub-agent
   - 让它自己 Read okf-spec.md 和 overview.md
4. 等所有 sub-agents 完成
5. 检查 `<WORK_DIR>/okf_cards/` 下的文件分布是否合理（产品/能力/规则比例）
6. 进入步骤 6（上传卡片）

## 聚类建议

按"产品归属"聚类一般最合理，例：

- 产品 A 相关 PRD → Group A → sub-agent A
- 产品 B 相关 PRD → Group B → sub-agent B
- ...

每组 5-15 份 PRD 比较舒适：太少（< 5）浪费 agent；太多（> 20）单个 agent context 紧张。

如果产品归属不清，先派一个 Explore agent 读所有源文件首页确认归属。
