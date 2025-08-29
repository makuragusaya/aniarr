#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse, os, re, shutil, sys, textwrap, json
from pathlib import Path
from typing import Optional, List, Tuple, Dict, Any
from shutil import get_terminal_size
from collections import defaultdict, Counter

VIDEO_EXTS = {'.mkv', '.mp4', '.avi', '.mov', '.wmv', '.m4v'}
SUB_EXTS   = {'.ass', '.srt', '.vtt', '.sub', '.ssa', '.sup'}

JF_CATEGORIES = {
    'behind the scenes', 'deleted scenes', 'interviews', 'scenes', 'samples',
    'shorts', 'featurettes', 'clips', 'other', 'extras', 'trailers'
}

# ---------- helpers ----------

def is_video(p: Path) -> bool: return p.suffix.lower() in VIDEO_EXTS
def is_sub(p: Path)   -> bool: return p.suffix.lower() in SUB_EXTS

def safe_folder(name: str) -> str:
    return re.sub(r'[/\\:*?"<>|]', '_', name).strip()

def clean_tokens(s: str) -> str:
    s = str(Path(s).with_suffix(''))
    # 去掉常见技术标签
    s = re.sub(r'\[(?:1080p|2160p|720p|x26[45]|HEVC|AVC|WEB[- ]?DL|BluRay|FLAC|AAC|HDR|DV|Ma10p_[^\]]+)\]', '', s, flags=re.I)
    s = re.sub(r'\b(1080p|2160p|720p|x26[45]|HEVC|AVC|WEB[- ]?DL|BluRay|FLAC|AAC|HDR|DV)\b', '', s, flags=re.I)
    s = re.sub(r'[ _\-]{2,}', ' ', s).strip(' -_')
    return s

def strip_all_brackets(s: str) -> str:
    # 删除任意位置的 [xxx] 模块（给 extras 提取系列名时用）
    return re.sub(r'\s*\[[^\[\]]+\]\s*', ' ', s).strip()

def normalize_lang(name: str) -> Optional[str]:
    lower = name.lower()
    mapping = {
        'chs':'zh-CN','sc':'zh-CN','simp':'zh-CN','chi':'zh-CN',
        'cht':'zh-TW','tc':'zh-TW','trad':'zh-TW',
        'zh-cn':'zh-CN','zh-sc':'zh-CN','zh_sc':'zh-CN',
        'zh-tw':'zh-TW','zh-tc':'zh-TW','zh_tc':'zh-TW',
        'chinese (simplified)':'zh-CN','chinese (traditional)':'zh-TW',
        'chinese':'zh-CN'
    }
    tokens = re.findall(r'[\._-]((?:zh[-_ ]?(?:cn|tw)|chs|cht|sc|tc|chi|chinese(?:\s*\(.*?\))?))(?:[_\-](\d+))?', lower)
    if not tokens: return None
    raw, idx = tokens[-1]
    raw = raw.strip()
    norm = mapping.get(raw) or ('zh-TW' if raw.startswith('chinese') and 'trad' in raw else ('zh-CN' if raw.startswith('chinese') else None))
    return f"{norm}_{idx}" if (norm and idx) else norm

def apply_lang(final_name: str, src_name: str) -> str:
    lang = normalize_lang(src_name) or normalize_lang(final_name)
    if not lang: return final_name
    stem = str(Path(final_name).with_suffix(''))
    ext  = Path(final_name).suffix
    stem = re.sub(r'[\._-](zh[-_ ]?(?:cn|tw))(?:[_\-]\d+)?$', '', stem, flags=re.I)
    return f"{stem}.{lang}{ext}"

def parse_group_from_prefix(raw: str) -> Optional[str]:
    m = re.match(r'\s*\[([^\[\]]+)\]\s*', raw)
    return f"[{m.group(1).strip()}]" if m else None

