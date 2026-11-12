#!/usr/bin/env python3
"""构建封装：校验 + 测试 + 导出。路径全部相对项目根。"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GODOT = shutil.which("godot") or "godot"

TARGETS = {
    "windows": ("Windows Desktop", "build/windows/tactics.exe"),
    "linux": ("Linux/X11", "build/linux/tactics.x86_64"),
}


def run(args: list[str]) -> None:
    print("+", " ".join(args), flush=True)
    proc = subprocess.run(args, cwd=ROOT)
    if proc.returncode != 0:
        raise SystemExit(f"命令失败，退出码 {proc.returncode}")


def check() -> None:
    run([sys.executable, str(ROOT / "tools" / "gen_units.py"), "--check"])


def test() -> None:
    gut = ROOT / "addons" / "gut" / "gut_cmdln.gd"
    if not gut.exists():
        print("跳过：未安装 GUT 插件")
        return
    run([
        GODOT, "--headless", "--path", str(ROOT),
        "-s", "addons/gut/gut_cmdln.gd",
        "-gdir=res://tests", "-gexit",
    ])


def export(target: str) -> None:
    if target not in TARGETS:
        raise SystemExit(f"未知目标 {target!r}，可选: {', '.join(TARGETS)}")
    preset, out = TARGETS[target]
    (ROOT / out).parent.mkdir(parents=True, exist_ok=True)
    run([GODOT, "--headless", "--path", str(ROOT),
         "--export-release", preset, out])


def main() -> int:
    argv = sys.argv[1:]
    if not argv:
        print("用法: python3 tools/build.py [check|test|export <windows|linux>|all]")
        return 2

    cmd, *rest = argv
    if cmd == "check":
        check()
    elif cmd == "test":
        test()
    elif cmd == "export":
        export(rest[0] if rest else "windows")
    elif cmd == "all":
        check()
        test()
        export("windows")
    else:
        raise SystemExit(f"未知命令 {cmd!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
