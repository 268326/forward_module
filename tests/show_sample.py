#!/usr/bin/env python3
import importlib.util
from pathlib import Path

project_root = Path(__file__).resolve().parents[1]
build_data_path = project_root / 'scripts' / 'build_data.py'
spec = importlib.util.spec_from_file_location('build_data_module', build_data_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class FakeBuilder(module.DataBuilder):
    def __init__(self):
        super().__init__(tmdb_api_key='dummy', max_workers=1, request_delay=0.0)

    def search_tmdb(self, original_title, chinese_title, year, *, require_animation=True):
        return {
            'id': 283905,
            'name': chinese_title or original_title or 'Sample TV',
            'poster_path': '/poster.jpg',
            'first_air_date': '2025-04-08',
            'vote_average': 8.7,
            'overview': 'sample overview',
            'origin_country': ['JP'],
            'genre_ids': [16],
        }

builder = FakeBuilder()
item = {
    'id': '999',
    'title': '机动战士高达 GQuuuuuuX',
    'cover': 'https://example.com/cover.jpg',
    'info': '2025年4月8日 / Sunrise',
    'rating': '8.0',
}
result = builder.build_page_item(item, 'anime')
for key in ['type', 'id', 'tmdb_id', 'mediaType', 'title', 'releaseDate']:
    print(f'{key}={result.get(key)}')
