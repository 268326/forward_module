#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / 'data'
PAGE_SIZE = 24


def ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, data):
    ensure_dir(path.parent)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def paged(items):
    rows = list(items)
    if not rows:
        return []
    return [rows[i:i + PAGE_SIZE] for i in range(0, len(rows), PAGE_SIZE)]


def build_daily_scope(items, mode: str, specific_weekday: int | None = None):
    if mode == 'all_week':
        return list(items)
    if mode == 'mon_thu':
        return [x for x in items if x.get('bgm_weekday_id') in {1, 2, 3, 4}]
    if mode == 'fri_sun':
        return [x for x in items if x.get('bgm_weekday_id') in {5, 6, 7}]
    if mode == 'specific_day' and specific_weekday is not None:
        return [x for x in items if x.get('bgm_weekday_id') == specific_weekday]
    return []


def sort_daily(items, sort_order: str):
    rows = list(items)
    if sort_order == 'popularity_rat_bgm':
        rows.sort(key=lambda x: x.get('bgm_rating_total') or 0, reverse=True)
    elif sort_order == 'score_bgm_desc':
        rows.sort(key=lambda x: x.get('bgm_score') or 0, reverse=True)
    elif sort_order == 'airdate_desc':
        rows.sort(key=lambda x: x.get('releaseDate') or x.get('bgm_air_date') or '', reverse=True)
    return rows


def filter_region(items, region_filter: str):
    if region_filter == 'all':
        return list(items)
    region_us_eu = {'US', 'GB', 'FR', 'DE', 'CA', 'AU', 'ES', 'IT'}
    rows = []
    for item in items:
        countries = item.get('tmdb_origin_countries') or []
        if item.get('type') != 'tmdb' or not item.get('tmdb_id'):
            if region_filter == 'OTHER':
                rows.append(item)
            continue
        if not countries:
            if region_filter == 'OTHER':
                rows.append(item)
            continue
        if region_filter == 'JP' and 'JP' in countries:
            rows.append(item)
        elif region_filter == 'CN' and 'CN' in countries:
            rows.append(item)
        elif region_filter == 'US_EU' and any(c in region_us_eu for c in countries):
            rows.append(item)
        elif region_filter == 'OTHER':
            if 'JP' not in countries and 'CN' not in countries and not any(c in region_us_eu for c in countries):
                rows.append(item)
    return rows


def main():
    recent_data = json.loads((ROOT / 'recent_data.json').read_text(encoding='utf-8'))

    # recent
    recent = ((recent_data.get('recentHot') or {}).get('anime') or [])
    for idx, page in enumerate(recent, start=1):
        write_json(DATA_DIR / 'recent' / 'anime' / f'page-{idx}.json', page)

    # current year airtime
    airtime = recent_data.get('airtimeRanking') or {}
    for category, category_data in airtime.items():
        for year, year_data in (category_data or {}).items():
            for month, month_data in (year_data or {}).items():
                for sort, pages in (month_data or {}).items():
                    for idx, page in enumerate(pages or [], start=1):
                        write_json(DATA_DIR / 'airtime' / category / str(year) / str(month) / str(sort) / f'page-{idx}.json', page)

    # archive airtime
    archive_dir = ROOT / 'archive'
    if archive_dir.exists():
        for archive_file in archive_dir.glob('*.json'):
            payload = json.loads(archive_file.read_text(encoding='utf-8'))
            airtime = payload.get('airtimeRanking') or {}
            for category, category_data in airtime.items():
                for year, year_data in (category_data or {}).items():
                    for month, month_data in (year_data or {}).items():
                        for sort, pages in (month_data or {}).items():
                            for idx, page in enumerate(pages or [], start=1):
                                write_json(DATA_DIR / 'airtime' / category / str(year) / str(month) / str(sort) / f'page-{idx}.json', page)

    # daily precomputed paged
    all_week = ((recent_data.get('dailyCalendar') or {}).get('all_week') or [])
    scopes = {
        'all_week': list(all_week),
        'mon_thu': build_daily_scope(all_week, 'mon_thu'),
        'fri_sun': build_daily_scope(all_week, 'fri_sun'),
    }
    for weekday in range(1, 8):
        scopes[f'day-{weekday}'] = build_daily_scope(all_week, 'specific_day', weekday)

    sort_orders = ['default', 'popularity_rat_bgm', 'score_bgm_desc', 'airdate_desc']
    region_filters = ['all', 'JP', 'CN', 'US_EU', 'OTHER']
    for scope_key, scope_items in scopes.items():
        for sort_order in sort_orders:
            sorted_items = scope_items if sort_order == 'default' else sort_daily(scope_items, sort_order)
            for region_filter in region_filters:
                filtered_items = filter_region(sorted_items, region_filter)
                for idx, page in enumerate(paged(filtered_items), start=1):
                    write_json(DATA_DIR / 'daily' / scope_key / sort_order / region_filter / f'page-{idx}.json', page)


if __name__ == '__main__':
    main()
