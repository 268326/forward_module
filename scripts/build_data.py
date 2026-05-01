#!/usr/bin/env python3
import argparse
import json
import math
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from bangumi_data_resolver import BangumiDataResolver, build_retrying_session

import requests
from bs4 import BeautifulSoup

BGM_BASE_URL = "https://bgm.tv"
BGM_CALENDAR_API = "https://api.bgm.tv/calendar"
TMDB_BASE_URL = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w500"
TMDB_ANIMATION_GENRE_ID = 16
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
YEAR_MONTHS = ["all", "1", "4", "7", "10"]
SORTS = ["rank", "trends", "collects", "date", "title"]
CATEGORIES = ["anime", "real"]


def log(msg: str) -> None:
    print(msg, flush=True)


def parse_args() -> argparse.Namespace:
    current_year = datetime.now().year
    parser = argparse.ArgumentParser(description="Build Bangumi widget data files")
    parser.add_argument("--output-dir", default=".", help="Repository root output directory")
    parser.add_argument("--current-year", type=int, default=current_year, help="Year stored in recent_data.json")
    parser.add_argument("--archive-years", default="", help="Comma separated archive years, e.g. 2024,2023")
    parser.add_argument("--recent-pages", type=int, default=2, help="Prebuild page count for recent hot")
    parser.add_argument("--year-pages", type=int, default=1, help="Prebuild page count per sort/month/year")
    parser.add_argument("--max-workers", type=int, default=4, help="Parallel detail worker count")
    parser.add_argument("--request-delay", type=float, default=0.0, help="Optional delay between page requests")
    parser.add_argument("--skip-recent", action="store_true", help="Skip recent hot build")
    parser.add_argument("--skip-current-year", action="store_true", help="Skip current year ranking build")
    parser.add_argument("--skip-daily", action="store_true", help="Skip daily calendar build")
    parser.add_argument("--no-tmdb", action="store_true", help="Disable TMDB enrichment even if TMDB_API_KEY exists")
    return parser.parse_args()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, data) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    log(f"Wrote {path}")


def normalize_tmdb_query(query: str) -> str:
    if not query or not isinstance(query, str):
        return ""
    query = query.lower().strip()
    query = re.sub(r"[\[\]【】（）()「」『』:：\-－_,\.・]", " ", query)
    query = re.sub(r"\s+", " ", query)
    return query.strip()


def parse_date(date_str: str) -> str:
    if not date_str or not isinstance(date_str, str):
        return ""
    date_str = date_str.strip()
    match = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", date_str)
    if match:
        return f"{match.group(1)}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"
    match = re.search(r"(\d{4})年(\d{1,2})月(?!日)", date_str)
    if match:
        return f"{match.group(1)}-{int(match.group(2)):02d}-01"
    match = re.search(r"(\d{4})", date_str)
    if match:
        return f"{match.group(1)}-01-01"
    return ""


def score_tmdb_result(result: dict, query: str, valid_year: str) -> float:
    score = 0.0
    result_title = normalize_tmdb_query(result.get("title") or result.get("name") or "")
    query_lower = normalize_tmdb_query(query or "")
    if result_title == query_lower:
        score += 15
    elif query_lower and query_lower in result_title:
        score += 7
    if valid_year:
        res_date = result.get("release_date") or result.get("first_air_date") or ""
        if res_date.startswith(valid_year):
            score += 6
    score += math.log10((result.get("popularity") or 0) + 1) * 2.2
    return score


