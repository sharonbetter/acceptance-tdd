#!/usr/bin/env python3
"""
分析层入口脚本：对目标仓库执行 detect_changes，解析变更符号，
逐个执行 impact 分析，检查 group 归属，汇总成统一影响视图。
"""

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional


def run_cmd(command: List[str], cwd: Path) -> subprocess.CompletedProcess:
 return subprocess.run(command, cwd=str(cwd), capture_output=True, text=True)


def try_json_load(text: str) -> Any:
 text = (text or "").strip()
 if not text:
 return None
 try:
 return json.loads(text)
 except Exception:
 return None


def parse_detect_changes_json(payload: Dict[str, Any]) -> Dict[str, Any]:
 changed_symbols: List[Dict[str, Any]] = []

 raw_symbols = (
 payload.get("changedSymbols")
 or payload.get("changed_symbols")
 or payload.get("symbols")
 or []
 )
 for item in raw_symbols:
 if not isinstance(item, dict):
 continue
 name = item.get("name") or item.get("symbol") or ""
 file_path = item.get("filePath") or item.get("file") or item.get("path") or ""
 kind = item.get("kind") or item.get("type") or ""
 if name:
 changed_symbols.append({"kind": kind, "name": name, "file": file_path})

 files_count = payload.get("changedFiles") or payload.get("changed_files") or payload.get("filesCount") or len(changed_symbols)
 symbols_count = payload.get("changedSymbolsCount") or payload.get("changed_symbols_count")
 processes_count = payload.get("affectedProcessesCount") or payload.get("affected_processes_count")
 risk_level = (payload.get("riskLevel") or payload.get("risk_level") or payload.get("risk") or "").lower() or None

 return {
 "source": "json",
 "changed_files": int(files_count) if files_count is not None else None,
 "changed_symbols_count": int(symbols_count) if symbols_count is not None else None,
 "affected_processes_count": int(processes_count) if processes_count is not None else None,
 "risk_level": risk_level,
 "changed_symbols": changed_symbols,
 }


def parse_detect_changes_text(text: str) -> Dict[str, Any]:
 raw = (text or "").strip()
 parsed: Dict[str, Any] = {
 "source": "text",
 "raw": raw,
 "changed_files": None,
 "changed_symbols_count": None,
 "affected_processes_count": None,
 "risk_level": None,
 "changed_symbols": [],
 }
 if not raw:
 return parsed

 match = re.search(r"Changes:\s+(\d+)\s+files?,\s+(\d+)\s+symbols?", raw)
 if match:
 parsed["changed_files"] = int(match.group(1))
 parsed["changed_symbols_count"] = int(match.group(2))

 match = re.search(r"Affected processes:\s+(\d+)", raw)
 if match:
 parsed["affected_processes_count"] = int(match.group(1))

 match = re.search(r"Risk level:\s+([A-Za-z]+)", raw)
 if match:
 parsed["risk_level"] = match.group(1).lower()

 lines = raw.splitlines()
 in_symbols = False
 for line in lines:
 stripped = line.strip()
 if not stripped:
 continue
 if stripped == "Changed symbols:":
 in_symbols = True
 continue
 if in_symbols:
 m = re.match(r"(.+?)\s+([A-Za-z_][A-Za-z0-9_]*)\s+->\s+(.+)", stripped)
 if m:
 parsed["changed_symbols"].append({
 "kind": m.group(1).strip(),
 "name": m.group(2).strip(),
 "file": m.group(3).strip(),
 })
 else:
 parsed["changed_symbols"].append({"raw": stripped})

 return parsed


def run_detect_changes(repo_path: Path, repo_name: str, scope: str, base_ref: Optional[str]) -> Dict[str, Any]:
 base_cmd = ["gitnexus", "detect_changes", "--scope", scope, "--repo", repo_name]
 if base_ref:
 base_cmd.extend(["--base-ref", base_ref])

 json_cmd = base_cmd + ["--format", "json"]
 proc = run_cmd(json_cmd, repo_path)
 stdout = (proc.stdout or "").strip()
 stderr = (proc.stderr or "").strip()

 if proc.returncode == 0:
 payload = try_json_load(stdout)
 if isinstance(payload, dict):
 parsed = parse_detect_changes_json(payload)
 parsed["returncode"] = proc.returncode
 parsed["command"] = json_cmd
 if stderr:
 parsed["stderr"] = stderr
 return parsed

 proc = run_cmd(base_cmd, repo_path)
 stdout = (proc.stdout or "").strip()
 stderr = (proc.stderr or "").strip()
 parsed = parse_detect_changes_text(stdout)
 parsed["returncode"] = proc.returncode
 parsed["command"] = base_cmd
 if stderr:
 parsed["stderr"] = stderr

 if proc.returncode == 0 and not parsed["changed_symbols"]:
 parsed["parse_warning"] = "detect_changes 执行成功但未能从文本输出中解析到任何符号。"

 return parsed


