#!/usr/bin/env python3
"""
召回层脚本：读取 detect_and_expand_impact.py 的输出，
在目标仓库内基于影响特征粗筛候选测试，输出 candidates.json。

优化点：
- 提升文件读取上限（16000 字节），避免漏掉长测试文件末尾的 case
- 新增 Java @Test 注解识别，支持 case 级召回
- 使用 utils.py 公共工具函数，消除重复代码
"""
import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from utils import normalize_text, tokenize, split_symbol, unique_list, STOPWORDS

# 标准测试目录模式：src/test/、__tests__/、tests/、spec/ 等
_TEST_DIR_RE = re.compile(r"(^|/)(src/test|__tests__|tests|spec)(/|$)", re.IGNORECASE)
# 文件名（不含扩展名）以 Test/Tests/Spec/Specs 结尾，或以 test_/spec_ 开头
_TEST_FILENAME_RE = re.compile(r"(^|/)test_[^/]+$|(^|/)[^/]+(Test|Tests|Spec|Specs)\.[^/]+$", re.IGNORECASE)


def is_test_file(rel_path: str) -> bool:
    """
    判断是否为真正的测试文件。
    条件：路径中包含标准测试目录（src/test/、__tests__/ 等），
    或文件名本身以 Test/Spec 结尾（如 FooTest.java、foo.spec.ts）。
    不再用宽泛的 'test' 字符串匹配，避免把 controller/test/BackDoor.java 这类
    非测试文件（后门接口、测试工具类）误判为测试用例。
    """
    return bool(_TEST_DIR_RE.search(rel_path) or _TEST_FILENAME_RE.search(rel_path))


TEXT_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".kt", ".go", ".rs", ".php", ".rb",
    ".md", ".txt", ".json", ".yaml", ".yml"
}

CAMEL_RE = re.compile(r"([a-z0-9])([A-Z])")

# JS/TS: test('...') / it('...') / test.each('...') / it.each('...')
JS_CASE_RE = re.compile(r"(test|it|test\.each|it\.each)\s*\(\s*(?P<q>['\"])(.+?)\2", re.IGNORECASE)
# JS/TS: describe('...')
DESCRIBE_RE = re.compile(r"describe\s*\(\s*(?P<q>['\"])(.+?)\1", re.IGNORECASE)
# Python: def test_xxx(...):
PY_CASE_RE = re.compile(r"def\s+(test_[A-Za-z0-9-_]+)\s*\(", re.IGNORECASE)
# Java: @Test 注解后跟方法定义（支持 public/protected/private/void 等修饰符）
JAVA_TEST_ANNOTATION_RE = re.compile(r"@Test\b")
JAVA_METHOD_RE = re.compile(r"(?:public|protected|private|static|\s)+\s+\w+\s+(\w+)\s*\(")
# 断言关键词
ASSERT_HINT_RE = re.compile(r"(assert|expect|should|then|verify)", re.IGNORECASE)


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def read_text_full(path: Path, limit: int = 16000) -> str:
    """
    读取文件内容，上限提升至 16000 字节（原为 4000），
    避免漏掉长测试文件末尾的 case。
    """
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
        return text[:limit]
    except Exception:
        return ""


def build_impact_features(analysis: Dict[str, Any]) -> Dict[str, Any]:
    merged = analysis.get("merged_summary", {}) or {}
    detect = analysis.get("detect_changes", {}) or {}
    impact_results = analysis.get("impact_results", []) or []

    seed_symbols = merged.get("seed_symbols", []) or []
    impacted_symbols = [
        item.get("name")
        for item in merged.get("impacted_symbols", []) or []
        if isinstance(item, dict) and item.get("name")
    ]
    symbols = unique_list(seed_symbols + impacted_symbols)

    changed_files = [
        item.get("file")
        for item in detect.get("changed_symbols", []) or []
        if isinstance(item, dict) and item.get("file")
    ]
    changed_files = unique_list(
        [item for item in changed_files if item] + (merged.get("impacted_files", []) or [])
    )

    module_paths: List[str] = []
    for path in changed_files:
        parent = str(Path(path).parent)
        if parent and parent != ".":
            module_paths.append(parent)
    module_paths = unique_list(module_paths)

    processes: List[str] = []
    for item in impact_results:
        summary = item.get("summary", {}) or {}
        for proc in summary.get("affected_processes", []) or []:
            if isinstance(proc, str):
                processes.append(proc)
            elif isinstance(proc, dict) and proc.get("name"):
                processes.append(proc["name"])
    processes = unique_list(processes)

    keywords: List[str] = []
    for sym in symbols:
        parts = split_symbol(sym)
        for part in parts:
            if part and len(part) > 2 and part.lower() not in STOPWORDS:
                keywords.append(part)
    for f in changed_files:
        name = Path(f).stem
        if name:
            parts = split_symbol(name)
            for part in parts:
                if part and len(part) > 2 and part.lower() not in STOPWORDS:
                    keywords.append(part)
    keywords = unique_list(keywords)

    return {
        "symbols": symbols,
        "changed_files": changed_files,
        "module_paths": module_paths,
        "processes": processes,
        "keywords": keywords,
    }


