# AniArr

将动画剧集整理成 Jellyfin/Plex 兼容的资料库结构，支持硬链接、字幕处理，以及可配置的额外内容分类（NCOP、NCED、PV、SP 等）。  
本脚本特别适用于 **VCB-Studio** 的发行版本。

---

## Features

- 可选择硬链接或移动模式，以适应你的存储环境。

- 自动检测并重命名字幕文件，与对应剧集保持一致。

- 自动识别预告片、NCOP/NCED、特别篇、菜单动画等，并放入 Jellyfin/Plex 的 extras 文件夹中。

- 可通过 `aniarr.conf` (JSON) 来自定义基于正则的规则。  
  默认规则涵盖了常见的 VCB-Studio SPs 命名规范。

---

## Configuration

- 默认配置路径：脚本同目录 `aniarr.conf`（JSON）。若不存在，使用内建默认配置。
- 显式指定：`--config /path/to/aniarr.conf`。
- 用途：定义“额外内容（extras）”的识别规则与分类映射，并决定 extras 放在剧集根目录还是季目录。


### 配置字段

- **extras_scope**：`series` 或 `season`。决定 extras 存放层级。配置文件优先于命令行。  
- **rules**：规则列表，按顺序匹配，命中第一条即停止。  
  - **pattern**：Python 正则（JSON 内需转义）。  
  - **category**：映射到 Jellyfin 分类，非法值回退为 `extras`。  
- **fallback_category**：未命中时使用的分类，默认 `extras`。

> extras 文件名规则：输出为 `<token> + 扩展名`，例如 `CM01.mkv`、`SP02.mkv`。

Default `aniarr.conf`:

    {
      "extras_scope": "series",
      "rules": [
        {"pattern": "\\bCM\\d*\\b",      "category": "trailers"},
        {"pattern": "\\bPV\\d*\\b",      "category": "trailers"},
        {"pattern": "\\bNCOP\\b",        "category": "clips"},
        {"pattern": "\\bNCED\\b",        "category": "clips"},
        {"pattern": "\\bSP\\d+\\b",      "category": "shorts"}
      ],
      "fallback_category": "extras"
    }

---

## Jellyfin Extra Categories

- behind the scenes
- deleted scenes
- interviews
- scenes
- samples
- shorts
- featurettes
- clips
- other
- extras
- trailers

---

## 示例目录结构

Series scope layout:

    Shows/
    └── Series Name (2021)/
        ├── Season 01/
        │   ├── Series Name (2021) S01E01.mkv
        │   └── …
        ├── trailers/CM01.mkv
        ├── clips/NCOP.mkv
        └── shorts/SP01.mkv

Season scope layout:

    Shows/
    └── Series Name (2021)/
        └── Season 01/
            ├── Series Name (2021) S01E01.mkv
            ├── trailers/CM01.mkv
            ├── clips/NCOP.mkv
            └── shorts/SP01.mkv
