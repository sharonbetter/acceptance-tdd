#!/usr/bin/env python3
"""
结果层脚本：将影响点与候选测试做覆盖匹配，生成两份报告。
- unit-test-report.md 单测报告：针对代码影响点（changed/impacted symbol）的单测用例召回
- integration-test-report.md 集成测试报告：针对受影响接口入口（Process entryPoint）的测试用例召回

优点点：
- 收紧覆盖判定逻辑：keyword 命中要求长度 > 3，避免 create/order 等短词导致覆盖率虚高
- 使用 utils.py 公共工具函数，消除重复代码
"""
import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from utils import normalize_text, tokenize, split_symbol, unique_list


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


# 通用停用词：包路径中的高频词，在同仓库所有文件都能命中，无区分度
_PATH_STOPWORDS = {
    "java", "main", "test", "src", "com", "org", "net", "io",
    "impl", "base", "abs", "abstract", "common", "util", "utils",
    "service", "controller", "facade", "dao", "mapper", "model",
    "dto", "vo", "po", "entity", "config", "handler", "factory",
    "manager", "helper", "builder", "converter", "adapter",
}


def _symbol_keywords(symbol_name: str) -> List[str]:
    """
    从符号名生成有区分度的关键词列表。
    只保留符号名本身及其驼峰/下划线拆分词，过滤掉路径停用词和长度 <= 3 的短词。
    不加文件路径分词，避免包路径词（com/java/main/service）污染覆盖判定。
    """
    raw = unique_list([symbol_name] + split_symbol(symbol_name))
    result = []
    for term in raw:
        normalized = normalize_text(term)
        if not normalized:
            continue
        if len(normalized) <= 3:
            continue
        if normalized in _PATH_STOPWORDS:
            continue
        result.append(normalized)
    return unique_list(result)


def candidate_text(candidate: Dict[str, Any]) -> str:
    """
    只取用例名和描述（断言/标签）做匹配文本，不加路径。
    路径词在同仓库所有文件都能命中，不应参与覆盖判定。
    """
    parts = [
        candidate.get("name", ""),
        candidate.get("case_name", ""),
        candidate.get("case_full_name", ""),
        candidate.get("description", ""),
        " ".join(candidate.get("assertions", []) or []),
        " ".join(candidate.get("covered_process_steps", []) or []),
    ]
    return normalize_text(" ".join(parts))


