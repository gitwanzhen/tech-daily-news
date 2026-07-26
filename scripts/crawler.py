import json
import feedparser
import re
import os
import time
import requests
import random
import shutil
from datetime import datetime, timezone, timedelta
from collections import defaultdict

# ==================== RSSHub 公共实例池（随机轮询）====================
RSSHUB_INSTANCES = [
    "https://rsshub.rssforever.com",
    "https://hub.slarker.me",
    "https://rsshub.pseudoyu.com",
    "https://rsshub.ktachibana.party",
    "https://rsshub.woodland.cafe",
    "https://rss.owo.nz",
    "https://rsshub.henry.wang",
    "https://rss.peachyjoy.top",
    "https://rsshub.speednet.icu",
    "https://rsshub.app",
]

# ==================== 技术源（只保留AI）====================
RSS_SOURCES = [
    {
        "name": "阮一峰科技爱好者周刊",
        "url": "http://www.ruanyifeng.com/blog/atom.xml",
        "category": "opensource",
        "categoryName": "开源/综合"
    },
    {
        "name": "开源中国",
        "url": "https://www.oschina.net/news/rss",
        "category": "opensource",
        "categoryName": "开源"
    },
    {
        "name": "InfoQ",
        "url": "https://feed.infoq.cn/",
        "category": "backend",
        "categoryName": "后端架构"
    },
    {
        "name": "掘金",
        "url": "https://juejin.cn/rss",
        "category": "frontend",
        "categoryName": "前端"
    },
    {
        "name": "CSDN 资讯",
        "url": "https://blog.csdn.net/rss.html",
        "category": "backend",
        "categoryName": "后端架构"
    },
    {
        "name": "SegmentFault",
        "url": "https://segmentfault.com/feeds",
        "category": "frontend",
        "categoryName": "前端"
    }
]

# ==================== 娱乐热搜源（路径形式，配合实例池使用）====================
HOT_SOURCES = [
    {
        "name": "微博热搜",
        "path": "/weibo/search/hot",
        "platform": "微博"
    },
    {
        "name": "知乎热榜",
        "path": "/zhihu/hotlist",
        "platform": "知乎"
    },
    {
        "name": "豆瓣热门",
        "path": "/douban/movie/playing",
        "platform": "豆瓣"
    },
    {
        "name": "哔哩哔哩热门",
        "path": "/bilibili/hot-search",
        "platform": "B站"
    }
]

