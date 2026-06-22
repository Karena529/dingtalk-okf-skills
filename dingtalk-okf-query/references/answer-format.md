# 回答格式规范

每个回答都按以下模板组织。**每条事实必须有引用**。

## 模板

```markdown
## 当前结论

<3-8 行核心结论，直接回答用户问题。如果有版本演进，明确说"当前版本是 X"。>

## 适用范围

- 产品 / 模块：<...>
- 渠道 / 用户类型 / 客群：<...>
- 时效：<effective_from 到 effective_to，或"当前生效"，或"待确认"> 

## 已知限制 / 边界

- <PRD 里写到的不支持场景、约束、特殊情况>
- <如果有版本差异，列出旧版的不同>

## 引用

| 原文 | nodeId / 链接 | 状态 | 更新时间 | 权威等级 |
|---|---|---|---|---|
| 《XXX PRD v1.1》 | https://alidocs... | active | 2026-04-15 | high |
| 《XXX PRD v1.0》 | https://alidocs... | active | 2026-04-14 | medium |

引用了哪张 OKF 卡片：
- `<okf-card-id>` — status: `active` — verified_at: `2026-06-22`

## 待确认事项（如有）

- <PRD 里悬而未决的问题、TBD、未实施的计划>
- <知识库里没有但回答可能需要的部分>
```

## 关键写作规则

### 1. 状态披露

如果引用的卡片或原文是 `superseded` / `deprecated` / `draft`：
- **不要** 把它当成当前结论
- 必须明确写 "**该信息来自 [状态] 版本**"
- 例：

> 注意：v1（PRD-2026-03-23）的 Task View 设计已被 V3（2026-03-24）取代，状态 superseded。本回答以 V3 为当前结论；v1 仅作为版本演进背景引用。

### 2. 时间披露

如果 OKF 卡片 `verified_at + review_cycle_days < today`，回答末尾加：

> ⚠️ 该 OKF 卡片最后校验于 2026-XX-XX，已超过 90 天复核周期。建议向 Owner（[product]）确认是否仍然有效。

### 3. 引用粒度

- 不要只引用 OKF 卡片 → 必须把卡片 sources 里实际读过的原文也列上
- 引用 nodeId 而不是 docUrl 的纯文本（因为 nodeId 更稳定，docUrl 可能因租户而异）
- 同时给 nodeId + URL，让用户能直接点开

### 4. 知识盲区披露

如果用户的问题超出已读卡片 + 原文的范围：
- 不要靠模型先验补全
- 明确写："本知识库未收录该部分细节，建议查阅 [原文 nodeId] 或问产品 Owner [name]。"

### 5. 冲突披露

如果多份原文给出冲突结论：
- 不要自行决定哪份对
- **同时**展示两份结论 + 各自的 `updated_at` 和 `authority`
- 让用户判断或转给 Owner

例：

> 关于 X，存在两个不同表述：
> - 《PRD v1.1》（updated_at 2026-04-15，authority high）说 A
> - 《技术方案》（updated_at 2026-04-20，authority high）说 B
> 两份都是 high authority，建议向 Owner 确认以哪个为准。

## 不允许的反模式

| ❌ 错误 | ✅ 正确 |
|---|---|
| "DMClaw 详情页有 6 个 Tab" | "v1.0 是 6 Tab，v1.1 已合并为 5 Tab（当前），引用《DMClaw_PRD v1.1》" |
| 只回答结论不带引用 | 每条事实后跟引用 |
| 把 superseded 当当前用 | 明确标 superseded，并指向 active 版本 |
| 编造 PRD 里没写的细节 | "知识库未收录该细节" |
| 用模糊词"通常 / 一般" | 引用具体 PRD 的具体表述 |

## 示例：好的回答（参考）

> ## 当前结论
> 
> DMClaw 详情页在 v1.1（effective_from 2026-04-15）由 v1.0 的 6 个 Tab 简化为 **5 个 Tab**：原"健康检查" + "诊断修复"两个独立 Tab 合并为单一"健康检查"Tab，上半区显示检查结果，下半区显示修复动作。"Token 用量"同时更名为"积分用量"。
> 
> ## 改动原因
> 
> 诊断修复需要先看健康检查结果，两者频繁切换；合并后用户可在一屏内"看问题→立即修"，减少 Tab 切换。
> 
> ## 适用范围
> 
> - 产品：DMClaw
> - 模块：Client 详情页
> - 时效：v1.1 生效（2026-04-15 起）
> 
> ## 已知限制
> 
> - 合并后单 Tab 内容更长，需要良好的视觉分区
> - v1.1 PRD 对"修复 Agent"等新动作与 v1.0 旧动作的语义差异未完全对齐
> 
> ## 引用
> 
> - 《DMClaw_PRD v1.1》— `QPGYqjp...` — status: active — updated_at: 2026-04-15 — authority: high
> - 《DMClaw_PRD v1.0》— `QPGYqjp...` — status: active — updated_at: 2026-04-14 — authority: medium（仅作为版本对照）
> - OKF 卡片 `decision-detail-tab-merge-v1.1` — status: active — verified_at: 2026-06-18
> 
> ## 进一步动向（待确认）
> 
> - v1.2 拟把详情页进一步简化为 2 Tab（OctoPush 风格），但 v1.2 当前只有 flow 设计稿，尚未发布正式 PRD（参考 OKF 卡片 `decision-detail-tab-simplify-v1.2`，status: draft）。

这种回答的结构、引用密度、状态披露是查询答复的金标准。