def extract_season_ep(s: str) -> Tuple[Optional[int], int]:
    m = re.search(r'[Ss](\d{1,2})[Ee](\d{1,3})', s)
    if m: return int(m.group(1)), int(m.group(2))
    m = re.search(r'[\[\(]\s*(\d{1,3})\s*[\]\)]', s) or re.search(r'[\s\-_](\d{1,3})(?=[\s\-_\.])', s)
    if m: return None, int(m.group(1))
    m = re.search(r'\b(?:EP|Ep|ep|E)(\d{1,3})\b', s)
    if m: return None, int(m.group(1))
    zh_map = {'零':0,'〇':0,'一':1,'二':2,'两':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9,'十':10}
    def zh2num(t):
        if t.isdigit(): return int(t)
        if len(t)==1: return zh_map.get(t,0)
        if '十' in t:
            L,_,R = t.partition('十')
            l = zh_map.get(L,1) if L else 1
            r = zh_map.get(R,0) if R else 0
            return l*10+r
        return 0
    m = re.search(r'第([零〇一二两三四五六七八九十\d]{1,3})\s*(?:話|话|集)', s)
    if m: return None, zh2num(m.group(1))
    return None, 1

def extract_year(s: str) -> Optional[str]:
    m = re.search(r'\((19|20)\d{2}\)', s)
    if m: return m.group(0).strip('()')
    m = re.search(r'\b(19|20)\d{2}\b', s)
    if m: return m.group(0)
    return None

def extract_title(s: str, forced: Optional[str]) -> str:
    if forced: return forced
    s2 = re.sub(r'^\s*\[[^\[\]]+\]\s*', '', s).strip()
    split_pos = None
    for pat in [r'[Ss]\d{1,2}[Ee]\d{1,3}', r'[\[\(]\s*\d{1,3}\s*[\]\)]',
                r'\b(?:EP|Ep|ep|E)\d{1,3}\b', r'第[零〇一二两三四五六七八九十\d]{1,3}\s*(?:話|话|集)']:
        m = re.search(pat, s2)
        if m: split_pos = m.start(); break
    title = s2[:split_pos] if split_pos not in (None, 0) else s2
    # 仅去掉**末尾**的 [xxx]
    title = re.sub(r'\s*\[[^\[\]]+\]\s*$', '', title).strip()
    title = re.sub(r'[ _\-]{2,}', ' ', title).strip(' -_')
    return title or "Unknown"

def term_width(default: int = 88) -> int:
    try:
        cols = get_terminal_size((default, 20)).columns
        return max(60, min(cols, 160))
    except Exception:
        return default

def wrap_line(line: str, width: Optional[int] = None, indent: int = 2) -> str:
    if width is None: width = term_width()
    return textwrap.fill(line, width=width, subsequent_indent=' ' * indent,
                         break_long_words=False, break_on_hyphens=False)

def lang_sort_key(lang: Optional[str]) -> int:
    if not lang: return 99
    return {'zh-CN': 0, 'zh-TW': 1}.get(lang.split('_')[0], 50)

# ---------- config ----------

DEFAULT_RULES = [
    {"pattern": r"\bCM\d*\b",      "category": "trailers",  "label_from": "match", "case": "upper"},
    {"pattern": r"\bPV\d*\b",      "category": "trailers",  "label_from": "match", "case": "upper"},
    {"pattern": r"\bPreview\d*\b", "category": "trailers",  "label_from": "match", "case": "match"},
    {"pattern": r"\bTrailer\b",    "category": "trailers",  "label_from": "match", "case": "match"},
    {"pattern": r"\bNCOP\b",       "category": "clips",     "label_from": "match", "case": "upper"},
    {"pattern": r"\bNCED\b",       "category": "clips",     "label_from": "match", "case": "upper"},
    {"pattern": r"\bMenu\d+\b",    "category": "other",     "label_from": "match", "case": "match"},
    {"pattern": r"\bSP\d+\b",      "category": "shorts",    "label_from": "match", "case": "upper"}
]
DEFAULT_FALLBACK = "extras"

def default_config_path() -> Path:
    try:
        here = Path(__file__).resolve().parent
    except NameError:
        here = Path.cwd()
    return here / "aniarr.conf"

