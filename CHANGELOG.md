# 更新记录

## 1.0.1

- 修复：`new_project.py` 生成的占位 trip.json，相邻两天共用的站点（例如 D1 终点 = D2 起点）现在两天都会出现，并按沿路线的先后排序。
- 修复：`geo_scan.py` 的骨架卡，河流或湖泊数据没取到时，不再写「没有找到」，改为「这次没取到，不代表这里没有」。湖和河分开判断。
- 修复：无名山峰的标签从英文 `N m peak` 改成「无名峰 N 米」。
- 新增：`PROMPT_XHS.md`，小红书帖子用的短版提示词。

## 1.0.0

首个公开版本。

- Skill 流程：收集行程、信息核对、地理骨架扫描、微缩构图、新建工程、处理照片视频、补做组件、校验与预览、可选部署。
- 引擎模板：Vite + Three.js，数据驱动（`scene.json` 管地图，`trip.json` 管内容），两套主题（冬季粉米色、夏季草地）。
- 组件：内置纸雕组件和「纸雕工具箱」，可按 `references/component-recipes.md` 自造组件。
- 脚本：`geo_scan.py`、`process_media.py`（去 GPS）、`validate.py`、`new_project.py`。
- 9 个可选 GLB 模型（见 `ASSETS_LICENSE.md`）。
- 示例：`examples/demo-trip/`。
- 画面饱满度检查：`scripts/fullness.py` 判断「空 / 及格 / 饱满」，指出哪里空，并给出可以直接问用户的问题；`--pre` 模式在构图之前预估内容够不够。具体的东西（建筑、动物、人、船、车）只放用户说过的，自然填充可以自己补。构图指南新增「填满画面」。
