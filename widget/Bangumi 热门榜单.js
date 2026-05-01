// --- 核心配置 ---
// 将下面的仓库地址改成你自己的 GitHub 仓库，例如 "yourname/bangumi-forward-rebuild"
const GITHUB_REPO = "268326/forward_module";
const BASE_DATA_URL = `https://raw.githubusercontent.com/${GITHUB_REPO}/main`;

// --- 动态年份生成 ---
const currentYear = new Date().getFullYear();
const startYear = currentYear; 
const yearOptions = [];
for (let year = startYear; year >= 1940; year--) { 
    yearOptions.push({ title: `${year}`, value: `${year}` });
}

var WidgetMetadata = {
    id: "bangumi_charts_tmdb_v3",
    title: "Bangumi 热门榜单",
    description: "获取Bangumi近期热门、每日放送数据，支持榜单筛选。",
    version: "2.0.0",
    author: "Autism ",
    site: "https://github.com/opix-maker/Forward",
    requiredVersion: "0.0.1",
    detailCacheDuration: 6000,
    modules: [
        {
            title: "近期热门",
            description: "按作品类型浏览近期热门内容 (固定按热度 trends 排序)",
            requiresWebView: false,
            functionName: "fetchRecentHot",
            cacheDuration: 500000,
            params: [
                { name: "category", title: "分类", type: "enumeration", value: "anime", enumOptions: [ { title: "动画", value: "anime" } ] },
                { name: "page", title: "页码", type: "page", value: "1" }
            ]
        },
        {
            title: "年度/季度榜单",
            description: "按年份、季度/全年及作品类型浏览排行",
            requiresWebView: false,
            functionName: "fetchAirtimeRanking",
            cacheDuration: 1000000,
            params: [
                { name: "category", title: "分类", type: "enumeration", value: "anime", enumOptions: [ { title: "动画", value: "anime" }, { title: "三次元", value: "real" } ] },
                { 
                    name: "year", 
                    title: "年份", 
                    type: "enumeration",
                    description: "选择一个年份进行浏览。", 
                    value: `${currentYear}`, // 默认值依然是当前年份
                    enumOptions: yearOptions // 使用新的年份列表
                },
                { name: "month", title: "月份/季度", type: "enumeration", value: "all", description: "选择全年或特定季度对应的月份。留空则为全年。", enumOptions: [ { title: "全年", value: "all" }, { title: "冬季 (1月)", value: "1" }, { title: "春季 (4月)", value: "4" }, { title: "夏季 (7月)", value: "7" }, { title: "秋季 (10月)", value: "10" } ] },
                { name: "sort", title: "排序方式", type: "enumeration", value: "collects", enumOptions: [ { title: "排名", value: "rank" }, { title: "热度", value: "trends" }, { title: "收藏数", value: "collects" }, { title: "发售日期", value: "date" }, { title: "名称", "value": "title" } ] },
                { name: "page", title: "页码", type: "page", value: "1" }
            ]
        },
        
        {
            title: "每日放送",
            description: "查看指定范围的放送（数据来自Bangumi API）",
            requiresWebView: false,
            functionName: "fetchDailyCalendarApi",
            cacheDuration: 20000,
            params: [
                {
                    name: "filterType",
                    title: "筛选范围",
                    type: "enumeration",
                    value: "today",
                    enumOptions: [
                        { title: "今日放送", value: "today" },
                        { title: "指定单日", value: "specific_day" },
                        { title: "本周一至四", value: "mon_thu" },
                        { title: "本周五至日", value: "fri_sun" },
                        { title: "整周放送", value: "all_week" }
                    ]
                },
                {
                    name: "specificWeekday",
                    title: "选择星期",
                    type: "enumeration",
                    value: "1",
                    description: "仅当筛选范围为“指定单日”时有效。",
                    enumOptions: [
                        { title: "星期一", value: "1" }, { title: "星期二", value: "2" },
                        { title: "星期三", value: "3" }, { title: "星期四", value: "4" },
                        { title: "星期五", value: "5" }, { title: "星期六", value: "6" },
                        { title: "星期日", value: "7" }
                    ],
                    belongTo: { paramName: "filterType", value: ["specific_day"] }
                },
                {
                    name: "dailySortOrder", title: "排序方式", type: "enumeration",
                    value: "popularity_rat_bgm",
                    description: "对每日放送结果进行排序",
                    enumOptions: [
                        { title: "热度(评分人数)", value: "popularity_rat_bgm" },
                        { title: "评分", value: "score_bgm_desc" },
                        { title: "放送日(更新日期)", value: "airdate_desc" },
                        { title: "默认", value: "default" }
                    ]
                },
                {
                    name: "dailyRegionFilter", title: "地区筛选", type: "enumeration", value: "all",
                    description: "筛选特定地区的放送内容 (主要依赖TMDB数据)",
                    enumOptions: [
                        { title: "全部地区", value: "all" },
                        { title: "日本", value: "JP" },
                        { title: "中国大陆", value: "CN" },
                        { title: "欧美", value: "US_EU" },
                        { title: "其他/未知", value: "OTHER" }
                    ]
                },
                { name: "page", title: "页码", type: "page", value: "1" }
            ]
        }
    ]
};