class DataBuilder:
    def __init__(self, tmdb_api_key: str | None, max_workers: int = 4, request_delay: float = 0.0):
        self.tmdb_api_key = tmdb_api_key
        self.max_workers = max_workers
        self.request_delay = request_delay
        self.http = build_retrying_session()
        self.http.headers.update({"User-Agent": USER_AGENT})
        self.tmdb = build_retrying_session()
        self.tmdb.headers.update({"User-Agent": USER_AGENT})
        self.bangumi_data_resolver = BangumiDataResolver(session=self.http, tmdb_api_key=tmdb_api_key)

    def _delay(self):
        if self.request_delay > 0:
            time.sleep(self.request_delay)

    def get_text(self, url: str) -> str:
        self._delay()
        response = self.http.get(url, timeout=30)
        response.raise_for_status()
        if not response.encoding or response.encoding.lower() in {"iso-8859-1", "latin-1", "ascii"}:
            response.encoding = response.apparent_encoding or "utf-8"
        return response.text

    def get_json(self, url: str, *, params: dict | None = None, tmdb: bool = False):
        self._delay()
        session = self.tmdb if tmdb else self.http
        response = session.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response.json()

    def resolve_tmdb_from_bangumi_data(self, title: str | None, original_title: str | None, release_date: str | None):
        try:
            return self.bangumi_data_resolver.match(title=title, ori_title=original_title, release_date=release_date)
        except Exception as exc:
            log(f"[warn] bangumi-data resolver failed for {title or original_title}: {exc}")
            return None

    def resolve_tmdb(self, title: str | None, original_title: str | None, release_date: str | None, *, require_animation: bool = True):
        try:
            return self.bangumi_data_resolver.match_with_fallback(
                title=title,
                ori_title=original_title,
                release_date=release_date,
                require_animation=require_animation,
            )
        except Exception as exc:
            log(f"[warn] tmdb resolve failed for {title or original_title}: {exc}")
            return None

    def search_tmdb(self, original_title: str, chinese_title: str | None, year: str | None, *, require_animation: bool = True):
        if not self.tmdb_api_key:
            return None
        release_date = f"{year}-01-01" if year else None
        resolved = self.bangumi_data_resolver.search_tmdb_fallback(
            title=chinese_title or original_title,
            ori_title=original_title,
            release_date=release_date,
            require_animation=require_animation,
        )
        if not resolved:
            return None
        return resolved.get("raw")

    def parse_bangumi_list_items(self, html: str):
        soup = BeautifulSoup(html, "html.parser")
        items = []
        for li in soup.select("ul#browserItemList li.item"):
            item_id = (li.get("id") or "")
            if not item_id.startswith("item_"):
                continue
            item_id = item_id[5:]
            title_link = li.select_one("h3 a.l")
            title = title_link.get_text(strip=True) if title_link else ""
            original_title_node = li.select_one("h3 small.grey")
            original_title = original_title_node.get_text(strip=True) if original_title_node else ""
            cover = None
            cover_img = li.select_one("a.subjectCover img.cover")
            if cover_img:
                cover = cover_img.get("src")
                if cover and cover.startswith("//"):
                    cover = "https:" + cover
            info_node = li.select_one("p.info.tip")
            rating_node = li.select_one("small.fade")
            items.append({
                "id": item_id,
                "title": title,
                "original_title": original_title,
                "cover": cover,
                "info": info_node.get_text(" ", strip=True) if info_node else "",
                "rating": rating_node.get_text(strip=True) if rating_node else "",
            })
        return items

    def build_page_item(self, item: dict, category: str):
        year_match = re.search(r"(\d{4})", item.get("info") or "")
        year = year_match.group(1) if year_match else ""
        release_date = parse_date(item.get("info") or "")
        base_item = {
            "id": str(item.get("id") or ""),
            "type": "link",
            "title": item.get("title") or "",
            "posterPath": item.get("cover"),
            "releaseDate": release_date,
            "mediaType": category,
            "rating": item.get("rating") or "",
            "description": item.get("info") or "",
            "link": f"{BGM_BASE_URL}/subject/{item.get('id')}",
        }

        resolved_match = self.resolve_tmdb(
            title=item.get("title") or "",
            original_title=item.get("original_title") or item.get("alt_title") or None,
            release_date=release_date,
            require_animation=(category == "anime"),
        )
        if resolved_match:
            source = resolved_match.get("source")
            raw = resolved_match.get("raw") or {}
            base_item.update({
                "id": str(resolved_match.get("tmdb_id")),
                "type": "tmdb",
                "mediaType": resolved_match.get("media_type") or "tv",
                "title": raw.get("name") or raw.get("title") or base_item["title"],
                "posterPath": f"{TMDB_IMAGE_BASE}{raw['poster_path']}" if raw.get("poster_path") else base_item["posterPath"],
                "releaseDate": release_date or resolved_match.get("begin") or raw.get("first_air_date") or raw.get("release_date") or base_item["releaseDate"],
                "rating": f"{raw.get('vote_average'):.1f}" if raw.get("vote_average") is not None else base_item["rating"],
                "description": raw.get("overview") or base_item["description"],
                "link": None,
                "tmdb_id": str(resolved_match.get("tmdb_id")),
                "tmdb_origin_countries": raw.get("origin_country") or [],
                "tmdb_source": source,
            })
            return base_item

        return base_item

    def process_bangumi_page(self, url: str, category: str):
        try:
            html = self.get_text(url)
            pending_items = self.parse_bangumi_list_items(html)
        except Exception as exc:
            log(f"[warn] failed to load {url}: {exc}")
            return []
        if not pending_items:
            return []
        if self.tmdb_api_key:
            results = [None] * len(pending_items)
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_map = {executor.submit(self.build_page_item, item, category): idx for idx, item in enumerate(pending_items)}
                for future in as_completed(future_map):
                    idx = future_map[future]
                    try:
                        results[idx] = future.result()
                    except Exception as exc:
                        log(f"[warn] detail build failed: {exc}")
                        results[idx] = self.build_page_item({**pending_items[idx], "title": pending_items[idx].get("title")}, category)
            return [x for x in results if x]
        return [self.build_page_item(item, category) for item in pending_items]

    def build_recent_hot(self, max_pages: int):
        pages = []
        for page in range(1, max_pages + 1):
            url = f"{BGM_BASE_URL}/anime/browser?sort=trends&page={page}"
            log(f"[recent] {url}")
            items = self.process_bangumi_page(url, "anime")
            if not items:
                break
            pages.append(items)
        return {"anime": pages}

    def build_airtime_year(self, year: int, max_pages: int):
        output = {}
        for category in CATEGORIES:
            year_key = str(year)
            output[category] = {year_key: {}}
            for month in YEAR_MONTHS:
                output[category][year_key][month] = {}
                for sort in SORTS:
                    page_results = []
                    for page in range(1, max_pages + 1):
                        url = f"{BGM_BASE_URL}/{category}/browser/airtime/{year}/{month}?sort={sort}&page={page}"
                        log(f"[airtime] {url}")
                        items = self.process_bangumi_page(url, category)
                        if not items:
                            break
                        page_results.append(items)
                    output[category][year_key][month][sort] = page_results
        return output

    def build_daily_calendar(self):
        try:
            api_data = self.get_json(BGM_CALENDAR_API)
        except Exception as exc:
            log(f"[warn] daily calendar fetch failed: {exc}")
            return []
        all_items = []
        for day_data in api_data:
            weekday_id = ((day_data.get("weekday") or {}).get("id"))
            weekday_cn = ((day_data.get("weekday") or {}).get("cn")) or ""
            for item in day_data.get("items") or []:
                item["bgm_weekday_id"] = weekday_id
                item["weekday_cn"] = weekday_cn
                all_items.append(item)

        def convert(item: dict):
            release_date = item.get("air_date") or ""
            base_item = {
                "id": str(item.get("id") or ""),
                "type": "link",
                "title": item.get("name_cn") or item.get("name") or "",
                "posterPath": None,
                "releaseDate": release_date,
                "mediaType": "anime",
                "rating": "N/A",
                "description": f"[{item.get('weekday_cn') or ''}] {item.get('summary') or ''}".strip(),
                "link": item.get("url"),
                "bgm_id": str(item.get("id") or ""),
                "bgm_score": 0,
                "bgm_rating_total": 0,
                "bgm_weekday_id": item.get("bgm_weekday_id"),
            }
            images = item.get("images") or {}
            large = images.get("large")
            if large:
                base_item["posterPath"] = f"https:{large}" if large.startswith("//") else large
            rating = item.get("rating") or {}
            score = rating.get("score")
            total = rating.get("total")
            if score is not None:
                base_item["rating"] = f"{score:.1f}" if isinstance(score, (int, float)) else str(score)
                base_item["bgm_score"] = float(score)
            if total is not None:
                base_item["bgm_rating_total"] = int(total)

            resolved_match = self.resolve_tmdb(
                title=item.get("name_cn") or item.get("name") or "",
                original_title=item.get("name") or None,
                release_date=release_date,
                require_animation=True,
            )
            if resolved_match:
                source = resolved_match.get("source")
                raw = resolved_match.get("raw") or {}
                base_item.update({
                    "id": str(resolved_match.get("tmdb_id")),
                    "type": "tmdb",
                    "mediaType": resolved_match.get("media_type") or "tv",
                    "title": raw.get("name") or raw.get("title") or base_item["title"],
                    "posterPath": f"{TMDB_IMAGE_BASE}{raw['poster_path']}" if raw.get("poster_path") else base_item["posterPath"],
                    "releaseDate": release_date or resolved_match.get("begin") or raw.get("first_air_date") or raw.get("release_date") or base_item["releaseDate"],
                    "rating": f"{raw.get('vote_average'):.1f}" if raw.get("vote_average") is not None else base_item["rating"],
                    "description": raw.get("overview") or base_item["description"],
                    "link": None,
                    "tmdb_id": str(resolved_match.get("tmdb_id")),
                    "tmdb_origin_countries": raw.get("origin_country") or [],
                    "tmdb_source": source,
                })
                return base_item

            return base_item

        if self.tmdb_api_key:
            results = [None] * len(all_items)
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_map = {executor.submit(convert, item): idx for idx, item in enumerate(all_items)}
                for future in as_completed(future_map):
                    idx = future_map[future]
                    try:
                        results[idx] = future.result()
                    except Exception as exc:
                        log(f"[warn] daily item build failed: {exc}")
            return [x for x in results if x]
        return [convert(item) for item in all_items]