def load_config(path_arg: Optional[str]) -> Dict[str, Any]:
    # 1) CLI 指定；2) 脚本同目录 aniarr.conf；3) 内建
    chosen = None
    if path_arg:
        p = Path(path_arg)
        if p.exists():
            chosen = p
    if chosen is None:
        p = default_config_path()
        if p.exists():
            chosen = p

    cfg = {"rules": DEFAULT_RULES, "fallback_category": DEFAULT_FALLBACK, "extras_scope": None, "_config_path": "(built-in)"}
    if chosen:
        try:
            user = json.loads(chosen.read_text(encoding="utf-8"))
            if isinstance(user.get("rules"), list) and user["rules"]:
                cfg["rules"] = user["rules"]
            if user.get("fallback_category"):
                cfg["fallback_category"] = user["fallback_category"]
            if user.get("extras_scope") in ("series", "season"):
                cfg["extras_scope"] = user["extras_scope"]
            cfg["_config_path"] = str(chosen)
        except Exception as e:
            print(f"[WARN] Failed to parse config '{chosen}': {e}. Using defaults.")
    return cfg

def validate_category(cat: str) -> str:
    return cat if cat in JF_CATEGORIES else "extras"

# ---------- extra classifier ----------

def _make_label(m: re.Match, rule: Dict[str, Any]) -> str:
    if "label" in rule and rule["label"]:
        return str(rule["label"])
    if rule.get("label_from") == "match":
        text = m.group(0)
        case = rule.get("case", "match")
        if case == "upper": return text.upper()
        if case == "lower": return text.lower()
        return text
    return m.group(0)

def classify_extra(name: str, rules: List[Dict[str, Any]], fallback: str) -> Tuple[str, str]:
    for rule in rules:
        pat = rule.get("pattern")
        cat = validate_category(str(rule.get("category", "")))
        if not pat: continue
        m = re.search(pat, name, flags=re.I)
        if m:
            return cat, _make_label(m, rule)
    return validate_category(fallback), "EXTRA"

# ---------- plan items ----------

class PlanItem:
    def __init__(self, src: Path, dst: Path, kind: str,
                 series_dir: str, series_name: str, title: str, year: Optional[str],
                 season: int, ep: Optional[int] = None, lang: Optional[str] = None,
                 extra_folder: Optional[str] = None, extra_token: Optional[str] = None):
        self.src = src; self.dst = dst; self.kind = kind
        self.series_dir = series_dir; self.series_name = series_name
        self.title = title; self.year = year; self.season = season
        self.ep = ep; self.lang = lang
        self.extra_folder = extra_folder; self.extra_token = extra_token

# ---------- plan builder ----------

def _parse_common_main(p: Path, season_arg: Optional[int], title_arg: Optional[str], year_arg: Optional[str]) -> Tuple[str, Optional[str], int, int, str, str, Optional[str]]:
    raw = p.name
    clean = clean_tokens(raw)
    s_found, ep = extract_season_ep(clean); use_season = season_arg if season_arg is not None else (s_found or 1)
    title = extract_title(clean, title_arg); year  = year_arg or extract_year(clean)
    name_year = f"{title} ({year})" if year else f"{title}"
    group = parse_group_from_prefix(raw)
    series_dir = safe_folder(name_year)
    return name_year, year, use_season, ep, series_dir, title, group

def _parse_common_extra(p: Path, season_arg: Optional[int], title_arg: Optional[str], year_arg: Optional[str]) -> Tuple[str, Optional[str], int, str, str, Optional[str]]:
    raw = p.name
    clean = clean_tokens(raw)
    # extras：系列名更激进，移除所有 [xxx]
    base_for_title = strip_all_brackets(clean)
    s_found, _ = extract_season_ep(base_for_title)
    use_season = season_arg if season_arg is not None else (s_found or 1)
    title = extract_title(base_for_title, title_arg)
    year  = year_arg or extract_year(base_for_title)
    name_year = f"{title} ({year})" if year else f"{title}"
    group = parse_group_from_prefix(raw)
    series_dir = safe_folder(name_year)
    return name_year, year, use_season, series_dir, title, group