def score_file(file_path: Path, rel_path: str, features: Dict[str, Any], text: str) -> Tuple[float, List[str]]:
    score = 0.0
    hit_keywords: List[str] = []
    norms = [normalize_text(t) for t in [rel_path, file_path.stem, text[:500]]]
    norms_joined = " ".join(norms)

    for kw in features.get("keywords", []) or []:
        kw_norm = normalize_text(kw)
        if len(kw_norm) < 2:
            continue
        if kw_norm in norms_joined:
            score += 1.0
            hit_keywords.append(kw)
        else:
            for seg in tokenize(norms_joined):
                if kw_norm in seg or seg in kw_norm:
                    score += 0.5
                    hit_keywords.append(kw)
                    break

    changed_files = features.get("changed_files", []) or []
    if any(Path(f).stem == file_path.stem for f in changed_files):
        score += 5.0

    for mp in features.get("module_paths", []) or []:
        if rel_path.startswith(mp) or mp in rel_path:
            score += 2.0
            break

    process: str
    for process in (features.get("processes") or []):
        proc_norm = normalize_text(process)
        if proc_norm in norms_joined:
            score += 1.5
            hit_keywords.append(process)
            break

    if ASSERT_HINT_RE.search(text):
        score += 0.5

    return score, hit_keywords


