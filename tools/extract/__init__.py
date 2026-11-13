"""FE6 反编译源码 → Godot 内容的导出工具包。

模块划分：

- `cexpr`      轻量 C 文本解析（去注释、花括号匹配、枚举/宏取値）
- `symbols`    汇总 include/ 下的枚举与 #define，得到 名字 → 整数
- `mapdata`    章节地图（.dmp + TsaConf）→ 网格 JSON + 预览 PNG
- `units`      `struct UnitInfo[]` → 单位配置
- `events`     `EventScr` / `EventListScr` → 事件指令流
- `texts`      `texts/**/*.txt` → 对白 JSON
- `chaptermeta` `ChapterInfoTable` → 章节元数据
- `tileset`    tileset 目录 → Godot 图集 + metatile 表

所有模块只做「读源码、写 JSON/PNG」，不含游戏逻辑。
"""