def _plan_main_file(p: Path, dst_root: Path, season_arg: Optional[int], title_arg: Optional[str], year_arg: Optional[str],
                    items: List[PlanItem], tmp_groups_per_series: Dict[str, List[str]], is_subtitle: bool):
    name_year, year, use_season, ep, series_dir, title, group = _parse_common_main(p, season_arg, title_arg, year_arg)
    out_dir = dst_root / series_dir / f"Season {use_season:02d}"
    base = f"{name_year} S{use_season:02d}E{ep:02d}"
    if group: base += f" - {group}"
    dst = out_dir / (base + p.suffix.lower())
    if is_subtitle:
        dst = Path(apply_lang(str(dst), p.name))
        items.append(PlanItem(p, dst, 'SUB', series_dir, name_year, title, year, use_season, ep, normalize_lang(p.name)))
    else:
        items.append(PlanItem(p, dst, 'VID', series_dir, name_year, title, year, use_season, ep))
    if group: tmp_groups_per_series.setdefault(series_dir, []).append(group)

def _plan_extra_file(p: Path, dst_root: Path, season_arg: Optional[int], title_arg: Optional[str], year_arg: Optional[str],
                     items: List[PlanItem], tmp_groups_per_series: Dict[str, List[str]],
                     rules: List[Dict[str, Any]], fallback: str, scope: str):
    name_year, year, use_season, series_dir, title, group = _parse_common_extra(p, season_arg, title_arg, year_arg)
    folder, token = classify_extra(p.name, rules, fallback)
    # 目录：series 或 season 层
    if scope == 'season':
        out_dir = dst_root / series_dir / f"Season {use_season:02d}" / folder
    else:
        out_dir = dst_root / series_dir / folder
    # 文件名：仅 Token（你要求）
    base = token
    dst = out_dir / (base + p.suffix.lower())
    items.append(PlanItem(p, dst, 'EXTRA', series_dir, name_year, title, year, use_season,
                          ep=None, lang=None, extra_folder=folder, extra_token=token))
    if group: tmp_groups_per_series.setdefault(series_dir, []).append(group)

def build_plan(src_dir: Path, dst_root: Path, season_arg: Optional[int],
               title_arg: Optional[str], year_arg: Optional[str],
               extras_on: bool, extras_scope_cli: str,
               rules: List[Dict[str, Any]], fallback_cat: str, cfg_scope: Optional[str]) -> Tuple[List[PlanItem], Dict[str, Optional[str]], Dict[str, List[str]]]:
    items: List[PlanItem] = []
    series_group: Dict[str, Optional[str]] = {}
    skipped: Dict[str, List[str]] = defaultdict(list)
    tmp_groups_per_series: Dict[str, List[str]] = {}

    extras_scope = cfg_scope or extras_scope_cli

    for p in sorted(src_dir.iterdir(), key=lambda x: x.name.lower()):
        if p.is_dir():
            # 允许用户把 extras 放一个子目录里（例如 SPs/extras），只处理该目录下的视频文件
            if extras_on and p.name.lower() in ('sps', 'sp', 'extras'):
                for fp in sorted(p.iterdir(), key=lambda x: x.name.lower()):
                    if fp.is_file() and is_video(fp):
                        _plan_extra_file(fp, dst_root, season_arg, title_arg, year_arg,
                                         items, tmp_groups_per_series, rules, fallback_cat, extras_scope)
                    else:
                        skipped["DIR_ITEM"].append(str(fp))
            else:
                skipped["DIR"].append(p.name)
            continue

        if not p.exists() or not p.is_file():
            skipped["NONFILE"].append(p.name); continue

        if is_sub(p):
            _plan_main_file(p, dst_root, season_arg, title_arg, year_arg,
                            items, tmp_groups_per_series, is_subtitle=True)
            continue

        if is_video(p):
            # 命中文件名中的任何 extras 规则 → 当作 EXTRA；否则当作主视频
            if extras_on and any(re.search(rule["pattern"], p.name, flags=re.I) for rule in rules):
                _plan_extra_file(p, dst_root, season_arg, title_arg, year_arg,
                                 items, tmp_groups_per_series, rules, fallback_cat, extras_scope)
            else:
                _plan_main_file(p, dst_root, season_arg, title_arg, year_arg,
                                items, tmp_groups_per_series, is_subtitle=False)
            continue

        skipped["UNKNOWN"].append(p.name)

    for series, groups in tmp_groups_per_series.items():
        series_group[series] = Counter(groups).most_common(1)[0][0] if groups else None

    def kind_order(k: str) -> int: return {'VID': 0, 'SUB': 1, 'EXTRA': 2}.get(k, 9)

    items.sort(key=lambda it: (
        it.series_dir.lower(), it.season, kind_order(it.kind),
        (it.ep or 0),
        (0 if it.lang == 'zh-CN' else 1 if it.lang == 'zh-TW' else 9),
        it.src.name.lower()
    ))
    return items, series_group, skipped

