---
name: code-impact-regression
description: 根据代码变更自动推导回归测试范围：分析本次改动影响了哪些代码符号和调用链路，从工程内测试代码、用例描述、测试名称中识别最相关的测试用例，生成分层回归执行计划，并指出尚无测试覆盖的影响点。当用户提到变更分析、影响范围、代码影响、回归范围、受影响测试、测试用例关联、根据改动找测试、根据变更测试、分析哪些用例需要回归、找相关测试点时，务必使用此技能。即使用户没有明确说出具体工具或测试用例，只要目标是"根据代码改动推导测试范围"，也应优先使用此技能。
---

# 代码影响用例回归

## Agent 职责

Agent 只做两件事：
- **开头**: 从用户输入推断参数、调用 `run_pipeline.py` 一次性跑完全流程
- **结尾**: 读取 `summary.json`，用自然语言向用户解读结果
中间六个分析步骤完全由 pipeline 脚本自动完成，Agent 不介入。

## 触发策略

当用户真实目标是"根据代码改动推导测试范围"时优先触发，不必等用户说出 GitNexus 等关键词。
应触发的场景：这次改动要回归哪些测试、这个 commit/PR/分支会影响哪些功能或测试、我改了某个接口/方法/模块哪些地方受影响、帮我根据改动筛回归范围、这次上线前哪些测试必须跑。
不应触发的场景：只想看函数实现、只想修编译错误、只想跑现成测试而不需要分析哪些该跑。

## 第一步：推断参数

Agent 只需要从用户输入中判断以下参数，无法推断时才补问**一个**最关键的问题：

| 参数 | 说明 | 何时传 |
| --- | --- | --- |
| `repo_path` | 仓库本地路径 | **必须主动查找后传入**，见下方「repo_path 查找规则」 |
| `git-url` | 仓库 git remote URL | 本地找不到对应仓库时才传，供脚本自动 clone |
| `base-ref` | 基准分支 | 见下方规则 |

---
**repo_path 查找规则（重要，必须在调用 pipeline 前执行）**:
用户提供了 git URL 或仓库名时，Agent **必须**先在本地查找，不能直接依赖脚本默认当前目录（当前目录是 workspace 根，不是目标仓库）：
1. 从 git URL 中提取仓库名（如 `ssh://git@git.sankua.com/fig/forbidden_sale.git` → `forbidden_sale`）
2. 在 workspace 目录下查找同名目录（`ls /workspace/*/`）
3. 若找到，用 `git remote -v` 确认 remote URL 与用户提供的一致，并确认目标分支存在（`git branch -a | grep <branch>`）
4. 找到本地仓库 → 传 `repo_path`，不传 `git-url`
5. 本地找不到 → 传 `git-url` 和目标 `repo_path`（如 `<workspace>/<repo_name>`），脚本会自动 clone

---
**base-ref 推断规则（重要）**:
以下情况**必须传** `--base-ref origin/master`（或对应主干分支名）：
- 用户提到"分支"、"feature 分支"、"PR"、"这次提交"、"已提交的改动"
- 用户提供了 git URL + 分支名（说明变更已提交到该分支）
- 用户说"对比 master/main"、"相对主干的变更"

以下情况**不传** `--base-ref`（分析工作区未提交的改动）：
- 用户明确说"未提交的改动"、"工作区改动"、"staged 的变更"

*不确定时优先传 `--base-ref origin/master`，因为 pipeline 有自动兜底：若 `scope=unstaged` 检测到 0 个变更符号，会自动推断 base-ref 并切换到 `scope=compare` 重试，但主动传参比依赖兜底更可靠。

**其余全部由脚本自动处理，Agent 不需要判断**:
- 目录不是 git 仓库 + 有 `--git-url` → 自动 clone
- 目录不是 git 仓库 + 无 `--git-url` → 报错，此时才需要询问用户提供 git URL
- `--base-ref` 存在 → 自动设 `scope=compare`；不存在 → 自动设 `scope=unstaged`
- `scope=unstaged` 且检测到 0 个变更符号 → 自动推断 `base-ref`（`origin/master` / `origin/main` / `origin/develop`）并以 `scope=compare` 重试
- gitnexus 索引缺失或过期 → 自动运行 `gitnexus analyze`
- gitnexus repo label repo 与目录名不匹配 → 自动从 remote URL 精确查找并重试

