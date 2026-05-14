#!/usr/bin/env python3
"""
排序层脚本：对召回的候选测试按影响特征进行打分和分层。

优化点：
- 分层阈值（high/medium）通过 --high-threshold / --medium-threshold 参数暴露，
 不再硬编码为 0.75 / 0.45，方便针对不同命名风格的仓库调整
- 使用 utils.py 公共工具函数，消除重复代码
"""
import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

from utils import normalize_text, tokenize, split_symbol, unique_list, text_contains_term, STOPWORDS


def build_feature_terms(impact: Dict[str, Any]) -> Dict[str, List[str]]:
 symbols = impact.get("symbols", []) or []
 module_paths = impact.get("module_paths", []) or []
 scenarios = impact.get("scenarios", []) or []
 changed_files = impact.get("changed_files", []) or []
 process_names = impact.get("processes", []) or []

 symbol_terms: List[str] = []
 for symbol in symbols:
 symbol_terms.append(normalize_text(symbol))
 symbol_terms.extend(split_symbol(symbol))

 module_terms: List[str] = []
 for path in module_paths + changed_files:
 module_terms.extend(tokenize(path))

 scenario_terms: List[str] = []
 for item in scenarios + process_names:
 scenario_terms.extend(tokenize(item))

 symbol_terms = [t for t in unique_list(symbol_terms) if t and t not in STOPWORDS and len(t) >= 3]
 module_terms = [t for t in unique_list(module_terms) if t and t not in STOPWORDS and len(t) >= 3]
 scenario_terms = [t for t in unique_list(scenario_terms) if t and t not in STOPWORDS and len(t) >= 3]

 return {
 "symbol_terms": symbol_terms,
 "module_terms": module_terms,
 "scenario_terms": scenario_terms,
 }


def count_hits(text: str, terms: List[str]) -> Tuple[int, List[str]]:
 hits = []
 for term in terms:
 if text_contains_term(text, term):
 hits.append(term)
 return len(hits), hits


def score_candidate(
 candidate: Dict[str, Any],
 features: Dict[str, List[str]],
 impact: Dict[str, Any],
 high_threshold: float,
 medium_threshold: float,
) -> Dict[str, Any]:
 name = candidate.get("name", "")
 path = candidate.get("path", "")
 description = candidate.get("description", "")
 assertions = " ".join(candidate.get("assertions", []) or [])
 tags = " ".join(candidate.get("tags", []) or [])
 covered_steps = candidate.get("covered_process_steps", []) or []

 full_text = normalize_text(" ".join([name, path, description, assertions, tags, " ".join(covered_steps)]))
 path_text = normalize_text(path)
 title_text = normalize_text(name)
 desc_text = normalize_text(" ".join([description, assertions, tags]))

 symbol_count, symbol_hits = count_hits(full_text, features["symbol_terms"])
 module_count, module_hits = count_hits(path_text + " " + full_text, features["module_terms"])
 scenario_count, scenario_hits = count_hits(desc_text + " " + full_text, features["scenario_terms"])

 affected_processes = [normalize_text(p) for p in (impact.get("processes", []) or [])]
 process_text = normalize_text(" ".join(covered_steps))
 process_hits = [p for p in affected_processes if p in process_text]
 process_count = len(process_hits)

 direct_symbol_match = any(
 normalize_text(s) in title_text or normalize_text(s) in full_text
 for s in (impact.get("symbols", []) or [])
 )

 risk_focus_terms = tokenize(" ".join(impact.get("risk_terms", []) or []))
 risk_count, risk_hits = count_hits(full_text, risk_focus_terms)

 score = 0.0
 score += min(symbol_count, 5) * 0.25
 score += min(scenario_count, 5) * 0.18
 score += min(module_count, 4) * 0.12
 score += min(process_count, 3) * 0.20
 score += min(risk_count, 3) * 0.12
 if direct_symbol_match:
 score += 0.25

 score = min(score, 1.0)

 # 分层判断：优先看直接符号匹配 + 语义/风险/流程命中的组合
 # 其次按可配置阈值分层（默认 high=0.75, medium=0.45）
 if direct_symbol_match and (scenario_count > 0 or risk_count > 0 or process_count > 0):
 tier = "high"
 elif score >= high_threshold:
 tier = "high"
 elif score >= medium_threshold:
 tier = "medium"
 else:
 tier = "low"

 evidence = []
 if symbol_hits:
 evidence.append(f"符号命中: {', '.join(symbol_hits[:6])}")
 if scenario_hits:
 evidence.append(f"语义命中: {', '.join(scenario_hits[:6])}")
 if module_hits:
 evidence.append(f"路径/模块命中: {', '.join(module_hits[:6])}")
 if process_hits:
 evidence.append(f"流程命中: {', '.join(process_hits[:4])}")
 if risk_hits:
 evidence.append(f"风险命中: {', '.join(risk_hits[:4])}")
 if direct_symbol_match:
 evidence.append("存在直接符号匹配")

 return {
 **candidate,
 "score": round(score, 3),
 "tier": tier,
 "evidence": evidence,
 "hit_summary": {
 "symbol_hits": symbol_hits,
 "scenario_hits": scenario_hits,
 "module_hits": module_hits,
 "process_hits": process_hits,
 "risk_hits": risk_hits,
 },
 }