# ---------- executor ----------

def act_hardlink(src: Path, dst: Path) -> Tuple[bool, str, Path]:
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        final = dst; i = 1
        while final.exists():
            final = final.with_stem(final.stem + f"_{i}"); i += 1
        os.link(str(src), str(final))
        return True, "LINK ", final
    except Exception as e:
        return False, str(e), dst

def act_move(src: Path, dst: Path) -> Tuple[bool, str, Path]:
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        final = dst; i = 1
        while final.exists():
            final = final.with_stem(final.stem + f"_{i}"); i += 1
        shutil.move(str(src), str(final))
        return True, "MOVED", final
    except Exception as e:
        return False, str(e), dst

# ---------- printing / header ----------

def width() -> int: return term_width()

def fmt_auto(val_user: Optional[str|int], val_auto: Optional[str|int], *, is_year=False, is_season=False) -> str:
    if val_user not in (None, ""):
        if is_season and isinstance(val_user, int): return f"S{val_user:02d}"
        return str(val_user)
    if is_season:
        if isinstance(val_auto, int): return f"S{val_auto:02d} (auto)"
        return "S01 (auto)"
    if is_year:
        return f"{val_auto}" if val_auto else "(empty)"
    return f"{val_auto} (auto)" if val_auto else "(empty)"

def resolve_group_for_header(plan: List[PlanItem], series_group_map: Dict[str, Optional[str]]) -> str:
    if not plan: return "-"
    series_set = {it.series_dir for it in plan}
    if len(series_set) == 1:
        sd = next(iter(series_set))
        return series_group_map.get(sd) or "-"
    return "-"

def print_header(src_dir: Path, dst_root: Path, mode: str,
                 user_title: Optional[str], user_year: Optional[str], user_season: Optional[int],
                 resolved_title: Optional[str], resolved_year: Optional[str], resolved_season: Optional[int],
                 group_str: str, files_count: int, extras: bool, extras_scope: str, config_path: str):
    print("=== AniArr v3.6 ===")
    print(f"Source      : {src_dir}")
    print(f"Destination : {dst_root}")
    print(f"Mode        : {mode}")
    print(f"Title       : {fmt_auto(user_title, resolved_title)}")
    print(f"Year        : {fmt_auto(user_year, resolved_year, is_year=True)}")
    print(f"Season      : {fmt_auto(user_season, resolved_season, is_season=True)}")
    print(f"Group       : {group_str}")
    print(f"Extras      : {'on' if extras else 'off'} (scope={extras_scope})")
    print(f"Config      : {config_path}")
    print(f"Files       : {files_count} planned (sorted)")
    print("====================\n")

def print_plan(items: List[PlanItem], dst_root: Path):
    w = width()
    for it in items:
        try: rel = it.dst.relative_to(dst_root)
        except Exception: rel = it.dst
        if it.kind == 'EXTRA':
            line = f"[EXTRA/{it.extra_folder}] -> {rel}"
        elif it.kind == 'VID':
            line = f"[VID] S{it.season:02d}E{it.ep:02d} -> {rel}"
        else:
            line = f"[SUB] S{it.season:02d}E{it.ep:02d} -> {rel}"
        print(wrap_line(line, w))

def print_skipped(skipped: Dict[str, List[str]]):
    if not skipped: return
    w = width()
    print("\n--- Skipped ---")
    for reason in sorted(skipped.keys()):
        paths = skipped[reason]
        if not paths: continue
        print(f"{reason} ({len(paths)}):")
        for name in sorted(paths, key=str.lower):
            print(wrap_line(f"  {name}", w, indent=4))

