#!/usr/bin/env python3
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
summary = {
    'files': [
        'widget/Bangumi 热门榜单.js',
        'scripts/build_data.py',
        'scripts/export_split_data.py',
        'README.md',
        'requirements.txt',
        '.github/workflows/refresh-recent-data.yml',
        '.github/workflows/refresh-archive-data.yml',
    ],
    'hosted_use': 'widget/Bangumi 热门榜单.js',
    'notes': [
        '严格托管模式：本地只读取远程分布式JSON',
        '数据更新由GitHub Actions自动构建并提交',
        'build_data.py 生成recent_data/archive，export_split_data.py 拆分为data目录'
    ]
}
print(json.dumps(summary, ensure_ascii=False, indent=2))
