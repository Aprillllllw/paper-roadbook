# trip.json 字段说明

`trip.json` 放你的内容：标题、每天走哪几站、每站的文字和照片视频。位置：工程里的 `src/data/trip.json`。

地图上的位置不在这里，在 `scene.json`（见 `scene-schema.md`）。两个文件靠**站点 id** 和**路线名**对上。

## 最小示例

```json
{
  "title": "我的海边三日",
  "subtitle": "自驾 · 3 天 · 10 月",
  "author": { "name": "你的名字", "line": "一句话介绍这趟旅行" },
  "lang": "zh",
  "days": [
    { "id": "D1", "label": "Day 1", "title": "机场到海边民宿", "km": 120,
      "drive": "约 2 小时", "route": "D1", "stops": ["airport", "beach-inn"] }
  ],
  "stops": {
    "airport":   { "name": "机场", "kind": "pass" },
    "beach-inn": {
      "name": "海边民宿", "kind": "stay",
      "media": [ { "type": "photo", "src": "media/beach-inn/beach-inn_01.webp" } ],
      "info": { "住": "在这里写你的住宿体验", "花费": "每晚 xxx 元" }
    }
  },
  "facts": [ { "label": "总里程", "value": "约 300 公里" } ],
  "disclaimer": "方位真实，距离已压缩，比例不按真实。"
}
```

## 顶层字段

| 字段 | 必填 | 说明 |
|---|---|---|
| `title` | 是 | 页面大标题，也是浏览器标签页标题 |
| `subtitle` | 否 | 副标题，写天数、季节、出行方式都行 |
| `author` | 否 | `name` 名字或昵称；`line` 一句话介绍；`avatar` 头像路径（相对 `public/`，如 `media/avatar.jpg`）；不想露面就删掉 `avatar` |
| `lang` | 否 | `zh` 或 `en`，决定页面按钮等固定文案的语言。默认 `zh` |
| `days` | 是 | 每一天，见下 |
| `stops` | 是 | 所有站点的内容，见下 |
| `facts` | 否 | 页面底部的几条小信息，如总里程、最佳季节、预算。每条 `label` 和 `value`，可选 `icon` |
| `disclaimer` | 建议保留 | 页面固定显示。可以改文案，不要删，它是对看路书的人的说明 |

## days[]

| 字段 | 必填 | 说明 |
|---|---|---|
| `id` | 是 | 唯一，如 `D1` |
| `label` | 否 | 显示名，如 `Day 1` |
| `title` | 建议 | 这一天一句话：从哪到哪 |
| `km` | 否 | 数字，当天里程 |
| `drive` | 否 | 文字，如「约 2 小时」。想写「地图上两小时，我开了三小时」也行 |
| `route` | 是 | 必须是 `scene.json` 里 `routes` 的一个键。通常和 `id` 同名 |
| `stops` | 是 | 当天经过的站点 id，按先后排列。同一站一天里出现两次（比如 丽江→蓝月谷→丽江）是允许的，地图上只会显示一个图钉，面板里的上一站/下一站仍按两次经过来走 |

## stops{}

键是站点 id，只用小写字母、数字、连字符（`beach-inn`）。**同一个 id 必须在 `scene.json` 的 `stops` 里也有**，否则地图上没处放它。

| 字段 | 说明 |
|---|---|
| `name` | 站点名（页面主显示） |
| `zh` | 另一种语言的名字，可省 |
| `kind` | `stay` 住宿 / `pass` 路过 / `sight` 景点。决定图钉样式 |
| `media` | 照片视频列表，见下。没有就不写，面板只显示文字，不留空框 |
| `info` | 任意键值对。键就是面板里的小标题，值是你的文字。常用键：住、吃、感受、花费、提醒 |
| `extra` | 预留，留 `null` 或不写 |

`info` 的键你自己定，写你真有的内容。没有的项目不要写，也不要让助手替你编。

### media[]

```json
{ "type": "photo", "src": "media/beach-inn/beach-inn_01.webp" }
{ "type": "video", "src": "media/beach-inn/beach-inn_02.mp4", "poster": "media/beach-inn/beach-inn_02_poster.webp" }
```

路径相对工程的 `public/` 目录。`process_media.py` 会生成这些文件，并在 `media_manifest.json` 里给出可以直接粘贴的列表。

## 常见错误

- 站点 id 在两个文件里拼写不同。`python3 scripts/validate.py <工程目录>` 会指出来。
- `days[].route` 写了 `scene.json` 里没有的路线名。
- 照片路径写成电脑上的绝对路径。必须是 `media/…` 这样相对 `public/` 的路径。