# ---------- interactive (two-stage) ----------

def stage1_confirm(src_dir: Path, dst_root: Path, args, cfg: Dict[str, Any]) -> Tuple[bool, Path, List[PlanItem], Dict[str, Optional[str]], Dict[str, List[str]]]:
    plan, sg, skipped = build_plan(
        src_dir, dst_root, args.season, args.title, args.year,
        (not args.no_extras), args.extras_scope, cfg["rules"], cfg["fallback_category"], cfg.get("extras_scope")
    )
    rt = plan[0].title if plan else None
    ry = plan[0].year if plan else None
    rs = plan[0].season if plan else None
    group_str = resolve_group_for_header(plan, sg)
    eff_scope = cfg.get("extras_scope") or args.extras_scope

    print_header(
        src_dir, dst_root,
        "DRY-RUN" if args.dry_run else ("MOVE" if args.move else "HARDLINK"),
        args.title, args.year, args.season,
        rt, ry, rs,
        group_str, len(plan), (not args.no_extras), eff_scope, cfg["_config_path"]
    )

    while True:
        prompt = "[Confirm 1/2] (Enter=next)  [t]itle  [y]ear  [s]eason  [d]estination  [m]ode  [x]extras  [q]uit"
        print(prompt)
        choice = input("> ").strip().lower()
        if choice in ("", "p"):
            return True, dst_root, plan, sg, skipped
        if choice == "q":
            print("Aborted."); sys.exit(0)
        if choice == "t":
            args.title = (input("New title (blank=auto): ").strip() or None)
        elif choice == "y":
            args.year = (input("New year (blank=auto): ").strip() or None)
        elif choice == "s":
            new_s = input("New season number (blank=auto): ").strip()
            args.season = int(new_s) if new_s else None
        elif choice == "d":
            new_r = input(f"New destination (blank to keep '{dst_root}'): ").strip()
            if new_r: dst_root = Path(new_r)
        elif choice == "m":
            args.move = not args.move
            print(f"Mode toggled => {'MOVE' if args.move else 'HARDLINK'}")
        elif choice == "x":
            args.no_extras = not args.no_extras
            print(f"Extras => {'on' if not args.no_extras else 'off'} (scope={cfg.get('extras_scope') or args.extras_scope})")
        else:
            print("Unknown option.")

        plan, sg, skipped = build_plan(
            src_dir, dst_root, args.season, args.title, args.year,
            (not args.no_extras), args.extras_scope, cfg["rules"], cfg["fallback_category"], cfg.get("extras_scope")
        )
        rt = plan[0].title if plan else None
        ry = plan[0].year if plan else None
        rs = plan[0].season if plan else None
        group_str = resolve_group_for_header(plan, sg)
        eff_scope = cfg.get("extras_scope") or args.extras_scope
        print_header(
            src_dir, dst_root,
            "DRY-RUN" if args.dry_run else ("MOVE" if args.move else "HARDLINK"),
            args.title, args.year, args.season,
            rt, ry, rs,
            group_str, len(plan), (not args.no_extras), eff_scope, cfg["_config_path"]
        )

def stage2_confirm(dst_root: Path, args, plan: List[PlanItem], sg: Dict[str, Optional[str]], skipped: Dict[str, List[str]]) -> bool:
    print_plan(plan, dst_root); print_skipped(skipped)
    while True:
        prompt = f"\n[Confirm 2/2] Execute {'MOVE' if args.move else 'HARDLINK'}?  (Enter=yes)  [b]ack  [m]ode  [q]uit"
        print(prompt)
        choice = input("> ").strip().lower()
        if choice in ("", "y"): return True
        if choice == "q": print("Aborted."); sys.exit(0)
        if choice == "b": return False
        if choice == "m":
            args.move = not args.move
            print(f"Mode toggled => {'MOVE' if args.move else 'HARDLINK'}")
            print_plan(plan, dst_root); print_skipped(skipped)
        else:
            print("Unknown option.")

# ---------- CLI ----------

