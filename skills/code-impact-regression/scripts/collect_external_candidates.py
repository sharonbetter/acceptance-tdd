#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


STANDARD_FIELDS = {
 "name",
 "path",
 "description",
 "assertions",
 "tags",
 "covered_process_steps",
 "candidate_type",
 "case_name",
 "case_full_name",
 "case_line",
 "describe_context",
 "file_name",
 "source_type",
 "source_system",
 "raw_record",
}

DEFAULT_CANDIDATE = {
 "name": "",
 "path": "",
 "description": "",
 "assertions": [],
 "tags": [],
 "covered_process_steps": [],
 "candidate_type": "external_case",
 "case_name": "",
 "case_full_name": "",
 "case_line": 0,
 "describe_context": [],
 "file_name": "",
 "source_type": "external_json",
 "source_system": "external",
}


def load_json(path: Path) -> Any:
 with path.open("r", encoding="utf-8") as f:
 return json.load(f)


def write_json(path: Path, payload: Dict[str, Any]) -> None:
 path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def ensure_list(value: Any) -> List[Any]:
 if value is None:
 return []
 if isinstance(value, list):
 return value
 return [value]


def stringify(value: Any) -> str:
 if value is None:
 return ""
 if isinstance(value, str):
 return value.strip()
 if isinstance(value, (int, float, bool)):
 return str(value)
 return json.dumps(value, ensure_ascii=False)


def dotted_get(record: Any, path: str) -> Any:
 if not path:
 return None
 current = record
 for part in path.split("."):
 if isinstance(current, dict):
 current = current.get(part)
 elif isinstance(current, list):
 try:
 index = int(part)
 except ValueError:
 return None
 if index < 0 or index >= len(current):
 return None
 current = current[index]
 else:
 return None
 return current


def detect_records(payload: Any, records_path: Optional[str]) -> List[Any]:
 if records_path:
 selected = dotted_get(payload, records_path)
 if isinstance(selected, list):
 return selected
 raise ValueError(f"records path '{records_path}' does not point to a list")

 if isinstance(payload, list):
 return payload
 if isinstance(payload, dict):
 for key in ["candidates", "records", "items", "data", "list", "rows"]:
 value = payload.get(key)
 if isinstance(value, list):
 return value
 if isinstance(value, dict):
 nested = value.get("items") or value.get("records") or value.get("rows") or value.get("list")
 if isinstance(nested, list):
 return nested
 raise ValueError("unable to detect record list from external json; please provide --records-path")


def normalize_string_list(value: Any) -> List[str]:
 if value is None:
 return []
 if isinstance(value, list):
 return [stringify(item) for item in value if stringify(item)]
 if isinstance(value, str):
 text = value.strip()
 if not text:
 return []
 if "," in text:
 return [item.strip() for item in text.split(",") if item.strip()]
 if "\n" in text:
 return [item.strip() for item in text.splitlines() if item.strip()]
 return [text]
 return [stringify(value)]


def infer_file_name(path_value: str, case_full_name: str, name_value: str) -> str:
 path_value = path_value or ""
 if path_value:
 return Path(path_value).stem
 if case_full_name:
 return case_full_name[:80]
 return name_value[:80]


def apply_mapping(record: Dict[str, Any], mapping: Dict[str, Any], source_system: str, keep_raw: bool) -> Dict[str, Any]:
 candidate = dict(DEFAULT_CANDIDATE)
 candidate["source_system"] = source_system

 for target_field, source_expr in mapping.items():
 if target_field not in STANDARD_FIELDS:
 continue
 if isinstance(source_expr, str):
 value = dotted_get(record, source_expr)
 else:
 value = source_expr

 if value is None:
 continue

 if target_field in {"assertions", "tags", "covered_process_steps", "describe_context"}:
 normalized_list = normalize_string_list(value)
 candidate[target_field] = normalized_list
 elif target_field == "case_line":
 try:
 candidate[target_field] = int(value or 0)
 except (TypeError, ValueError):
 candidate[target_field] = 0
 else:
 normalized_value = stringify(value)
 if normalized_value:
 candidate[target_field] = normalized_value

 if not candidate["case_name"]:
 candidate["case_name"] = candidate["name"]
 if not candidate["case_full_name"]:
 candidate["case_full_name"] = candidate["name"]
 if not candidate["name"]:
 candidate["name"] = candidate["case_full_name"] or candidate["case_name"] or candidate["path"] or "external_candidate"
 if not candidate["description"]:
 candidate["description"] = candidate["case_full_name"] or candidate["name"]
 if not candidate["file_name"]:
 candidate["file_name"] = infer_file_name(candidate["path"], candidate["case_full_name"], candidate["name"])
 if not candidate["candidate_type"]:
 candidate["candidate_type"] = "external_case"
 if not candidate["source_type"]:
 candidate["source_type"] = "external_json"

 if keep_raw:
 candidate["raw_record"] = record

 return candidate


def build_default_mapping() -> Dict[str, str]:
 return {
 "name": "name",
 "path": "path",
 "description": "description",
 "assertions": "assertions",
 "tags": "tags",
 "covered_process_steps": "covered_process_steps",
 "candidate_type": "candidate_type",
 "case_name": "case_name",
 "case_full_name": "case_full_name",
 "case_line": "case_line",
 "describe_context": "describe_context",
 "file_name": "file_name",
 "source_type": "source_type",
 "source_system": "source_system",
 }


def parse_args() -> argparse.Namespace:
 parser = argparse.ArgumentParser(description="Collect external test candidates and convert them to candidates.json format.")
 parser.add_argument("external_json", help="Path to external JSON payload or exported candidate data")
 parser.add_argument("output_candidates", help="Output path for normalized candidates.json")
 parser.add_argument("--mapping-json", help="Path to field mapping json")
 parser.add_argument("--records-path", help="Dotted path to the record list inside the external payload")
 parser.add_argument("--source-system", default="external", help="Logical source record system name")
 parser.add_argument("--keep-raw", action="store_true", help="Keep original raw record under raw_record field")
 return parser.parse_args()


def main() -> int:
 args = parse_args()
 external_path = Path(args.external_json).expanduser().resolve()
 output_path = Path(args.output_candidates).expanduser().resolve()

 payload = load_json(external_path)
 records = detect_records(payload, args.records_path)

 mapping = build_default_mapping()
 if args.mapping_json:
 custom_mapping = load_json(Path(args.mapping_json).expanduser().resolve())
 if not isinstance(custom_mapping, dict):
 raise ValueError("mapping json must be an object")
 mapping.update(custom_mapping)

 candidates = [
 apply_mapping(record, mapping, args.source_system, args.keep_raw)
 for record in records
 if isinstance(record, dict)
 ]

 result = {
 "source": str(external_path),
 "source_system": args.source_system,
 "candidate_count": len(candidates),
 "candidates": candidates,
 }
 write_json(output_path, result)
 return 0


if __name__ == "__main__":
 raise SystemExit(main())