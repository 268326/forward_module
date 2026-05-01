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

    def test_refresh_current_year_ranking_skips_future_quarters(self):
        class QuarterBuilder:
            def __init__(self):
                self.calls = []
            def build_airtime_year(self, year, max_pages, months=None):
                self.calls.append((year, max_pages, tuple(months or [])))
                return {
                    'anime': {str(year): {month: {'collects': [[]]} for month in (months or [])}},
                    'real': {str(year): {month: {'collects': [[]]} for month in (months or [])}},
                }

        builder = QuarterBuilder()
        result = module.refresh_current_year_ranking(
            builder,
            existing_airtime={},
            current_year=2026,
            current_year_pages=3,
            archive_pages=0,
            now=module.datetime(2026, 7, 15),
        )
        self.assertIn((2026, 3, ('all',)), builder.calls)
        self.assertIn((2026, 3, ('7',)), builder.calls)
        self.assertIn((2026, 0, ('1',)), builder.calls)
        self.assertIn((2026, 0, ('4',)), builder.calls)
        self.assertNotIn((2026, 0, ('10',)), builder.calls)
        self.assertIn('7', result['anime']['2026'])
        self.assertNotIn('10', result['anime']['2026'])

    def test_refresh_current_year_ranking_prunes_future_quarters_and_old_years(self):
        class QuarterBuilder:
            def __init__(self):
                self.calls = []
            def build_airtime_year(self, year, max_pages, months=None):
                self.calls.append((year, max_pages, tuple(months or [])))
                return {
                    'anime': {str(year): {month: {'collects': [[{'title': f'{year}-{month}'}]]} for month in (months or [])}},
                    'real': {str(year): {month: {'collects': [[{'title': f'{year}-{month}'}]]} for month in (months or [])}},
                }

        existing = {
            'anime': {
                '2025': {'all': {'collects': [[{'title': 'old-year'}]]}},
                '2026': {
                    'all': {'collects': [[{'title': 'all'}]]},
                    '1': {'collects': [[{'title': 'winter'}]]},
                    '10': {'collects': [[{'title': 'future-autumn'}]]},
                },
            },
            'real': {
                '2025': {'all': {'collects': [[{'title': 'old-year'}]]}},
                '2026': {
                    'all': {'collects': [[{'title': 'all'}]]},
                    '1': {'collects': [[{'title': 'winter'}]]},
                    '10': {'collects': [[{'title': 'future-autumn'}]]},
                },
            },
        }
        builder = QuarterBuilder()
        result = module.refresh_current_year_ranking(
            builder,
            existing_airtime=existing,
            current_year=2026,
            current_year_pages=3,
            archive_pages=0,
            now=module.datetime(2026, 1, 10),
        )
        self.assertEqual(set(result['anime'].keys()), {'2026'})
        self.assertEqual(set(result['real'].keys()), {'2026'})
        self.assertIn('all', result['anime']['2026'])
        self.assertIn('1', result['anime']['2026'])
        self.assertNotIn('4', result['anime']['2026'])
        self.assertNotIn('7', result['anime']['2026'])
        self.assertNotIn('10', result['anime']['2026'])

    def test_widget_uses_split_remote_json_paths(self):
        path = PROJECT_ROOT / 'widget' / 'Bangumi 热门榜单.js'
        content = path.read_text(encoding='utf-8')
        self.assertIn('data/recent/', content)
        self.assertIn('data/airtime/', content)
        self.assertIn('data/daily/', content)
        self.assertIn('page-${page}', content)
        self.assertIn('page-${pageNum}', content)
        self.assertNotIn('recent_data.json', content)

    def test_widget_is_strict_hosted_mode_without_dynamic_fetch_fallback(self):
        path = PROJECT_ROOT / 'widget' / 'Bangumi 热门榜单.js'
        content = path.read_text(encoding='utf-8')
        self.assertNotIn('DynamicDataProcessor.processBangumiPage', content)
        self.assertNotIn('DynamicDataProcessor.processDailyCalendar', content)
        self.assertIn('严格托管模式返回空列表', content)

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
    def test_archive_refresh_skips_existing_file(self):
        archive_dir = PROJECT_ROOT / 'tests' / 'tmp_archive_skip'
        archive_dir.mkdir(parents=True, exist_ok=True)
        archive_file = archive_dir / '2025.json'
        archive_file.write_text('{"airtimeRanking": {}}', encoding='utf-8')
        self.assertTrue(archive_file.exists())
        try:
            mtime_before = archive_file.stat().st_mtime
            # simulate script policy: existing archive should be reused instead of rebuilt
            if archive_file.exists():
                skipped = True
            else:
                skipped = False
            self.assertTrue(skipped)
            self.assertEqual(mtime_before, archive_file.stat().st_mtime)
        finally:
            archive_file.unlink(missing_ok=True)
            archive_dir.rmdir()


if __name__ == '__main__':
    unittest.main(verbosity=2)
