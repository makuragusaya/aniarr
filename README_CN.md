# AniArr 配置说明（中文，简化版）

适用版本：**v3.6**（Extras 默认开启，支持可配置映射）

---

## 概览

- 默认配置路径：脚本同目录 `aniarr.conf`（JSON）。若不存在，使用内建默认配置。
- 显式指定：`--config /path/to/aniarr.conf`。
- 用途：定义“额外内容（extras）”的识别规则与分类映射，并决定 extras 放在剧集根目录还是季目录。

---

## 配置字段

- **extras_scope**：`series` 或 `season`。决定 extras 存放层级。配置文件优先于命令行。  
- **rules**：规则列表，按顺序匹配，命中第一条即停止。  
  - **pattern**：Python 正则（JSON 内需转义）。  
  - **category**：映射到 Jellyfin 分类，非法值回退为 `extras`。  
  - **label_from**：通常为 `"match"`，使用正则命中的文本。  
  - **case**：大小写规则，`upper`、`lower` 或 `match`。  
  - **label**：固定 token。若存在则忽略 `label_from` 与 `case`。  
- **fallback_category**：未命中时使用的分类，默认 `extras`。

> extras 文件名规则：输出为 `<token> + 扩展名`，例如 `CM01.mkv`、`SP02.mkv`。

---

## Jellyfin 支持的分类

```
behind the scenes, deleted scenes, interviews, scenes,
samples, shorts, featurettes, clips, other, extras, trailers
```

---

## 推荐默认配置

```json
{
  "extras_scope": "series",
  "rules": [
    {"pattern": "\\bCM\\d*\\b",      "category": "trailers",  "label_from": "match", "case": "upper"},
    {"pattern": "\\bPV\\d*\\b",      "category": "trailers",  "label_from": "match", "case": "upper"},
    {"pattern": "\\bPreview\\d*\\b", "category": "trailers",  "label_from": "match", "case": "match"},
    {"pattern": "\\bTrailer\\b",       "category": "trailers",  "label_from": "match", "case": "match"},
    {"pattern": "\\bNCOP\\b",          "category": "clips",     "label_from": "match", "case": "upper"},
    {"pattern": "\\bNCED\\b",          "category": "clips",     "label_from": "match", "case": "upper"},
    {"pattern": "\\bMenu\\d+\\b",    "category": "other",     "label_from": "match", "case": "match"},
    {"pattern": "\\bSP\\d+\\b",      "category": "shorts",    "label_from": "match", "case": "upper"}
  ],
  "fallback_category": "extras"
}
```

---

## 示例目录结构

**series scope**

```
Shows/
└── Series Name (2021)/
    ├── Season 01/
    │   ├── Series Name (2021) S01E01.mkv
    │   └── …
    ├── trailers/CM01.mkv
    ├── clips/NCOP.mkv
    ├── shorts/SP01.mkv
    └── other/Menu01.mkv
```

**season scope**

```
Shows/
└── Series Name (2021)/
    └── Season 01/
        ├── Series Name (2021) S01E01.mkv
        ├── trailers/CM01.mkv
        ├── clips/NCOP.mkv
        └── shorts/SP01.mkv
```