def load_json(path: Path) -> Dict[str, Any]:
 with path.open("r", encoding="utf-8") as f:
 return json.load(f)


def parse_args() -> argparse.Namespace:
 parser = argparse.ArgumentParser(
 description="Rank and tier test candidates based on impact features."
 )
 parser.add_argument("impact_json", help="impact.json describing the code change features")
 parser.add_argument("candidates_json", help="candidates.json with test candidate list")
 parser.add_argument("output_json", nargs="?", help="optional output path for ranked results")
 parser.add_argument(
 "--high-threshold",
 type=float,
 default=0.75,
 help=(
 "Score threshold for 'high' tier (default: 0.75). "
 "Lower this value if your repo uses Chinese/business-term-heavy test names "
 "and too many relevant tests are falling into 'low'."
 ),
 )
 parser.add_argument(
 "--medium-threshold",
 type=float,
 default=0.45,
 help="Score threshold for 'medium' tier (default: 0.45).",
 )
 return parser.parse_args()


def main() -> int:
 args = parse_args()

 if args.high_threshold <= args.medium_threshold:
 print(
 f"Error: --high-threshold ({args.high_threshold}) must be greater than "
 f"--medium-threshold ({args.medium_threshold})",
 file=sys.stderr,
 )
 return 1

 impact_path = Path(args.impact_json)
 candidates_path = Path(args.candidates_json)
 output_path = Path(args.output_json) if args.output_json else None

 impact = load_json(impact_path)
 payload = load_json(candidates_path)
 candidates = payload.get("candidates", payload if isinstance(payload, list) else [])
 if not isinstance(candidates, list):
 raise ValueError("candidates.json must be a list or an object with a 'candidates' field")

 features = build_feature_terms(impact)
 ranked = []
 for candidate in candidates:
 ranked.append(
 score_candidate(candidate, features, impact, args.high_threshold, args.medium_threshold)
 )

 ranked.sort(key=lambda item: (-item["score"], item.get("name", ""), item.get("path", "")))

 result = {
 "impact_summary": {
 "symbols": impact.get("symbols", []),
 "business_terms": impact.get("business_terms", []),
 "module_paths": impact.get("module_paths", []),
 "processes": impact.get("processes", []),
 "risk_terms": impact.get("risk_terms", []),
 },
 "thresholds": {
 "high": args.high_threshold,
 "medium": args.medium_threshold,
 },
 "derived_features": features,
 "ranked_candidates": ranked,
 "grouped": {
 "high": [item for item in ranked if item["tier"] == "high"],
 "medium": [item for item in ranked if item["tier"] == "medium"],
 "low": [item for item in ranked if item["tier"] == "low"],
 },
 }

 text = json.dumps(result, ensure_ascii=False, indent=2)
 if output_path:
 output_path.write_text(text + "\n", encoding="utf-8")
 else:
 print(text)
 return 0


if __name__ == "__main__":
 raise SystemExit(main())