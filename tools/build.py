#!/usr/bin/env python3
"""构建封装：校验 + 测试 + 导出。路径全部相对项目根。"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FE6_ROOT = Path(os.environ.get("FE6_ROOT", Path.home() / "fe6-rebuild"))


def _find_godot() -> str:
    """优先 PATH，其次 ~/tools 下的 4.7.2 官方二进制（Server 环境常没建软链）。"""
    found = shutil.which("godot")
    if found:
        return found
    for candidate in sorted(Path.home().glob("tools/Godot_v4.7.2-stable_linux.*"), reverse=True):
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return "godot"


GODOT = _find_godot()

TARGETS = {
    "windows": ("Windows Desktop", "build/windows/tactics.exe"),
    "linux": ("Linux/X11", "build/linux/tactics.x86_64"),
}

# 纯脚本测试（不依赖 GUT）。新增测试文件后加到这里。
SCRIPT_TESTS = ["tests/test_rng.gd", "tests/test_extract.gd"]


def run(args: list[str]) -> None:
    print("+", " ".join(args), flush=True)
    proc = subprocess.run(args, cwd=ROOT)
    if proc.returncode != 0:
        raise SystemExit(f"命令失败，退出码 {proc.returncode}")


def check() -> None:
    run([sys.executable, str(ROOT / "tools" / "gen_units.py"), "--check"])
    run([sys.executable, str(ROOT / "tools" / "gen_rng_golden.py"), "--check"])
    if (FE6_ROOT / "Makefile").is_file():
        run([sys.executable, str(ROOT / "tools" / "extract_chapter.py"), "--chapter", "1", "--check"])
    else:
        print(f"跳过：未找到 fe6-rebuild（{FE6_ROOT}），设置 FE6_ROOT 可启用内容导出校验")


def extract() -> None:
    run([sys.executable, str(ROOT / "tools" / "extract_chapter.py"), "--chapter", "1"])


def test() -> None:
    for script in SCRIPT_TESTS:
        run([GODOT, "--headless", "--path", str(ROOT), "-s", script])

    gut = ROOT / "addons" / "gut" / "gut_cmdln.gd"
    if not gut.exists():
        print("跳过 GUT：未安装 addons/gut")
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
        print("用法: python3 tools/build.py [check|test|extract|export <windows|linux>|all]")
        return 2

    cmd, *rest = argv
    if cmd == "check":
        check()
    elif cmd == "test":
        test()
    elif cmd == "extract":
        extract()
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
