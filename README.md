# bili-inspector

`bili-inspector` 是一个 **AI-first、BVID-only** 的 Bilibili 视频检查 CLI。

它复用现有 Python 抓取内核，通过 `agent-browser` 打开视频页，在浏览器上下文里读取视频状态，再抓取字幕和评论；但对外接口从“好用脚本”升级为“稳定 CLI 契约”：

- 只接受 **BVID** 输入
- 使用显式子命令表达意图
- 支持 `--json` 机器可读输出
- 提供稳定错误码、阶段信息、重试提示
- 提供 `doctor` 进行环境探测

## Requirements

- `python3`
- `agent-browser`
- 可用的 Bilibili 浏览器会话，默认 `--session-name main`

## Install

开发安装：

```bash
python3 -m pip install -e .
```

安装后可使用：

```bash
bili-inspector --help
```

如果你还没有安装到环境里，也可以直接使用模块入口：

```bash
python3 -m bili_inspector --help
```

## Command Surface

```bash
bili-inspector inspect <bvid> [options]
bili-inspector meta <bvid> [options]
bili-inspector subtitles <bvid> [options]
bili-inspector comments <bvid> [options]
bili-inspector search <keyword...> [options]
bili-inspector doctor [options]
bili-inspector --version
```

## Global Options

```bash
--session-name <name>   默认 main
--json                  stdout 输出单个 JSON 对象
--verbose               stderr 输出阶段日志
```

## Commands

### `inspect <bvid>`

一次性抓取：

- meta
- subtitles
- comments
- README summary

选项：

```bash
--lang <lan>             可选单值；不传时只自动导出 1 种字幕语言
--mode <mode>            可重复；默认 hot + latest
--comment-limit <n|all>  默认 20
--subreply-limit <n|all> 默认 10
```

默认字幕选择顺序：

1. 中文：优先 `ai-zh`，兼容 `zh*`
2. 英文：优先 `ai-en`，兼容 `en*`
3. 日文：优先 `ai-ja`，兼容 `ja*`
4. 其他：按 Bilibili 返回顺序取第一个

示例：

```bash
bili-inspector inspect BV1aurMBCEkE --json
```

### `meta <bvid>`

只抓视频基础信息和可用性摘要，并刷新根目录 `README.md`：

```bash
bili-inspector meta BV1aurMBCEkE --json
```

### `subtitles <bvid>`

抓字幕轨和字幕文件。默认只导出 1 种语言；如需指定语言，可显式传 `--lang`。该命令只会重建 `subtitles/` 分区，并自动刷新根目录 `README.md`：

```bash
bili-inspector subtitles BV1aurMBCEkE --lang ai-zh --json
```

### `comments <bvid>`

抓评论和楼中楼。该命令只会重建 `comments/` 分区，并自动刷新根目录 `README.md`：

```bash
bili-inspector comments BV1aurMBCEkE --mode hot --comment-limit 5 --json
```


### `search <keyword...>`

按关键词搜索 Bilibili 视频结果。默认只返回**精简结果**，方便 AI 或脚本直接消费：

- `title`
- `bvid`
- `pubdate`
- `play`

选项：

```bash
--page <n>      页码，默认 1
--limit <n>     返回条数，默认 10，最大 20
--save-raw      额外把完整原始搜索结果保存到文件
```

示例：

```bash
bili-inspector search 原神 启动器 --json
bili-inspector search 原神 启动器 --page 2 --limit 5 --json
bili-inspector search 原神 启动器 --json --save-raw
```

### `doctor`

检查：

- `python3`
- `agent-browser`
- 浏览器是否可打开 Bilibili
- 当前 session 是否可完成 nav fetch

```bash
bili-inspector doctor --json
```

## Input Contract

所有抓取命令只接受 BVID：

```python
^BV[0-9A-Za-z]{10}$
```

不再支持：

- URL
- `av`
- `aid`

非法输入会返回：

- 错误码：`E_INVALID_BVID`
- 退出码：`2`

## Output Contract

推荐 AI 默认总是带 `--json`。

在 `--json` 模式下：

- **stdout**：只输出单个 JSON 对象
- **stderr**：只输出日志

统一结果信封：

### Success

```json
{
  "ok": true,
  "schema_version": "1",
  "command": "meta",
  "input": {
    "bvid": "BV1aurMBCEkE",
    "session_name": "main"
  },
  "data": {
    "video": {
      "bvid": "BV1aurMBCEkE",
      "aid": "115865802510979",
      "cid": "35287862688",
      "title": "十分钟教你解开XZ1c日版bl锁",
      "owner_name": "思想不科學實驗",
      "pubdate": "2026-01-09 23:19:59",
      "reply_count": 112,
      "url": "https://www.bilibili.com/video/BV1aurMBCEkE/"
    },
    "availability": {
      "subtitles": {
        "track_count": 1,
        "langs": ["ai-zh"]
      },
      "comments": {
        "reply_count": 112
      }
    }
  },
  "artifacts": {
    "output_dir": "/abs/path/output/BV1aurMBCEkE",
    "files": ["README.md", "meta.json"]
  },
  "warnings": []
}
```

### Search Success Example

```json
{
  "ok": true,
  "schema_version": "1",
  "command": "search",
  "input": {
    "keyword": "原神 启动器",
    "page": 1,
    "limit": 10,
    "session_name": "main"
  },
  "data": {
    "search": {
      "keyword": "原神 启动器",
      "page": 1,
      "limit": 10,
      "total": 1234,
      "pages": 62,
      "returned": 2,
      "results": [
        {
          "title": "原神 启动器",
          "bvid": "BV1aaaaaa111",
          "pubdate": "2024-03-01 17:50:00",
          "play": "12.3万"
        }
      ]
    }
  },
  "warnings": []
}
```