def parse_archive_years(raw: str):
    years = []
    for part in (raw or "").split(","):
        part = part.strip()
        if not part:
            continue
        years.append(int(part))
    return years


def make_empty_recent_data() -> dict:
    return {
        "airtimeRanking": {},
        "recentHot": {},
        "dailyCalendar": {},
    }


def load_existing_recent_data(path: Path) -> dict:
    data = make_empty_recent_data()
    if not path.exists():
        return data
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        log(f"[warn] failed to read existing recent_data.json, rebuilding from scratch: {exc}")
        return data
    for key in data:
        if isinstance(payload.get(key), dict):
            data[key] = payload[key]
    return data


def has_current_year_ranking(data: dict, year: int) -> bool:
    year_key = str(year)
    airtime = data.get("airtimeRanking") or {}
    for category in ("anime", "real"):
        if ((airtime.get(category) or {}).get(year_key)):
            return True
    return False


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir).resolve()
    archive_dir = output_dir / "archive"
    ensure_dir(output_dir)
    ensure_dir(archive_dir)

    tmdb_api_key = None if args.no_tmdb else os.getenv("TMDB_API_KEY")
    if tmdb_api_key:
        log("TMDB enrichment: enabled")
    else:
        log("TMDB enrichment: disabled")

    builder = DataBuilder(tmdb_api_key, max_workers=args.max_workers, request_delay=args.request_delay)

    recent_data_path = output_dir / "recent_data.json"
    recent_data = load_existing_recent_data(recent_data_path)
    bootstrap_current_year = args.skip_current_year and not has_current_year_ranking(recent_data, args.current_year)
    if bootstrap_current_year:
        log("[warn] current year ranking missing; bootstrapping current-year airtime ranking once")

    if not args.skip_recent:
        recent_data["recentHot"] = builder.build_recent_hot(args.recent_pages)

    if not args.skip_current_year or bootstrap_current_year:
        recent_data["airtimeRanking"] = builder.build_airtime_year(args.current_year, args.year_pages)

    if not args.skip_daily:
        recent_data["dailyCalendar"]["all_week"] = builder.build_daily_calendar()

    write_json(recent_data_path, recent_data)

    for year in parse_archive_years(args.archive_years):
        archive_data = {
            "airtimeRanking": builder.build_airtime_year(year, args.year_pages)
        }
        write_json(archive_dir / f"{year}.json", archive_data)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
