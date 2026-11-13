"""够用即可的 C 文本解析。

只覆盖 FE6 反编译源码里实际出现的形态：
- `enum { A = 0x00, B, };`
- `#define NAME 0x1234`
- `static struct Foo const Bar[] = { ... };`
- 以括号调用、以空白分隔的宏流（`EvtTalk(MSG_008)`）

不做通用 C 语法分析；遇到不认识的结构宁可返回 None 也不抛异常。
"""

from __future__ import annotations

import re
from pathlib import Path


def strip_comments(text: str) -> str:
    """去掉 // 与 /* */ 注释。

    字符串/字符字面量原样保留；块注释里的换行保留，使行号大致稳定。
    """
    out: list[str] = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c in ('"', "'"):
            j = i + 1
            while j < n:
                if text[j] == "\\":
                    j += 2
                    continue
                if text[j] == c:
                    j += 1
                    break
                j += 1
            out.append(text[i:j])
            i = j
            continue
        if c == "/" and i + 1 < n and text[i + 1] == "/":
            j = text.find("\n", i)
            i = n if j < 0 else j
            continue
        if c == "/" and i + 1 < n and text[i + 1] == "*":
            j = text.find("*/", i + 2)
            end = n if j < 0 else j + 2
            out.append("\n" * text.count("\n", i, end))
            i = end
            continue
        out.append(c)
        i += 1
    return "".join(out)


def match_brace(text: str, open_idx: int) -> int:
    """返回与 text[open_idx]=='{' 匹配的 '}' 下标；不匹配返回 -1。"""
    depth = 0
    i, n = open_idx, len(text)
    while i < n:
        c = text[i]
        if c in ('"', "'"):
            q = c
            i += 1
            while i < n:
                if text[i] == "\\":
                    i += 2
                    continue
                if text[i] == q:
                    break
                i += 1
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def split_top(text: str, sep: str = ",") -> list[str]:
    """按顶层分隔符切分，忽略 () [] {} 与字符串内部的分隔符。"""
    parts: list[str] = []
    depth = 0
    cur: list[str] = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c in ('"', "'"):
            q = c
            j = i + 1
            while j < n:
                if text[j] == "\\":
                    j += 2
                    continue
                if text[j] == q:
                    j += 1
                    break
                j += 1
            cur.append(text[i:j])
            i = j
            continue
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        elif c == sep and depth == 0:
            parts.append("".join(cur))
            cur = []
            i += 1
            continue
        cur.append(c)
        i += 1
    tail = "".join(cur)
    if tail.strip():
        parts.append(tail)
    return parts


_INT_SUFFIX = re.compile(r"[uUlL]+$")


def parse_int(tok: str | None) -> int | None:
    """解析整数字面量；支持 0x / 0b / 十进制 / 字符字面量 / `1 << n`。"""
    if tok is None:
        return None
    t = tok.strip()
    if not t:
        return None
    if t.startswith("(") and t.endswith(")"):
        return parse_int(t[1:-1])
    m = re.fullmatch(r"(0[xX][0-9A-Fa-f]+|0[bB][01]+|\d+)", _INT_SUFFIX.sub("", t))
    if m:
        s = m.group(1)
        if s[:2].lower() == "0x":
            return int(s, 16)
        if s[:2].lower() == "0b":
            return int(s, 2)
        return int(s, 10)
    m = re.fullmatch(r"(\d+)\s*<<\s*(\d+)", t)
    if m:
        return int(m.group(1)) << int(m.group(2))
    if len(t) == 3 and t[0] == "'" and t[2] == "'":
        return ord(t[1])
    return None


def find_initializers(text: str, decl_pattern: str) -> list[tuple[str, str, int]]:
    """找出所有 `... <pattern 捕获名> ... = { ... }`，返回 (名字, 花括号内文, 行号)。"""
    out: list[tuple[str, str, int]] = []
    for m in re.finditer(decl_pattern, text):
        open_idx = text.find("{", m.end())
        if open_idx < 0:
            continue
        close_idx = match_brace(text, open_idx)
        if close_idx < 0:
            continue
        line = text.count("\n", 0, open_idx) + 1
        out.append((m.group(1), text[open_idx + 1 : close_idx], line))
    return out


def parse_enum_blocks(text: str, known: dict[str, int] | None = None) -> dict[str, int]:
    """解析所有 `enum { ... }` 块。未知表达式记 None 并跳过该名字。"""
    result: dict[str, int] = dict(known or {})
    for m in re.finditer(r"\benum\b[^{;]*\{", text):
        open_idx = m.end() - 1
        close_idx = match_brace(text, open_idx)
        if close_idx < 0:
            continue
        body = text[open_idx + 1 : close_idx]
        next_value = 0
        for entry in split_top(body):
            e = entry.strip()
            if not e:
                continue
            if "=" in e:
                name, _, expr = e.partition("=")
                name = name.strip()
                expr = expr.strip()
                value = parse_int(expr)
                if value is None:
                    value = result.get(expr)
                if value is None:
                    next_value = None
                    continue
                next_value = value + 1
            else:
                name = e
                if next_value is None:
                    continue
                value = next_value
                next_value = value + 1
            if re.fullmatch(r"[A-Za-z_]\w*", name):
                result[name] = value
    return result


def parse_defines(text: str, known: dict[str, int] | None = None) -> dict[str, int]:
    """解析 `#define NAME <整数字面量>`；带参数的宏与字符串宏忽略。"""
    result: dict[str, int] = dict(known or {})
    for m in re.finditer(r"^[ \t]*#[ \t]*define[ \t]+([A-Za-z_]\w*)[ \t]+([^\n/]+)", text, re.M):
        name, expr = m.group(1), m.group(2).strip()
        value = parse_int(expr)
        if value is not None:
            result[name] = value
    return result


def read(path: Path) -> str:
    return strip_comments(path.read_text(encoding="utf-8", errors="replace"))
