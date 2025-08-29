# AniArr Configuration Guide (English, simplified)

Applies to **v3.6** (Extras enabled by default, configurable mapping supported)

---

## Overview

- **Default config path:** `aniarr.conf` (JSON) in the same folder as the script. If missing, the built-in defaults are used.
- **Explicit path:** `--config /path/to/aniarr.conf`.
- **Purpose:** Define rules for detecting and classifying **extras**, and choose whether extras live at the **series** level or the **season** level.

---

## Config Fields

- **extras_scope:** `series` or `season`. Controls where extras are stored. Values in the config file override CLI flags.  
- **rules:** An ordered list; the first matching rule wins.  
  - **pattern:** Python regular expression (escape properly in JSON).  
  - **category:** Maps to a Jellyfin extra category; invalid values fall back to `extras`.  
  - **label_from:** Usually `"match"`; uses the matched text from the regex.  
  - **case:** Case rule for the label: `upper`, `lower`, or `match`.  
  - **label:** Fixed token; if set, it overrides `label_from` and `case`.  
- **fallback_category:** Used when nothing matches; default is `extras`.

> File naming for extras: output uses `<token> + extension`, e.g., `CM01.mkv`, `SP02.mkv`.

---

## Jellyfin Extra Categories

```
behind the scenes, deleted scenes, interviews, scenes,
samples, shorts, featurettes, clips, other, extras, trailers
```

---

## Recommended Default Config

```json
{
  "extras_scope": "series",
  "rules": [
    {"pattern": "\\bCM\\d*\\b",      "category": "trailers",  "label_from": "match", "case": "upper"},
    {"pattern": "\\bPV\\d*\\b",      "category": "trailers",  "label_from": "match", "case": "upper"},
    {"pattern": "\\bPreview\\d*\\b", "category": "trailers",  "label_from": "match", "case": "match"},
    {"pattern": "\\bTrailer\\b",     "category": "trailers",  "label_from": "match", "case": "match"},
    {"pattern": "\\bNCOP\\b",        "category": "clips",     "label_from": "match", "case": "upper"},
    {"pattern": "\\bNCED\\b",        "category": "clips",     "label_from": "match", "case": "upper"},
    {"pattern": "\\bMenu\\d+\\b",    "category": "other",     "label_from": "match", "case": "match"},
    {"pattern": "\\bSP\\d+\\b",      "category": "shorts",    "label_from": "match", "case": "upper"}
  ],
  "fallback_category": "extras"
}
```

---

## Example Directory Layouts

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
