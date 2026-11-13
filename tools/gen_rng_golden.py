#!/usr/bin/env python3
"""生成 `tests/golden/rng.json`：FE6 随机数的参考序列。

用途只有一个：给 `core/rng.gd` 一个可以自动对拍的目标。C 实现见
`fe6-rebuild/src/Common/sys/random.c`，本文件按同一算法重写一遍。

> 阶段说明：这里验证的是「GDScript 是否精确复现了 C 的位运算与截断」，
> 不是「C 是否与 ROM 一致」。M1 会用 `tools/emu/gbarun` 从 ROM 里取真实序列
> 做来源校验，两者互补。

用法：
```bash
python3 tools/gen_rng_golden.py            # 写 tests/golden/rng.json
python3 tools/gen_rng_golden.py --check    # 只校验
```
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GOLDEN = ROOT / "tests" / "golden" / "rng.json"

U16 = 0xFFFF
INIT_TABLE = [0xA36E, 0x924E, 0xB784, 0x4F67, 0x8092, 0x592D, 0x8E70, 0xA794]


class Rng:
    """`NextRN` / `RandInit` 的 Python 参考实现。"""

    def __init__(self) -> None:
        self.state = [0, 0, 0]
        self.lcg = 0

    def rand_init(self, seed: int) -> None:
        i = seed % 7
        self.state = [INIT_TABLE[i % 8], INIT_TABLE[(i + 1) % 8], INIT_TABLE[(i + 2) % 8]]
        for _ in range(seed % 23):
            self.next_rn()

    def next_rn(self) -> int:
        rn = ((self.state[1] << 11) + (self.state[0] >> 5)) & U16
        s2 = (self.state[2] << 1) & U16
        if self.state[1] & 0x8000:
            s2 = (s2 + 1) & U16
        rn ^= s2
        self.state = [rn, self.state[0], self.state[1]]
        return rn

    def next_range(self, max_value: int) -> int:
        return (self.next_rn() * max_value) // 65535

    def next_100(self) -> int:
        return self.next_range(100)

    def roll(self, threshold: int) -> bool:
        return threshold > self.next_100()

    def roll_2rn(self, threshold: int) -> bool:
        return threshold > ((self.next_100() + self.next_100()) // 2)

    def rand_init_b(self, seed: int) -> None:
        self.lcg = seed & 0xFFFFFFFF

    def next_b(self) -> int:
        value = ((self.lcg << 2) + 2) & 0xFFFFFFFF
        value = (value * (value + 1)) & 0xFFFFFFFF
        value >>= 2
        self.lcg = value
        return value


def build() -> dict:
    cases = []
    for seed in range(8):
        rng = Rng()
        rng.rand_init(seed)
        cases.append(
            {
                "seed": seed,
                "state_after_init": list(rng.state),
                "rn": [rng.next_rn() for _ in range(16)],
            }
        )

    # 带 burn 的种子（seed % 23 != 0），覆盖 burn 循环
    burn = []
    for seed in (23, 45, 100, 1234):
        rng = Rng()
        rng.rand_init(seed)
        burn.append(
            {
                "seed": seed,
                "state_after_init": list(rng.state),
                "rn": [rng.next_rn() for _ in range(8)],
            }
        )

    ranged = Rng()
    ranged.rand_init(1234)
    range_case = {
        "seed": 1234,
        "max": 100,
        "values": [ranged.next_100() for _ in range(24)],
    }

    rolls = Rng()
    rolls.rand_init(777)
    roll_case = {
        "seed": 777,
        "threshold": 30,
        "values": [rolls.roll(30) for _ in range(24)],
        "two_rn": [rolls.roll_2rn(30) for _ in range(24)],
    }

    lcg = Rng()
    lcg.rand_init_b(1)
    lcg_case = {"seed": 1, "values": [lcg.next_b() for _ in range(8)]}

    return {
        "_comment": "由 tools/gen_rng_golden.py 生成；算法见 fe6-rebuild src/Common/sys/random.c",
        "init_table": INIT_TABLE,
        "cases": cases,
        "burn_cases": burn,
        "range": range_case,
        "roll": roll_case,
        "lcg": lcg_case,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    content = json.dumps(build(), ensure_ascii=False, indent=1) + "\n"
    if args.check:
        if not GOLDEN.is_file() or GOLDEN.read_text(encoding="utf-8") != content:
            print(f"drift: {GOLDEN.relative_to(ROOT)}", flush=True)
            return 1
        print("OK: rng.json 与参考实现一致")
        return 0

    GOLDEN.parent.mkdir(parents=True, exist_ok=True)
    if not GOLDEN.is_file() or GOLDEN.read_text(encoding="utf-8") != content:
        GOLDEN.write_text(content, encoding="utf-8", newline="\n")
        print(f"写入 {GOLDEN.relative_to(ROOT)}")
    else:
        print(f"未变化 {GOLDEN.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
