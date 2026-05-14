#!/usr/bin/env python3
import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

AUTO_EXECUTION_TYPES = {"test_case", "test_file", "external_case"}
AUTO_EXTERNAL_SOURCE_TYPES = set()
MANUAL_SOURCE_TYPES = {"external_json", "manual_case", "doc_case", "e2e_manual"}


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def unique_list(items: List[str]) -> List[str]:
    seen: Set[str] = set()
    ordered: List[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def build_candidate_index(ranked_payload: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    ranked_candidates = ranked_payload.get("ranked_candidates", []) or []
    index: Dict[str, Dict[str, Any]] = {}
    for candidate in ranked_candidates:
        if not isinstance(candidate, dict):
            continue
        key = candidate_key(candidate)
        if key:
            index[key] = candidate
    return index


def candidate_key(candidate: Dict[str, Any]) -> str:
    if not isinstance(candidate, dict):
        return ""
    external_ids = candidate.get("external_ids", {}) or {}
    if isinstance(external_ids, dict):
        case_id = external_ids.get("case_id") or external_ids.get("fst_case_id")
        if case_id:
            return f"external:{case_id}"
    path = candidate.get("path") or ""
    name = candidate.get("name") or ""
    return f"{path}::{name}"


def classify_candidate(candidate: Dict[str, Any]) -> Dict[str, Any]:
    candidate_type = candidate.get("candidate_type") or ""
    source_type = candidate.get("source_type") or ""
    path = candidate.get("path") or ""

    if source_type in MANUAL_SOURCE_TYPES:
        execution_mode = "manual"
        reason = "候选来源本身是手工或文档型测试资产，默认不自动执行"
    if candidate_type in {"test_case", "test_file"}:
        execution_mode = "repo_auto"
        reason = "候选来自工程内测试资产，可由工程内测试命令或 CI 触发执行"
    else:
        execution_mode = "manual"
        reason = "无法可靠映射到自动执行入口，需要人工确认"

    return {
        "execution_mode": execution_mode,
        "reason": reason,
    }


def build_coverage_lookup(coverage_payload: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    lookup: Dict[str, List[Dict[str, Any]]] = {}
    for row in coverage_payload.get("coverage", []) or []:
        if not isinstance(row, dict):
            continue
        impact = row.get("impact", {}) or {}
        impact_name = impact.get("name") or ""
        if impact_name:
            lookup[impact_name] = row.get("matched_candidates", []) or []
    return lookup


def query_changed_files_in_process(process_id: str, repo_path: str, repo_name: str, changed_files: set) -> List[str]:
    """
    查询 Process 调用链中哪些步骤文件引用了变更文件。
    通过 File 节点的 CodeRelation 关系：调用链步骤文件 → 变更文件。
    返回去重后的变更文件名简写列表（去掉路径前缀和 .java 后缀）。
    """
    if not changed_files:
        return []

    # 构造 IN 列表字符串
    files_list = ", ".join(f"'{f}'" for f in sorted(changed_files))
    cypher = (
        f"MATCH (p:Process {{id: '{process_id}'}})<-[:CodeRelation]-(step), "
        f"(stepFile:File {{filePath: step.filePath}})-[:CodeRelation]->(changedFile:File) "
        f"WHERE changedFile.filePath IN [{files_list}] "
        f"RETURN changedFile.filePath"
    )

    try:
        proc = subprocess.run(
            ["gitnexus", "cypher", "--repo", repo_name, "--cypher", cypher],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=20,
        )
        stdout = (proc.stdout or "").strip()
        if not stdout:
            return []
        parsed = json.loads(stdout)
        if not isinstance(parsed, dict):
            return []
        md = parsed.get("markdown", "")
        result: List[str] = []
        seen: set = set()
        for line in md.split("\n"):
            line = line.strip()
            if not line.startswith("|") or "----" in line or "changedFile" in line:
                continue
            parts = [p.strip() for p in line.strip("|").split("|")]
            if not parts:
                continue
            fp = parts[0]
            if not fp or fp in seen:
                continue
            seen.add(fp)
            short = fp.split("/")[-1].replace(".java", "")
            result.append(short)
        return result
    except Exception:
        return []


def build_interface_e2e_items(
    integration_payload: Dict[str, Any],
    analysis_payload: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    从 integration-test-report.json 的未覆盖 entrypoint 生成接口/E2E 验证项。
    每条附上调用链中命中变更文件的节点（涉及变更点）。
    """
    # 变更文件集合
    detect = analysis_payload.get("detect_changes", {}) or {}
    changed_files = set()
    for sym in detect.get("changed_symbols", []) or []:
        if isinstance(sym, dict) and sym.get("file"):
            changed_files.add(sym["file"])

    # entry_method → process_id 映射
    affected_processes = (
        analysis_payload.get("merged_summary", {}).get("affected_processes")
        or analysis_payload.get("affected_processes")
        or {}
    )
    ep_to_proc: Dict[str, str] = {}
    for ep in affected_processes.get("entry_points") or []:
        if ep.get("entry_method") and ep.get("process_id"):
            ep_to_proc[ep["entry_method"]] = ep["process_id"]

    repo_path = analysis_payload.get("repo_path", ".")
    repo_name = analysis_payload.get("repo", Path(repo_path).name)

    items: List[Dict[str, Any]] = []
    for row in (integration_payload.get("entry_point_coverage") or []):
        if not isinstance(row, dict) or row.get("covered"):
            continue
        entry_method = row.get("entry_method", "")
        label = row.get("label", "")
        process_id = ep_to_proc.get(entry_method, "")

        changed_points: List[str] = []
        if process_id and changed_files:
            changed_points = query_changed_files_in_process(
                process_id, repo_path, repo_name, changed_files
            )

        items.append({
            "entry_method": entry_method,
            "label": label,
            "changed_points": changed_points,
        })
    return items


def build_generation_recommendations(coverage_payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    recommendations: List[Dict[str, Any]] = []
    for row in coverage_payload.get("coverage", []) or []:
        if not isinstance(row, dict):
            continue
        if row.get("covered"):
            continue
        impact = row.get("impact", {}) or {}
        risk = impact.get("risk") or "unknown"
        relation = impact.get("relation") or "unknown"
        depth = impact.get("depth", 0)
        # 只保留 depth < 2 且有路径的影响点
        if depth >= 2:
            continue
        if not impact.get("path"):
            continue
        recommendation = "建议优先补自动化用例"
        recommendations.append({
            "impact_name": impact.get("name"),
            "impact_type": impact.get("impact_type"),
            "path": impact.get("path"),
            "relation": relation,
            "depth": depth,
            "risk": risk,
            "recommendation": recommendation,
            "suggested_asset_type": "auto_case",
        })
    return recommendations


def build_execution_groups(ranked_payload: Dict[str, Any]) -> Dict[str, Any]:
    ranked_candidates = ranked_payload.get("ranked_candidates", []) or []
    repo_auto: List[Dict[str, Any]] = []
    external_dispatch: List[Dict[str, Any]] = []
    manual_followups: List[Dict[str, Any]] = []

    for candidate in ranked_candidates:
        if not isinstance(candidate, dict):
            continue
        classified = classify_candidate(candidate)
        item = {
            "name": candidate.get("name"),
            "path": candidate.get("path"),
            "candidate_type": candidate.get("candidate_type"),
            "source_type": candidate.get("source_type"),
            "tier": candidate.get("tier"),
            "score": candidate.get("score"),
            "execution_mode": classified["execution_mode"],
            "execution_reason": classified["reason"],
            "external_ids": candidate.get("external_ids", {}),
            "interface_name": candidate.get("interface_name"),
        }
        if classified["execution_mode"] == "repo_auto":
            repo_auto.append(item)
        elif classified["execution_mode"] == "external_dispatch":
            external_dispatch.append(item)
        else:
            manual_followups.append(item)

    return {
        "repo_auto": repo_auto,
        "external_dispatch": external_dispatch,
        "manual_followups": manual_followups,
    }


def build_summary(
    execution_groups: Dict[str, Any],
    generation_recommendations: List[Dict[str, Any]],
    interface_e2e_items: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    repo_auto = execution_groups.get("repo_auto", []) or []
    external_dispatch = execution_groups.get("external_dispatch", []) or []
    manual_followups = execution_groups.get("manual_followups", []) or []
    return {
        "repo_auto_count": len(repo_auto),
        "external_dispatch_count": len(external_dispatch),
        "manual_followup_count": len(manual_followups),
        "coverage_gap_count": len(generation_recommendations),
        "interface_e2e_count": len(interface_e2e_items) if interface_e2e_items is not None else 0,
        "needs_case_generation": bool(generation_recommendations),
    }


def render_markdown_summary(
    summary: Dict[str, Any],
    execution_groups: Dict[str, Any],
    generation_recommendations: List[Dict[str, Any]],
    interface_e2e_items: Optional[List[Dict[str, Any]]] = None
) -> str:
    lines: List[str] = []
    lines.append("# 回归执行计划")
    lines.append("")
    lines.append("## 总体预览")
    lines.append(f"- 工程内自动执行候选数：{summary['repo_auto_count']}")
    lines.append(f"- 外部平台调度候选数：{summary['external_dispatch_count']}")
    lines.append(f"- 需人工跟进候选数：{summary['manual_followup_count']}")
    lines.append(f"- 需补充 auto-case 的影响点数：{summary['coverage_gap_count']}")
    lines.append(f"- 需补充接口/E2E 验证的入口数：{summary['interface_e2e_count']}")
    lines.append(f"- 是否建议补充新用例：{'是' if summary['needs_case_generation'] else '否'}")
    lines.append("")

    lines.append("## 工程内自动执行")
    repo_auto = execution_groups.get("repo_auto", []) or []
    if not repo_auto:
        lines.append("当前没有明确可由工程内测试命令直接执行的候选。")
    else:
        for item in repo_auto:
            lines.append(f"- `{item['name']}` (`{item['path']}`), 分层={item['tier']}, 得分={item['score']}, 原因: {item['execution_reason']}")
    lines.append("")

    lines.append("## 外部平台调度执行")
    external_dispatch = execution_groups.get("external_dispatch", []) or []
    if not external_dispatch:
        lines.append("当前没有明确可直接交给外部平台调度的候选。")
    else:
        for item in external_dispatch:
            external_ids = item.get("external_ids", {}) or {}
            case_id = external_ids.get("case_id") or external_ids.get("fst_case_id") or ""
            interface_name = item.get("interface_name") or ""
            lines.append(f"- `{item['name']}` (case_id={case_id}), 接口={interface_name}, 分层={item['tier']}, 得分={item['score']}, 原因: {item['execution_reason']}")
    lines.append("")

    lines.append("## 需补充 auto-case")
    if not generation_recommendations:
        lines.append("当前 depth < 2 的影响点均已有候选单测用例。")
    else:
        for recommendation in generation_recommendations:
            lines.append(
                f"- **未覆盖影响点** (depth={recommendation['depth']}, risk={recommendation['risk']}): "
                f"`{recommendation['impact_name']}` (`{recommendation['path']}`), "
                f"关系={recommendation['relation']}, 建议资产形态={recommendation['suggested_asset_type']}"
            )
    lines.append("")

    lines.append("## 需补充接口/E2E 验证")
    if not interface_e2e_items:
        lines.append("当前所有受影响的接口入口均已有测试覆盖。")
    else:
        for item in interface_e2e_items:
            changed_str = ", ".join(item["changed_points"]) if item["changed_points"] else "（未能匹配到变更点）"
            lines.append(f"- `{item['entry_method']}` — `{item['label']}`")
            lines.append(f"  涉及变更点: {changed_str}")
    lines.append("")

    lines.append("## 执行策略建议")
    lines.append("优先自动执行工程内测试；depth < 2 的未覆盖影响点补充 auto-case；接口/E2E 验证针对未覆盖的接口入口，每条已标注其调用链中涉及的变更点。\n")

    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an execution plan from ranked candidates and coverage report.")
    parser.add_argument("--ranked-json", help="ranked-output.json from rank_test_candidates.py")
    parser.add_argument("--coverage-json", help="unit-test-report.json from build_coverage_report.py --output-json")
    parser.add_argument("--output-md", help="output markdown execution plan path")
    parser.add_argument("--output-json", help="optional execution plan json path")
    parser.add_argument("--integration-json", help="integration-test-report.json from build_coverage_report.py --output-integration-json")
    parser.add_argument("--analysis-json", help="analysis.json from detect_and_expand_impact.py")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ranked_path = Path(args.ranked_json).expanduser().resolve()
    coverage_path = Path(args.coverage_json).expanduser().resolve()
    output_md = Path(args.output_md).expanduser().resolve()
    output_json = Path(args.output_json).expanduser().resolve() if args.output_json else None

    ranked_payload = load_json(ranked_path)
    coverage_payload = load_json(coverage_path)

    # 加载 integration coverage 和 analysis（可选，有则生成接口/E2E 验证项）
    integration_payload: Dict[str, Any] = {}
    analysis_payload: Dict[str, Any] = {}
    if args.integration_json:
        integration_path = Path(args.integration_json).expanduser().resolve()
        if integration_path.exists():
            integration_payload = load_json(integration_path)
    if args.analysis_json:
        analysis_path = Path(args.analysis_json).expanduser().resolve()
        if analysis_path.exists():
            analysis_payload = load_json(analysis_path)

    execution_groups = build_execution_groups(ranked_payload)
    generation_recommendations = build_generation_recommendations(coverage_payload)
    interface_e2e_items = build_interface_e2e_items(integration_payload, analysis_payload) if integration_payload and analysis_payload else []

    summary = build_summary(execution_groups, generation_recommendations, interface_e2e_items)

    payload = {
        "ranked_source": str(ranked_path),
        "coverage_source": str(coverage_path),
        "summary": summary,
        "execution_groups": execution_groups,
        "generation_recommendations": generation_recommendations,
        "interface_e2e_items": interface_e2e_items,
    }

    output_md.write_text(render_markdown_summary(summary, execution_groups, generation_recommendations, interface_e2e_items), encoding="utf-8")
    if output_json:
        write_json(output_json, payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())