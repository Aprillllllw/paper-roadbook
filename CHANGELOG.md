# 更新记录

## 1.0.0

首个公开版本。

- Skill 流程：收集行程、信息核对、地理骨架扫描、微缩构图、新建工程、处理照片视频、补做组件、校验与预览、可选部署。
- 引擎模板：Vite + Three.js，数据驱动（`scene.json` 管地图，`trip.json` 管内容），两套主题（冬季粉米色、夏季草地）。
- 组件：内置纸雕组件和「纸雕工具箱」，可按 `references/component-recipes.md` 自造组件。
- 脚本：`geo_scan.py`、`process_media.py`（去 GPS）、`validate.py`、`new_project.py`。
- 9 个可选 GLB 模型（见 `ASSETS_LICENSE.md`）。
- 示例：`examples/demo-trip/`。
- 画面饱满度检查：`scripts/fullness.py` 判断「空 / 及格 / 饱满」，指出哪里空，并给出可以直接问用户的问题；`--pre` 模式在构图之前预估内容够不够。具体的东西（建筑、动物、人、船、车）只放用户说过的，自然填充可以自己补。构图指南新增「填满画面」。
