"""章节事件脚本 → JSON 指令流。

源码形态（`gameinfo/chapterinfo/events/*.c`）：

```c
static EventScr const EventScr_Chapter1_Opening[] =
{
	EvtUnitCameraOff
	EvtLoadUnits(UnitInfo_Chapter1_RedA)
	EvtCamera(11, 12)
	EvtEnd
};
```

宏之间没有分隔符，一个宏就是一条指令。导出成：

```json
{"op": "LoadUnits", "args": ["UnitInfo_Chapter1_RedA"]}
```

参数里的符号名（`MSG_008`、`FACTION_RED`、`EventScr_Chapter1_Village`）
原样保留，由消费端用 `symbols.json` 解析 —— 这样 JSON 保持可读、可 diff。

移动脚本（`MoveScr_*`）是逗号分隔的字节流（`MOVE_CMD_MOVE_UP, 18`），
只导出 token 序列，指令化留给事件 VM（M3）。
"""

from __future__ import annotations

import re
from pathlib import Path

from . import cexpr

_EVENT_DECL = re.compile(
    r"(?:EventListScr|EventScr)\b[^\n;{]*?([A-Za-z_]\w*)\s*\[\s*\]\s*="
)
_MOVE_DECL = re.compile(r"\bMoveScr\b[^\n;{]*?([A-Za-z_]\w*)\s*\[\s*\]\s*=")
_OP = re.compile(r"\bEvt([A-Za-z0-9_]+)")


def _scan_call(text: str, start: int) -> tuple[str | None, int]:
    """从 `(` 起找配对的 `)`，返回 (括号内文, 结束下标)。"""
    depth = 0
    i = start
    while i < len(text):
        c = text[i]
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return text[start + 1 : i], i + 1
        i += 1
    return None, len(text)


def parse_args(raw: str | None) -> list:
    if raw is None:
        return []
    args: list = []
    for item in cexpr.split_top(raw):
        token = item.strip()
        if not token:
            continue
        literal = cexpr.parse_int(token)
        args.append(literal if literal is not None else token)
    return args


def parse_ops(body: str) -> tuple[list[dict], list[str]]:
    """把宏流拆成指令；返回 (指令列表, 无法识别的宏名)。"""
    ops: list[dict] = []
    unknown: list[str] = []
    pos = 0
    while True:
        m = _OP.search(body, pos)
        if not m:
            break
        name = m.group(0)
        pos = m.end()
        args_raw = None
        probe = pos
        while probe < len(body) and body[probe] in " \t\r\n":
            probe += 1
        if probe < len(body) and body[probe] == "(":
            args_raw, pos = _scan_call(body, probe)
        ops.append({"op": m.group(1), "args": parse_args(args_raw)})
        if not name.startswith("Evt"):
            unknown.append(name)
    return ops, unknown


def parse(path: Path) -> dict:
    """返回 {"event_scripts": {...}, "event_lists": {...}, "move_scripts": {...}}。"""
    text = cexpr.read(path)
    scripts: dict[str, list[dict]] = {}
    lists: dict[str, list[dict]] = {}
    moves: dict[str, list[str]] = {}

    for name, body, _line in cexpr.find_initializers(text, _EVENT_DECL.pattern):
        ops, _ = parse_ops(body)
        # EventListScr_* 里的 EvtList* 指令与 EventScr 同名空间，按名字归类
        if "List" in name or any(op["op"].startswith("List") for op in ops):
            lists[name] = ops
        else:
            scripts[name] = ops

    for name, body, _line in cexpr.find_initializers(text, _MOVE_DECL.pattern):
        tokens = [t.strip() for t in cexpr.split_top(body)]
        moves[name] = [t for t in tokens if t]

    return {"event_scripts": scripts, "event_lists": lists, "move_scripts": moves}