def main():
    ap = argparse.ArgumentParser(
        description="Arrange anime for Jellyfin with episodes/subtitles and configurable extras (SP/PV/CM/NCOP...).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  # Dry-run (extras default ON)
  python ani_arr_v3_6.py -d ./src ./Anime

  # Season-level extras
  python ani_arr_v3_6.py --extras-scope season ./src ./Anime

  # With config file (else default to script-dir aniarr.conf, then built-in)
  python ani_arr_v3_6.py --config ./aniarr.conf ./src ./Anime
""")
    ap.add_argument("source", help="Source folder")
    ap.add_argument("destination", nargs="?", help="Destination root (default: source/organized)")
    ap.add_argument("-d", "--dry-run", action="store_true", help="Preview only (no writes)")
    ap.add_argument("-m", "--move", action="store_true", help="Move files instead of hardlink")
    ap.add_argument("-s", "--season", type=int, help="Season number (if set, overrides filename)")
    ap.add_argument("--title", help="Force series title (e.g., '胆大党')")
    ap.add_argument("--year", help="Force release year (e.g., 2024)")
    # extras
    ap.add_argument("--no-extras", action="store_true", help="Disable extras processing (default: ON)")
    ap.add_argument("--extras-scope", choices=["series","season"], default="series", help="Series-level (default) or season-level extras (config can override)")
    ap.add_argument("--config", help="Path to JSON config (default: <script_dir>/aniarr.conf if present)")
    # non-interactive
    ap.add_argument("-y", "--yes", action="store_true", help="Auto confirm and proceed (non-interactive)")

    args = ap.parse_args()
    src_dir = Path(args.source)
    dst_root = Path(args.destination) if args.destination else (src_dir / "organized")
    if not src_dir.exists() or not src_dir.is_dir():
        print(f"[ERROR] invalid source: {src_dir}"); sys.exit(1)

    cfg = load_config(args.config)

    # non-interactive
    if args.yes:
        plan, sg, skipped = build_plan(
            src_dir, dst_root, args.season, args.title, args.year,
            (not args.no_extras), args.extras_scope, cfg["rules"], cfg["fallback_category"], cfg.get("extras_scope")
        )
        rt = plan[0].title if plan else None
        ry = plan[0].year if plan else None
        rs = plan[0].season if plan else None
        group_str = resolve_group_for_header(plan, sg)
        eff_scope = cfg.get("extras_scope") or args.extras_scope
        print_header(
            src_dir, dst_root,
            "DRY-RUN" if args.dry_run else ("MOVE" if args.move else "HARDLINK"),
            args.title, args.year, args.season,
            rt, ry, rs,
            group_str, len(plan), (not args.no_extras), eff_scope, cfg["_config_path"]
        )
        print_plan(plan, dst_root); print_skipped(skipped)
        if args.dry_run:
            print("\nSummary: dry-run only."); return
        ok = fail = 0
        act_fn = act_move if args.move else act_hardlink
        for it in plan:
            success, how, final_path = act_fn(it.src, it.dst)
            if success: ok += 1; print(wrap_line(f"[{how}] -> {final_path}"))
            else: fail += 1; print(wrap_line(f"[FAIL] {it.src.name} :: {how}"))
        print(f"\nDone. OK={ok}  FAIL={fail}"); 
        if fail: sys.exit(2); 
        return

    # interactive 2-stage
    while True:
        proceed, dst_root, plan, sg, skipped = stage1_confirm(src_dir, dst_root, args, cfg)
        if not proceed:
            print("Aborted."); sys.exit(0)
        proceed2 = stage2_confirm(dst_root, args, plan, sg, skipped)
        if not proceed2:
            continue
        if args.dry_run:
            print("\nSummary: dry-run only."); return
        ok = fail = 0
        act_fn = act_move if args.move else act_hardlink
        for it in plan:
            success, how, final_path = act_fn(it.src, it.dst)
            if success: ok += 1; print(wrap_line(f"[{how}] -> {final_path}"))
            else: fail += 1; print(wrap_line(f"[FAIL] {it.src.name} :: {how}"))
        print(f"\nDone. OK={ok}  FAIL={fail}")
        if fail: sys.exit(2); 
        return

if __name__ == "__main__":
    main()