// --- 远程分布式 JSON 路径 ---
function buildRecentUrl(category, page) {
    return `${BASE_DATA_URL}/data/recent/${category}/page-${page}.json`;
}

function buildAirtimeUrl(category, year, month, sort, page) {
    return `${BASE_DATA_URL}/data/airtime/${category}/${year}/${month}/${sort}/page-${page}.json`;
}

function buildDailyScopeKey(filterType, specificWeekday) {
    const today = new Date();
    const jsDayToBgm = { 0: 7, 1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6 };
    switch (filterType) {
        case "today":
            return `day-${jsDayToBgm[today.getDay()]}`;
        case "specific_day":
            return `day-${parseInt(specificWeekday || "1", 10)}`;
        case "mon_thu":
            return "mon_thu";
        case "fri_sun":
            return "fri_sun";
        case "all_week":
        default:
            return "all_week";
    }
}

function buildDailyUrl(scopeKey, sortOrder, regionFilter, page) {
    return `${BASE_DATA_URL}/data/daily/${scopeKey}/${sortOrder}/${regionFilter}/page-${page}.json`;
}

async function fetchRemoteArray(url, logLabel) {
    try {
        const response = await Widget.http.get(url, { headers: { 'Cache-Control': 'no-cache' } });
        if (Array.isArray(response.data)) {
            console.log(`[BGM Widget v10.4] 命中远程数据: ${logLabel}`);
            return response.data;
        }
        console.warn(`[BGM Widget v10.4] 远程数据格式异常: ${logLabel}`);
        return [];
    } catch (e) {
        console.warn(`[BGM Widget v10.4] 远程数据缺失，严格托管模式返回空列表: ${logLabel} - ${e.message}`);
        return [];
    }
}

// --- 模块实现 ---

async function fetchRecentHot(params = {}) {
    const category = "anime";
    const page = parseInt(params.page || "1", 10);
    return await fetchRemoteArray(buildRecentUrl(category, page), `recent/${category}/page-${page}`);
}

async function fetchAirtimeRanking(params = {}) {
    const category = params.category || "anime";
    const year = params.year || `${new Date().getFullYear()}`;
    const month = params.month || "all";
    const sort = params.sort || "collects";
    const page = parseInt(params.page || "1", 10);
    return await fetchRemoteArray(buildAirtimeUrl(category, year, month, sort, page), `airtime/${category}/${year}/${month}/${sort}/page-${page}`);
}

async function fetchDailyCalendarApi(params = {}) {
    const {
        filterType = "today",
        specificWeekday = "1",
        dailySortOrder = "popularity_rat_bgm",
        dailyRegionFilter = "all",
        page = "1"
    } = params;
    const scopeKey = buildDailyScopeKey(filterType, specificWeekday);
    const pageNum = parseInt(page || "1", 10);
    return await fetchRemoteArray(buildDailyUrl(scopeKey, dailySortOrder, dailyRegionFilter, pageNum), `daily/${scopeKey}/${dailySortOrder}/${dailyRegionFilter}/page-${pageNum}`);
}
