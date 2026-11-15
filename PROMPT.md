# 不装 Skill，直接用提示词

复制下面的提示词，发给你的 AI 编程助手。助手需要能在你的电脑上读写文件、运行命令。下面共四个版本，选一个用。

1. 仓库版（中文）：助手能从仓库地址取回完整工程。
2. 仓库版（英文）。
3. 自包含版（中文）：助手拿不到仓库时用。
4. 自包含版（英文）。



## 1. 仓库版（中文）

```
我想把自己的一趟旅行做成「3D 纸雕路书」：一个可以旋转的微缩纸雕地图网页，点每个站点能看我的照片、视频和笔记。

请这样做：
1. 先检查电脑上有没有 Node 20.19+ 或 22.12+、Python 3.9+、ffmpeg。缺的告诉我怎么装。
2. 从 https://github.com/Aprillllllw/paper-roadbook 取回这个工程（git clone 或下载 zip 都行），放到我指定的目录。
3. 读工程根目录的 SKILL.md，严格按里面的 9 个步骤带我做。每一步做完先和我确认再往下走。
4. 三条原则：方位真实，距离压缩，比例不按真实；不使用任何付费 API 或 3D 软件；不编造，我没说的点评、价格、体验就留空，要问我。
5. 我的照片和视频必须用 scripts/process_media.py 处理，去掉 GPS 后才能放进网页。
6. 发布到公网之前一定先问我。

现在从第 1 步开始：问我这趟旅行有几天、每天去哪几站，以及照片放在哪个文件夹。
```

## 2. Repo version (English)

```
I want to turn one of my trips into a 3D paper-diorama road book: a rotatable miniature map web page where each stop opens my photos, videos and notes.

Please:
1. Check that Node 20.19+ or 22.12+, Python 3.9+ and ffmpeg are installed. Tell me how to install anything missing.
2. Get the project from https://github.com/Aprillllllw/paper-roadbook (git clone or zip) into a folder I choose.
3. Read SKILL.md at the project root and follow its 9 steps in order. Confirm with me after each step before moving on.
4. Three principles: real directions, compressed distances, scale not true; no paid APIs or 3D software; no invention. Leave anything I did not tell you (reviews, prices, experiences) empty and ask me.
5. Process all my photos and videos with scripts/process_media.py so GPS data is removed before they go into the page.
6. Always ask me before publishing anything online.

Start with step 1: ask how many days the trip was, which stops each day had, and which folder holds my photos.
```

## 3. 自包含版（中文）

助手拿不到仓库时用，整段复制。