def extract_symbols_from_detect(parsed_detect: Dict[str, Any]) -> List[str]:
 symbols: List[str] = []
 for item in parsed_detect.get("changed_symbols", []) or []:
 if isinstance(item, dict):
 name = item.get("name")
 if isinstance(name, str) and name.strip():
 symbols.append(name.strip())
 return symbols


def summarize_impact(payload: Dict[str, Any]) -> Dict[str, Any]:
 by_depth = payload.get("byDepth", {}) or {}
 impacted_symbols: List[Dict[str, Any]] = []
 impacted_files: List[str] = []
 max_depth = 0

 for depth_key, items in by_depth.items():
 try:
 depth_num = int(depth_key)
 except Exception:
 depth_num = 0
 max_depth = max(max_depth, depth_num)
 if isinstance(items, list):
 for item in items:
 if not isinstance(item, dict):
 continue
 impacted_symbols.append({
 "depth": depth_num,
 "name": item.get("name"),
 "filePath": item.get("filePath"),
 "relationType": item.get("relationType"),
 "confidence": item.get("confidence"),
 })
 file_path = item.get("filePath")
 if isinstance(file_path, str) and file_path:
 impacted_files.append(file_path)

 unique_files: List[str] = []
 seen = set()
 for file_path in impacted_files:
 if file_path not in seen:
 seen.add(file_path)
 unique_files.append(file_path)

 return {
 "target": payload.get("target", {}),
 "direction": payload.get("direction"),
 "risk": payload.get("risk"),
 "impactedCount": payload.get("impactedCount"),
 "summary": payload.get("summary", {}),
 "affected_processes": payload.get("affected_processes", []),
 "affected_modules": payload.get("affected_modules", []),
 "max_depth": max_depth,
 "impacted_symbols": impacted_symbols,
 "impacted_files": unique_files,
 }


def detect_group_info(repo_path: Path) -> Dict[str, Any]:
 proc = run_cmd(["gitnexus", "group", "list"], repo_path)
 stdout = (proc.stdout or "").strip()
 stderr = (proc.stderr or "").strip()
 raw = stdout or stderr

 info: Dict[str, Any] = {
 "checked": True,
 "returncode": proc.returncode,
 "raw": raw,
 "has_groups": False,
 "groups": [],
 }

 if "No groups configured" in raw:
 return info

 lines = [line.strip() for line in raw.splitlines() if line.strip()]
 guessed_groups: List[str] = []
 for line in lines:
 if line.lower().startswith("usage:"):
 continue
 guessed_groups.append(line)

 if guessed_groups:
 info["has_groups"] = True
 info["groups"] = guessed_groups
 return info


def query_affected_processes(repo_path: Path, repo_name: str, impacted_file_paths: List[str]) -> Dict[str, Any]:
 result: Dict[str, Any] = {
 "affected_processes_count": 0,
 "entry_points": [],
 "error": None,
 }

 if not impacted_file_paths:
 return result

 BATCH = 10
 seen_entry_points: set = set()
 all_entry_points: List[Dict[str, Any]] = []

 for i in range(0, len(impacted_file_paths), BATCH):
 batch = impacted_file_paths[i: i + BATCH]
 conditions = " OR ".join([f"s.filePath CONTAINS '{fp}'" for fp in batch])
 cypher = (
 f"MATCH (s)-[r:CodeRelation]->(p:Process) "
 f"WHERE {conditions} "
 f"RETURN DISTINCT p.id, p.label, p.entryPointId"
 )
 cmd = ["gitnexus", "cypher", "cypher", "--repo", repo_name]
 proc = run_cmd(cmd, repo_path)
 stdout = (proc.stdout or "").strip()
 if proc.returncode != 0 or not stdout:
 continue
 parsed = try_json_load(stdout)
 if not isinstance(parsed, dict):
 continue

 md = parsed.get("markdown", "")
 for line in md.split("\n"):
 line = line.strip()
 if not line.startswith("|") or "---" in line or "p.id" in line:
 continue
 parts = [p.strip() for p in line.strip("|").split("|")]
 if len(parts) < 3:
 continue
 proc_id, label, entry_point_id = parts[0], parts[1], parts[2]
 if not entry_point_id or entry_point_id in seen_entry_points:
 continue
 seen_entry_points.add(entry_point_id)
 entry_method = entry_point_id.split(":")[-1] if ":" in entry_point_id else entry_point_id
 all_entry_points.append({
 "process_id": proc_id,
 "label": label,
 "entry_point_id": entry_point_id,
 "entry_method": entry_method,
 })

 result["affected_processes_count"] = len(all_entry_points)
 result["entry_points"] = all_entry_points
 return result


