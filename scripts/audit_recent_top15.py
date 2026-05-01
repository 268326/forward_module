#!/usr/bin/env python3
import json
from pathlib import Path
from bs4 import BeautifulSoup

from build_data import DataBuilder, parse_date

ROOT = Path(__file__).resolve().parents[1]
HTML_PATH = ROOT / 'tmp_recent_top15.html'
OUTPUT_PATH = ROOT / 'top15_recent_audit.json'


def fetch_top15_html(builder: DataBuilder) -> str:
    return builder.get_text('https://bgm.tv/anime/browser?sort=trends&page=1')


def parse_top15(html: str):
    soup = BeautifulSoup(html, 'html.parser')
    rows = []
    for idx, li in enumerate(soup.select('ul#browserItemList li.item')[:15], start=1):
        item_id = (li.get('id') or '')[5:]
        title = li.select_one('h3 a.l').get_text(strip=True)
        original_node = li.select_one('h3 small.grey')
        original_title = original_node.get_text(strip=True) if original_node else ''
        info_node = li.select_one('p.info.tip')
        info = info_node.get_text(' ', strip=True) if info_node else ''
        release_date = parse_date(info)
        rows.append({
            'rank': idx,
            'bgm_id': item_id,
            'title': title,
            'original_title': original_title,
            'info': info,
            'release_date': release_date,
        })
    return rows


def main():
    builder = DataBuilder(tmdb_api_key=None, max_workers=1, request_delay=0.0)
    builder.bangumi_data_resolver.tmdb_api_key = __import__('os').environ.get('TMDB_API_KEY')
    html = fetch_top15_html(builder)
    HTML_PATH.write_text(html, encoding='utf-8')
    items = parse_top15(html)
    audited = []
    for item in items:
        resolved = builder.bangumi_data_resolver.match_with_fallback(
            title=item['title'],
            ori_title=item['original_title'] or None,
            release_date=item['release_date'] or None,
            require_animation=True,
        )
        row = dict(item)
        if resolved:
            row.update({
                'resolved': True,
                'source': resolved.get('source'),
                'tmdb_site_id': resolved.get('tmdb_site_id'),
                'tmdb_id': resolved.get('tmdb_id'),
                'media_type': resolved.get('media_type'),
                'matched_title': resolved.get('title'),
                'matched_begin': resolved.get('begin'),
            })
            raw = resolved.get('raw') or {}
            row['tmdb_result_name'] = raw.get('name') or raw.get('title')
            row['tmdb_vote_average'] = raw.get('vote_average')
            row['tmdb_origin_countries'] = raw.get('origin_country')
        else:
            row.update({
                'resolved': False,
                'source': None,
                'tmdb_site_id': None,
                'tmdb_id': None,
                'media_type': None,
                'matched_title': None,
                'matched_begin': None,
            })
        audited.append(row)
    OUTPUT_PATH.write_text(json.dumps(audited, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(OUTPUT_PATH)


if __name__ == '__main__':
    main()
