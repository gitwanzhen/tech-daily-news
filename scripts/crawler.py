import json
import feedparser
import re
import os
import time
import requests
import random
import hashlib
from datetime import datetime, timezone, timedelta
from collections import defaultdict

# ==================== 配置 ====================
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

RSS_SOURCES = [
    {"name": "阮一峰科技爱好者周刊", "url": "http://www.ruanyifeng.com/blog/atom.xml"},
    {"name": "开源中国", "url": "https://www.oschina.net/news/rss"},
    {"name": "掘金", "url": "https://juejin.cn/rss"},
    {"name": "SegmentFault", "url": "https://segmentfault.com/feeds"},
]

MODEL_SOURCES = [
    {
        "name": "OpenAI",
        "rss_url": "https://openai.com/blog/rss.xml",
        "rsshub_path": "/openai/news",
        "category": "ai",
        "categoryName": "AI/大模型"
    },
    {
        "name": "Anthropic",
        "rss_url": "https://www.anthropic.com/blog.rss",
        "rsshub_path": "/anthropic/news",
        "category": "ai",
        "categoryName": "AI/大模型"
    },
    {
        "name": "Google AI",
        "rss_url": "https://ai.googleblog.com/feeds/posts/default",
        "rsshub_path": "/google/ai",
        "category": "ai",
        "categoryName": "AI/大模型"
    },
    {
        "name": "Meta AI",
        "rsshub_path": "/meta/ai",
        "category": "ai",
        "categoryName": "AI/大模型"
    },
    {
        "name": "Mistral AI",
        "rsshub_path": "/mistral/news",
        "category": "ai",
        "categoryName": "AI/大模型"
    },
]

HOT_SOURCES = [
    {"name": "微博热搜", "path": "/weibo/search/hot", "platform": "微博"},
    {"name": "知乎热榜", "path": "/zhihu/hotlist", "platform": "知乎"},
    {"name": "豆瓣热门", "path": "/douban/movie/playing", "platform": "豆瓣"},
    {"name": "哔哩哔哩热门", "path": "/bilibili/hot-search", "platform": "B站"},
]

API_TYPE_MAP = {"微博": "weibo", "知乎": "zhihu", "B站": "bilihot"}
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
os.makedirs(DATA_DIR, exist_ok=True)

# ==================== 工具函数 ====================
def clean_html(text):
    if not text: return ""
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'&\w+;', '', text)
    return text.strip()

def generate_summary(content, length=120):
    text = clean_html(content)
    return text[:length] + "..." if len(text) > length else text

def extract_full_content(entry):
    """提取完整的HTML内容（用于详情展示）"""
    # 优先取 content 字段（通常是完整HTML）
    if hasattr(entry, 'content') and entry.content:
        if isinstance(entry.content, list) and len(entry.content) > 0:
            return entry.content[0].value
        else:
            return entry.content
    # 其次取 summary
    if hasattr(entry, 'summary') and entry.summary:
        return entry.summary
    # 最后取 description
    if hasattr(entry, 'description') and entry.description:
        return entry.description
    return ""

def parse_date(entry):
    try:
        if hasattr(entry, 'published_parsed') and entry.published_parsed:
            dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc).astimezone(timezone(timedelta(hours=8)))
            return dt.strftime("%Y-%m-%d")
    except: pass
    try:
        if hasattr(entry, 'published'):
            text = entry.published.replace('GMT', '+0000').replace('UTC', '+0000')
            for fmt in ["%a, %d %b %Y %H:%M:%S %z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S"]:
                try:
                    dt = datetime.strptime(text, fmt).astimezone(timezone(timedelta(hours=8)))
                    return dt.strftime("%Y-%m-%d")
                except: continue
    except: pass
    return datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")

def fetch_feed(url, retries=3):
    for i in range(retries):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=25, allow_redirects=True)
            resp.raise_for_status()
            feed = feedparser.parse(resp.text)
            if feed.entries: return feed
            time.sleep(2)
        except Exception as e:
            print(f"    第{i+1}次失败: {str(e)[:80]}")
            time.sleep(2)
    return None

def fetch_rsshub(path, retries_per_instance=2):
    random.shuffle(RSSHUB_INSTANCES)
    for instance in RSSHUB_INSTANCES:
        full_url = instance + path
        for i in range(retries_per_instance):
            try:
                resp = requests.get(full_url, headers=HEADERS, timeout=25)
                resp.raise_for_status()
                feed = feedparser.parse(resp.text)
                if feed.entries: return feed
                time.sleep(1)
            except Exception as e:
                if "403" in str(e):
                    break
                time.sleep(1)
    return None