API_TYPE_MAP = {
    "微博": "weibo",
    "知乎": "zhihu",
    "B站": "bilihot",
}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/rss+xml, application/xml, text/xml, */*',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Referer': 'https://www.google.com/'
}

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
os.makedirs(DATA_DIR, exist_ok=True)

# ==================== 工具函数 ====================
def clean_html(text):
    if not text:
        return ""
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'&\w+;', '', text)
    return text.strip()

def generate_summary(content, length=120):
    text = clean_html(content)
    if len(text) > length:
        return text[:length] + "..."
    return text

def determine_category(title, summary):
    """判断是否为AI内容"""
    text = (title + summary).lower()
    ai_keywords = [
        "gpt", "llm", "大模型", "openai", "claude", "gemini", "ai ", "人工智能",
        "深度学习", "神经网络", "transformer", "agent", "rag", "mistral", "千问",
        "通义", "文心", "deepseek", "llama", "copilot", "chatgpt", "stable diffusion",
        "midjourney", "sora", "多模态", "微调", "预训练", "推理模型", "智谱",
        "百川", "星火", "盘古", "混元", "kimi", "阶跃", "商汤", "旷视"
    ]
    for word in ai_keywords:
        if word in text:
            return "ai"
    return ""

def parse_date(entry):
    try:
        if hasattr(entry, 'published_parsed') and entry.published_parsed:
            dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            dt = dt.astimezone(timezone(timedelta(hours=8)))
            return dt.strftime("%Y-%m-%d")
    except Exception as e:
        print(f"    published_parsed 失败: {e}")

    try:
        if hasattr(entry, 'published') and entry.published:
            text = entry.published.replace('GMT', '+0000').replace('UTC', '+0000')
            for fmt in ["%a, %d %b %Y %H:%M:%S %z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S"]:
                try:
                    dt = datetime.strptime(text, fmt)
                    dt = dt.astimezone(timezone(timedelta(hours=8)))
                    return dt.strftime("%Y-%m-%d")
                except:
                    continue
    except Exception as e:
        print(f"    published 失败: {e")

    return datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")

def fetch_feed(url, retries=3):
    """抓取普通RSS源（技术源）"""
    for i in range(retries):
        try:
            print(f"    尝试第 {i+1} 次...")
            response = requests.get(url, headers=HEADERS, timeout=25, allow_redirects=True)
            response.raise_for_status()
            feed = feedparser.parse(response.text)
            if hasattr(feed, 'entries') and feed.entries:
                print(f"    成功获取 {len(feed.entries)} 条")
                return feed
            else:
                print(f"    返回空数据，2秒后重试...")
                time.sleep(2)
        except Exception as e:
            print(f"    第 {i+1} 次失败: {e}")
            time.sleep(2)
    return None

def fetch_rsshub(path, retries_per_instance=2):
    """从多个 RSSHub 实例轮询获取数据"""
    instances = RSSHUB_INSTANCES.copy()
    random.shuffle(instances)
    for instance in instances:
        full_url = instance + path
        print(f"    尝试实例: {instance}")
        for i in range(retries_per_instance):
            try:
                response = requests.get(full_url, headers=HEADERS, timeout=25, allow_redirects=True)
                response.raise_for_status()
                feed = feedparser.parse(response.text)
                if hasattr(feed, 'entries') and feed.entries:
                    print(f"    ✅ 实例成功获取 {len(feed.entries)} 条")
                    return feed
                else:
                    time.sleep(1)
            except Exception as e:
                err_msg = str(e)
                if "403" in err_msg:
                    print(f"      第 {i+1} 次失败: 403 Forbidden，跳过该实例")
                    break
                print(f"      第 {i+1} 次失败: {err_msg[:60]}")
                time.sleep(1)
    print(f"    ❌ 所有 RSSHub 实例均失败")
    return None

def fetch_hot_api(platform_type, platform_name):
    """聚合API兜底"""
    api_url = f"http://api.guiguiya.com/api/hotlist?type={platform_type}"
    try:
        print(f"    尝试聚合API兜底: {api_url}")
        response = requests.get(api_url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        data = response.json()
        items = []
        item_list = None
        if isinstance(data, dict):
            item_list = data.get("data") or data.get("result") or data.get("list")
        elif isinstance(data, list):
            item_list = data
        if not item_list:
            return None
        for item in item_list[:10]:
            if isinstance(item, str):
                title = item
                url = ""
                hot = ""
            else:
                title = item.get("title", "")
                url = item.get("url", "") or item.get("link", "") or item.get("scheme", "")
                hot = item.get("hot", "") or item.get("hotnum", "") or item.get("desc_extr", "") or item.get("heat", "")
            if not title:
                continue
            summary = f"热度: {hot}" if hot else title
            items.append({
                "title": title,
                "summary": summary,
                "category": "hot",
                "categoryName": "🔥 热搜",
                "date": datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d"),
                "source": platform_name,
                "url": url
            })
        return items
    except Exception as e:
        print(f"    聚合API也失败了: {e}")
        return None

# ==================== 核心爬取 ====================
def crawl():
    print("\n" + "="*40)
    print("📡 开始抓取资讯")
    print("="*40)

    all_articles = []  # 存放本次抓取的所有新文章（不含旧数据）

    # 1. 技术源（只保留AI）
    print("\n" + "="*40)
    print("📡 开始抓取技术资讯")
    print("="*40)
    for source in RSS_SOURCES:
        print(f"\n[{source['name']}]")
        feed = fetch_feed(source["url"])
        if not feed:
            print(f"  ❌ 抓取失败，跳过")
            continue
        print(f"  解析中...")
        ai_count = 0
        for entry in feed.entries[:8]:
            try:
                title = clean_html(entry.get("title", "无标题"))
                if not title or title == "无标题":
                    continue
                link = entry.get("link", "")
                content = entry.get("summary", entry.get("description", ""))
                summary = generate_summary(content)
                cat = determine_category(title, summary)
                if cat != "ai":
                    continue
                date_str = parse_date(entry)
                article = {
                    "title": title,
                    "summary": summary,
                    "category": "ai",
                    "categoryName": "AI/大模型",
                    "date": date_str,
                    "source": source["name"],
                    "url": link
                }
                all_articles.append(article)
                ai_count += 1
                print(f"    ✓ [AI] {title[:50]}...")
            except Exception as e:
                print(f"    解析单条失败: {e}")
        print(f"  本源共提取 {ai_count} 条 AI 资讯")

    # 2. 娱乐热搜
    print("\n" + "="*40)
    print("🔥 开始抓取娱乐热搜")
    print("="*40)
    for source in HOT_SOURCES:
        print(f"\n[{source['name']}]")
        feed = fetch_rsshub(source["path"])
        if not feed and source["platform"] in API_TYPE_MAP:
            api_items = fetch_hot_api(API_TYPE_MAP[source["platform"]], source["platform"])
            if api_items:
                for item in api_items:
                    all_articles.append(item)
                    print(f"    ✓ [API兜底] {item['title'][:50]}...")
                print(f"  聚合API兜底提取 {len(api_items)} 条")
                continue
        if not feed:
            print(f"  ❌ 抓取失败，跳过")
            continue
        print(f"  解析中...")
        hot_count = 0
        for entry in feed.entries[:10]:
            try:
                title = clean_html(entry.get("title", "无标题"))
                if not title or title == "无标题":
                    continue
                link = entry.get("link", "")
                content = entry.get("summary", entry.get("description", ""))
                summary = generate_summary(content)
                if not summary:
                    summary = title[:80] + "..." if len(title) > 80 else title
                date_str = parse_date(entry)
                article = {
                    "title": title,
                    "summary": summary,
                    "category": "hot",
                    "categoryName": "🔥 热搜",
                    "date": date_str,
                    "source": source["platform"],
                    "url": link
                }
                all_articles.append(article)
                hot_count += 1
                print(f"    ✓ [热搜] {title[:50]}...")
            except Exception as e:
                print(f"    解析单条失败: {e}")
        print(f"  本源共提取 {hot_count} 条热搜")

    # 3. 去重（按标题）
    seen = set()
    unique_new = []
    for a in all_articles:
        if a["title"] not in seen:
            seen.add(a["title"])
            unique_new.append(a)

    if not unique_new:
        print("\n⚠️ 本次未抓取到任何新内容，程序退出。")
        # 仍然执行清理（清理旧文件）
        clean_old_files()
        return

    # 4. 按日期分组
    grouped = defaultdict(list)
    for art in unique_new:
        grouped[art["date"]].append(art)

    # 5. 读取现有日期文件，合并去重并写入
    total_new = 0
    for date_str, articles in grouped.items():
        file_path = os.path.join(DATA_DIR, f"{date_str}.json")
        old_articles = []
        if os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    old_articles = json.load(f)
            except Exception as e:
                print(f"读取 {file_path} 失败: {e}")

        # 合并：用标题+来源作为唯一键
        old_titles = { (a["title"], a["source"]) for a in old_articles }
        new_entries = []
        for a in articles:
            if (a["title"], a["source"]) not in old_titles:
                new_entries.append(a)
                old_titles.add((a["title"], a["source"]))

        if new_entries:
            combined = old_articles + new_entries
            combined.sort(key=lambda x: (x.get("date", ""), x.get("source", "")))
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(combined, f, ensure_ascii=False, indent=2)
            total_new += len(new_entries)
            print(f"📝 写入 {file_path}: 新增 {len(new_entries)} 条")

    # 6. 更新索引文件 index.json
    update_index()

    # 7. 清理旧文件（保留最近30天）
    clean_old_files()

    print(f"\n✅ 本次共新增 {total_new} 条文章（按日期文件存储）")
    print("="*40)

# ==================== 索引更新 ====================
def update_index():
    """扫描 data/ 目录，生成 index.json，包含每个日期的文章数、最新更新时间"""
    index = {}
    for filename in os.listdir(DATA_DIR):
        if filename.endswith(".json") and filename != "index.json" and filename != "news.json":
            date_str = filename.replace(".json", "")
            file_path = os.path.join(DATA_DIR, filename)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                count = len(data)
                mtime = os.path.getmtime(file_path)
                index[date_str] = {
                    "count": count,
                    "updated": datetime.fromtimestamp(mtime, tz=timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S")
                }
            except Exception as e:
                print(f"读取 {filename} 索引失败: {e}")
    index_path = os.path.join(DATA_DIR, "index.json")
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    print(f"📋 索引已更新，共 {len(index)} 个日期")

# ==================== 清理过期文件 ====================
def clean_old_files(days=30):
    """删除 days 天前的日期 JSON 文件（保留当天和最近 days 天）"""
    now = datetime.now(timezone(timedelta(hours=8)))
    cutoff = now - timedelta(days=days)
    cutoff_str = cutoff.strftime("%Y-%m-%d")
    for filename in os.listdir(DATA_DIR):
        if filename.endswith(".json") and filename != "index.json" and filename != "news.json":
            date_str = filename.replace(".json", "")
            try:
                dt = datetime.strptime(date_str, "%Y-%m-%d")
                dt = dt.replace(tzinfo=timezone(timedelta(hours=8)))
                if dt < cutoff:
                    file_path = os.path.join(DATA_DIR, filename)
                    os.remove(file_path)
                    print(f"🗑️ 删除过期文件: {filename}")
            except ValueError:
                continue  # 非日期格式文件忽略

# ==================== 迁移旧数据（可选） ====================
def migrate_old_news():
    """如果存在旧的 news.json，按日期拆分，并生成日期文件"""
    old_file = os.path.join(DATA_DIR, "news.json")
    if not os.path.exists(old_file):
        return
    try:
        with open(old_file, "r", encoding="utf-8") as f:
            old_data = json.load(f)
    except Exception as e:
        print(f"迁移：读取 news.json 失败: {e}")
        return

    # 按日期分组
    grouped = defaultdict(list)
    for art in old_data:
        date_str = art.get("date", datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d"))
        # 确保有 id 字段（旧数据可能有，也可能没有）
        grouped[date_str].append(art)

    for date_str, articles in grouped.items():
        file_path = os.path.join(DATA_DIR, f"{date_str}.json")
        if not os.path.exists(file_path):
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(articles, f, ensure_ascii=False, indent=2)
            print(f"迁移：创建 {date_str}.json，含 {len(articles)} 条")
        else:
            # 合并去重
            with open(file_path, "r", encoding="utf-8") as f:
                existing = json.load(f)
            existing_titles = {(a["title"], a["source"]) for a in existing}
            new_entries = [a for a in articles if (a["title"], a["source"]) not in existing_titles]
            if new_entries:
                combined = existing + new_entries
                combined.sort(key=lambda x: (x.get("date", ""), x.get("source", "")))
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(combined, f, ensure_ascii=False, indent=2)
                print(f"迁移：合并 {date_str}.json，新增 {len(new_entries)} 条")

    # 迁移完成后可重命名 news.json 为 news.json.bak 或删除
    # 这里不删除，留作备份
    print("迁移完成，旧的 news.json 保留为备份，您可手动删除。")
    # 更新索引
    update_index()

# ==================== 主入口 ====================
if __name__ == "__main__":
    # 检查是否需要迁移旧数据（首次运行或 data 目录无日期文件时）
    date_files = [f for f in os.listdir(DATA_DIR) if f.endswith(".json") and f != "index.json" and f != "news.json"]
    if not date_files and os.path.exists(os.path.join(DATA_DIR, "news.json")):
        print("检测到旧的 news.json，正在迁移...")
        migrate_old_news()

    crawl()
