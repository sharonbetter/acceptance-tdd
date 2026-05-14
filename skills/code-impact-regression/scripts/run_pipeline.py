#!/usr/bin/env python3
"""
Pipeline 入口脚本：一次性串联完整分析流程。

流程：
1. detect_and_expand_impact → analysis.json + impact-features.json
2. recall_test_candidates → candidates.json
3. rank_test_candidates → ranked-output.json
4. build_coverage_report → unit-test-report.md + integration-test-report.md
5. build_execution_plan → execution-plan.md + execution-plan.json

所有中间产物写入 --work-dir（默认 <当前目录>/impact-regression-<timestamp>）。
最终输出：
- <work-dir>/unit-test-report.md 单测回归报告（影响点 × 单测用例）
- <work-dir>/integration-test-report.md 集成测试报告（接口入口 × 集成测试用例）
- <work-dir>/execution-plan.md
- <work-dir>/summary.json 供 Agent 读取并解读给用户

Agent 只需调用本脚本，然后读取 summary.json 和三个 Markdown 报告。
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


# -----------------------------------------------------------------------------
# 工具函数
# -----------------------------------------------------------------------------

def run_script(
 script: Path,
 args: List[str],
 label: str,
 notes: List[Dict[str, Any]],
) -> bool:
 """运行一个子脚本，失败时记录 note 并返回 False。"""
 cmd = [sys.executable, str(script)] + args
 print(f"[pipeline] {label} ...", flush=True)
 proc = subprocess.run(cmd, capture_output=True, text=True)
 if proc.returncode != 0:
 notes.append({
 "stage": label,
 "status": "failed",
 "returncode": proc.returncode,
 "stderr": (proc.stderr or "").strip()[-2000:],
 "stdout": (proc.stdout or "").strip()[-1000:],
 })
 print(f"[pipeline] {label} FAILED (rc={proc.returncode})", flush=True)
 print(proc.stderr or "", file=sys.stderr)
 return False
 notes.append({"stage": label, "status": "ok"})
 print(f"[pipeline] {label} OK", flush=True)
 return True


def load_json_safe(path: Path) -> Any:
 try:
 return json.loads(path.read_text(encoding="utf-8"))
 except Exception:
 return {}


def write_json(path: Path, payload: Any) -> None:
 path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


# -----------------------------------------------------------------------------
# 摘要提取：从各产物中提取关键数字，供 Agent 解读
# -----------------------------------------------------------------------------

def build_summary(
 work_dir: Path,
 notes: List[Dict[str, Any]],
 args: argparse.Namespace,
) -> Dict[str, Any]:
 analysis = load_json_safe(work_dir / "analysis.json")
 ranked = load_json_safe(work_dir / "ranked-output.json")
 coverage = load_json_safe(work_dir / "unit-test-report.json")
 integration = load_json_safe(work_dir / "integration-test-report.json")
 plan = load_json_safe(work_dir / "execution-plan.json")

 merged = (analysis.get("merged_summary") or {})
 coverage_summary = coverage.get("summary") or {}
 plan_summary = plan.get("summary") or {}

 # 变更信息
 seed_symbols: List[str] = merged.get("seed_symbols") or []
 changed_files_count = merged.get("changed_files")
 detect_risk = merged.get("detect_risk") or "unknown"
 expanded_risk = merged.get("expanded_risk") or detect_risk
 max_depth = merged.get("max_impact_depth") or 0

 # 候选测试
 ranked_candidates: List[Dict] = ranked.get("ranked_candidates") or []
 high = [c for c in ranked_candidates if c.get("tier") == "high"]
 medium = [c for c in ranked_candidates if c.get("tier") == "medium"]
 low = [c for c in ranked_candidates if c.get("tier") == "low"]

 # 单测覆盖情况
 impact_point_count = coverage_summary.get("impact_point_count", 0)
 covered_count = coverage_summary.get("covered_count", 0)
 uncovered_count = coverage_summary.get("uncovered_count", 0)
 coverage_ratio = coverage_summary.get("coverage_ratio", 0.0)

 # 未覆盖影响点列表（供 Agent 重点提示）
 uncovered_points = [
 {
 "name": row.get("impact", {}).get("name"),
 "depth": row.get("impact", {}).get("depth"),
 "risk": row.get("impact", {}).get("risk"),
 "relation": row.get("impact", {}).get("relation"),
 }
 for row in (coverage.get("coverage") or [])
 if not row.get("covered")
 ]

 # 集成测试覆盖情况
 integration_summary_data = integration.get("summary") or {}
 integration_uncovered = [
 r.get("entry_method")
 for r in (integration.get("entry_point_coverage") or [])
 if not r.get("covered")
 ]

 # 执行计划
 repo_auto_count = plan_summary.get("repo_auto_count", 0)
 external_dispatch_count = plan_summary.get("external_dispatch_count", 0)
 manual_followup_count = plan_summary.get("manual_followup_count", 0)
 needs_case_generation = plan_summary.get("needs_case_generation", False)

 # pipeline 执行情况
 failed_stages = [n["stage"] for n in notes if n.get("status") == "failed"]

 return {
 "pipeline_status": "partial" if failed_stages else "complete",
 "failed_stages": failed_stages,
 "work_dir": str(work_dir),
 "reports": {
 "unit_test_report_md": str(work_dir / "unit-test-report.md"),
 "integration_test_report_md": str(work_dir / "integration-test-report.md"),
 "execution_plan_md": str(work_dir / "execution-plan.md"),
 },
 "change_summary": {
 "seed_symbols": seed_symbols,
 "changed_files_count": changed_files_count,
 "detect_risk": detect_risk,
 "expanded_risk": expanded_risk,
 "max_impact_depth": max_depth,
 "affected_processes": merged.get("affected_processes") or {},
 },
 "test_candidates": {
 "total": len(ranked_candidates),
 "high": len(high),
 "medium": len(medium),
 "low": len(low),
 "high_names": [c.get("name") for c in high[:10]],
 },
 "unit_test_coverage": {
 "impact_point_count": impact_point_count,
 "covered_count": covered_count,
 "uncovered_count": uncovered_count,
 "coverage_ratio": coverage_ratio,
 "uncovered_points": uncovered_points,
 },
 "integration_test_coverage": {
 "entry_point_count": integration_summary_data.get("entry_point_count", 0),
 "covered_count": integration_summary_data.get("covered_count", 0),
 "uncovered_count": integration_summary_data.get("uncovered_count", 0),
 "coverage_ratio": integration_summary_data.get("coverage_ratio", 0.0),
 "uncovered_entry_points": integration_uncovered,
 },
 "execution_plan": {
 "repo_auto_count": repo_auto_count,
 "external_dispatch_count": external_dispatch_count,
 "manual_followup_count": manual_followup_count,
 "needs_case_generation": needs_case_generation,
 },
 "pipeline_notes": notes,
 }


# -----------------------------------------------------------------------------
# 参数解析
# -----------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
 parser = argparse.ArgumentParser(
 description=(
 "One-shot pipeline: detect → recall → rank → coverage → execution plan.\n"
 "Agent calls this script once, then reads summary.json and the two Markdown reports."
 ),
 formatter_class=argparse.RawDescriptionHelpFormatter,
 )

 # 仓库路径：可选，默认当前工作目录
 parser.add_argument(
 "repo_path", nargs="?", default=".",
 help="Target repository path (default: current working directory)",
 )

 # 仓库来源：本地不存在时从 git URL clone
 parser.add_argument(
 "--git-url",
 help="Git remote URL; used to clone the repo if repo_path does not exist or is not a git repo",
 )

 # gitnexus 分析参数
 # --base-ref 存在时自动使用 scope=compare，否则默认 scope=unstaged
 parser.add_argument(
 "--base-ref",
 help="Base ref for comparison, e.g. main or origin/main. When provided, scope is automatically set to 'compare'.")
 parser.add_argument(
 "--scope", choices=["unstaged", "staged", "all", "compare"], default=None,
 help="Override detect changes scope. Usually not needed: scope is auto-inferred from --base-ref.")
 parser.add_argument(
 "--direction", default="upstream", choices=["upstream", "downstream"])
 parser.add_argument(
 "--depth", type=int, default=3, help="Impact analysis depth (default: 3)")
 parser.add_argument(
 "--max-symbols", type=int, default=20)

 # 排序阈值
 parser.add_argument(
 "--high-threshold", type=float, default=0.75)
 parser.add_argument(
 "--medium-threshold", type=float, default=0.45)

 # 执行参数（可选）
 parser.add_argument(
 "--repo-command", help="Test command for repo_auto execution, e.g. 'pytest -q'")
 parser.add_argument(
 "--apply", action="store_true", help="Actually run test commands")
 parser.add_argument(
 "--timeout", type=int, default=300)

 # 输出目录
 parser.add_argument(
 "--work-dir",
 help="Directory for all intermediate and final outputs. "
 "Defaults to <cwd>/impact-regression-<timestamp>",
 )

 return parser.parse_args()


# -----------------------------------------------------------------------------
# 辅助：从 "not found. Available: a, b, c" 错误信息中选最接近的 repo 名
# -----------------------------------------------------------------------------

def _get_git_remote_url(repo_path: Path) -> str:
 """读取仓库的 git remote origin URL，失败时返回空字符串。"""
 try:
 proc = subprocess.run(
 ["git", "remote", "get-url", "origin"],
 cwd=str(repo_path), capture_output=True, text=True, timeout=5,
 )
 return (proc.stdout or "").strip()
 except Exception:
 return ""


def _normalize_git_url(url: str) -> str:
 """标准化 git URL：去掉 .git 后缀、统一小写，方便比对。"""
 url = url.strip().lower()
 if url.endswith(".git"):
 url = url[:-4]
 return url


def _pick_repo_by_git_url(git_url: str, available: List[str]) -> Optional[str]:
 """
 遍历 gitnexus list 输出，获取 label → path 映射，
 读取各自的 git remote origin URL，与 git_url 精确比对。
 找到匹配的返回其 label，否则返回 None。
 """
 if not git_url:
 return None

 # 解析 gitnexus list 输出，获取 label → path 映射
 try:
 proc = subprocess.run(
 ["gitnexus", "list"], capture_output=True, text=True, timeout=10,
 )
 output = proc.stdout or ""
 except Exception:
 return None

 # 解析格式：每个 repo 块以 " <label>" 开头，下一行 " Path: <path>"
 import re as _re
 label_path_pairs: List[tuple] = []
 current_label: Optional[str] = None
 for line in output.splitlines():
 label_m = _re.match(r"^ ([^\s]+)$", line)
 path_m = _re.match(r"^\s+Path:\s+(.+)$", line)
 if label_m:
 current_label = label_m.group(1).strip()
 elif path_m and current_label:
 label_path_pairs.append((current_label, path_m.group(1).strip()))
 current_label = None

 target_url = _normalize_git_url(git_url)
 for label, path in label_path_pairs:
 remote_url = _get_git_remote_url(Path(path))
 if remote_url and _normalize_git_url(remote_url) == target_url:
 return label

 return None


def _pick_repo_from_available(stderr: str, dir_name: str, git_url: str = "") -> Optional[str]:
 """
 从 gitnexus 的 'not found. Available: a, b, c' 错误中找到正确的 repo label。
 匹配优先级：
 1. git remote URL 精确匹配（最可靠，用用户提供的 git_url）
 2. normalize 后目录名精确匹配（忽略大小写、下划线/连字符差异）
 3. 包含匹配（兜底）
 """
 import re as _re
 m = _re.search(r"Available:\s*(.+)", stderr)
 if not m:
 return None
 available = [s.strip().rstrip(".") for s in m.group(1).split(",") if s.strip()]
 if not available:
 return None

 # 优先：git URL 精确匹配
 if git_url:
 result = _pick_repo_by_git_url(git_url, available)
 if result:
 return result

 def normalize(s: str) -> str:
 return s.lower().replace("-", "").replace("_", "")

 target = normalize(dir_name)
 # 次优：normalize 后精确匹配
 for name in available:
 if normalize(name) == target:
 return name
 # 兜底：包含匹配
 for name in available:
 if target in normalize(name) or normalize(name) in target:
 return name
 return None


# -----------------------------------------------------------------------------
# 仓库准备：确保 repo_path 是有效 git 仓库，gitnexus 索引存在且最新
# -----------------------------------------------------------------------------

def _is_git_repo(path: Path) -> bool:
 """判断目录是否是有效的 git 仓库。"""
 try:
 proc = subprocess.run(
 ["git", "rev-parse", "--git-dir"],
 cwd=str(path), capture_output=True, text=True, timeout=5,
 )
 return proc.returncode == 0
 except Exception:
 return False


def _clone_repo(git_url: str, target_path: Path, notes: List[Dict[str, Any]]) -> bool:
 """将 git_url clone 到 target_path，返回是否成功。"""
 print(f"[pipeline] cloning {git_url} → {target_path}", flush=True)
 target_path.mkdir(parents=True, exist_ok=True)
 proc = subprocess.run(
 ["git", "clone", git_url, str(target_path)],
 capture_output=True, text=True,
 )
 if proc.returncode != 0:
 notes.append({
 "stage": "prepare:clone",
 "status": "failed",
 "returncode": proc.returncode,
 "stderr": (proc.stderr or "").strip(),
 })
 print(f"[pipeline] clone FAILED: {proc.stderr}", flush=True)
 return False
 notes.append({"stage": "prepare:clone", "status": "ok", "url": git_url})
 print(f"[pipeline] clone OK", flush=True)
 return True


def _ensure_gitnexus_index(repo_path: Path, notes: List[Dict[str, Any]]) -> bool:
 """
 检查 gitnexus 索引状态：
 - up-to-date: 直接返回 True
 - 不存在或过期：自动运行 gitnexus analyze，返回是否成功
 """
 print(f"[pipeline] checking gitnexus index ...", flush=True)
 proc = subprocess.run(
 ["gitnexus", "status"],
 cwd=str(repo_path), capture_output=True, text=True, timeout=30,
 )
 output = (proc.stdout or "") + (proc.stderr or "")
 if proc.returncode == 0 and "up-to-date" in output:
 print(f"[pipeline] gitnexus index up-to-date", flush=True)
 notes.append({"stage": "prepare:gitnexus_index", "status": "ok", "detail": "up-to-date"})
 return True

 # 索引不存在或过期，自动重建
 print(f"[pipeline] gitnexus index missing or stale, running analyze ...", flush=True)
 analyze_proc = subprocess.run(
 ["gitnexus", "analyze"],
 cwd=str(repo_path), capture_output=True, text=True, timeout=30,
 )
 if analyze_proc.returncode != 0:
 notes.append({
 "stage": "prepare:gitnexus_analyze",
 "status": "failed",
 "returncode": analyze_proc.returncode,
 "stderr": (analyze_proc.stderr or "").strip()[-2000:],
 })
 print(f"[pipeline] gitnexus analyze FAILED", flush=True)
 return False
 notes.append({"stage": "prepare:gitnexus_analyze", "status": "ok"})
 print(f"[pipeline] gitnexus analyze OK", flush=True)
 return True


# -----------------------------------------------------------------------------
# 辅助：自动推断 base-ref（当 scope=unstaged 且 changed_symbols=0 时兜底）
# -----------------------------------------------------------------------------

def _infer_base_ref(repo_path: Path) -> Optional[str]:
 """
 当 scope=unstaged 检测不到变更时，尝试自动推断合适的 base-ref。
 策略：
 1. 找出当前分支相对各远端主干分支（origin/master、origin/main、origin/develop）
 有多少提交差异，取差异最小且 >0 的那个作为 base-ref。
 2. 如果都没有差异，返回 None（说明确实没有变更）。
 """
 candidates = ["origin/master", "origin/main", "origin/develop"]
 best: Optional[str] = None
 best_count = 0

 for ref in candidates:
 try:
 proc = subprocess.run(
 ["git", "rev-list", "--count", f"{ref}..HEAD"],
 cwd=str(repo_path), capture_output=True, text=True, timeout=10,
 )
 if proc.returncode != 0:
 continue
 count = int((proc.stdout or "0").strip())
 if count > 0 and (best is None or count < best_count):
 best = ref
 best_count = count
 except Exception:
 continue
 return best


def _count_changed_symbols(analysis_json: Path) -> int:
 """读取 analysis.json，返回 changed_symbols 数量；读取失败返回 0。"""
 try:
 data = json.loads(analysis_json.read_text(encoding="utf-8"))
 syms = (data.get("detect_changes") or {}).get("changed_symbols") or []
 return len(syms)
 except Exception:
 return 0


# -----------------------------------------------------------------------------
# 主流程
# -----------------------------------------------------------------------------

def main() -> int:
 args = parse_args()
 scripts_dir = Path(__file__).parent.resolve()

 # 确定工作目录
 if args.work_dir:
 work_dir = Path(args.work_dir).expanduser().resolve()
 else:
 work_dir = Path.cwd() / f"impact-regression-{int(time.time())}"
 work_dir.mkdir(parents=True, exist_ok=True)
 print(f"[pipeline] work_dir = {work_dir}", flush=True)

 repo_path = Path(args.repo_path).expanduser().resolve()
 notes: List[Dict[str, Any]] = []

 # scope 自动推断：有 --base-ref 则 compare，否则 unstaged
 effective_scope = args.scope or ("compare" if args.base_ref else "unstaged")
 print(f"[pipeline] scope = {effective_scope}" + (f" (base-ref: {args.base_ref})" if args.base_ref else ""), flush=True)

 # -------------------------------------------------------------------------
 # 准备阶段：确保仓库存在 + gitnexus 索引就绪
 # -------------------------------------------------------------------------

 # 1. 仓库不存在或不是 git 仓库时，尝试 clone
 if not repo_path.exists() or not _is_git_repo(repo_path):
 git_url = args.git_url or ""
 if not git_url:
 print(
 f"[pipeline] ERROR: {repo_path} is not a git repository and --git-url is not provided.",
 file=sys.stderr,
 )
 notes.append({
 "stage": "prepare:repo_check",
 "status": "failed",
 "error": f"{repo_path} is not a git repository. Please provide --git-url to clone it.",
 })
 write_json(work_dir / "summary.json", build_summary(work_dir, notes, args))
 return 1
 if not _clone_repo(git_url, repo_path, notes):
 write_json(work_dir / "summary.json", build_summary(work_dir, notes, args))
 return 1

 # 2. 确保 gitnexus 索引存在且最新
 if not _ensure_gitnexus_index(repo_path, notes):
 write_json(work_dir / "summary.json", build_summary(work_dir, notes, args))
 return 1

 # -------------------------------------------------------------------------
 # Step 1: detect_and_expand_impact → analysis.json
 # -------------------------------------------------------------------------
 analysis_json = work_dir / "analysis.json"
 step1_args = [str(repo_path), str(analysis_json),
 "--scope", effective_scope,
 "--direction", args.direction,
 "--depth", str(args.depth),
 "--max-symbols", str(args.max_symbols)]
 if args.base_ref:
 step1_args += ["--base-ref", args.base_ref]

 if not run_script(scripts_dir / "detect_and_expand_impact.py", step1_args,
 "step1:detect_and_expand_impact", notes):
 # 自动恢复：若错误是 repo label not found，从本地 remote URL 精确匹配后重试
 last_note = notes[-1] if notes else {}
 stderr = last_note.get("stderr", "")
 local_git_url = _get_git_remote_url(repo_path)
 recovered_repo = _pick_repo_from_available(stderr, repo_path.name, git_url=local_git_url)
 if recovered_repo:
 print(f"[pipeline] auto-retry step1 with --repo {recovered_repo}", flush=True)
 notes.pop()
 retry_args = step1_args + ["--repo", recovered_repo]
 if not run_script(scripts_dir / "detect_and_expand_impact.py", retry_args,
 "step1:detect_and_expand_impact", notes):
 write_json(work_dir / "summary.json", build_summary(work_dir, notes, args))
 return 1
 else:
 write_json(work_dir / "summary.json", build_summary(work_dir, notes, args))
 return 1

 # 自动兜底：scope=unstaged 且 changed_symbols=0 时，尝试推断 base-ref 重跑
 # 仅在用户未显式指定 --scope 和 --base-ref 时触发，避免覆盖用户意图
 if (
 not args.scope # 用户未显式指定 --scope
 and not args.base_ref # 用户未显式指定 --base-ref
 and effective_scope == "unstaged"
 and _count_changed_symbols(analysis_json) == 0
 ):
 inferred_ref = _infer_base_ref(repo_path)
 if inferred_ref:
 print(
 f"[pipeline] scope=unstaged detected 0 changed symbols; "
 f"auto-retrying with --base-ref {inferred_ref} (scope=compare)",
 flush=True,
 )
 notes.append({
 "stage": "step1:auto_scope_fallback",
 "status": "ok",
 "detail": f"unstaged found 0 symbols; auto-switched to scope=compare base-ref={inferred_ref}",
 })
 effective_scope = "compare"
 retry_step1_args = [str(repo_path), str(analysis_json),
 "--scope", "compare",
 "--base-ref", inferred_ref,
 "--direction", args.direction,
 "--depth", str(args.depth),
 "--max-symbols", str(args.max_symbols)]
 if not run_script(scripts_dir / "detect_and_expand_impact.py", retry_step1_args,
 "step1:detect_and_expand_impact(compare)", notes):
 write_json(work_dir / "summary.json", build_summary(work_dir, notes, args))
 return 1
 # 更新 step1_args 供后续步骤引用（实际后续步骤只用 analysis_json 文件，不用 step1_args）
 step1_args = retry_step1_args
 else:
 print(
 "[pipeline] scope=unstaged detected 0 changed symbols and no diverged remote branch found; "
 "proceeding with empty change set.",
 flush=True,
 )
 notes.append({
 "stage": "step1:auto_scope_fallback",
 "status": "skipped",
 "detail": "unstaged found 0 symbols; no diverged remote branch detected, keeping empty result",
 })

 # -------------------------------------------------------------------------
 # Step 2: recall_test_candidates → candidates.json + impact-features.json
 # -------------------------------------------------------------------------
 candidates_json = work_dir / "candidates.json"
 impact_features_json = work_dir / "impact-features.json"
 step2_args = [str(analysis_json), str(repo_path), str(candidates_json),
 "--output-impact", str(impact_features_json)]
 if not run_script(scripts_dir / "recall_test_candidates.py", step2_args,
 "step2:recall_test_candidates", notes):
 write_json(work_dir / "summary.json", build_summary(work_dir, notes, args))
 return 1

 # -------------------------------------------------------------------------
 # Step 3: rank_test_candidates → ranked-output.json
 # -------------------------------------------------------------------------
 ranked_json = work_dir / "ranked-output.json"
 step3_args = [str(impact_features_json), str(candidates_json), str(ranked_json),
 "--high-threshold", str(args.high_threshold),
 "--medium-threshold", str(args.medium_threshold)]
 if not run_script(scripts_dir / "rank_test_candidates.py", step3_args,
 "step3:rank_test_candidates", notes):
 write_json(work_dir / "summary.json", build_summary(work_dir, notes, args))
 return 1

 # -------------------------------------------------------------------------
 # Step 4: build_coverage_report → unit-test-report.md + integration-test-report.md
 # -------------------------------------------------------------------------
 unit_test_md = work_dir / "unit-test-report.md"
 integration_test_md = work_dir / "integration-test-report.md"
 unit_json_path = work_dir / "unit-test-report.json"
 integration_json_path = work_dir / "integration-test-report.json"
 step4_args = [
 str(analysis_json), str(ranked_json),
 str(unit_test_md), str(integration_test_md),
 "--output-json", str(unit_json_path),
 "--output-integration-json", str(integration_json_path),
 ]
 if not run_script(scripts_dir / "build_coverage_report.py", step4_args,
 "step4:build_coverage_report", notes):
 write_json(work_dir / "summary.json", build_summary(work_dir, notes, args))
 return 1

 # -------------------------------------------------------------------------
 # Step 5: build_execution_plan → execution-plan.md + execution-plan.json
 # -------------------------------------------------------------------------
 plan_md = work_dir / "execution-plan.md"
 plan_json_path = work_dir / "execution-plan.json"
 step5_args = [str(ranked_json), str(unit_json_path), str(plan_md),
 "--output-json", str(plan_json_path),
 "--integration-json", str(integration_json_path),
 "--analysis-json", str(analysis_json)]
 if not run_script(scripts_dir / "build_execution_plan.py", step5_args,
 "step5:build_execution_plan", notes):
 write_json(work_dir / "summary.json", build_summary(work_dir, notes, args))
 return 1

 # 写入 summary.json
 summary = build_summary(work_dir, notes, args)
 write_json(work_dir / "summary.json", summary)

 print(f"[pipeline] Done. summary → {work_dir / 'summary.json'}", flush=True)
 print(f"[pipeline] unit-test → {unit_test_md}", flush=True)
 print(f"[pipeline] integration → {integration_test_md}", flush=True)
 print(f"[pipeline] plan → {plan_md}", flush=True)
 return 0


if __name__ == "__main__":
 raise SystemExit(main())