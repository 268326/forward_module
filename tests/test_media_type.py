#!/usr/bin/env python3
import importlib.util
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BUILD_DATA_PATH = PROJECT_ROOT / 'scripts' / 'build_data.py'

spec = importlib.util.spec_from_file_location('build_data_module', BUILD_DATA_PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class FakeResolver:
    def __init__(self, tmdb_id='tv/283905'):
        self.tmdb_id = tmdb_id

    def match(self, title, ori_title=None, release_date=None):
        return {
            'tmdb_site_id': self.tmdb_id,
            'tmdb_id': self.tmdb_id.split('/', 1)[1],
            'media_type': self.tmdb_id.split('/', 1)[0],
            'begin': release_date or '2025-04-08',
            'title': title or ori_title or '',
        }

    def match_with_fallback(self, title, ori_title=None, release_date=None, require_animation=True):
        result = self.match(title, ori_title=ori_title, release_date=release_date)
        result = dict(result)
        result['source'] = 'bangumi_data'
        return result


class NullResolver:
    def match(self, title, ori_title=None, release_date=None):
        return None


class TmdbFallbackResolver:
    def match(self, title, ori_title=None, release_date=None):
        return None

    def match_with_fallback(self, title, ori_title=None, release_date=None, require_animation=True):
        return None

    def search_tmdb_fallback(self, title=None, ori_title=None, release_date=None, require_animation=True):
        return None


class FakeBuilder(module.DataBuilder):
    def __init__(self):
        super().__init__(tmdb_api_key='dummy', max_workers=1, request_delay=0.0)
        self.bangumi_data_resolver = FakeResolver('tv/283905')

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

    def get_json(self, url, *, params=None, tmdb=False):
        if url == module.BGM_CALENDAR_API:
            return [
                {
                    'weekday': {'id': 2, 'cn': '星期二'},
                    'items': [
                        {
                            'id': 123,
                            'name': '機動戦士Gundam GQuuuuuuX',
                            'name_cn': '机动战士高达 GQuuuuuuX',
                            'air_date': '2025-04-08',
                            'url': 'https://bgm.tv/subject/123',
                            'summary': 'sample summary',
                            'images': {'large': '//lain.bgm.tv/r/400/pic/cover/l/sample.jpg'},
                            'rating': {'score': 7.9, 'total': 1200},
                        }
                    ],
                }
            ]
        return super().get_json(url, params=params, tmdb=tmdb)


class MediaTypeRegressionTests(unittest.TestCase):
    def test_build_page_item_sets_tmdb_media_type_tv(self):
        builder = FakeBuilder()
        item = {
            'id': '999',
            'title': '机动战士高达 GQuuuuuuX',
            'cover': 'https://example.com/cover.jpg',
            'info': '2025年4月8日 / Sunrise',
            'rating': '8.0',
        }
        result = builder.build_page_item(item, 'anime')
        self.assertEqual(result['type'], 'tmdb')
        self.assertEqual(result['id'], '283905')
        self.assertEqual(result['tmdb_id'], '283905')
        self.assertEqual(result['mediaType'], 'tv')

    def test_build_daily_calendar_sets_tmdb_media_type_tv(self):
        builder = FakeBuilder()
        results = builder.build_daily_calendar()
        self.assertTrue(results)
        first = results[0]
        self.assertEqual(first['type'], 'tmdb')
        self.assertEqual(first['tmdb_id'], '283905')
        self.assertEqual(first['mediaType'], 'tv')

    def test_season_level_tmdb_path_is_normalized_to_series_id(self):
        resolver = module.BangumiDataResolver(items=[
            {
                'title': '転生したらスライムだった件 第4期',
                'titleTranslate': {'zh-Hans': ['关于我转生变成史莱姆这档事 第四季']},
                'begin': '2026-04-03T00:00:00.000Z',
                'sites': [
                    {'site': 'tmdb', 'id': 'tv/82684/season/4'}
                ],
            }
        ])
        result = resolver.match('关于我转生变成史莱姆这档事 第四季', '転生したらスライムだった件 第4期', '2026-04-03')
        self.assertEqual(result['tmdb_id'], '82684')
        self.assertEqual(result['tmdb_site_id'], 'tv/82684/season/4')
        self.assertEqual(result['tmdb_season_number'], 4)
        self.assertEqual(result['media_type'] if 'media_type' in result else result['media_type'], 'tv')

    def test_widget_scripts_contain_tv_media_type_assignment(self):
        path = PROJECT_ROOT / 'widget' / 'Bangumi 热门榜单.js'
        content = path.read_text(encoding='utf-8')
        self.assertGreaterEqual(content.count('baseItem.mediaType = "tv";'), 2, msg=str(path))


if __name__ == '__main__':
    unittest.main(verbosity=2)
