# AniArr

Arrange anime episodes into a Jellyfin/Plex-friendly library structure, with support for hardlinks, subtitles, and configurable classification of extras (NCOP, NCED, PV, SP, etc.).
This script is particularly suited for anime releases from **VCB-Studio**

---

## Features

- Flexible file handling
  Choose between hardlink or move modes to suit your storage setup.

- Subtitle handling
  Detect and rename subtitle files alongside their episodes.

- Extras classification
  Detect trailers, NCOP/NCED, specials, menus, and more into Jellyfin/Plex extras folders.

- Configurable rules
  Customize regex-based rules via `aniarr.conf` (JSON).
  Default rules cover common VCB-Studio naming conventions.

---

## Configuration

- **Default config path:** `aniarr.conf` (JSON) in the same folder as the script. If missing, the built-in defaults are used.
- **Explicit path:** `--config /path/to/aniarr.conf`.
- **Purpose:** Define rules for detecting and classifying **extras**, and choose whether extras live at the **series** level or the **season** level.


### Config Fields
- **extras_scope:** `series` or `season`. Place extras at the `series` or `season` level.
- **rules**: Ordered regex rules for classifying extras.
  - **pattern:** Python regular expression (escape properly in JSON).
  - **category:** Maps to a Jellyfin extra category; invalid values fall back to `extras`.
- **fallback_category**: Default category if nothing matches.

> File naming for extras: output uses `<token> + extension`, e.g., `CM01.mkv`, `SP02.mkv`.

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

## Example Output

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
