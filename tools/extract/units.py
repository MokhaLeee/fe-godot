"""`struct UnitInfo[]` → 单位配置 JSON。

结构（`include/unit.h`）：

```
u8 pid, jid, pid_lead;
u8 autolevel:1, faction_id:2, level:5;
u8 x_load, y_load, x_move, y_move;
u8 items[4];
u8 ai[4];
```

初始化里都是位置参数，所以按顺序取 10 个标量 + 2 个花括号组。
`{ 0 }` 是数组终止符。
"""

from __future__ import annotations

import re
from pathlib import Path

from . import cexpr
from .symbols import Symbols

_DECL = re.compile(
    r"struct\s+UnitInfo\s+(?:CONST_DATA\s+|const\s+)*([A-Za-z_]\w*)\s*\[\s*\]\s*="
)

_SCALARS = (
    "pid",
    "jid",
    "pid_lead",
    "autolevel",
    "faction_id",
    "level",
    "x_load",
    "y_load",
    "x_move",
    "y_move",
)


def _bool(token: str) -> int:
    t = token.strip()
    if t in ("TRUE", "true"):
        return 1
    if t in ("FALSE", "false"):
        return 0
    value = cexpr.parse_int(t)
    return 0 if value is None else value


def _symbolic(symbols: Symbols, token: str, prefix: str) -> tuple[str | None, int | None]:
    """`PID_ROY` / `0x01` → (名字, 数值)；取不到名字时返回 None。"""
    t = token.strip()
    literal = cexpr.parse_int(t)
    if literal is not None:
        return symbols.name_of(literal, prefix), literal
    return t, symbols.values.get(t)


def _token_list(symbols: Symbols, group: str, prefix: str) -> list:
    """解析 `{ A, B, ... }` 花括号组。

    注意：必须先剥掉最外层花括号再切分，否则逗号会被当成「在花括号内部」而
    整组当成一个 token。
    """
    inner = group.strip()
    if inner.startswith("{") and inner.endswith("}"):
        inner = inner[1:-1]
    tokens = [t.strip() for t in cexpr.split_top(inner) if t.strip()]
    # 全 0 的组是 C 里的终止符，等价于空表
    if not tokens or all(cexpr.parse_int(t) == 0 for t in tokens):
        return []
    out: list = []
    for t in tokens:
        name, value = _symbolic(symbols, t, prefix)
        out.append(name if name else (value if value is not None else t))
    return out


def _raw_list(group: str) -> list:
    """原样保留 token（用于 AI 这种「前两个是宏、后两个是裸参数」的混合字段）。"""
    inner = group.strip()
    if inner.startswith("{") and inner.endswith("}"):
        inner = inner[1:-1]
    tokens = [t.strip() for t in cexpr.split_top(inner) if t.strip()]
    if all(cexpr.parse_int(t) == 0 for t in tokens):
        return []
    return tokens


def parse(path: Path, symbols: Symbols) -> dict[str, list[dict]]:
    """返回 {数组名: [单位, ...]}。"""
    text = cexpr.read(path)
    tables: dict[str, list[dict]] = {}

    for name, body, _line in cexpr.find_initializers(text, _DECL.pattern):
        units: list[dict] = []
        for row in cexpr.split_top(body):
            row = row.strip()
            if not row.startswith("{"):
                continue
            fields = cexpr.split_top(row.strip("{}"), ",")
            fields = [f.strip() for f in fields if f.strip()]
            if len(fields) < 10:
                continue
            if cexpr.parse_int(fields[0]) == 0 and len(fields) == 1:
                continue  # { 0 } 终止符
            pid, pid_id = _symbolic(symbols, fields[0], "PID_")
            jid, jid_id = _symbolic(symbols, fields[1], "JID_")
            lead, lead_id = _symbolic(symbols, fields[2], "PID_")
            faction, faction_id = _symbolic(symbols, fields[4], "FACTION_ID_")
            units.append(
                {
                    "pid": pid,
                    "pid_id": pid_id,
                    "jid": jid,
                    "jid_id": jid_id,
                    "leader": lead,
                    "leader_id": lead_id,
                    "autolevel": _bool(fields[3]),
                    "faction": faction,
                    "faction_id": faction_id,
                    "level": cexpr.parse_int(fields[5]),
                    "x_load": cexpr.parse_int(fields[6]),
                    "y_load": cexpr.parse_int(fields[7]),
                    "x_move": cexpr.parse_int(fields[8]),
                    "y_move": cexpr.parse_int(fields[9]),
                    "items": _token_list(symbols, fields[10], "IID_") if len(fields) > 10 else [],
                    "ai": _raw_list(fields[11]) if len(fields) > 11 else [],
                }
            )
        tables[name] = units
    return tables
