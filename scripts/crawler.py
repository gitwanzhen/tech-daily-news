import json
import logging
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
    {"name": "OpenAI", "rss_url": "https://openai.com/blog/rss.xml", "rsshub_path": "/openai/news"},
    {"name": "Anthropic", "rss_url": "https://www.anthropic.com/blog.rss", "rsshub_path": "/anthropic/news"},
    {"name": "Google AI", "rss_url": "https://ai.googleblog.com/feeds/posts/default", "rsshub_path": "/google/ai"},
    {"name": "Meta AI", "rsshub_path": "/meta/ai"},
    {"name": "Mistral AI", "rsshub_path": "/mistral/news"},
]

HOT_SOURCES = [
    {"name": "微博热搜", "path": "/weibo/search/hot", "platform": "微博"},
    {"name": "知乎热榜", "path": "/zhihu/hotlist", "platform": "知乎"},
    {"name": "豆瓣热门", "path": "/douban/movie/playing", "platform": "豆瓣"},
    {"name": "哔哩哔哩热门", "path": "/bilibili/hot-search", "platform": "B站"},
]

API_TYPE_MAP = {"微博": "weibo", "知乎": "zhihu", "B站": "bilihot"}
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}

# 日志：避免裸 except 吞错，线上可观测
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("tech-news-crawler")

# 复用 TCP 连接，减少握手开销
SESSION = requests.Session()
SESSION.headers.update(HEADERS)

# AI 过滤：英文用词边界匹配（避免 "ai" 命中 available/main/email 等），中文用全词匹配
AI_EN_PATTERN = re.compile(r"(?i)\b(gpt|llm|rag|agent|ai|openai|claude|gemini|deepseek|llama|mistral|chatgpt|copilot|transformer|diffusion|neural|gpt4|gpt5)\b")
AI_ZH_KEYWORDS = ["大模型", "人工智能", "机器学习", "深度学习", "智能体", "神经网络", "生成式"]

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
os.makedirs(DATA_DIR, exist_ok=True)

# 去重索引持久化（替代每次全量扫描历史文件）
DEDUP_FILE = os.path.join(DATA_DIR, "dedup.json")

# ==================== 工具函数 ====================
def clean_html(text):
    if not text: return ""
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'&\w+;', '', text)
    return text.strip()

def generate_summary(content, length=120):
    text = clean_html(content)
    return text[:length] + "..." if len(text) > length else text

def cap_content(text, limit=1800):
    """限制正文长度，避免单条 full_content 过大导致 data 文件膨胀。
    截断时尽量不切断在 HTML 标签中间，避免产生破损标签。"""
    if not text:
        return text
    text = text.strip()
    if len(text) <= limit:
        return text
    cut = text[:limit]
    last_open = cut.rfind("<")
    last_close = cut.rfind(">")
    if last_open > last_close:
        cut = cut[:last_open]
    return cut.rstrip() + "…"

def escape_html(text):
    """构造热搜兜底 HTML 前对文本/URL 做转义，纵深防御存储型 XSS。"""
    if not text:
        return ""
    return (str(text).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;").replace("'", "&#39;"))

def make_id(article):
    """为每条资讯生成稳定 id：优先用 url，缺失则用 标题|来源|日期 兜底。"""
    key = article.get("url") or f"{article.get('title','')}|{article.get('source','')}|{article.get('date','')}"
    return hashlib.md5(key.encode("utf-8")).hexdigest()[:16]

def validate_date(date_str):
    """日期边界校验：解析失败或未来日期都回退为今天，杜绝生成未来文件。"""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        today = datetime.now(timezone(timedelta(hours=8))).replace(tzinfo=None)
        if dt > today:
            logger.warning("未来日期 %s 已回退为今天", date_str)
            return today.strftime("%Y-%m-%d")
        return date_str
    except Exception as e:
        logger.warning("日期校验失败 %s: %s", date_str, e)
        return datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")

def extract_full_content(entry):
    if hasattr(entry, 'content') and entry.content:
        if isinstance(entry.content, list) and len(entry.content) > 0:
            return entry.content[0].value
        else:
            return entry.content
    if hasattr(entry, 'summary') and entry.summary:
        return entry.summary
    if hasattr(entry, 'description') and entry.description:
        return entry.description
    return ""

def parse_date(entry):
    try:
        if hasattr(entry, 'published_parsed') and entry.published_parsed:
            dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc).astimezone(timezone(timedelta(hours=8)))
            return dt.strftime("%Y-%m-%d")
    except Exception as e:
        logger.debug("published_parsed 解析失败: %s", e)
    try:
        if hasattr(entry, 'published'):
            text = entry.published.replace('GMT', '+0000').replace('UTC', '+0000')
            for fmt in ["%a, %d %b %Y %H:%M:%S %z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S"]:
                try:
                    dt = datetime.strptime(text, fmt).astimezone(timezone(timedelta(hours=8)))
                    return dt.strftime("%Y-%m-%d")
                except ValueError:
                    continue
    except Exception as e:
        logger.debug("published 解析失败: %s", e)
    return datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")

