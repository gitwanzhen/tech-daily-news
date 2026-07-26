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

# ==================== 原有技术 RSS 源 ====================
RSS_SOURCES = [
    {"name": "阮一峰科技爱好者周刊", "url": "http://www.ruanyifeng.com/blog/atom.xml"},
    {"name": "开源中国", "url": "https://www.oschina.net/news/rss"},
    {"name": "InfoQ", "url": "https://feed.infoq.cn/"},
    {"name": "掘金", "url": "https://juejin.cn/rss"},
    {"name": "CSDN 资讯", "url": "https://blog.csdn.net/rss.html"},
    {"name": "SegmentFault", "url": "https://segmentfault.com/feeds"},
]

# ==================== 新增：各大模型厂商官方资讯源（RSSHub 路由） ====================
MODEL_SOURCES = [
    {"name": "OpenAI", "rsshub_path": "/openai/news", "category": "ai", "categoryName": "AI/大模型"},
    {"name": "Anthropic", "rsshub_path": "/anthropic/news", "category": "ai", "categoryName": "AI/大模型"},
    {"name": "Google DeepMind", "rsshub_path": "/google/deepmind", "category": "ai", "categoryName": "AI/大模型"},  # 需验证
    {"name": "Meta AI", "rsshub_path": "/meta/ai", "category": "ai", "categoryName": "AI/大模型"},
    {"name": "Mistral AI", "rsshub_path": "/mistral/news", "category": "ai", "categoryName": "AI/大模型"},
    # 以下厂商暂无公开 RSSHub 路由，可自行添加或后续扩展（例如使用通用 RSS 或网页解析）
    # {"name": "DeepSeek", "rsshub_path": None, "url": "https://www.deepseek.com/", "type": "web"},
    # {"name": "Qwen", "rsshub_path": "/alibaba/qwen", "category": "ai", "categoryName": "AI/大模型"},
    # {"name": "xAI (Grok)", "rsshub_path": "/xai/news", "category": "ai", "categoryName": "AI/大模型"},
    # {"name": "Kimi (Moonshot)", "rsshub_path": None, "url": "https://www.moonshot.ai/", "type": "web"},
    # {"name": "GLM (智谱)", "rsshub_path": None, "url": "https://www.zhipuai.cn/", "type": "web"},
]

# ==================== 热搜源 ====================
HOT_SOURCES = [
    {"name": "微博热搜", "path": "/weibo/search/hot", "platform": "微博"},
    {"name": "知乎热榜", "path": "/zhihu/hotlist", "platform": "知乎"},
    {"name": "豆瓣热门", "path": "/douban/movie/playing", "platform": "豆瓣"},
    {"name": "哔哩哔哩热门", "path": "/bilibili/hot-search", "platform": "B站"},
]

API_TYPE_MAP = {"微博": "weibo", "知乎": "zhihu", "B站": "bilihot"}
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) ...'}

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
os.makedirs(DATA_DIR, exist_ok=True)

# ==================== 工具函数（保持不变） ====================
def clean_html(text):
    if not text: return ""
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'&\w+;', '', text)
    return text.strip()

def generate_summary(content, length=120):
    text = clean_html(content)
    return text[:length] + "..." if len(text) > length else text

def determine_category(title, summary):
    # 保留原 AI 检测（现在大部分模型相关都会自动识别）
    text = (title + summary).lower()
    ai_keywords = ["gpt", "llm", "大模型", "openai", "claude", "gemini", "ai", "人工智能", "深度学习", "transformer", "agent", "rag", "deepseek", "llama"]
    return "ai" if any(k in text for k in ai_keywords) else ""

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
            print(f"    第{i+1}次失败: {e}")
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
                "title": title, "summary": summary, "category": "hot",
                "categoryName": "🔥 热搜", "source": platform_name, "url": url
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

# ==================== 新增：抓取模型厂商资讯 ====================
def fetch_model_news():
    """遍历 MODEL_SOURCES，通过 RSSHub 抓取各厂商官方资讯"""
    model_articles = []
    for src in MODEL_SOURCES:
        print(f"\n[{src['name']}]")
        if not src.get("rsshub_path"):
            print(f"  跳过（暂无 RSSHub 路由）")
            continue
        feed = fetch_rsshub(src["rsshub_path"])
        if not feed:
            print(f"  ❌ 抓取失败")
            continue
        print(f"  解析中...")
        count = 0
        for entry in feed.entries[:6]:  # 每个源最多取 6 条
            try:
                title = clean_html(entry.get("title", ""))
                if not title: continue
                link = entry.get("link", "")
                content = entry.get("summary", entry.get("description", ""))
                summary = generate_summary(content)
                date_str = parse_date(entry)
                # 即使 title 不含 AI 关键词，因为来源是官方，我们仍标记为 ai
                article = {
                    "title": title,
                    "summary": summary,
                    "category": "ai",
                    "categoryName": "AI/大模型",
                    "date": date_str,
                    "source": src["name"],
                    "url": link,
                    "read_time": estimate_read_time(summary)
                }
                model_articles.append(article)
                count += 1
                print(f"    ✓ [{src['name']}] {title[:50]}...")
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

    # 1. 技术源（原有，只保留 AI）
    print("\n📡 技术资讯")
    for src in RSS_SOURCES:
        print(f"\n[{src['name']}]")
        feed = fetch_feed(src["url"])
        if not feed:
            print("  ❌ 失败")
            continue
        for entry in feed.entries[:8]:
            try:
                title = clean_html(entry.get("title", ""))
                if not title: continue
                link = entry.get("link", "")
                content = entry.get("summary", entry.get("description", ""))
                summary = generate_summary(content)
                cat = determine_category(title, summary)
                if cat != "ai": continue
                date_str = parse_date(entry)
                all_articles.append({
                    "title": title,
                    "summary": summary,
                    "category": "ai",
                    "categoryName": "AI/大模型",
                    "date": date_str,
                    "source": src["name"],
                    "url": link,
                    "read_time": estimate_read_time(summary)
                })
                print(f"    ✓ {title[:40]}...")
            except Exception as e:
                print(f"    解析失败: {e}")

    # 2. 模型厂商官方资讯（新增）
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
        for entry in feed.entries[:10]:
            try:
                title = clean_html(entry.get("title", ""))
                if not title: continue
                link = entry.get("link", "")
                content = entry.get("summary", entry.get("description", ""))
                summary = generate_summary(content) or title
                date_str = parse_date(entry)
                all_articles.append({
                    "title": title,
                    "summary": summary,
                    "category": "hot",
                    "categoryName": "🔥 热搜",
                    "date": date_str,
                    "source": src["platform"],
                    "url": link,
                    "read_time": estimate_read_time(summary)
                })
                print(f"    ✓ {title[:40]}...")
            except Exception as e:
                print(f"    解析失败: {e}")

    # 4. 去重（按标题+来源）
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
    cutoff_str = cutoff.strftime("%Y-%m-%d")
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

# ==================== 主入口 ====================
if __name__ == "__main__":
    # 首次运行迁移旧 news.json（如果有）
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
