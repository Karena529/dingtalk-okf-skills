# DingTalk OKF Skills

把钉钉知识库变成一个"可被 Agent 自动检索"的产品知识库 —— 一组 Claude Code skill 的集合。

## 整体方案

> 钉钉作为**权威知识源 + 权限系统**，OKF 元数据卡片作为**索引层**，外部 Agent 通过钉钉 CLI（`dws`）查询元数据→定位原文→生成带引用的回答。

详细方案见 [`dingtalk-okf-kb/references/overview.md`](./dingtalk-okf-kb/references/overview.md)（OKF 双层架构 + 标准检索流程 + 评测指标）。

## Skill 清单

| Skill | 状态 | 作用 |
|---|---|---|
| [`dingtalk-okf-kb`](./dingtalk-okf-kb/) | ✅ v0.1 | **建库**：把本地 PRD 整理成 OKF 卡片体系 + 上传到钉钉知识库 |
| `dingtalk-okf-query` | 🚧 规划中 | **调用**：外部 Agent 标准检索流程（manifest → OKF 卡 → 原文 → 答案） |
| `dingtalk-okf-maintain` | 🚧 规划中 | **维护**：新 PRD 增量更新、定期复核、`verified_at` 过期通知 |
| `dingtalk-okf-eval` | 🚧 规划中 | **评测**：跑命中率 / 过期事实误用率 / 检索成本指标 |

未来会按"建 → 用 → 维护 → 评测"四个阶段补齐。

## 安装

### 前置依赖

```bash
# 1. dws CLI（钉钉 Workspace CLI）
curl -fsSL https://raw.githubusercontent.com/DingTalk-Real-AI/dingtalk-workspace-cli/main/scripts/install.sh | sh
dws auth login              # 完成钉钉 OAuth 授权（需要组织管理员开启 CLI 访问）

# 2. pandoc（docx 转 markdown）
brew install pandoc          # macOS
# 或: apt install pandoc      # Debian/Ubuntu

# 3. jq（脚本处理 JSON）
brew install jq

# 4. Python 3.10+（脚本运行环境）
python3 --version
```

### 安装到 Claude Code

```bash
git clone https://github.com/Karena529/dingtalk-okf-skills.git
cd dingtalk-okf-skills
./install.sh                 # 软链接所有 skill 到 ~/.claude/skills/
```

`install.sh` 会为每个 skill 子目录在 `~/.claude/skills/` 下建一个符号链接。这意味着仓库更新后，你 `git pull` 一次，所有已链接的 skill 自动跟着更新。

### 验证

```bash
ls -la ~/.claude/skills/ | grep dingtalk
# dingtalk-okf-kb -> /path/to/dingtalk-okf-skills/dingtalk-okf-kb
```

下次 Claude 会话里说"把这些 PRD 整理成 OKF 进钉钉"，应当自动触发 `dingtalk-okf-kb` skill。

## 当前能力（dingtalk-okf-kb v0.1）

- 自动扫描本地源目录，提取 markdown / docx / txt
- pandoc 自动转 docx → markdown
- 在钉钉知识库下建立 9 层 OKF 目录骨架（00_MANIFEST … 08_SOURCE）
- 上传原文 markdown 到 `08_SOURCE/<子目录>`，自动处理超 10000 字符分块
- 可选：上传原 docx 二进制做附件归档
- 通过 sub-agent 协作并行提炼 OKF 卡片（按产品聚类）
- 上传 OKF 卡片到 02_PRODUCT … 07_SERVICE 对应目录
- 生成 6 份 manifest（按类型）+ 2 份 index（按产品 / 按原文）
- 全流程**幂等**：失败重跑只补缺，不重复

## 实测数据（首次跑通的 PoC）

- 输入：3 个本地源目录、共 ~60 份候选文档
- 输出：33 份原文上传 + 76 张 OKF 卡片 + 10 份 docx 附件 + 8 份 manifest/index
- 评测：钉钉原生搜索 Top-1 仅 33%；先读 manifest 路径 Top-1 83%（盲评 Agent，自抽关键词）
- 关键发现：`status` 字段成功隔离 superseded 内容 → 过期事实误用率 0%

## 设计原则

1. **零硬编码绝对路径**：所有路径来自 CLI 参数；`dws` 二进制走 `DWS_BIN` 环境变量 → `PATH` → `~/.local/bin/dws`
2. **每步幂等**：每个步骤通过 `*_index.json` 跟踪进度，重跑只补缺
3. **支持 `--dry-run`**：所有 6 个核心脚本都能预览不真做
4. **OKF 提取是 LLM 任务**：不写死提取逻辑，靠 sub-agent + 提示词模板 + 字段规范的组合
5. **manifest 是检索的真正主路径**：不依赖钉钉原生搜索，用结构化清单 + aliases + summary 做命中

## 限制

- 钉钉个人账号无法用 —— 必须有组织（即使是免费团队）
- 组织管理员需要在 [open-dev.dingtalk.com](https://open-dev.dingtalk.com) 开启 CLI 访问
- 钉钉 doc create 单次内容上限 10000 字符（已在脚本里自动分块处理）
- 需要 `pandoc` / `jq` 在 PATH 中

## License

MIT —— 随便用、随便改、随便分发。

---

> 📌 这是产品知识库方案的**第一阶段**（建库）。第二阶段（调用）的 skill 会很快补上。整体目标是建一个**可复用的产品知识库搭建及调用完整方案**。