def fetch_feed(url, retries=3):
    for i in range(retries):
        try:
            resp = SESSION.get(url, timeout=25, allow_redirects=True)
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
                resp = SESSION.get(full_url, timeout=25)
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
    api_url = f"http://api.guiguiya.com/api/hotlist?type={platform_type}"
    try:
        resp = SESSION.get(api_url, timeout=15)
        data = resp.json()
        items = []
        item_list = data.get("data") or data.get("list") or []
        today = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")
        for item in item_list[:10]:
            title = item.get("title", "")
            if not title:
                continue
            item_url = item.get("url", "") or item.get("link", "")
            hot = item.get("hot", "") or item.get("heat", "")
            summary = f"热度: {hot}" if hot else title
            safe_title = escape_html(title)
            safe_url = escape_html(item_url)
            full_content = f"<p><strong>标题：</strong>{safe_title}</p>"
            if hot:
                full_content += f"<p><strong>热度：</strong>🔥 {escape_html(hot)}</p>"
            full_content += f"<p><strong>来源：</strong>{escape_html(platform_name)}</p>"
            if item_url:
                full_content += f"<p><a href='{safe_url}' target='_blank' rel='noopener'>查看原文</a></p>"
            items.append({
                "title": title,
                "summary": summary,
                "full_content": full_content,
                "category": "hot",
                "categoryName": "🔥 热搜",
                "date": today,
                "source": platform_name,
                "url": item_url,
                "hot_score": int(hot) if str(hot).isdigit() else None,
                "read_time": estimate_read_time(summary)
            })
        return items
    except Exception as e:
        logger.warning("热搜 API 抓取失败(%s): %s", platform_name, e)
        return None