```
请帮我把一趟旅行做成「3D 纸雕路书」网页：一块可以旋转的微缩纸雕地图，上面有山、湖、路线和纸模型小物件，点每个站点能看我的照片、视频和笔记。请从零搭一个，不要用任何付费 API 或 3D 软件。

【三条原则】
1. 方位真实，距离压缩，比例不按真实。页面上固定显示这句说明。
2. 零付费依赖，不要我提供任何 API key。
3. 不编造。内容只用我告诉你的和公开地理数据，没有的字段留空，或者问我。

【技术栈】
Vite + Three.js（纯前端，npm 安装），数据分成两个 JSON：trip.json 放内容，scene.json 放地图构图。照片和视频放 public/media/。

【流程】
1. 先问我：天数、每天的站点（先后顺序）、每站的类型（住/路过/景点）、住宿、吃饭、感受、花费、素材文件夹、语言、季节。没说的不要补。列成清单让我逐项确认。
2. 地理骨架扫描：
   - 拿到每个站点的经纬度（我给，或你查后让我确认）。
   - 用公开的高程瓦片取地形：AWS 公开数据桶里的 Terrarium 格式瓦片（路径 elevation-tiles-prod/terrarium/{z}/{x}/{y}.png），免费无需 key。高程 = R*256 + G + B/256 - 32768，单位米。
   - 把行程范围的真实位置换算成相对方位：以所有站点的中心为原点，dx = 经度差 × cos(中心纬度)，dz = -纬度差（北在上），再按镜头方位旋转（镜头从南面看进来时北在后排）。
   - 距离压缩：把每个点到中心的距离 r 压成 R × (r / r_max)^0.7，方向不变，让所有点落在底板椭圆（半轴 a=62、b=46）的 85% 以内。
   - 高程高的区域变成山，放在对应方位，最高的山放后排（z 为负）；水面变成湖和河。
   - 写一张「骨架卡」：每个站点相对中心的方位和压缩后的距离，山在哪一侧，水在哪一侧，镜头从哪个方位看。给我确认或纠正，纠正后再继续。
3. scene.json 的结构：
   {version:1, board:{a:62,b:46}, theme:{season, preset}, stops:{id:[x,z]}, routes:{"D1":[[x,z],...]}, peaks:[{x,z,H,R,n}], ranges:[{pts,H,W}], lakes:[{x,z,rx,rz,rot}], rivers:[{w,pts}], props:[{type,x,z,s,rotY}], clumps:[{type,x,z,n,r}]}
   x 向右，z 朝镜头，y 向上；所有内容在椭圆内。
   trip.json 的结构：
   {title, subtitle, author:{name,line}, lang, days:[{id,title,km,drive,route,stops:[]}], stops:{id:{name,kind,media:[{type,src,poster}],info:{}}}, facts:[], disclaimer}
   两个文件的站点 id 必须一致，days[].route 必须是 scene.routes 里的键。
4. 照片和视频：用脚本（ffmpeg + Pillow）处理。照片转 webp，长边最长 1600；视频转 720p、无声、最长 15 秒，加一张封面；所有输出去掉 EXIF 和 GPS。不要把原图直接放进网页。
5. 渲染：底板是椭圆纸板，地形用低多边形（山用 5–7 面的锥体，湖是略低于地面的蓝色椭圆），镜头从斜上方俯视，可以用鼠标旋转。路线是沿折线移动的小车和一条发光的线。每个站点是一个图钉，点开后显示面板。没有照片的站点只显示文字。
6. 纸雕组件（毡房、桥、房子、动物、树等）全部用代码做，分三种手法：
   - 旋转体：圆的对称物体，画半边轮廓绕轴转一圈（毡房、灯塔、树干）。
   - 搭积木：方的物体，用盒子、圆柱、圆锥拼装（房子、桥、车）。
   - 剪影叠片：有机物体，画侧面轮廓，挤出厚度，至少 3 层沿 z 方向错开叠起来（动物、人、树冠），不能只用一片，否则正面看是一块木板。
   每个组件最多 5 种颜色，带倒角，外轮廓加一圈深色描边；冬季才加雪。
7. 必须自查：每做完一个组件，用浏览器（或无头浏览器）从斜俯视、正侧面、正前方三个角度截图，检查缩小后认得出是什么、没有零件埋住、没有变成一块板，不合格就改。整页做完后再截图一次俯视和一次点开站点面板的画面给我看。
8. 数据检查：站点和摆件都在椭圆内，id 两边一致，媒体文件都存在。再做一次饱满度自查：把底板切成约 10×8 的格子，看有多少格里有东西（站点、摆件、湖、山、路线），低于 70% 就算空；找出最大的一块空地；每个站点周围要有标志性的东西，路线两侧不要长段空着，摆件种类至少 5 种。哪里空，就问我那里真实有什么（建筑、动物、人、船、车），我说了你再摆，不要自己编；树、草丛、石头这类自然填充可以自己补。
9. 本地预览给我看，按我的意见改。发布到公网之前一定先问我。

请从第 1 步开始，先问我天数、每天的站点和照片在哪个文件夹。
```

## 4. Self-contained version (English)

For assistants that cannot fetch the repo. Copy it whole.

