# Windows ⇄ Ubuntu 分工

| 路径 | 归属 |
|---|---|
| `scenes/` | Windows 独占 |
| `assets/` 视觉 | Windows 独占 |
| `core/` | Ubuntu 独占 |
| `data/*.tres` | Ubuntu 生成 |
| `tools/` | Ubuntu |
| `tests/` | Ubuntu 主写 |
| `project.godot` / `export_presets.cfg` | 改前告知 |

开工：`git pull --rebase --autostash`
收工：`git push`

**永远不要两边同时编辑同一个 `.tscn`。**

`.tscn` 冲突处理：
```bash
git checkout --theirs scenes/battle.tscn
git add scenes/battle.tscn
```
然后回 Windows 编辑器重做本地改动。