def fetch_hot_api(platform_type, platform_name):
    url = f"http://api.guiguiya.com/api/hotlist?type={platform_type}"
    try:
        resp = requests.get(url, timeout=15)
        data = resp.json()
        items = []
        item_list = data.get("data") or data.get("list") or []
        for item in item_list[:10]:
            title = item.get("title", "")
            if not title: continue
            url = item.get("url", "") or item.get("link", "")
            hot = item.get("hot", "") or item.get("heat", "")
            summary = f"热度: {hot}" if hot else title
            items.append({
                "title": title,
                "summary": summary,
                "full_content": summary,  # 热搜无全文，用摘要代替
                "category": "hot",
                "categoryName": "🔥 热搜",
                "source": platform_name,
                "url": url
            })
        return items
    except:
        return None

def compute_hot_score(title, source, date_str):
    seed_str = f"{title}{source}{date_str}"
    hash_int = int(hashlib.md5(seed_str.encode()).hexdigest(), 16)
    return 30 + (hash_int % 70)

def estimate_read_time(text):
    words = len(re.findall(r'[\u4e00-\u9fa5a-zA-Z0-9]', text))
    return max(1, round(words / 150))

# ==================== 抓取模型厂商资讯 ====================
def fetch_model_news():
    model_articles = []
    for src in MODEL_SOURCES:
        print(f"\n[{src['name']}]")
        feed = None

        if src.get("rss_url"):
            print(f"  尝试直接 RSS: {src['rss_url']}")
            feed = fetch_feed(src["rss_url"], retries=2)
            if feed:
                print(f"  直接 RSS 成功")

        if not feed and src.get("rsshub_path"):
            print(f"  尝试 RSSHub: {src['rsshub_path']}")
            feed = fetch_rsshub(src["rsshub_path"])
            if feed:
                print(f"  RSSHub 成功")

        if not feed:
            print(f"  ❌ 抓取失败（跳过）")
            continue

        count = 0
        for entry in feed.entries[:8]:
            try:
                title = clean_html(entry.get("title", ""))
                if not title: continue
                link = entry.get("link", "")
                # 获取全文（保留HTML）
                full_content = extract_full_content(entry)
                # 生成纯文本摘要（用于列表）
                summary = generate_summary(full_content) if full_content else title
                date_str = parse_date(entry)
                article = {
                    "title": title,
                    "summary": summary,
                    "full_content": full_content,   # 新增字段
                    "category": "ai",
                    "categoryName": "AI/大模型",
                    "date": date_str,
                    "source": src["name"],
                    "url": link,
                    "read_time": estimate_read_time(full_content or summary)
                }
                model_articles.append(article)
                count += 1
                print(f"    ✓ {title[:50]}...")
            except Exception as e:
                print(f"    解析失败: {e}")
        print(f"  共抓取 {count} 条")
    return model_articles

