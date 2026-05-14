#!/usr/bin/env python3
"""
执行层脚本: 读取执行计划, 生成或实际执行回归测试命令。

优化点:
- supply 模式下为 subprocess.run 添加 timeout 参数 (默认 300 秒),
  避免测试命令挂起导致脚本无限阻塞
- 超时时记录 status = "timeout" 而不是让进程挂死
- 通过 --timeout 参数允许用户自定义超时时间
"""
import argparse
import json
import shlex
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float, bool)):
        return str(value)
    return json.dumps(value, ensure_ascii=False)


def run_cmd(command: List[str], cwd: Path, timeout: int) -> subprocess.CompletedProcess:
    return subprocess.run(command, cwd=str(cwd), capture_output=True, text=True, timeout=timeout)


def load_repo_command_map(path: Optional[Path]) -> Dict[str, str]:
    if not path:
        return {}
    payload = load_json(path)
    if not isinstance(payload, dict):
        raise ValueError("repo command map must be a json object")
    result: Dict[str, str] = {}
    for key, value in payload.items():
        if isinstance(key, str) and isinstance(value, str) and key.strip() and value.strip():
            result[key.strip()] = value.strip()
    return result


def select_repo_command(candidate: Dict[str, Any], command_map: Dict[str, str], default_command: str) -> str:
    path = stringify(candidate.get("path"))
    name = stringify(candidate.get("name"))
    for key, value in command_map.items():
        if key in path or key in name:
            return value
    if default_command:
        return default_command
    return ""


def build_repo_execution_item(candidate: Dict[str, Any], command_map: Dict[str, str], default_command: str) -> Dict[str, Any]:
    command = select_repo_command(candidate, command_map, default_command)
    return {
        "name": candidate.get("name"),
        "path": candidate.get("path"),
        "tier": candidate.get("tier"),
        "score": candidate.get("score"),
        "execution_mode": "repo_auto",
        "command": command,
        "status": "planned" if command else "missing_command",
        "message": "已生成工程内执行命令" if command else "未提供工程内执行命令映射, 暂不自动执行",
    }


def execute_planned_item(item: Dict[str, Any], cwd: Path, timeout: int) -> Dict[str, Any]:
    """
    执行单个计划。
    - 对 subprocess.run 设置 timeout, 超时时记录 status = "timeout", 不让进程挂死。
    - timeout 默认 300 秒, 可通过 --timeout 参数调整。
    """
    command = item.get("command")
    if not command:
        item["status"] = "skipped"
        return item

    try:
        if isinstance(command, str):
            proc = subprocess.run(
                command, cwd=str(cwd), shell=True,
                capture_output=True, text=True, timeout=timeout,
            )
            item["command_display"] = command
        else:
            proc = run_cmd(command, cwd, timeout)
            item["command_display"] = " ".join(shlex.quote(part) for part in command)

        item["returncode"] = proc.returncode
        item["stdout"] = (proc.stdout or "").strip()
        item["stderr"] = (proc.stderr or "").strip()
        item["status"] = "success" if proc.returncode == 0 else "failed"
    except subprocess.TimeoutExpired:
        item["status"] = "timeout"
        item["message"] = f"命令执行超时 (超过 {timeout} 秒), 已终止。可通过 --timeout 参数调整超时时间。"
        item["returncode"] = None

    return item