```
Please build me a "3D paper-diorama road book" web page from scratch: a rotatable miniature paper map with mountains, lakes, a route and little paper-model props, where each stop opens my photos, videos and notes. Do not use any paid API or 3D software.

Principles:
1. Real directions, compressed distances, scale not true. Show this sentence on the page.
2. Zero paid dependencies. Never ask me for an API key.
3. No invention. Use only what I tell you plus public geographic data. Leave missing fields empty or ask me.

Stack: Vite + Three.js (front end only, installed with npm). Two JSON files: trip.json for content, scene.json for the map composition. Media goes in public/media/.

Steps:
1. Ask me: number of days, the stops for each day in order, the type of each stop (stay/pass/sight), lodging, food, feelings, costs, my media folder, language, season. Do not fill in anything I did not say. List it all back for me to confirm.
2. Geographic skeleton scan:
   - Get each stop's latitude and longitude (from me, or look up and let me confirm).
   - Get terrain from public elevation tiles: the Terrarium-format tiles in the AWS public data bucket (path elevation-tiles-prod/terrarium/{z}/{x}/{y}.png), free, no key. Elevation in meters = R*256 + G + B/256 - 32768.
   - Convert real positions to relative bearings: origin at the centroid of all stops, dx = longitude difference * cos(centroid latitude), dz = -latitude difference, then rotate for the camera direction (looking in from the south puts north at the back row).
   - Compress distances: map each point's distance r from the centroid to R * (r / r_max)^0.7, keeping the direction, so everything sits within 85% of the elliptical board (semi-axes a=62, b=46).
   - High terrain becomes mountains at the matching bearing, tallest at the back (negative z). Water becomes lakes and rivers.
   - Write a "skeleton card": each stop's bearing and compressed distance from the centroid, which side the mountains are on, which side the water is on, and the camera direction. Let me confirm or correct it before you continue.
3. scene.json: {version:1, board:{a:62,b:46}, theme:{season,preset}, stops:{id:[x,z]}, routes:{"D1":[[x,z],...]}, peaks:[{x,z,H,R,n}], ranges:[{pts,H,W}], lakes:[{x,z,rx,rz,rot}], rivers:[{w,pts}], props:[{type,x,z,s,rotY}], clumps:[{type,x,z,n,r}]}. x is right, z is toward the camera, y is up; everything inside the ellipse.
   trip.json: {title, subtitle, author:{name,line}, lang, days:[{id,title,km,drive,route,stops:[]}], stops:{id:{name,kind,media:[{type,src,poster}],info:{}}}, facts:[], disclaimer}.
   Stop ids must match across both files, and days[].route must be a key of scene.routes.
4. Photos and videos: process with a script (ffmpeg + Pillow). Photos to webp, long edge at most 1600. Videos to 720p, no audio, at most 15 seconds, plus a poster image. Strip EXIF and GPS from every output. Never put originals in the page.
5. Rendering: an elliptical paper board, low-poly terrain (mountains as 5-7 sided cones, lakes as slightly sunken blue ellipses), camera looking down at an angle, mouse rotation. The route is a small car moving along a polyline plus a glowing line. Each stop is a pin that opens a panel. A stop with no media shows text only.
6. Paper-model props (yurt, bridge, house, animals, trees) are all made in code with three techniques:
   - Lathe: round, symmetric objects. Draw half the profile and revolve it (yurts, lighthouses, trunks).
   - Blocks: boxy objects built from boxes, cylinders and cones (houses, bridges, cars).
   - Layered silhouettes: organic objects. Draw the side outline, extrude it, stack at least 3 layers offset along z (animals, people, tree crowns). One layer alone looks like a plank from the front.
   Each prop uses at most 5 colors, has beveled edges and a dark outline. Snow only in winter.
7. Self-check is required: after each prop, screenshot it from a high oblique angle, the side and the front in a browser (headless is fine). Check that it is recognizable when small, that no part is buried, and that it is not a flat plank. Fix and recheck. After the whole page is done, send me one top-down screenshot and one with a stop panel open.
8. Data check: stops and props inside the ellipse, ids consistent, media files exist. Then do a fullness check: cut the board into roughly a 10x8 grid and count the cells that hold something (stop, prop, lake, mountain, route); under 70% means too empty. Find the largest empty patch. Each stop needs a landmark nearby, no long stretch of route should be bare on both sides, and use at least 5 kinds of props. For every empty area, ask me what is really there (buildings, animals, people, boats, vehicles) and place it only after I answer; never invent it. Trees, grass and rocks are natural filler and you may add them yourself.
9. Preview locally and iterate on my feedback. Always ask me before publishing anything online.

Start with step 1: ask me how many days, the stops for each day, and which folder holds my photos.
```