def compute_hot_score(title, source, date_str, real_hot=None):
    """优先使用来源返回的真实热度；缺失时给出确定性兜底值（非随机）。"""
    if real_hot is not None:
        try:
            return int(real_hot)
        except (ValueError, TypeError):
            pass
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
                full_content = cap_content(extract_full_content(entry))
                summary = generate_summary(full_content) if full_content else title
                date_str = validate_date(parse_date(entry))
                article = {
                    "title": title,
                    "summary": summary,
                    "full_content": full_content,
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

# ==================== 去重索引（持久化，替代每次全量扫描） ====================
def load_dedup():
    """
    读取持久化的去重索引（dedup.json，存 id 集合）。
    首次运行（文件不存在）时从已有数据文件惰性构建一次。
    """
    if os.path.exists(DEDUP_FILE):
        try:
            with open(DEDUP_FILE, 'r', encoding='utf-8') as f:
                return set(json.load(f))
        except Exception as e:
            logger.warning("读取去重索引失败，重新构建: %s", e)
    logger.info("从历史文件初始化去重索引（仅首次较慢）...")
    s = set()
    for fname in os.listdir(DATA_DIR):
        if fname.endswith(".json") and fname not in ("index.json", "news.json", "dedup.json"):
            try:
                with open(os.path.join(DATA_DIR, fname), 'r', encoding='utf-8') as f:
                    for item in json.load(f):
                        s.add(make_id(item))
            except Exception as e:
                logger.warning("读取 %s 失败: %s", fname, e)
    return s

def save_dedup(id_set):
    try:
        with open(DEDUP_FILE, 'w', encoding='utf-8') as f:
            json.dump(sorted(id_set), f, ensure_ascii=False)
    except Exception as e:
        logger.warning("保存去重索引失败: %s", e)

# ==================== 主爬虫 ====================
def crawl():
    print("\n" + "="*40)
    print("📡 开始抓取资讯")
    print("="*40)

    all_articles = []  # 本次抓取的所有新文章（尚未去重）

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
                full_content = cap_content(extract_full_content(entry))
                summary = generate_summary(full_content) if full_content else title
                # 只保留 AI 相关（英文词边界 + 中文全词，避免误判）
                text = title + " " + summary
                if not (AI_EN_PATTERN.search(text) or any(z in text for z in AI_ZH_KEYWORDS)):
                    continue
                date_str = validate_date(parse_date(entry))
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
                full_content = cap_content(extract_full_content(entry))
                summary = generate_summary(full_content) if full_content else title
                if not summary or summary.strip() == '':
                    summary = title
                # 如果 full_content 为空或只有空标签，构造描述
                if not full_content or len(clean_html(full_content).strip()) < 5:
                    hot_value = compute_hot_score(title, src["platform"], parse_date(entry))
                    full_content = f"""
                    <div style="font-family: inherit;">
                        <p><strong>标题：</strong>{title}</p>
                        <p><strong>来源：</strong>{src["platform"]}</p>
                        <p><strong>热度：</strong>🔥 {hot_value}</p>
                        <p><strong>日期：</strong>{validate_date(parse_date(entry))}</p>
                        <p style="color: #808a99; font-size: 0.9rem; margin-top: 12px; border-top: 1px solid #374151; padding-top: 12px;">
                            此热搜由 {src["platform"]} 提供，当前源未返回详细内容。
                        </p>
                    </div>
                    """
                date_str = validate_date(parse_date(entry))
                all_articles.append({
                    "title": title,
                    "summary": summary,
                    "full_content": cap_content(full_content),
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

    # 4. 全局去重（基于持久化去重索引，避免每次全量扫描历史）
    print("\n🔄 正在加载去重索引...")
    existing = load_dedup()
    print(f"  已加载 {len(existing)} 条历史 id")

    new_unique = []
    for a in all_articles:
        aid = make_id(a)
        a["id"] = aid
        if aid not in existing:
            new_unique.append(a)
        else:
            print(f"  跳过重复: {a['title'][:40]}... ({a['source']})")
    # 把本次新增 id 写回索引
    for a in new_unique:
        existing.add(a["id"])
    save_dedup(existing)

    print(f"\n  抓取总数: {len(all_articles)}，去重后新增: {len(new_unique)}")

    if not new_unique:
        print("\n⚠️ 无新内容（全部已在历史中出现）")
        clean_old_files()
        return

    # 5. 按日期分组
    grouped = defaultdict(list)
    for art in new_unique:
        grouped[art["date"]].append(art)

    # 6. 写入日期文件（此时新条目保证不与历史重复，但同一天内仍可能重复，需二次去重）
    total_new = 0
    for date_str, articles in grouped.items():
        file_path = os.path.join(DATA_DIR, f"{date_str}.json")
        old = []
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                old = json.load(f)
        # 与当天现有数据去重
        old_titles = {(a["title"], a["source"]) for a in old}
        new_entries = [a for a in articles if (a["title"], a["source"]) not in old_titles]
        if new_entries:
            combined = old + new_entries
            combined.sort(key=lambda x: (x.get("date", ""), x.get("source", "")))
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(combined, f, ensure_ascii=False, indent=2)
            total_new += len(new_entries)
            print(f"📝 {date_str}.json 新增 {len(new_entries)} 条")
        else:
            print(f"📝 {date_str}.json 无新增（当天已存在）")

    # 7. 更新索引
    update_index()

    # 8. 清理旧文件（保留30天）
    clean_old_files()

    print(f"\n✅ 本次新增 {total_new} 条")
    print("="*40)

def update_index():
    index = {}
    for fname in os.listdir(DATA_DIR):
        if fname.endswith(".json") and fname not in ["index.json", "news.json", "dedup.json"]:
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
            except Exception as e:
                logger.warning("处理 %s 失败: %s", fname, e)
                continue
    with open(os.path.join(DATA_DIR, "index.json"), 'w', encoding='utf-8') as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    print(f"📋 索引更新，共 {len(index)} 天")

def clean_old_files(days=30):
    now = datetime.now(timezone(timedelta(hours=8)))
    cutoff = now - timedelta(days=days)
    for fname in os.listdir(DATA_DIR):
        if fname.endswith(".json") and fname not in ["index.json", "news.json", "dedup.json"]:
            date_str = fname.replace(".json", "")
            try:
                dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone(timedelta(hours=8)))
                if dt < cutoff:
                    os.remove(os.path.join(DATA_DIR, fname))
                    print(f"🗑️ 删除 {fname}")
            except Exception as e:
                logger.warning("处理 %s 失败: %s", fname, e)
                continue

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