# ==================== 主爬虫 ====================
def crawl():
    print("\n" + "="*40)
    print("📡 开始抓取资讯")
    print("="*40)

    all_articles = []

    # 1. 技术源
    print("\n📡 技术资讯")
    for src in RSS_SOURCES:
        print(f"\n[{src['name']}]")
        feed = fetch_feed(src["url"])
        if not feed:
            print("  ❌ 失败")
            continue
        count = 0
        for entry in feed.entries[:8]:
            try:
                title = clean_html(entry.get("title", ""))
                if not title: continue
                link = entry.get("link", "")
                full_content = extract_full_content(entry)
                summary = generate_summary(full_content) if full_content else title
                # 只保留 AI 相关
                text = (title + summary).lower()
                if not any(k in text for k in ["gpt", "llm", "大模型", "openai", "claude", "gemini", "ai", "人工智能", "deepseek", "llama", "agent", "rag"]):
                    continue
                date_str = parse_date(entry)
                all_articles.append({
                    "title": title,
                    "summary": summary,
                    "full_content": full_content,
                    "category": "ai",
                    "categoryName": "AI/大模型",
                    "date": date_str,
                    "source": src["name"],
                    "url": link,
                    "read_time": estimate_read_time(full_content or summary)
                })
                count += 1
                print(f"    ✓ {title[:40]}...")
            except Exception as e:
                print(f"    解析失败: {e}")
        print(f"  共提取 {count} 条 AI 资讯")

    # 2. 模型厂商官方资讯
    print("\n🤖 模型厂商官方资讯")
    model_articles = fetch_model_news()
    all_articles.extend(model_articles)

    # 3. 热搜
    print("\n🔥 热搜")
    for src in HOT_SOURCES:
        print(f"\n[{src['name']}]")
        feed = fetch_rsshub(src["path"])
        if not feed and src["platform"] in API_TYPE_MAP:
            items = fetch_hot_api(API_TYPE_MAP[src["platform"]], src["platform"])
            if items:
                all_articles.extend(items)
                print(f"    API兜底 {len(items)} 条")
                continue
        if not feed:
            print("  ❌ 失败")
            continue
        count = 0
        for entry in feed.entries[:10]:
            try:
                title = clean_html(entry.get("title", ""))
                if not title: continue
                link = entry.get("link", "")
                full_content = extract_full_content(entry)
                summary = generate_summary(full_content) if full_content else title
                date_str = parse_date(entry)
                all_articles.append({
                    "title": title,
                    "summary": summary,
                    "full_content": full_content,
                    "category": "hot",
                    "categoryName": "🔥 热搜",
                    "date": date_str,
                    "source": src["platform"],
                    "url": link,
                    "read_time": estimate_read_time(full_content or summary)
                })
                count += 1
                print(f"    ✓ {title[:40]}...")
            except Exception as e:
                print(f"    解析失败: {e}")
        print(f"  共抓取 {count} 条")

    # 4. 去重
    seen = set()
    unique = []
    for a in all_articles:
        key = (a["title"], a["source"])
        if key not in seen:
            seen.add(key)
            a["hot_score"] = compute_hot_score(a["title"], a["source"], a["date"])
            unique.append(a)

    if not unique:
        print("\n⚠️ 无新内容")
        clean_old_files()
        return

    # 5. 按日期分组存储
    grouped = defaultdict(list)
    for art in unique:
        grouped[art["date"]].append(art)

    total_new = 0
    for date_str, articles in grouped.items():
        file_path = os.path.join(DATA_DIR, f"{date_str}.json")
        old = []
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                old = json.load(f)
        old_titles = {(a["title"], a["source"]) for a in old}
        new_entries = [a for a in articles if (a["title"], a["source"]) not in old_titles]
        if new_entries:
            combined = old + new_entries
            combined.sort(key=lambda x: x.get("date", ""))
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(combined, f, ensure_ascii=False, indent=2)
            total_new += len(new_entries)
            print(f"📝 {date_str}.json 新增 {len(new_entries)} 条")

    # 6. 更新索引
    update_index()

    # 7. 清理旧文件（保留30天）
    clean_old_files()

    print(f"\n✅ 本次新增 {total_new} 条")
    print("="*40)

def update_index():
    index = {}
    for fname in os.listdir(DATA_DIR):
        if fname.endswith(".json") and fname not in ["index.json", "news.json"]:
            date_str = fname.replace(".json", "")
            file_path = os.path.join(DATA_DIR, fname)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                count = len(data)
                mtime = os.path.getmtime(file_path)
                index[date_str] = {
                    "count": count,
                    "updated": datetime.fromtimestamp(mtime, tz=timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S")
                }
            except:
                continue
    with open(os.path.join(DATA_DIR, "index.json"), 'w', encoding='utf-8') as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    print(f"📋 索引更新，共 {len(index)} 天")

def clean_old_files(days=30):
    now = datetime.now(timezone(timedelta(hours=8)))
    cutoff = now - timedelta(days=days)
    for fname in os.listdir(DATA_DIR):
        if fname.endswith(".json") and fname not in ["index.json", "news.json"]:
            date_str = fname.replace(".json", "")
            try:
                dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone(timedelta(hours=8)))
                if dt < cutoff:
                    os.remove(os.path.join(DATA_DIR, fname))
                    print(f"🗑️ 删除 {fname}")
            except:
                continue

if __name__ == "__main__":
    # 迁移旧数据（首次运行）
    old_file = os.path.join(DATA_DIR, "news.json")
    if os.path.exists(old_file) and not any(f.endswith(".json") and f not in ["index.json", "news.json"] for f in os.listdir(DATA_DIR)):
        print("迁移旧数据...")
        with open(old_file, 'r', encoding='utf-8') as f:
            old_data = json.load(f)
        grouped = defaultdict(list)
        for art in old_data:
            date_str = art.get("date", datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d"))
            grouped[date_str].append(art)
        for date_str, arts in grouped.items():
            fpath = os.path.join(DATA_DIR, f"{date_str}.json")
            if not os.path.exists(fpath):
                with open(fpath, 'w', encoding='utf-8') as f:
                    json.dump(arts, f, ensure_ascii=False, indent=2)
        update_index()
    crawl()