def extract_cases_from_text(rel_path: str, text: str, file_path: Path, score: float) -> List[Dict[str, Any]]:
    hits: List[Dict[str, Any]] = []
    ext = file_path.suffix.lower()
    norms_joined = normalize_text(text)

    if ext == ".java":
        if JAVA_TEST_ANNOTATION_RE.search(text):
            lines = text.split("\n")
            in_test_method = False
            current_method_name = ""
            for line in lines:
                if JAVA_TEST_ANNOTATION_RE.search(line):
                    in_test_method = True
                    current_method_name = ""
                elif in_test_method:
                    m = JAVA_METHOD_RE.search(line)
                    if m:
                        current_method_name = m.group(1)
                        break
            if in_test_method and current_method_name:
                hits.append({
                    "name": current_method_name,
                    "kind": "test_case",
                    "path": str(rel_path),
                    "score": score,
                    "interface_name": "",
                })
    elif ext in {".js", ".ts", ".tsx", ".jsx"}:
        for m in JS_CASE_RE.finditer(text):
            case_name = m.group(3).strip()
            if case_name and len(case_name) > 1:
                hits.append({
                    "name": case_name,
                    "kind": "test_case",
                    "path": str(rel_path),
                    "score": score,
                    "interface_name": "",
                })
        for m in DESCRIBE_RE.finditer(text):
            suite_name = m.group(2).strip()
            if suite_name and len(suite_name) > 1:
                hits.append({
                    "name": suite_name,
                    "kind": "test_suite",
                    "path": str(rel_path),
                    "score": score,
                    "interface_name": "",
                })
    elif ext == ".py":
        for m in PY_CASE_RE.finditer(text):
            case_name = m.group(1).strip()
            if case_name and len(case_name) > 1:
                hits.append({
                    "name": case_name,
                    "kind": "test_case",
                    "path": str(rel_path),
                    "score": score,
                    "interface_name": "",
                })

    if not hits:
        hits.append({
            "name": file_path.stem,
            "kind": "test_file",
            "path": str(rel_path),
            "score": score,
            "interface_name": "",
        })

    return hits


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Recall test candidates from repo based on impact features.")
    parser.add_argument("--analysis-json", required=True, help="analysis.json from detect_and_expand_impact.py")
    parser.add_argument("--repo-path", required=True, help="repo root path")
    parser.add_argument("--output-json", required=True, help="output candidates.json")
    parser.add_argument("--output-features", help="optional output impact-features.json for rank_test_candidates.py")
    parser.add_argument("--score-threshold", type=float, default=0.5, help="minimum score to include a file (default: 0.5)")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    analysis_path = Path(args.analysis_json).expanduser().resolve()
    repo_path = Path(args.repo_path).expanduser().resolve()
    output_path = Path(args.output_json).expanduser().resolve()

    analysis = load_json(analysis_path)
    features = build_impact_features(analysis)

    all_files = list(repo_path.rglob("*"))
    test_files = [
        f for f in all_files
        if f.is_file()
        and f.suffix.lower() in TEXT_EXTENSIONS
        and is_test_file(str(f.relative_to(repo_path)))
    ]

    candidates: List[Dict[str, Any]] = []
    seen_names: set = set()

    for file_path in test_files:
        rel_path = str(file_path.relative_to(repo_path))
        text = read_text_full(file_path)
        score, hit_keywords = score_file(file_path, rel_path, features, text)
        if score < args.score_threshold:
            continue

        cases = extract_cases_from_text(rel_path, text, file_path, score)
        for case in cases:
            key = f"{case['path']}::{case['name']}"
            if key in seen_names:
                continue
            seen_names.add(key)
            case["source_type"] = "repo_scan"
            case["candidate_type"] = case.pop("kind")
            case["hit_keywords"] = hit_keywords
            candidates.append(case)

    output_path.write_text(json.dumps({"candidates": candidates, "features": features}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.output_features:
        features_path = Path(args.output_features).expanduser().resolve()
        features_path.write_text(json.dumps(features, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
    risk_terms: List[str] = []
    detect_risk = merged.get("detect_risk")
    expanded_risk = merged.get("expanded_risk")
    if detect_risk:
        risk_terms.append(str(detect_risk))
    if expanded_risk and expanded_risk != detect_risk:
        risk_terms.append(str(expanded_risk))
    if (merged.get("max_impact_depth") or 0) >= 2:
        risk_terms.append("扩散")
    if (merged.get("max_impact_depth") or 0) >= 3:
        risk_terms.append("深链路")

    scenarios: List[str] = []
    for item in merged.get("impacted_symbols", []) or []:
        if isinstance(item, dict):
            name = item.get("name")
            relation = item.get("relationType")
            if name:
                if relation:
                    scenarios.append(f"{relation} {name}")
                else:
                    scenarios.append(str(name))

    return {
        "symbols": symbols,
        "module_paths": module_paths,
        "processes": processes,
        "risk_terms": unique_list(risk_terms),
        "scenarios": unique_list(scenarios),
        "changed_files": changed_files,
    }


def coarse_match_score(rel_path: str, text: str, impact_features: Dict[str, Any]) -> Tuple[int, Dict[str, List[str]]]:
    path_text = normalize_text(rel_path)
    full_text = normalize_text(rel_path + "\n" + text)

    symbol_hits: List[str] = []
    module_hits: List[str] = []
    scenario_hits: List[str] = []
    risk_hits: List[str] = []

    for symbol in impact_features.get("symbols", []) or []:
        normalized_symbol = normalize_text(symbol)
        if normalized_symbol and normalized_symbol in full_text:
            symbol_hits.append(symbol)
        else:
            split_terms = split_symbol(symbol)
            if split_terms and all(term in full_text for term in split_terms[: min(3, len(split_terms))]):
                symbol_hits.append(symbol)

    for module in impact_features.get("module_paths", []) or []:
        tokens = [t for t in tokenize(module) if t not in STOPWORDS]
        if tokens and any(term in path_text or term in full_text for term in tokens):
            module_hits.append(module)

    for scenario in impact_features.get("scenarios", []) or []:
        tokens = [t for t in tokenize(scenario) if t not in STOPWORDS]
        if tokens and any(term in full_text for term in tokens):
            scenario_hits.append(scenario)

    for risk in impact_features.get("risk_terms", []) or []:
        risk_text = normalize_text(risk)
        if risk_text and risk_text in full_text:
            risk_hits.append(risk)

    score = 0
    score += len(unique_list(symbol_hits)) * 5
    score += len(unique_list(module_hits)) * 3
    score += len(unique_list(scenario_hits)) * 2
    score += len(unique_list(risk_hits)) * 1
    if is_test_file(rel_path):
        score += 2

    return score, {
        "symbol_hits": unique_list(symbol_hits),
        "module_hits": unique_list(module_hits),
        "scenario_hits": unique_list(scenario_hits),
        "risk_hits": unique_list(risk_hits),
    }


def collect_assertions(lines: List[str], start_idx: int, end_idx: int, limit: int = 5) -> List[str]:
    assertions: List[str] = []
    for line in lines[start_idx:end_idx]:
        if ASSERT_HINT_RE.search(line):
            assertions.append(line.strip()[:200])
        if len(assertions) >= limit:
            break
    return assertions


def extract_describe_context(lines: List[str], case_index: int) -> List[str]:
    contexts: List[str] = []
    brace_balance = 0
    for idx in range(case_index - 1, -1, -1):
        line = lines[idx]
        brace_balance += line.count("}") - line.count("{")
        match = DESCRIBE_RE.search(line)
        if match and brace_balance <= 0:
            contexts.append(match.group(2).strip())
            brace_balance = 0
        if len(contexts) >= 3:
            break
    contexts.reverse()
    return contexts


def build_case_candidate(
    rel_path: str,
    file_stem: str,
    lines: List[str],
    case_name: str,
    line_no: int,
    hit_summary: Dict[str, List[str]],
    coarse_score: int,
    describe_context: Optional[List[str]] = None,
) -> Dict[str, Any]:
    start_idx = max(0, line_no - 1)
    end_idx = min(len(lines), start_idx + 12)
    snippet_lines = [line.rstrip() for line in lines[start_idx:end_idx] if line.strip()]
    snippet = "\n".join(snippet_lines[:8])[:500]
    assertions = collect_assertions(lines, start_idx, end_idx)
    covered_process_steps = unique_list(hit_summary.get("scenario_hits", []))
    tags = unique_list(hit_summary.get("module_hits", []) + hit_summary.get("risk_hits", []))
    describe_context = describe_context or []
    full_name = " > ".join(describe_context + [case_name]) if describe_context else case_name

    return {
        "name": full_name,
        "path": rel_path,
        "description": snippet or case_name,
        "assertions": assertions,
        "tags": tags,
        "covered_process_steps": covered_process_steps,
        "recall_score": coarse_score + 3,
        "recall_hits": hit_summary,
        "candidate_type": "test_case",
        "case_name": case_name,
        "case_full_name": full_name,
        "case_line": line_no,
        "describe_context": describe_context,
        "file_name": file_stem,
    }

def extract_java_case_candidates(
    path: Path,
    repo_path: Path,
    text: str,
    hit_summary: Dict[str, List[str]],
    coarse_score: int,
) -> List[Dict[str, Any]]:
    """
    从 Java 测试文件中提取 @Test 注解标注的测试方法。
    支持 JUnit 4/5 风格的 @Test 注解。
    """
    rel_path = str(path.relative_to(repo_path))
    lines = text.splitlines()
    candidates: List[Dict[str, Any]] = []

    i = 0
    while i < len(lines):
        line = lines[i]
        if JAVA_TEST_ANNOTATION_RE.search(line):
            # 向后查找方法定义（最多看 3 行）
            for j in range(i + 1, min(i + 4, len(lines))):
                method_match = JAVA_METHOD_RE.search(lines[j])
                if method_match:
                    method_name = method_match.group(1)
                    # 将下划线/驼峰转为可读名称
                    human_name = re.sub(r"([a-z])([A-Z])", r"\1 \2", method_name)
                    human_name = human_name.replace("_", " ")
                    candidates.append(
                        build_case_candidate(rel_path, path.stem, lines, human_name, j + 1, hit_summary, coarse_score)
                    )
                    break
        i += 1

    return candidates


def extract_case_candidates(
    path: Path,
    repo_path: Path,
    text: str,
    hit_summary: Dict[str, List[str]],
    coarse_score: int,
) -> List[Dict[str, Any]]:
    """从测试文件中提取 case 级候选，支持 JS/TS、Python、Java。"""
    rel_path = str(path.relative_to(repo_path))
    suffix = path.suffix.lower()

    # Java 单独处理
    if suffix == ".java":
        return extract_java_case_candidates(path, repo_path, text, hit_summary, coarse_score)

    lines = text.splitlines()
    candidates: List[Dict[str, Any]] = []

    for idx, line in enumerate(lines, start=1):
        js_match = JS_CASE_RE.search(line)
        if js_match:
            case_name = js_match.group(3).strip()
            describe_context = extract_describe_context(lines, idx - 1)
            candidates.append(
                build_case_candidate(rel_path, path.stem, lines, case_name, idx, hit_summary, coarse_score, describe_context)
            )
            continue

        py_match = PY_CASE_RE.search(line)
        if py_match:
            raw_name = py_match.group(1).strip()
            human_name = raw_name.replace("_", " ")
            candidates.append(
                build_case_candidate(rel_path, path.stem, lines, human_name, idx, hit_summary, coarse_score)
            )

    return candidates


def extract_file_candidate(
    path: Path,
    repo_path: Path,
    text: str,
    hit_summary: Dict[str, List[str]],
    coarse_score: int,
) -> Dict[str, Any]:
    rel_path = str(path.relative_to(repo_path))
    lines = [line.rstrip() for line in text.splitlines() if line.strip()]
    case_count = len(extract_case_candidates(path, repo_path, text, hit_summary, coarse_score))
    description = ""
    for line in lines[:20]:
        description += line + " "
        if len(description) >= 160:
            break
    assertions = []
    for line in lines:
        lowered = line.lower()
        if any(keyword in lowered for keyword in ["assert", "expect", "should", "then", "verify"]):
            assertions.append(line[:200])
        if len(assertions) >= 5:
            break

    covered_process_steps = unique_list(hit_summary.get("scenario_hits", []))
    tags = unique_list(hit_summary.get("module_hits", []) + hit_summary.get("risk_hits", []))

    return {
        "name": path.stem,
        "path": rel_path,
        "description": description,
        "assertions": assertions,
        "tags": tags,
        "covered_process_steps": covered_process_steps,
        "recall_score": coarse_score,
        "recall_hits": hit_summary,
        "candidate_type": "test_file",
        "file_name": path.stem,
        "child_case_count": case_count,
    }


def scan_candidates(repo_path: Path, impact_features: Dict[str, Any], max_candidates: int) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []

    for path in repo_path.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in TEXT_EXTENSIONS:
            continue
        rel_path = str(path.relative_to(repo_path))
        if ".git/" in rel_path or rel_path.startswith(".git/"):
            continue
        if rel_path.endswith("analysis-output.json") or rel_path.endswith("impact-features.json") or rel_path.endswith("candidates-output.json") or rel_path.endswith("ranked-output.json"):
            continue
        if not is_test_file(rel_path):
            continue

        text = read_text_full(path)
        score, hits = coarse_match_score(rel_path, text, impact_features)
        if score <= 0:
            continue

        case_candidates = extract_case_candidates(path, repo_path, text, hits, score)
        if case_candidates:
            candidates.extend(case_candidates)
        else:
            candidates.append(extract_file_candidate(path, repo_path, text, hits, score))

    candidates.sort(
        key=lambda item: (
            -item.get("recall_score", 0),
            0 if item.get("candidate_type") == "test_case" else 1,
            item.get("path", ""),
            item.get("case_line", 0),
        )
    )
    return candidates[:max_candidates]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Recall candidate tests from repository using analysis output.")
    parser.add_argument("analysis_json", help="Output JSON from detect_and_expand_impact.py")
    parser.add_argument("repo_path", help="Repository path to scan")
    parser.add_argument("--output-candidates", nargs="?", help="Optional output path for candidates.json")
    parser.add_argument("--output-impact", help="Optional output path for generated impact.features.json")
    parser.add_argument("--max-candidates", type=int, default=100, help="Maximum recalled candidates")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    analysis_path = Path(args.analysis_json).expanduser().resolve()
    repo_path = Path(args.repo_path).expanduser().resolve()
    output_candidates = Path(args.output_candidates).expanduser().resolve() if args.output_candidates else None
    output_impact = Path(args.output_impact).expanduser().resolve() if args.output_impact else None

    analysis = load_json(analysis_path)
    impact_features = build_impact_features(analysis)
    candidates = scan_candidates(repo_path, impact_features, args.max_candidates)

    result = {
        "analysis_source": str(analysis_path),
        "repo_path": str(repo_path),
        "candidate_count": len(candidates),
        "candidates": candidates,
    }

    if output_impact:
        output_impact.write_text(json.dumps(impact_features, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    text = json.dumps(result, ensure_ascii=False, indent=2)
    if output_candidates:
        output_candidates.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
