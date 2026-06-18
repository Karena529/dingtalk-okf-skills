#!/bin/bash
# install.sh — 把仓库里的 skill 软链接到 ~/.claude/skills/
#
# 软链接的好处：本仓库 git pull 后所有已安装的 skill 自动跟随更新。
# 如果你想要"复制"模式（独立副本，不跟随更新），把脚本里的 ln -snf 改成 cp -r 即可。

set -e

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
TARGET="${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}"

mkdir -p "$TARGET"

echo "Installing skills from: $REPO_ROOT"
echo "                    to: $TARGET"
echo

installed=0
skipped=0

for skill_dir in "$REPO_ROOT"/*/; do
    skill_name="$(basename "$skill_dir")"
    # 跳过非 skill 目录（必须含 SKILL.md）
    if [ ! -f "$skill_dir/SKILL.md" ]; then
        continue
    fi
    target_link="$TARGET/$skill_name"

    if [ -L "$target_link" ]; then
        # 已是符号链接：检查是否指向当前仓库
        existing=$(readlink "$target_link")
        expected="${skill_dir%/}"
        if [ "$existing" = "$expected" ]; then
            echo "  [skip] $skill_name → 已正确链接"
            skipped=$((skipped + 1))
            continue
        else
            echo "  [update] $skill_name → 链接指向变更"
            ln -snf "$expected" "$target_link"
            installed=$((installed + 1))
        fi
    elif [ -e "$target_link" ]; then
        # 已是真实目录/文件：警告，不覆盖
        echo "  [WARN] $target_link 已存在且不是符号链接，跳过。如需替换请手动删除后重跑。"
        skipped=$((skipped + 1))
    else
        ln -snf "${skill_dir%/}" "$target_link"
        echo "  [ok] $skill_name → $target_link"
        installed=$((installed + 1))
    fi
done

echo
echo "Done. installed=$installed  skipped=$skipped"
echo
echo "Verify:  ls -la \"$TARGET\" | grep '^l'"
