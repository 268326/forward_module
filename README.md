# Bangumi 热门榜单

基于 GitHub 托管 JSON 数据的 Bangumi 榜单脚本。

## 当前使用方式

- 宿主脚本：`widget/Bangumi 热门榜单.js`
- GitHub 仓库：`268326/forward_module`
- 当前为**严格托管模式**：本地不再直接抓 Bangumi，不做本地 TMDB 反查；远程 JSON 没有的数据，本地直接不展示。
- 当前为**分布式 JSON 模式**：宿主会按模块和参数请求不同的小 JSON，而不是先拉一个大 JSON。

远程路径结构：
- `data/recent/<category>/page-<n>.json`
- `data/airtime/<category>/<year>/<month>/<sort>/page-<n>.json`
- `data/daily/<scope>/<sort>/<region>/page-<n>.json`

所有模块都按页按需加载：
- 当前只看第 1 页，就只拉第 1 页 JSON
- 不翻页，就不会继续拉后面的 JSON

## 自动更新

### 1. recent_data.json
- workflow：`refresh-recent-data.yml`
- 频率：每天两次
- cron：`20 0,12 * * *`
- 北京时间：`08:20`、`20:20`

更新内容：
- 近期热门
- 每日放送

### 2. archive/*.json + 当前年份榜单
- workflow：`refresh-archive-data.yml`
- 频率：每四天一次
- cron：`40 1 */4 * *`
- 北京时间：每四天 `09:40`

更新内容：
- `recent_data.json` 中当前年份榜单
- `archive/*.json`

## 首次上线

### 1. 推送仓库

```bash
git add .
git commit -m "feat: setup hosted bangumi data pipeline"
git branch -M main
git remote add origin https://github.com/268326/forward_module.git
git push -u origin main
```

如果 remote 已存在：

```bash
git add .
git commit -m "feat: setup hosted bangumi data pipeline"
git push
```

### 2. 设置 GitHub Actions Secret

名称：

```text
TMDB_API_KEY
```

### 3. 手动触发一次 workflow

在 GitHub Actions 页面分别触发：
- `Refresh recent Bangumi data`
- `Refresh archive and current-year ranking`

## 本地检查

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

## 目录

```text
.
├── .github/workflows/
├── archive/
├── scripts/
├── tests/
└── widget/
```