默认 `search` 不写输出文件；只有显式传 `--save-raw` 时，才会把完整原始搜索结果保存到：

```text
output/search/<keyword>/raw.json
```

### Error

```json
{
  "ok": false,
  "schema_version": "1",
  "command": "subtitles",
  "input": {
    "bvid": "BV1aurMBCEkE",
    "session_name": "main"
  },
  "error": {
    "code": "E_SUBTITLE_LANG_NOT_FOUND",
    "message": "Requested subtitle languages were not found",
    "stage": "subtitles.select_tracks",
    "retryable": false,
    "hint": "Run `bili-inspector meta <bvid> --json` to inspect available subtitle langs first."
  }
}
```

## Output Files

默认输出目录为项目根目录下的 `output/` 子目录：

```text
output/<bvid>
```

`inspect` 会先清空整个 `output/<bvid>/` 再重建，因此目录内容始终代表**本次完整抓取的快照**。

分步命令的刷新策略：

- `meta`：更新 `meta.json`，并重写根目录 `README.md`
- `subtitles`：只重建 `subtitles/`，保留 `meta.json` 与 `comments/`，并重写根目录 `README.md`
- `comments`：只重建 `comments/`，保留 `meta.json` 与 `subtitles/`，并重写根目录 `README.md`

因此，同一个 BVID 可以安全分步抓取，目录会逐渐汇总成完整快照，而不是互相覆盖掉。

`search` 默认**不写文件**。只有显式传 `--save-raw` 时，才会写入：

```text
output/search/<keyword>/raw.json
```

用于保留完整原始搜索结果；stdout 仍然只返回精简结果。

`inspect` 典型产物：

```text
output/BV1aurMBCEkE/
├── README.md
├── meta.json
├── comments/
│   ├── hot.json
│   ├── hot.md
│   ├── latest.json
│   └── latest.md
└── subtitles/
    ├── tracks.json
    ├── ai-zh.json
    ├── ai-zh.txt
    ├── ai-zh.plain.txt
    └── ai-zh.srt
```

说明：

- `subtitles/*.plain.txt`：最适合 AI 直接阅读、总结
- `subtitles/*.txt`：带时间区间，适合按时间顺序分析
- `subtitles/*.srt`：标准字幕格式
- `subtitles/*.json`：原始结构化字幕
- `comments/hot.json` / `comments/latest.json`：结构化评论数据
- `comments/hot.md` / `comments/latest.md`：快速浏览版
- `hot` 表示最热评论，`latest` 表示最新评论

CLI 返回的 `artifacts.files` 应与磁盘实际生成文件一致，并代表当前 `output/<bvid>/` 下的完整文件快照。

## Error Codes

| Code | Meaning | Exit |
|------|---------|------|
| `E_INVALID_BVID` | 输入不是合法 BVID | `2` |
| `E_INVALID_ARGUMENTS` | CLI 参数错误 | `2` |
| `E_DEPENDENCY_MISSING` | 缺少 `python3` 或 `agent-browser` | `3` |
| `E_SESSION_INVALID` | session 不可用或未登录 | `4` |
| `E_SUBTITLE_LANG_NOT_FOUND` | 请求的字幕语言不存在 | `5` |
| `E_SUBTITLE_TRACKS_UNAVAILABLE` | 视频没有可用字幕轨 | `5` |
| `E_COMMENTS_UNAVAILABLE` | 评论不可用 | `5` |
| `E_BROWSER_OPEN_FAILED` | 无法通过 `agent-browser` 打开页面 | `6` |
| `E_VIDEO_STATE_MISSING` | 页面上下文里缺少视频状态 | `6` |
| `E_PLAYER_INFO_FETCH_FAILED` | player info 获取失败 | `6` |
| `E_BILIBILI_API_FAILED` | Bilibili API 调用失败 | `6` |
| `E_INTERNAL` | 未预期内部错误 | `7` |

## Exit Codes

| Exit code | Meaning |
|-----------|---------|
| `0` | 成功 |
| `2` | CLI 参数错误 |
| `3` | 依赖/环境错误 |
| `4` | session / 鉴权错误 |
| `5` | 资源不存在或请求选择无效 |
| `6` | 远端抓取失败 |
| `7` | 未预期内部错误 |

## AI Usage Recommendations

### 1. 先做环境检查

```bash
bili-inspector doctor --json
```

### 2. 先看 meta，再决定是否抓大内容

```bash
bili-inspector meta BV1aurMBCEkE --json
```

### 3. 只在需要时抓字幕或评论

```bash
bili-inspector subtitles BV1aurMBCEkE --json
bili-inspector subtitles BV1aurMBCEkE --lang ai-zh --json
bili-inspector comments BV1aurMBCEkE --mode hot --comment-limit 10 --json
```

### 4. 需要完整导出时再用 inspect

```bash
bili-inspector inspect BV1aurMBCEkE --json
```

### 5. AI 默认读取优先级

- 字幕优先读 `*.plain.txt`
- 需要时间信息时再读 `*.txt` 或 `*.srt`
- 需要结构化处理时读 `subtitles/*.json`
- 评论优先读 `comments/*.json` 做程序化处理
- 只需快速浏览时读 `comments/*.md`

## Tests

项目包含以契约为中心的测试：

- CLI parser
- success/error envelope
- service 层字幕/评论行为
- doctor 聚合结果
- mocked CLI integration

运行测试：

```bash
python3 -m pytest
```

如果本机尚未安装 pytest，可先安装开发依赖：

```bash
python3 -m pip install -e .[dev]
```
