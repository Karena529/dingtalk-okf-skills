# 已知陷阱与避坑指南

按 PoC 评测踩出来的真实坑，每条都有失败模式 + 修复方法。

## 坑 1：直接 `dws doc search` 找答案

**症状**：搜索结果 Top-1 命中率仅 33%，因为钉钉原生搜索把原文 PRD 排在卡片前面。

**示例**：
- 问"Skill 命名约束"
- 直接 `dws doc search --query "Skill 命名"` → Top-1 返回的是 PRD 全文，需要读完才能找到规则
- 正确做法：先 `02_match_cards.py` 在 manifest 里命中 `rule-skill-naming-and-uniqueness` 卡片

**修复**：永远先走 manifest 路径，把 `dws doc search` 当成兜底（manifest 路径全失败时才用）。

---

## 坑 2：把 `superseded` / `deprecated` 卡片当成当前事实

**症状**：回答里说"现在的规则是 X"，但 X 已经被新版本替代了。

**示例**：
- 问"Agent 协作工作台 Task View 长什么样？"
- 命中 `capability-task-view-prd-v1-card`（status: superseded，被 V3 取代）
- 错误回答："Task View 有 4 大头部指标 Assets / Proposals / Approvals / Executor + 5 个 Tabs"
- 正确做法：看到 status: superseded → 用 supersedes 字段找到新版（capability-task-driven-workitem-view），用新卡片回答

**修复**：
- `02_match_cards.py` 默认 `--status active`，不会返回 superseded
- 如果用户明确问历史版本，加 `--include-superseded`，但回答里必须明确标"该信息来自已被取代的版本"

---

## 坑 3：keywords 抽得太窄（召回不到）

**症状**：`02_match_cards.py` 返回的 Top-5 都不相关。

**示例**：
- 问"提前还款规则"，只填 keywords `["提前还款"]`
- manifest 里这张卡 aliases 是 `["提前结清", "提前清贷", "一次性结清"]` —— 没命中
- 正确：keywords 应填 `["提前还款", "提前结清", "提前清贷", "一次性结清", "还款", "结清"]`

**修复**：抽关键词时**必须**做同义词扩展，覆盖至少 3-5 条；不确定时多抽一些（脚本会去重）。

---

## 坑 4：keywords 抽得太宽（精度低）

**症状**：Top-5 里掺了一堆无关产品的卡片。

**示例**：
- 问"DMClaw 安装流程"，keywords 抽成 `["流程", "安装", "配置"]`
- 命中所有产品的"流程"类卡片 —— 噪音爆炸
- 正确：keywords 必须包含产品名 `["DMClaw", "安装", "配置流程"]`

**修复**：keywords 第一条永远是**产品名 / 域名**，剩下才是动作 / 对象。

---

## 坑 5：单读 OKF 卡片就回答，不读原文

**症状**：回答缺少边界条件 / 例外情况。

**示例**：
- 卡片说"DMClaw v1.1 详情页 5 Tab"
- 但卡片正文里没说"什么情况下某些 Tab 会隐藏"
- 直接用卡片回答 → 用户问到"未签约的 Claw 详情页是几 Tab"答不上来
- 正确：读 sources 里的 PRD 原文，原文里写了未签约时的特殊形态

**修复**：用户问"为什么 / 怎么实现 / 边界" → 必须读至少 1 篇 high-authority 原文。

---

## 坑 6：多份原文冲突时自行判断

**症状**：多份原文说不同的话，Agent 强行选一个。

**示例**：
- 一份 PRD（updated 2026-03-15）说"X 默认值是 100"
- 另一份技术文档（updated 2026-04-10）说"X 默认值是 200"
- 错误：Agent 直接选 200（因为更新）
- 正确：**同时展示两份**，标各自的 updated_at + authority，让用户确认

**修复**：见 [answer-format.md 第 5 条](./answer-format.md#5-冲突披露)。

---

## 坑 7：忽略 `verified_at` 过期

**症状**：用了一张 90 天没被 verified_at 校验的卡片，其实信息已经变了。

**修复**：
- 03_read_card.py 的输出会标记是否 `verified_at + review_cycle_days < today`
- 卡片过期 → 回答末尾必须加 ⚠️ 提示用户找 Owner 复核

---

## 坑 8：没读 `effective_from` / `effective_to`

**症状**：当前是 2026-06，引用了一张 effective_from = 2026-08 的卡片，但卡片对应的能力其实还没上线。

**修复**：
- 卡片 `effective_from` 在未来 → 回答里写"计划于 [date] 生效，目前尚未上线"
- 卡片 `effective_to` 已过 → 等同 deprecated 处理

---

## 坑 9：把 `draft` 当成确定结论

**症状**：用了一张 status: draft 的卡片回答，告诉用户"现在的规则是 X"，但其实 draft 还没确认。

**修复**：
- draft 卡片 → 回答里**必须**说"该规则**当前是草稿状态**，尚未正式确认"
- 默认 `--status active` 不返回 draft；用户明确问"将来的规则"才返回

---

## 坑 10：把 OKF 卡片当成"原文摘要"用

**症状**：用户问"这部分原文里具体怎么写的？"，Agent 直接复述卡片正文。

**修复**：
- 卡片正文是**人写的概括**，可能丢失原文的精确表述
- 用户问原文细节 → 必须读 sources 引用的原文，引用原文片段
- 例：用户问"PRD 里关于 X 的原话是什么" → 用 04_read_source.py + 引用具体段落

---

## 坑 11：知识库未收录时强行回答

**症状**：问的产品 / 能力根本没入库，Agent 靠模型先验编了一段。

**修复**：
- `02_match_cards.py` Top-5 score 都很低（< 1）→ 大概率没收录
- 老老实实告诉用户："知识库里没找到 X 相关内容，可以确认一下产品名是否拼写正确，或者去钉钉知识库管理员处申请补充。"
- 不要编

---

## 坑 12：缓存过期但不知道

**症状**：1 小时前缓存的 manifest 没有今天新增的卡片，回答漏了新内容。

**修复**：
- 当用户提到"刚发布的 / 最新的 / 上周的"等新鲜度信号 → 加 `--force` 重新拉缓存
- 用户在同一会话里频繁问 → 缓存够用，无需 force
- 默认 1 小时 TTL 已经覆盖大多数场景

---

## 速查：每条规则对应的判断点

| 接到问题时检查 | 对应坑 |
|---|---|
| keywords 是否覆盖产品名 + 同义词？ | 坑 3 / 4 |
| 命中卡片的 status 是不是 active？ | 坑 2 / 9 |
| 卡片 verified_at 是否过期？ | 坑 7 |
| 卡片 effective_from/to 是否在生效期？ | 坑 8 |
| 是否需要读原文取细节？ | 坑 5 / 10 |
| 多份原文有没有冲突？ | 坑 6 |
| 知识库到底有没有这部分？ | 坑 11 |
| 是不是新发布的内容？ | 坑 12 |