def build_followups(execution_plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    followups: List[Dict[str, Any]] = []
    for item in execution_plan.get("generation_recommendations", []) or []:
        if not isinstance(item, dict):
            continue
        followups.append({
            "type": "coverage_gap",
            "impact_name": item.get("impact_name"),
            "path": item.get("path"),
            "recommendation": item.get("recommendation"),
            "suggested_asset_type": item.get("suggested_asset_type"),
            "status": "pending_manual_confirmation"
        })
    for item in execution_plan.get("execution_groups", {}).get("manual_followups", []) or []:
        if not isinstance(item, dict):
            continue
        followups.append({
            "type": "manual_case",
            "name": item.get("name"),
            "path": item.get("path"),
            "reason": item.get("execution_reason"),
            "status": "manual_or_e2e_gap",
        })
    return followups


def render_markdown(result: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append("# 回归执行结果")
    lines.append("")
    lines.append("## 总览")
    lines.append("")
    summary = result.get("summary", {}) or {}
    lines.append(f"- 已计划工程内执行: {summary.get('repo_planned', 0)}")
    lines.append(f"- 成功执行项: {summary.get('success_count', 0)}")
    lines.append(f"- 执行失败项: {summary.get('failed_count', 0)}")
    lines.append(f"- 执行超时项: {summary.get('timeout_count', 0)}")
    lines.append(f"- 需人工跟进项: {summary.get('manual_followup_count', 0)}")
    lines.append("")

    lines.append("## 工程内执行项")
    lines.append("")
    repo_results = result.get("repo_results", []) or []
    if not repo_results:
        lines.append("当前没有工程内执行项。")
    else:
        for item in repo_results:
            lines.append(
                f"- `{item.get('name')}` (`{item.get('path')}`), "
                f"状态={item.get('status')}, 命令={item.get('command_display') or item.get('command') or ''}"
            )
    lines.append("")

    lines.append("## 手工跟进与缺口")
    lines.append("")
    followups = result.get("followups", []) or []
    if not followups:
        lines.append("当前没有额外手工跟进项。")
    else:
        for item in followups:
            if item.get("type") == "coverage_gap":
                lines.append(
                    f"- 未覆盖影响点: `{item.get('impact_name')}` (`{item.get('path')}`), "
                    f"建议={item.get('recommendation')}, 资产形态={item.get('suggested_asset_type')}, 状态={item.get('status')}"
                )
            else:
                lines.append(
                    f"- 手工/E2E 缺口: `{item.get('name')}` (`{item.get('path')}`), "
                    f"原因={item.get('reason')}, 状态={item.get('status')}"
                )
    lines.append("")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Execute or dry-run a regression execution plan.")
    parser.add_argument("execution_plan_json", help="execution plan json generated by build_execution_plan.py")
    parser.add_argument("--output-json", help="optional execution result json path")
    parser.add_argument("--output-md", help="output markdown result path")
    parser.add_argument("--repo-path", required=True, help="repository path used as cwd for repo execution commands")
    parser.add_argument("--repo-command", help="default repo command used for repo_auto candidates, e.g. 'pytest -q' or 'npm test --'")
    parser.add_argument("--repo-command-map", help="json file that maps path/name keyword to command")
    parser.add_argument("--apply", action="store_true", help="actually run commands instead of only generating them")
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help=(
            "Timeout in seconds for each command when --apply is set (default: 300). "
            "Commands exceeding this limit will be marked as 'timeout' instead of hanging indefinitely."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    execution_plan_path = Path(args.execution_plan_json).expanduser().resolve()
    output_md = Path(args.output_md).expanduser().resolve() if args.output_md else None
    output_json = Path(args.output_json).expanduser().resolve() if args.output_json else None
    repo_path = Path(args.repo_path).expanduser().resolve()

    execution_plan = load_json(execution_plan_path)
    command_map = (
        load_repo_command_map(Path(args.repo_command_map).expanduser().resolve())
        if args.repo_command_map
        else {}
    )

    repo_candidates = execution_plan.get("execution_groups", {}).get("repo_auto", []) or []

    repo_results = []
    for candidate in repo_candidates:
        if isinstance(candidate, dict):
            item = build_repo_execution_item(candidate, command_map, args.repo_command or "")
            repo_results.append(item)

    if args.apply:
        repo_results = [execute_planned_item(item, repo_path, args.timeout) for item in repo_results]
    else:
        for item in repo_results:
            cmd = item.get("command")
            if isinstance(cmd, str):
                item["command_display"] = cmd
            elif isinstance(cmd, list):
                item["command_display"] = " ".join(shlex.quote(part) for part in cmd)
            else:
                item["command_display"] = ""

    followups = build_followups(execution_plan)

    success_count = sum(1 for r in repo_results if r.get("status") == "success")
    failed_count = sum(1 for r in repo_results if r.get("status") == "failed")
    timeout_count = sum(1 for r in repo_results if r.get("status") == "timeout")

    result = {
        "execution_plan_source": str(execution_plan_path),
        "repo_path": str(repo_path),
        "apply": args.apply,
        "timeout": args.timeout,
        "summary": {
            "repo_planned": len(repo_results),
            "success_count": success_count,
            "failed_count": failed_count,
            "timeout_count": timeout_count,
            "manual_followup_count": len(followups),
        },
        "repo_results": repo_results,
        "followups": followups,
    }

    if output_md:
        output_md.write_text(render_markdown(result), encoding="utf-8")
    if output_json:
        write_json(output_json, result)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())