## 第二步：调用 pipeline

```bash
# 分析分支差异（有基准分支时）
python <skill_dir>/scripts/run_pipeline.py [repo_path] \
 --base-ref origin/master \
 [--git-url ssh://git@github.com/your-org/your-repo.git]

# 分析未提交改动（无基准分支时）
python <skill_dir>/scripts/run_pipeline.py [repo_path]
```

脚本会在 `[repo_path]/code-impact-regression/` 下生成结果文件，分析完成后进入第三步。

## 第三步：解读结果

Pipeline 完成后，读取 `summary.json` 并用自然语言向用户解读：
- 影响范围摘要（哪些模块/接口受影响）
- 推荐回归的分层测试集（按优先级）
- 当前无测试覆盖的风险点

如遇报错，参考 `summary.json` 中的 `errors` 字段定位问题。

pipeline 会自动完成: detect_changes → impact 分析 → 测试召回 → 排序 → 覆盖报告 → 执行计划，所有产物写入 '--work-dir'（默认当前目录下的 'impact-regression-<timestamp>/')。
**阈值调整**: 如果仓库测试命名以中文/业务词为主，可降低 '--high-threshold'（默认 0.75）和 '--medium-threshold'（默认 0.45）。

## 第三步：解读结果
pipeline 完成后读取 'summary.json'，按以下结构向用户输出:
**1. 变更范围**: 'change_summary' 中的 'seed_symbols'（直接变更的符号）、'changed_files_count'、'expanded_risk'（综合风险等级）、'max_impact_depth'（影响链路深度）。
**2. 推荐回归用例**: 'test_candidates' 中 high/medium/low 各层数量，重点列出 'high_names'（高相关用例名）。
**3. 覆盖缺口**: 'coverage_uncovered_points' 列出没有找到对应测试的影响点，按 depth 和 risk 排序提示优先级。
**4. 执行计划**: 'execution_plan' 中 'repo_auto_count'（可直接跑的工程内测试数）、'manual_followup_count'（需人工跟进数）、'needs_case_generation'（是否建议补用例）。
**5. 详细报告**: 告知用户完整报告路径: 'unit-test-report.md'、'integration-test-report.md' 和 'execution-plan.md'。

## 失败处理
pipeline 失败时，'summary.json' 中 'pipeline_status' 为 'partial'，'failed_stages' 列出失败步骤。
- 'prepare:repo_check' 失败: 'repo_path' 不是 git 仓库且未提供 '--git-url'，需要询问用户提供 git URL。
- 'prepare:clone' 失败: clone 失败，查看 stderr，通常是网络或权限问题，告知用户。
- 'prepare:gitnexus_analyze' 失败: 索引构建失败，查看 stderr 告知用户。
- 'step:detect_and_expand_impact' 失败: repo label 自动匹配也失败（极少见），查看 stderr 告知用户。若 gitnexus 完全不可用，告知用户安装后重试。
- 其他步骤失败: 查看 'pipeline_notes' 中对应 stage 的 'stderr'，向用户同步错误现象和可选处理路径，不要擅自降级。

## gitnexus 环境准备
```bash
# 确认是否可用
gitnexus --version || npx -y gitnexus@latest --version

# 确认仓库索引状态
cd <repo_path> && gitnexus status

# 索引缺失或过期时重建
gitnexus analyze
```
## 脚本说明（Agent 不直接调用）

所有脚本位于 `<skill_dir>/scripts/`，由 `run_pipeline.py` 统一调度：

- `detect_and_expand_impact.py`：调用 gitnexus detect_changes + impact，生成 analysis.json
- `recall_test_candidates.py`：扫描仓库内测试文件，生成 candidates.json + impact-features.json
- `rank_test_candidates.py`：对候选打分分层，生成 ranked-output.json；第一个参数是 impact-features.json，不是 gitnexus 原始 impact 文件
- `build_coverage_report.py`：生成影响点覆盖关系报告
- `build_execution_plan.py`：生成回归执行计划