# 安装

有四种方式，选一种就行。先看你用什么助手。

| 你用的助手 | 推荐方式 |
|---|---|
| Claude Code | 方式一（最直接）或方式二 |
| claude.ai 网页版 | 方式三 |
| Codex 或其他能读文件、跑命令的助手 | 方式四 |

不管哪种方式，电脑上都要有 Node 20.19+ 或 22.12+、Python 3.9+、ffmpeg。可以先自己确认：

```
node --version
python3 --version
ffmpeg -version
```

哪个报「找不到命令」，就让助手带你装，或看 [references/troubleshooting.md](references/troubleshooting.md)。

## 方式一：Claude Code，手动复制到 skills 目录

1. 下载或克隆这个仓库，得到一个文件夹。
2. 把整个文件夹复制到 Claude Code 的 skills 目录，文件夹名用 `paper-roadbook`：
   - 所有项目都能用：`~/.claude/skills/paper-roadbook/`
   - 只在某个项目里用：该项目下的 `.claude/skills/paper-roadbook/`
3. 确认 `paper-roadbook/SKILL.md` 就在这个文件夹的第一层。
4. 重新打开 Claude Code，对它说「帮我把这趟旅行做成 3D 纸雕路书」。

不要复制 `node_modules` 和 `dist`（如果有的话）。

## 方式二：Claude Code，通过 plugin marketplace

仓库里带了 plugin 配置。在 Claude Code 里依次运行：

```
/plugin marketplace add Aprillllllw/paper-roadbook
/plugin install paper-roadbook@paper-roadbook
```

命令的写法和 plugin 的启用方式随版本可能有变化，以 Claude Code 官方文档为准。

## 方式三：claude.ai 上传 zip

1. 把 Skill 文件夹压缩成 zip。zip 里要有一个名为 `paper-roadbook` 的文件夹，`SKILL.md` 在这个文件夹的第一层。
2. 在 claude.ai 的设置里找到 Skills（技能）相关页面，上传这个 zip。具体菜单位置和文件大小限制，以官方文档为准。
3. 注意：这个 Skill 要运行本地命令（`npm`、`python3`、`ffmpeg`）。能不能在网页版里运行，取决于你的账号是否开启了代码执行功能，以官方文档为准。需要在自己电脑上生成网页的话，推荐用 Claude Code。

## 方式四：不装 Skill，直接用 PROMPT.md

打开 [PROMPT.md](PROMPT.md)，复制里面的提示词发给你的助手。

- 助手能访问网络和你的电脑：用「仓库版」，它会自己取回仓库并按 `SKILL.md` 的流程做。
- 助手没法取回仓库：用「自包含版」，里面把方法都写出来了，助手自己搭一个。效果和细节会比仓库版少一些。

## 装好后怎么确认

对助手说「你有 paper-roadbook 这个 Skill 吗」。它应该能说出流程的第一步：问你每天的站点和照片放在哪。
