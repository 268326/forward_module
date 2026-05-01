#!/usr/bin/env python3
import json
from pathlib import Path

root = Path('/var/minis/workspace/bangumi-forward-rebuild')
summary = {
    'files': [
        'widget/Bangumi 热门榜单-即用版.js',
        'widget/Bangumi 热门榜单.js',
        'scripts/build_data.py',
        'README.md',
        'requirements.txt',
        '.github/workflows/build-data.yml',
    ],
    'immediate_use': 'widget/Bangumi 热门榜单-即用版.js',
    'self_hosted_use': 'widget/Bangumi 热门榜单.js',
    'notes': [
        '即用版默认走动态抓取，不依赖 raw JSON',
        '自托管版需要把 GITHUB_REPO 改成你自己的仓库',
        'build_data.py 用于生成 recent_data.json 和 archive/*.json'
    ]
}
print(json.dumps(summary, ensure_ascii=False, indent=2))