# -----------------------------------------------------------------------------
# 单测：影响点构建 & 覆盖匹配
# -----------------------------------------------------------------------------
def build_impact_points(analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
    points: List[Dict[str, Any]] = []
    detect = analysis.get("detect_changes", {}) or {}
    merged = analysis.get("merged_summary", {}) or {}
    impact_results = analysis.get("impact_results", []) or []

    for item in detect.get("changed_symbols", []) or []:
        if not isinstance(item, dict) or not item.get("name"):
            continue
        sym_name = item.get("name", "")
        points.append({
            "impact_type": "changed_symbol",
            "name": sym_name,
            "path": item.get("file", ""),
            "relation": "changed",
            "depth": 0,
            "risk": merged.get("detect_risk", "unknown"),
            "keywords": _symbol_keywords(sym_name),
        })

    for item in merged.get("impacted_symbols", []) or []:
        if not isinstance(item, dict) or not item.get("name"):
            continue
        sym_name = item.get("name", "")
        points.append({
            "impact_type": "impacted_symbol",
            "name": sym_name,
            "path": item.get("filePath", ""),
            "relation": item.get("relationType", "impacted"),
            "depth": item.get("depth", 0),
            "risk": merged.get("expanded_risk", merged.get("detect_risk", "unknown")),
            "keywords": _symbol_keywords(sym_name),
        })

    seen_targets = set()
    deduped: List[Dict[str, Any]] = []
    for point in points:
        key = (point["impact_type"], point["name"], point["path"], point["relation"], point["depth"])
        if key not in seen_targets:
            seen_targets.add(key)
            deduped.append(point)

    for result in impact_results:
        summary = result.get("summary", {}) or {}
        target = summary.get("target", {}) or {}
        target_name = target.get("name")
        if not target_name:
            continue
        target_key = ("impact_target", target_name, target.get("filePath", ""), summary.get("direction", ""), 0)
        if target_key in seen_targets:
            continue
        deduped.append({
            "impact_type": "impact_target",
            "name": target_name,
            "path": target.get("filePath", ""),
            "relation": summary.get("direction", "impact"),
            "depth": 0,
            "risk": summary.get("risk", merged.get("expanded_risk", "unknown")),
            "keywords": _symbol_keywords(target_name),
        })
        seen_targets.add(target_key)

    return deduped


def score_candidate_for_point(point: Dict[str, Any], candidate: Dict[str, Any]) -> Tuple[int, List[str], bool]:
    """
    判断候选用例是否覆盖某个影响点。
    覆盖判定策略（从严到宽，满足任一即视为覆盖）：
    1. 强匹配：影响符号名（normalize 后）直接出现在用例名或描述中
    2. 拆分词匹配：影响符号的有意义拆分词（过滤停用词和短词后）
       有 >= 2 个命中用例名/描述，且至少 1 个长度 >= 5
    """
    text = candidate_text(candidate)
    name_text = normalize_text(" ".join([
        candidate.get("name", ""),
        candidate.get("case_name", ""),
        candidate.get("case_full_name", ""),
    ]))

    evidence: List[str] = []
    score = 0
    strong_match = False

    sym_name = normalize_text(point.get("name", ""))
    if sym_name and len(sym_name) > 3 and sym_name not in _PATH_STOPWORDS:
        if sym_name in name_text:
            score += 6
            strong_match = True
            evidence.append(f"用例名命中符号 {point.get('name', '')}")
        elif sym_name in text:
            score += 4
            strong_match = True
            evidence.append(f"描述命中符号 {point.get('name', '')}")

    keyword_hits: List[str] = []
    for keyword in point.get("keywords", []):
        if keyword == sym_name:
            continue
        if keyword in name_text or keyword in text:
            score += 1
            keyword_hits.append(keyword)
            evidence.append(f"命中拆分词 {keyword}")

    meaningful_hits = [kw for kw in keyword_hits if len(kw) >= 5]
    # 判定覆盖条件：强匹配 或 满足拆分词条件
    covered = strong_match or (len(keyword_hits) >= 2 and len(meaningful_hits) >= 1)

    return score, unique_list(evidence), covered


def select_covering_candidates(
    points: List[Dict[str, Any]],
    ranked_candidates: List[Dict[str, Any]],
    max_cases: int,
) -> List[Dict[str, Any]]:
    coverage_rows: List[Dict[str, Any]] = []
    for point in points:
        matched: List[Dict[str, Any]] = []
        for candidate in ranked_candidates:
            score, reasons, covered = score_candidate_for_point(point, candidate)
            if score <= 0 or not covered:
                continue
            matched.append({
                "candidate": {
                    "name": candidate.get("name", ""),
                    "path": candidate.get("path", ""),
                    "tier": candidate.get("tier", ""),
                    "score": candidate.get("score", 0),
                    "candidate_type": candidate.get("candidate_type", ""),
                },
                "coverage_score": score,
                "coverage_reasons": reasons,
            })
        # 按覆盖得分降序、用例得分降序、用例名升序排序
        matched.sort(key=lambda item: (-item["coverage_score"], -item["candidate"]["score"], item["candidate"]["name"]))
        selected = matched[:max_cases]
        coverage_rows.append({
            "impact": point,
            "covered": bool(selected),
            "matched_candidates": selected,
        })
    return coverage_rows


def build_unit_summary(coverage_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    covered = [row for row in coverage_rows if row["covered"]]
    uncovered = [row for row in coverage_rows if not row["covered"]]
    return {
        "impact_point_count": len(coverage_rows),
        "covered_count": len(covered),
        "uncovered_count": len(uncovered),
        "coverage_ratio": round(len(covered) / len(coverage_rows), 3) if coverage_rows else 0.0,
    }


# -----------------------------------------------------------------------------
# 集成测试：接口入口覆盖匹配
# -----------------------------------------------------------------------------
def score_entry_point_for_candidate(entry_method: str, candidate: Dict[str, Any]) -> Tuple[int, List[str], bool]:
    """
    判断候选用例是否覆盖某个接口入口方法。
    """
    text = candidate_text(candidate)
    name_text = normalize_text(" ".join([
        candidate.get("name", ""),
        candidate.get("case_name", ""),
        candidate.get("case_full_name", ""),
    ]))

    evidence: List[str] = []
    score = 0
    covered = False

    entry_normalized = normalize_text(entry_method)
    if not entry_normalized:
        return score, evidence, covered

    # 强匹配：接口名直接命中
    if entry_normalized in name_text:
        score += 6
        covered = True
        evidence.append(f"用例名命中接口 {entry_method}")
    elif entry_normalized in text:
        score += 4
        covered = True
        evidence.append(f"描述命中接口 {entry_method}")

    # 拆分词匹配
    keywords = _symbol_keywords(entry_method)
    meaningful_hits = 0
    for kw in keywords:
        if kw in name_text or kw in text:
            score += 1
            meaningful_hits += 1
            evidence.append(f"命中接口拆分词 {kw}")

    # 拆分词覆盖条件：至少2个命中且至少1个长度≥5
    if meaningful_hits >= 2 and any(len(kw) >= 5 for kw in keywords if kw in text or kw in name_text):
        covered = True

    return score, unique_list(evidence), covered
    """
    判断候选用例是否覆盖某个接口入口方法。
    entry_method 格式如 'OrderController.create#1', 取 Class.method 部分做匹配。
    """
    raw = entry_method.split("#")[0]  # e.g. OrderController.create
    parts = raw.split(".")
    class_name = parts[0] if parts else raw
    method_name = parts[1] if len(parts) > 1 else ""

    text = candidate_text(candidate)
    name_text = normalize_text(" ".join([
        candidate.get("name", ""),
        candidate.get("case_name", ""),
        candidate.get("case_full_name", ""),
    ]))
    # 对接口入口匹配, 路径里的 Controller 类名有区分度 (不同 Controller 对应不同接口)
    path_text = normalize_text(candidate.get("path", ""))

    evidence: List[str] = []
    score = 0
    strong_match = False

    # 强匹配: 类名 (normalize) 直接命中用例名或路径
    class_norm = normalize_text(class_name)
    if class_norm and len(class_norm) > 4 and class_norm not in _PATH_STOPWORDS:
        if class_norm in name_text:
            score += 5
            strong_match = True
            evidence.append(f"用例命名中类名 {class_name}")
        elif class_norm in path_text:
            score += 4
            strong_match = True
            evidence.append(f"路径命中类名 {class_name}")
        elif class_norm in text:
            score += 3
            strong_match = True
            evidence.append(f"描述命中类名 {class_name}")

    # 方法名匹配
    method_norm = normalize_text(method_name)
    if method_norm and len(method_norm) > 3 and method_norm not in _PATH_STOPWORDS:
        if method_norm in name_text:
            score += 4
            strong_match = True
            evidence.append(f"用例命名中方法名 {method_name}")
        elif method_norm in text:
            score += 2
            evidence.append(f"描述命中方法名 {method_name}")

    # 拆分词匹配 (类名拆分)
    for kw in split_symbol(class_name):
        kw_norm = normalize_text(kw)
        if not kw_norm or len(kw_norm) <= 3 or kw_norm in _PATH_STOPWORDS:
            continue
        if kw_norm in name_text or kw_norm in text:
            score += 1
            evidence.append(f"命中拆分词 {kw}")

    covered = strong_match or score >= 3
    return score, unique_list(evidence), covered


def match_entry_points_coverage(
    entry_points: List[Dict[str, Any]],
    ranked_candidates: List[Dict[str, Any]],
    max_cases: int = 3,
) -> List[Dict[str, Any]]:
    """对每个接口入口方法做覆盖匹配, 返回带覆盖结果的列表。"""
    results = []
    for ep in entry_points:
        entry_method = ep.get("entry_method", "")
        matched: List[Dict[str, Any]] = []
        for candidate in ranked_candidates:
            score, reasons, covered = score_entry_point_for_candidate(entry_method, candidate)
            if score <= 0 or not covered:
                continue
            matched.append({
                "candidate": {
                    "name": candidate.get("name", ""),
                    "path": candidate.get("path", ""),
                    "tier": candidate.get("tier", ""),
                    "score": candidate.get("score", 0),
                },
                "coverage_score": score,
                "coverage_reasons": reasons,
            })
        matched.sort(key=lambda x: (-x["coverage_score"], -x["candidate"].get("score", 0)))
        results.append({
            "entry_method": entry_method,
            "label": ep.get("label", ""),
            "covered": bool(matched),
            "matched_candidates": matched[:max_cases],
        })
    return results


def build_integration_summary(ep_coverage: List[Dict[str, Any]]) -> Dict[str, Any]:
    covered = [r for r in ep_coverage if r["covered"]]
    uncovered = [r for r in ep_coverage if not r["covered"]]
    total = len(ep_coverage)
    return {
        "entry_point_count": total,
        "covered_count": len(covered),
        "uncovered_count": len(uncovered),
        "coverage_ratio": round(len(covered) / total, 3) if total else 0.0,
    }


# -----------------------------------------------------------------------------
# 渲染: 单测报告
# -----------------------------------------------------------------------------
def render_unit_test_report(
    summary: Dict[str, Any],
    coverage_rows: List[Dict[str, Any]],
    analysis_path: Path,
    ranked_path: Path,
) -> str:
    lines: List[str] = []
    lines.append("# 单测回归报告")
    lines.append("")
    lines.append(f"分析结果来源: `{analysis_path}`")
    lines.append(f"排序结果来源: `{ranked_path}`")
    lines.append("")
    lines.append("## 总览")
    lines.append("")
    lines.append(f"- 影响点总数: {summary['impact_point_count']}")
    lines.append(f"- 已找到单测覆盖的影响点: {summary['covered_count']}")
    lines.append(f"- 未找到对应单测用例的影响点: {summary['uncovered_count']}")
    lines.append(f"- 覆盖率: {summary['coverage_ratio']}")
    lines.append("")
    lines.append("## 已覆盖的代码影响点")
    lines.append("")
    covered_rows = [row for row in coverage_rows if row["covered"]]
    if not covered_rows:
        lines.append("当前没有识别到已覆盖的影响点。")
        lines.append("")
    else:
        for row in covered_rows:
            impact = row["impact"]
            lines.append(f"### {impact['name']}")
            lines.append("")
            lines.append(f"- 影响类型: {impact['impact_type']}")
            lines.append(f"- 文件: `{impact['path']}`")
            lines.append(f"- 关系: {impact['relation']}")
            lines.append(f"- 深度: {impact['depth']}")
            lines.append(f"- 风险: {impact['risk']}")
            lines.append(f"- 覆盖用例数: {len(row['matched_candidates'])}")
            lines.append("")
            for matched in row["matched_candidates"]:
                candidate = matched["candidate"]
                reasons = "; ".join(matched["coverage_reasons"]) if matched["coverage_reasons"] else "无明确证据"
                lines.append(
                    f"- 用例: `{candidate['name']}` (`{candidate['path']}`), "
                    f"分层={candidate['tier']}, 排序分={candidate['score']}, 覆盖证据: {reasons}"
                )
            lines.append("")
    lines.append("## 未覆盖的代码影响点")
    lines.append("")
    uncovered_rows = [row for row in coverage_rows if not row["covered"]]
    if not uncovered_rows:
        lines.append("当前所有影响点均已找到候选单测用例。")
        lines.append("")
    else:
        for row in uncovered_rows:
            impact = row["impact"]
            lines.append(
                f"- `{impact['name']}` (`{impact['path']}`), "
                f"影响类型={impact['impact_type']}, 关系={impact['relation']}, "
                f"深度={impact['depth']}, 风险={impact['risk']}"
            )
        lines.append("")
    lines.append("## 建议")
    lines.append("")
    if uncovered_rows:
        lines.append(
            "建议优先为未覆盖影响点补充对应单测用例, "
            "尤其优先处理 depth 较浅、风险较高、或属于直接变更符号的影响点。"
        )
    else:
        lines.append(
            "当前影响点均已有候选单测用例, "
            "建议继续人工复核这些候选是否真实覆盖关键场景和异常分支。"
        )
        lines.append("")
    return "\n".join(lines)


# -----------------------------------------------------------------------------
# 渲染: 集成测试报告
# -----------------------------------------------------------------------------
def render_integration_test_report(
    summary: Dict[str, Any],
    ep_coverage: List[Dict[str, Any]],
    analysis_path: Path,
    ranked_path: Path,
) -> str:
    lines: List[str] = []
    lines.append("# 集成测试回归报告")
    lines.append("")
    lines.append(f"分析结果来源: `{analysis_path}`")
    lines.append(f"排序结果来源: `{ranked_path}`")
    lines.append("")
    lines.append("## 总览")
    lines.append("")
    lines.append(f"- 受影响接口入口总数: {summary['entry_point_count']}")
    lines.append(f"- 已找到集成测试覆盖的接口入口: {summary['covered_count']}")
    lines.append(f"- 暂无集成测试覆盖的接口入口: {summary['uncovered_count']}")
    lines.append(f"- 覆盖率: {summary['coverage_ratio']}")
    lines.append("")
    ep_covered = [r for r in ep_coverage if r["covered"]]
    ep_uncovered = [r for r in ep_coverage if not r["covered"]]
    lines.append("## 已有覆盖的接口入口")
    lines.append("")
