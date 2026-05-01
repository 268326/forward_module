#!/usr/bin/env python3
import importlib.util
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BUILD_DATA_PATH = PROJECT_ROOT / 'scripts' / 'build_data.py'

spec = importlib.util.spec_from_file_location('build_data_module_regressions', BUILD_DATA_PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

HTML_FIXTURE = '''
<ul id="browserItemList">
  <li class="item" id="item_101">
    <a class="subjectCover"><img class="cover" src="//example.com/alpha.jpg" /></a>
    <h3><a class="l">Alpha Anime</a></h3>
    <p class="info tip">2025年4月8日 / Studio A</p>
    <small class="fade">8.3</small>
  </li>
  <li class="item" id="item_102">
    <a class="subjectCover"><img class="cover" src="//example.com/beta.jpg" /></a>
    <h3><a class="l">Beta Anime</a></h3>
    <p class="info tip">2025年4月15日 / Studio B</p>
    <small class="fade">7.9</small>
  </li>
</ul>
'''


class FakeResolver:
    def __init__(self, mapping=None):
        self.mapping = mapping or {}

    def match(self, title, ori_title=None, release_date=None):
        key = title or ori_title or ''
        raw = self.mapping.get(key)
        if not raw:
            return None
        return {
            'tmdb_site_id': raw,
            'tmdb_id': raw.split('/', 1)[1],
            'media_type': raw.split('/', 1)[0],
            'begin': release_date or '2025-04-08',
            'title': key,
        }

    def match_with_fallback(self, title, ori_title=None, release_date=None, require_animation=True):
        result = self.match(title, ori_title=ori_title, release_date=release_date)
        if result:
            result = dict(result)
            result['source'] = 'bangumi_data'
        return result


class NullResolver:
    def match(self, title, ori_title=None, release_date=None):
        return None

    def match_with_fallback(self, title, ori_title=None, release_date=None, require_animation=True):
        return None


class TmdbFallbackOnlyResolver:
    def match(self, title, ori_title=None, release_date=None):
        return None

    def match_with_fallback(self, title, ori_title=None, release_date=None, require_animation=True):
        return {
            'tmdb_site_id': 'tv/667788',
            'tmdb_id': '667788',
            'media_type': 'tv',
            'begin': release_date or '2025-04-08',
            'title': title or ori_title or 'Fallback Show',
            'source': 'tmdb_api',
            'raw': {
                'id': 667788,
                'name': title or ori_title or 'Fallback Show',
                'poster_path': '/667788.jpg',
                'first_air_date': release_date or '2025-04-08',
                'vote_average': 7.3,
                'overview': 'fallback overview',
                'origin_country': ['JP'],
                'genre_ids': [16],
            },
        }


class BaseFixtureBuilder(module.DataBuilder):
    def __init__(self):
        super().__init__(tmdb_api_key='dummy', max_workers=1, request_delay=0.0)

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


class NoTmdbBuilder(BaseFixtureBuilder):
    def __init__(self):
        super().__init__()
        self.tmdb_api_key = None
        self.bangumi_data_resolver = NullResolver()

    def search_tmdb(self, original_title, chinese_title, year, *, require_animation=True):
        return None


class SelectiveTmdbBuilder(BaseFixtureBuilder):
    def __init__(self):
        super().__init__()
        self.bangumi_data_resolver = FakeResolver({
            'Alpha Anime': 'tv/9001',
            'Beta Anime': 'tv/9002',
            '机动战士高达 GQuuuuuuX': 'tv/283905',
            '真人示例剧': 'tv/445566',
        })

    def search_tmdb(self, original_title, chinese_title, year, *, require_animation=True):
        title = chinese_title or original_title or ''
        mapping = {
            'Alpha Anime': 9001,
            'Beta Anime': 9002,
            '机动战士高达 GQuuuuuuX': 283905,
            '真人示例剧': 445566,
        }
        tmdb_id = mapping.get(title)
        if tmdb_id is None:
            return None
        return {
            'id': tmdb_id,
            'name': title,
            'poster_path': f'/{tmdb_id}.jpg',
            'first_air_date': '2025-04-08',
            'vote_average': 8.6,
            'overview': f'{title} overview',
            'origin_country': ['JP'],
            'genre_ids': [16],
        }

    def get_text(self, url: str) -> str:
        return HTML_FIXTURE


class WidgetRegressionTests(unittest.TestCase):
    def test_page_item_without_tmdb_keeps_bangumi_link_contract(self):
        builder = NoTmdbBuilder()
        item = {
            'id': '999',
            'title': 'No Match Anime',
            'cover': 'https://example.com/cover.jpg',
            'info': '2025年4月8日 / Sunrise',
            'rating': '8.0',
        }
        result = builder.build_page_item(item, 'anime')
        self.assertEqual(result['type'], 'link')
        self.assertEqual(result['id'], '999')
        self.assertEqual(result['mediaType'], 'anime')
        self.assertEqual(result['link'], 'https://bgm.tv/subject/999')
        self.assertNotIn('tmdb_id', result)

    def test_real_category_tmdb_hit_still_uses_tv_media_type(self):
        builder = SelectiveTmdbBuilder()
        item = {
            'id': '777',
            'title': '真人示例剧',
            'cover': 'https://example.com/real.jpg',
            'info': '2025年4月8日 / Sample TV',
            'rating': '7.5',
        }
        result = builder.build_page_item(item, 'real')
        self.assertEqual(result['type'], 'tmdb')
        self.assertEqual(result['tmdb_id'], '445566')
        self.assertEqual(result['mediaType'], 'tv')
        self.assertIsNone(result['link'])

    def test_daily_calendar_without_tmdb_keeps_bangumi_fields(self):
        builder = NoTmdbBuilder()
        results = builder.build_daily_calendar()
        self.assertTrue(results)
        first = results[0]
        self.assertEqual(first['type'], 'link')
        self.assertEqual(first['mediaType'], 'anime')
        self.assertEqual(first['bgm_id'], '123')
        self.assertEqual(first['bgm_weekday_id'], 2)
        self.assertEqual(first['link'], 'https://bgm.tv/subject/123')
        self.assertNotIn('tmdb_id', first)

    def test_parse_bangumi_list_items_keeps_chinese_and_original_titles(self):
        builder = SelectiveTmdbBuilder()
        html = '''
<ul id="browserItemList">
  <li class="item" id="item_543360">
    <a class="subjectCover"><img class="cover" src="//example.com/alpha.jpg" /></a>
    <h3>
      <a class="l">上伊那牡丹，酒醉身姿似百合花般</a>
      <small class="grey">上伊那ぼたん、酔へる姿は百合の花</small>
    </h3>
    <p class="info tip">12话 / 2026年4月10日 / Sample Staff</p>
    <small class="fade">7.5</small>
  </li>
</ul>
'''
        items = builder.parse_bangumi_list_items(html)
        self.assertEqual(items[0]['title'], '上伊那牡丹，酒醉身姿似百合花般')
        self.assertEqual(items[0]['original_title'], '上伊那ぼたん、酔へる姿は百合の花')

    def test_process_bangumi_page_preserves_order_and_tv_media_type(self):
        builder = SelectiveTmdbBuilder()
        results = builder.process_bangumi_page('https://bgm.tv/anime/browser?sort=trends&page=1', 'anime')
        self.assertEqual([item['tmdb_id'] for item in results], ['9001', '9002'])
        self.assertEqual([item['title'] for item in results], ['Alpha Anime', 'Beta Anime'])
        self.assertTrue(all(item['mediaType'] == 'tv' for item in results))
        self.assertTrue(all(item['type'] == 'tmdb' for item in results))

    def test_tmdb_api_fallback_path_is_consumed(self):
        builder = BaseFixtureBuilder()
        builder.bangumi_data_resolver = TmdbFallbackOnlyResolver()
        item = {
            'id': '1001',
            'title': 'Fallback Anime',
            'original_title': 'フォールバックアニメ',
            'cover': 'https://example.com/fallback.jpg',
            'info': '2025年4月8日 / Studio Fallback',
            'rating': '7.0',
        }
        result = builder.build_page_item(item, 'anime')
        self.assertEqual(result['type'], 'tmdb')
        self.assertEqual(result['tmdb_id'], '667788')
        self.assertEqual(result['mediaType'], 'tv')
        self.assertEqual(result['tmdb_source'], 'tmdb_api')
        self.assertEqual(result['title'], 'Fallback Anime')
        self.assertEqual(result['releaseDate'], '2025-04-08')

    def test_tmdb_result_contains_host_required_keys(self):
        builder = SelectiveTmdbBuilder()
        item = {
            'id': '999',
            'title': '机动战士高达 GQuuuuuuX',
            'cover': 'https://example.com/cover.jpg',
            'info': '2025年4月8日 / Sunrise',
            'rating': '8.0',
        }
        result = builder.build_page_item(item, 'anime')
        required_keys = {
            'id', 'type', 'title', 'posterPath', 'releaseDate',
            'mediaType', 'rating', 'description', 'tmdb_id', 'tmdb_origin_countries'
        }
        self.assertTrue(required_keys.issubset(result.keys()))
        self.assertEqual(result['mediaType'], 'tv')
        self.assertIsNone(result['link'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
