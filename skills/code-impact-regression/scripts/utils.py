#!/usr/bin/env python3
"""
公共工具函数模块，供 code-impact-regression 各脚本共享使用。
避免在多个脚本中重复定义相同的文本处理、符号拆分、去重等工具函数。
"""
import re
from typing import List

CAMEL_RE = re.compile(r"([a-z0-9])([A-Z])")

# 通用停用词，过滤掉无区分度的词汇
# 包含：语言关键词、架构层通用词、业务无关的技术词
STOPWORDS = {
    # 语言/逻辑关键词
    "the", "and", "for", "with", "from", "into", "this", "that", "true", "false",
    "not", "new", "null", "void", "list", "map", "set", "get",
    # 架构/分层通用词（在任何仓库都大量出现，无区分度）
    "data", "info", "util", "utils", "helper", "service", "manager", "handler",
    "impl", "default", "base", "common", "core", "api", "dto", "vo", "bo", "po",
    "request", "response", "result", "param", "params", "context", "config",
    "factory", "builder", "converter", "adapter", "proxy", "wrapper",
    "controller", "repository", "dao", "entity", "model", "domain",
    # 测试相关（召回脚本里不应用测试词匹配测试词）
    "test", "tests", "case", "cases", "spec", "mock", "stub",
    # 路径/包名常见通用段
    "src", "main", "java", "kotlin", "resources", "com", "org", "net",
    # 动词/操作词（过于宽泛）
    "create", "update", "delete", "query", "find", "load", "save", "build",
    "init", "check", "validate", "process", "handle", "execute", "run",
    "add", "remove", "insert", "select",
}


def normalize_text(value: str) -> str:
    """将文本统一转为小写、去除非字母数字字符（保留中文），并压缩空白。"""
    value = value or ""
    value = value.lower()
    value = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def tokenize(value: str) -> List[str]:
    """将文本 normalize 后按空格分词，返回非空 token 列表。"""
    text = normalize_text(value)
    if not text:
        return []
    return [t for t in text.split(" ") if t]


def split_symbol(symbol: str) -> List[str]:
    """
    将驼峰命名、下划线命名、连字符命名的符号拆分为词列表。
    例如：createOrderV2 -> ["create", "order", "v2"]
    """
    if not symbol:
        return []
    symbol = CAMEL_RE.sub(r"\1 \2", symbol)
    symbol = symbol.replace("_", " ").replace("-", " ").replace("/", " ")
    return tokenize(symbol)


def unique_list(items: List[str]) -> List[str]:
    """保序去重，过滤空字符串。"""
    seen = set()
    ordered = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def text_contains_term(text: str, term: str) -> bool:
    """
    判断 text 中是否包含 term。
    对于长度 > 2 的词直接做子串匹配；对于短词（≤2）使用词边界匹配，避免误命中。
    """
    if not term:
        return False
    if len(term) > 2:
        return term in text
    return re.search(rf"\b{re.escape(term)}\b", text) is not None