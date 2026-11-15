# 常见问题

按症状找，每条先说原因，再说怎么办。AI 助手遇到问题先看这里，再自己动手改，别让用户去敲命令。

## 环境和安装

### `node: command not found`，或 Node 版本太低
需要 Node 20.19 或更高（或 22.12 以上）。运行 `node --version` 看版本。去 Node.js 官网下载 LTS 版本安装，装完重开终端。

### `npm install` 很慢或失败
多半是网络。先重试一次。国内网络可以换 npm 镜像源，换源命令以所用镜像站的说明为准。报 `EACCES` 是目录权限问题，别用 `sudo`，把工程放到自己的文档目录里再装。

### `python3: command not found`（Windows）
Windows 上命令可能叫 `python` 或 `py`。把文档里的 `python3` 换成能用的那个。需要 Python 3.9 或更高。

### `没找到 Pillow`
运行 `pip install Pillow`（或 `python3 -m pip install Pillow`）。

### `没找到 ffmpeg`
只有素材里有视频时才需要。macOS：`brew install ffmpeg`。Windows：`winget install ffmpeg`。Ubuntu：`sudo apt install ffmpeg`。装完重开终端，再运行 `ffmpeg -version` 确认。

## 照片和视频

### HEIC 照片读不了
iPhone 默认格式。运行 `pip install pillow-heif` 后重试。macOS 上没装也会自动尝试系统自带的 `sips`。实在不行，先在手机相册里把照片导出成 JPG。

### 视频处理很慢
原片是 4K 或很长时，转码要几十秒到几分钟，正常。脚本只取 15 秒以内、720p。

### 页面里照片不显示
1. 运行 `python3 scripts/validate.py <工程目录>`，它会指出不存在的文件。
2. `trip.json` 里的路径要写成 `media/站点id/文件名`，相对 `public/`，不能是电脑上的绝对路径。
3. 文件名区分大小写，部署到服务器后尤其要注意。

### 视频在手机上不能播放
脚本输出的是 H.264 的 mp4，手机浏览器都能播。如果你自己放了别的格式，改用 `process_media.py` 重新生成。iOS 上视频需要点一下才开始播放，这是系统限制。

## 页面和构建

### 页面一片空白
打开浏览器的开发者工具（一般按 F12），看 Console 里的第一条红色报错。常见原因：
- `trip.json` 或 `scene.json` 少了逗号、引号。`validate.py` 会指出行号附近的位置。
- 站点 id 或路线名在两个文件里不一致。
- 直接双击打开了 `dist/index.html`。构建产物要放到网站服务器上，或用 `npm run preview` 打开。

### `npm run dev` 说端口被占用
Vite 会自动换下一个端口，看终端里打印的网址。

### `npm run build` 失败
先把报错最后几行读一遍。常见：`src/data/` 下的 JSON 不合法；自造组件文件里有语法错误。修好后重试。

### 部署后页面空白，但本地正常
页面里的脚本和媒体路径是从网站根目录开始的。把站点放在一个独立域名或根路径下最稳。放在子路径下（例如 `https://example.com/my-trip/`）时可能找不到文件，需要调整 Vite 的 `base` 设置，请助手按所用托管服务的说明处理。

## 画面

### 某个物件变成了一张纸牌
`scene.json` 里这个物件的 `type` 引擎里没有。检查拼写，或者按 `component-recipes.md` 做一个。

### 物件悬空或埋进地里
`y` 省略时会自动贴地。如果手写了 `y`，删掉它。物件在湖上时会贴水面，这是预期。

### 路线穿过山或湖
`routes` 里的点是手摆的折线。把路线点挪到平地上，或者在山和路之间多加几个点绕开。

### 山在错误的一侧
检查 `meta.viewFrom`，它是镜头在真实世界的方位。镜头从哪个方位看进来，哪个方位就在画面下方，对面方位在后排。骨架卡里确认过的方位关系优先。

### 站点挤在一起，点不开
距离压缩过头了，把站点之间拉开一点（保持相对方位不变），或者把相近的站点合并成一个。

### 纸雕组件看起来像一块板
这是剪影叠片最常见的问题，只用了一片。回到 `component-recipes.md` 第 3 步，按「至少 3 层」的要求加副层。

## 还是解决不了

把完整的报错文字复制给你的 AI 助手，同时说明做到了哪一步。不要只发截图的一角。