def build_merged_summary(parsed_detect: Dict[str, Any], impact_results: List[Dict[str, Any]], group_info: Dict[str, Any], affected_processes: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
 impacted_files: List[str] = []
 impacted_symbols: List[Dict[str, Any]] = []
 highest_risk = parsed_detect.get("risk_level") or "unknown"
 max_depth = 0

 for item in impact_results:
 summary = item.get("summary") or {}
 risk_value = str(summary.get("risk", "unknown").lower())
 max_depth = max(max_depth, int(summary.get("max_depth") or 0))
 for file_path in summary.get("impacted_files", []) or []:
 if file_path not in impacted_files:
 impacted_files.append(file_path)
 for symbol in summary.get("impacted_symbols", []) or []:
 impacted_symbols.append(symbol)

 return {
 "changed_files": parsed_detect.get("changed_files"),
 "changed_symbols_count": parsed_detect.get("changed_symbols_count"),
 "detect_risk": parsed_detect.get("risk_level"),
 "expanded_risk": highest_risk,
 "max_impact_depth": max_depth,
 "seed_symbols": [item.get("name") for item in parsed_detect.get("changed_symbols", []) if isinstance(item, dict) and item.get("name")],
 "impacted_files": impacted_files,
 "impacted_symbols": impacted_symbols,
 "group_detected": group_info.get("has_groups", False),
 "affected_processes": affected_processes or {"affected_processes_count": 0, "entry_points": []},
 }


def choose_context_candidate(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
 status = payload.get("status")
 if status == "found":
 symbol = payload.get("symbol")
 if isinstance(symbol, dict):
 return symbol

 if status == "ambiguous":
 candidates = payload.get("candidates") or []
 if not isinstance(candidates, list) or not candidates:
 return None

 def sort_key(item: Dict[str, Any]) -> tuple:
 kind = str(item.get("kind") or "")
 score = item.get("score")
 try:
 score_num = float(score)
 except Exception:
 score_num = -1.0
 method_rank = 0 if kind == "Method" else 1
 has_file = 0 if item.get("filePath") else 1
 return (method_rank, has_file, -score_num)

 sorted_candidates = sorted(
 [item for item in candidates if isinstance(item, dict)],
 key=sort_key,
 )
 return sorted_candidates[0] if sorted_candidates else None

 return None


def resolve_symbol_via_context(symbol: str, repo_path: Path, repo_name: Optional[str]) -> Dict[str, Any]:
 context_cmd = ["gitnexus", "context"]
 if repo_name:
 context_cmd.extend(["--repo", repo_name])
 context_cmd.append(symbol)
 context_proc = run_cmd(context_cmd, repo_path)
 stdout = (context_proc.stdout or "").strip()
 stderr = (context_proc.stderr or "").strip()
 parsed = try_json_load(stdout)

 resolution: Dict[str, Any] = {
 "symbol": symbol,
 "context_command": context_cmd,
 "returncode": context_proc.returncode,
 "stdout": stdout,
 "stderr": stderr,
 "parsed": parsed if isinstance(parsed, dict) else None,
 "used_target": None,
 "selected_candidate": None,
 }

 if isinstance(parsed, dict):
 chosen = choose_context_candidate(parsed)
 if isinstance(chosen, dict):
 resolution["selected_candidate"] = chosen
 uid = chosen.get("uid")
 if isinstance(uid, str) and uid.strip():
 resolution["used_target"] = uid.strip()

 return resolution


def infer_repo_name(repo_path: Path) -> str:
 return repo_path.name


def parse_args() -> argparse.Namespace:
 parser = argparse.ArgumentParser(
 description="Run detect_changes, resolve symbols via context, expand into per-symbol impact analysis, and summarize results."
 )
 parser.add_argument("repo_path", help="Target repository path")
 parser.add_argument("--output-path", nargs="?", help="Optional output JSON path")
 parser.add_argument("--scope", default="unstaged", choices=["unstaged", "staged", "all", "compare"], help="detect_changes scope")
 parser.add_argument("--base-ref", help="Base ref used when scope=compare")
 parser.add_argument("--repo", help="Explicit GitNexus repo name; defaults to the repository directory name")
 parser.add_argument("--direction", default="upstream", choices=["upstream", "downstream"], help="impact direction")
 parser.add_argument("--depth", type=int, default=3, help="impact max depth")
 parser.add_argument("--include-tests", action="store_true", help="include tests in impact results")
 parser.add_argument("--max-symbols", type=int, default=20, help="max number of extracted symbols to expand")
 return parser.parse_args()


def main() -> int:
 args = parse_args()
 repo_path = Path(args.repo_path).expanduser().resolve()
 output_path = Path(args.output_path).expanduser().resolve() if args.output_path else None
 repo_name = args.repo or infer_repo_name(repo_path)

 result: Dict[str, Any] = {
 "repo_path": str(repo_path),
 "repo": repo_name,
 "parameters": {
 "scope": args.scope,
 "base_ref": args.base_ref,
 "repo": repo_name,
 "direction": args.direction,
 "depth": args.depth,
 "include_tests": args.include_tests,
 "max_symbols": args.max_symbols,
 },
 "detect_changes": None,
 "extracted_symbols": [],
 "impact_results": [],
 "group_analysis": None,
 "merged_summary": None,
 "notes": [],
 }

 if not repo_path.exists() or not repo_path.is_dir():
 print(json.dumps({"error": f"repo path does not exist: {repo_path}"}, ensure_ascii=False, indent=2))
 return 1

 parsed_detect = run_detect_changes(repo_path, repo_name, args.scope, args.base_ref)
 result["detect_changes"] = parsed_detect

 if parsed_detect.get("parse_warning"):
 result["notes"].append({
 "stage": "detect_changes",
 "warning": parsed_detect["parse_warning"],
 })

 if parsed_detect.get("returncode", 0) != 0:
 result["notes"].append({
 "stage": "detect_changes",
 "error": parsed_detect.get("stderr") or "detect_changes failed",
 "returncode": parsed_detect.get("returncode"),
 "command": parsed_detect.get("command"),
 })
 else:
 extracted_symbols = extract_symbols_from_detect(parsed_detect)[:args.max_symbols]
 result["extracted_symbols"] = extracted_symbols
 if not extracted_symbols:
 result["notes"].append({
 "stage": "extract_symbols",
 "message": "No symbols extracted from detect_changes output.",
 })

 for symbol in extracted_symbols:
 resolution = resolve_symbol_via_context(symbol, repo_path, repo_name)
 used_target = resolution.get("used_target")
 impact_item: Dict[str, Any] = {
 "symbol": symbol,
 "resolution": resolution,
 "used_target": used_target,
 }

 if not isinstance(used_target, str) or not used_target.strip():
 impact_item["returncode"] = resolution.get("returncode")
 impact_item["stdout"] = resolution.get("stdout")
 impact_item["stderr"] = resolution.get("stderr")
 impact_item["summary"] = {
 "target": {"name": symbol},
 "risk": None,
 "impacted_symbols": [],
 "impacted_files": [],
 "max_depth": 0,
 }
 result["notes"].append({
 "stage": "resolve_symbol",
 "symbol": symbol,
 "message": "context could not resolve a usable uid for impact",
 })
 result["impact_results"].append(impact_item)
 continue

 impact_cmd = ["gitnexus", "impact", "--repo", repo_name, used_target, "--direction", args.direction, "--depth", str(args.depth)]
 if args.include_tests:
 impact_cmd.append("--include-tests")
 impact_proc = run_cmd(impact_cmd, repo_path)
 parsed_impact = try_json_load(impact_proc.stdout)
 impact_item.update({
 "impact_command": impact_cmd,
 "returncode": impact_proc.returncode,
 "stdout": (impact_proc.stdout or "").strip(),
 "stderr": (impact_proc.stderr or "").strip(),
 })
 if isinstance(parsed_impact, dict):
 impact_item["parsed"] = parsed_impact
 impact_item["summary"] = summarize_impact(parsed_impact)
 else:
 impact_item["summary"] = {
 "target": {"name": used_target},
 "risk": None,
 "impacted_symbols": [],
 "impacted_files": [],
 "max_depth": 0,
 }
 result["notes"].append({
 "stage": "impact",
 "symbol": symbol,
 "used_target": used_target,
 "message": "impact output is not JSON",
 })
 result["impact_results"].append(impact_item)

 group_info = detect_group_info(repo_path)
 result["group_analysis"] = group_info
 if group_info.get("has_groups"):
 result["notes"].append({
 "stage": "group_detection",
 "message": "Groups detected.",
 "groups": group_info.get("groups", []),
 })
 else:
 result["notes"].append({
 "stage": "group_detection",
 "message": "No groups configured.",
 })

 impacted_files = build_merged_summary(result["detect_changes"] or {}, result["impact_results"], group_info).get("impacted_files", [])
 affected_processes = query_affected_processes(repo_path, repo_name, impacted_files)
 result["affected_processes"] = affected_processes

 result["merged_summary"] = build_merged_summary(result["detect_changes"] or {}, result["impact_results"], group_info, affected_processes)

 text = json.dumps(result, ensure_ascii=False, indent=2)
 if output_path:
 output_path.write_text(text + "\n", encoding="utf-8")
 else:
 print(text)

 return 0


if __name__ == "__main__":
 raise SystemExit(main())