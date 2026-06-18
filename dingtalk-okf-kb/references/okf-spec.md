# OKF 卡片产出规范

## 一卡一文件

每张卡片 = 一个 markdown 文件，落到对应 type 子目录。

## 命名

```
<type>-<kebab-slug>.md
```

| 文件名前缀 | 落地子目录 | 含义 |
|---|---|---|
| `product-` | `02_PRODUCT/` | 产品本身的事实卡（一个产品 1 张） |
| `capability-` | `03_CAPABILITY/` | 产品具体能力 / 模块 |
| `rule-` | `04_RULE/` | 业务规则、约束、流程规则 |
| `resource-` | `05_RESOURCE/` | 金融资源、合作方、第三方供应商（如适用） |
| `decision-` | `06_DECISION/` | 关键产品决策记录（为什么选 A 不选 B） |
| `service-` | `07_SERVICE/` | 底层服务、接口、技术能力 |

例：

- `product-dmclaw.md`
- `capability-agent-collaboration-binding.md`
- `rule-skill-naming-and-uniqueness.md`
- `decision-mvp-api-first-approach.md`
- `service-async-task-polling.md`

## 卡片正文结构

```markdown
---
id: <type>-<slug>
type: product | capability | product_rule | resource | decision | service
title: <人类可读标题>
status: active | draft | deprecated | superseded | unknown
summary: >
  一段话讲清楚这个知识对象当前的事实结论（≤ 150 字）。
  覆盖产品名、版本号、核心动词等高区分度关键词。

product:
  - <所属产品名>

module:
  - <子模块名，可选>

aliases:
  - <PRD 里出现的别名 / 俗称 / 英文名 / 简写 / 用户口语>
  # aliases 是召回关键，能想到的都写上

effective_from: null   # YYYY-MM-DD 或 null
effective_to: null
verified_at: <构建日期>
review_cycle_days: 90

owner:
  product: <产品 Owner，未指定就写"未指定">
  technical: <技术 Owner>

sources:
  - title: <原文标题>
    doc_id: <wiki nodeId>
    url: <docUrl>
    source_type: prd | technical_doc | feature_list | implementation_plan | design_doc
    authority: high | medium | low
    updated_at: <从原文推断>

related:
  - <其它卡片 id，可选>

supersedes:
  - <被本卡片取代的旧卡片 id，可选>
---

# 当前结论

<3-8 行正文，把核心事实讲清楚>

# 适用范围

- 限定产品 / 渠道 / 用户类型 / 客群 / 模块

# 已知限制

- PRD 里写到的边界、不支持的场景、约束

# 待确认事项

- PRD 里悬而未决的问题、TBD、未实施的计划

# 关联文档

- 《<原文标题>》— wiki nodeId: <nodeId>
```

## 字段填写约束

### `status` 枚举

| 状态 | 含义 |
|---|---|
| `draft` | 尚未正式确认 |
| `active` | 当前有效 |
| `deprecated` | 已废弃，但仍保留历史记录 |
| `superseded` | 已被新知识对象替代（必须用 `supersedes` 引用替代者） |
| `unknown` | 当前状态尚未确认 |

Agent 回答时优先用 `active`，其它状态降权或仅作为历史背景。

### `aliases` 写法

覆盖：

- 正式名称
- 业务俗称
- 历史名称
- 英文简称
- 常见缩写
- 用户口语化问法

不要只写一个名字，**至少 3-5 条**。

### `summary` 写法

- 2-3 行（不是 1 行）
- 必须包含产品名、版本号、状态判断、核心动作 / 对象
- 用 `>` 折叠多行 YAML

### `sources` 写法

每个 source 必须填全：

- `title`：原文标题（用 source_node_index.json 里的 doc_name）
- `doc_id`：wiki nodeId
- `url`：完整 docUrl
- `source_type`：根据原文性质选（PRD / 技术文档 / Feature 清单 / 实施计划 / 设计稿）
- `authority`：当前发布版 PRD = high；中间稿 / 历史版 = medium；草稿 / 讨论稿 = low
- `updated_at`：可从原文头部 / git 历史推断

## 提炼规则

1. **产品卡片**：每个独立产品 1 张
2. **能力卡片**：每份 PRD 至少抽 1-3 张能力卡（PRD 题目本身往往是一张能力卡）
3. **同一对象多 PRD → 1 张 + 多 sources**：不要为每份 PRD 都产独立卡片
4. **版本演进**：以最新 PRD 为 active；旧版本若描述完全不同形态，单独产 superseded 卡片记录历史；若仅是迭代，不产单独卡，只把旧版列入 sources
5. **规则 / 决策 / 服务卡只在 PRD 明确写到时产**：不要为每个细节凑数

## frontmatter 写法注意

- 用 YAML 子集，缩进 2 空格
- 字符串含 `:` 时必须加引号
- 多行字符串用 `>` 或 `|`
- 数组用 `- item` 形式
- null 直接写 `null`

## 质量 > 数量

每张卡片至少要：

- frontmatter 完整（缺值用 null 或"未指定"）
- "当前结论"段（3-8 行）
- "适用范围"段
- "已知限制"段
- "待确认事项"段（PRD 里有 TBD 才写）
- "关联文档"段
