#!/usr/bin/env python3
import re
from datetime import datetime
from typing import Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BANGUMI_DATA_URL = "https://unpkg.com/bangumi-data@0.3/dist/data.json"
TMDB_BASE_URL = "https://api.themoviedb.org/3"
TMDB_ANIMATION_GENRE_ID = 16
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


def normalize_title(value: str | None) -> str:
    if not value or not isinstance(value, str):
        return ""
    value = value.lower().strip()
    value = re.sub(r"[\[\]【】（）()「」『』:：\-－_,\.・/／!！?？'\"~～]", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def normalize_tmdb_query(query: str) -> str:
    if not query or not isinstance(query, str):
        return ""
    query = query.lower().strip()
    query = re.sub(r"[\[\]【】（）()「」『』:：\-－_,\.・]", " ", query)
    query = re.sub(r"\s+", " ", query)
    return query.strip()


def normalize_date(value: str | None) -> str:
    if not value:
        return ""
    text = str(value).strip()
    match = re.search(r"(\d{4})-(\d{2})-(\d{2})", text)
    if match:
        return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
    return ""


def date_diff_days(left: str | None, right: str | None) -> int:
    left_norm = normalize_date(left)
    right_norm = normalize_date(right)
    if not left_norm or not right_norm:
        return 10**9
    return abs((datetime.fromisoformat(left_norm) - datetime.fromisoformat(right_norm)).days)


def score_tmdb_result(result: dict, query: str, valid_year: str) -> float:
    import math

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


def build_retrying_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    retry = Retry(
        total=3,
        connect=3,
        read=3,
        status=3,
        backoff_factor=0.8,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET", "HEAD"]),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


class BangumiDataResolver:
    def __init__(
        self,
        session: Optional[requests.Session] = None,
        data_url: str = BANGUMI_DATA_URL,
        items: Optional[list[dict]] = None,
        tmdb_api_key: Optional[str] = None,
    ):
        self.session = session or build_retrying_session()
        self.data_url = data_url
        self._items = items
        self._index: dict[str, list[dict]] | None = None
        self.tmdb_api_key = tmdb_api_key

    def _load_items(self) -> list[dict]:
        if self._items is None:
            response = self.session.get(self.data_url, timeout=60)
            response.raise_for_status()
            payload = response.json()
            self._items = payload.get("items", [])
        return self._items

    @staticmethod
    def _extract_tmdb_site_info(item: dict) -> Optional[dict]:
        for site in item.get("sites", []) or []:
            if site.get("site") != "tmdb" or not site.get("id"):
                continue
            raw = str(site.get("id"))
            media_type = "movie" if raw.startswith("movie/") else "tv"
            tmdb_id = raw.split("/", 1)[1] if "/" in raw else raw
            return {
                "tmdb_site_id": raw,
                "tmdb_id": tmdb_id,
                "media_type": media_type,
                "begin": normalize_date(item.get("begin")),
                "title": item.get("title") or "",
            }
        return None

    @staticmethod
    def _iter_titles(item: dict) -> list[str]:
        titles: list[str] = []
        raw = item.get("title")
        if raw and raw.strip():
            titles.append(raw.strip())
        title_translate = item.get("titleTranslate") or {}
        for key in ("zh-Hans", "zh-Hant", "en"):
            for value in title_translate.get(key, []) or []:
                if value and isinstance(value, str) and value.strip():
                    titles.append(value.strip())
        deduped: list[str] = []
        seen: set[str] = set()
        for title in titles:
            normalized = normalize_title(title)
            if normalized and normalized not in seen:
                seen.add(normalized)
                deduped.append(title)
        return deduped

    def _build_index(self) -> dict[str, list[dict]]:
        if self._index is not None:
            return self._index
        index: dict[str, list[dict]] = {}
        for item in self._load_items():
            tmdb_info = self._extract_tmdb_site_info(item)
            if not tmdb_info:
                continue
            for title in self._iter_titles(item):
                key = normalize_title(title)
                if not key:
                    continue
                index.setdefault(key, []).append(tmdb_info)
        self._index = index
        return self._index

    def match(self, title: str | None, ori_title: str | None = None, release_date: str | None = None) -> Optional[dict]:
        index = self._build_index()
        keys: list[str] = []
        for value in (title, ori_title):
            key = normalize_title(value)
            if key and key not in keys:
                keys.append(key)
        candidates: list[dict] = []
        seen: set[str] = set()
        for key in keys:
            for entry in index.get(key, []) or []:
                tmdb_site_id = entry.get("tmdb_site_id")
                if not tmdb_site_id or tmdb_site_id in seen:
                    continue
                seen.add(tmdb_site_id)
                candidates.append(entry)
        if not candidates:
            return None
        if release_date:
            candidates.sort(key=lambda entry: date_diff_days(entry.get("begin"), release_date))
        return dict(candidates[0])

    def search_tmdb_fallback(
        self,
        title: str | None,
        ori_title: str | None = None,
        release_date: str | None = None,
        require_animation: bool = True,
    ) -> Optional[dict]:
        if not self.tmdb_api_key:
            return None
        year = normalize_date(release_date)[:4] if release_date else ""
        query = title or ori_title or ""
        if not query:
            return None
        params = {
            "api_key": self.tmdb_api_key,
            "query": query,
            "language": "zh-CN",
            "include_adult": "false",
        }
        if year:
            params["first_air_date_year"] = year
        try:
            response = self.session.get(
                f"{TMDB_BASE_URL}/search/tv",
                params=params,
                timeout=30,
                verify=False,
            )
            response.raise_for_status()
            data = response.json()
        except Exception:
            try:
                response = self.session.get(
                    f"{TMDB_BASE_URL}/search/tv",
                    params=params,
                    timeout=30,
                )
                response.raise_for_status()
                data = response.json()
            except Exception:
                return None
        best_match = None
        max_score = -1.0
        for result in data.get("results", []) or []:
            genre_ids = result.get("genre_ids") or []
            if require_animation and TMDB_ANIMATION_GENRE_ID not in genre_ids:
                continue
            score = score_tmdb_result(result, query, year)
            if score > max_score:
                max_score = score
                best_match = result
        if not best_match:
            return None
        return {
            "tmdb_site_id": f"tv/{best_match.get('id')}",
            "tmdb_id": str(best_match.get("id")),
            "media_type": "tv",
            "begin": normalize_date(best_match.get("first_air_date") or best_match.get("release_date")),
            "title": best_match.get("name") or best_match.get("title") or query,
            "source": "tmdb_api",
            "raw": best_match,
        }

    def match_with_fallback(
        self,
        title: str | None,
        ori_title: str | None = None,
        release_date: str | None = None,
        require_animation: bool = True,
    ) -> Optional[dict]:
        direct = self.match(title=title, ori_title=ori_title, release_date=release_date)
        if direct:
            direct = dict(direct)
            direct["source"] = "bangumi_data"
            return direct
        return self.search_tmdb_fallback(
            title=title,
            ori_title=ori_title,
            release_date=release_date,
            require_animation=require_animation,
        )
