import json
import feedparser
import re
import os
import time
import requests
import random
from datetime import datetime, timezone, timedelta

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
    # 官方实例放最后，作为兜底
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

# 聚合API兜底映射（豆瓣不在支持列表中）
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
        print(f"    published 失败: {e}")

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
    """
    从多个 RSSHub 实例轮询获取数据
    path: RSSHub 路由路径，如 /weibo/search/hot
    """
    instances = RSSHUB_INSTANCES.copy()
    random.shuffle(instances)  # 随机打乱，避免总是打同一个

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
                    break  # 403 没必要重试，直接换实例
                print(f"      第 {i+1} 次失败: {err_msg[:60]}")
                time.sleep(1)

    print(f"    ❌ 所有 RSSHub 实例均失败")
    return None

def fetch_hot_api(platform_type, platform_name):
    """
    使用聚合API作为兜底方案
    支持: weibo, zhihu, bilihot
    """
    api_url = f"http://api.guiguiya.com/api/hotlist?type={platform_type}"
    try:
        print(f"    尝试聚合API兜底: {api_url}")
        response = requests.get(api_url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        data = response.json()

        items = []
        # 适配多种可能的返回结构
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

def crawl():
    all_articles = []
    id_counter = 1

    # ==================== 第1步：抓技术源（只保留AI）====================
    print("\n" + "="*40)
    print("📡 开始抓取技术资讯")
    print("="*40)

    for source in RSS_SOURCES:
        print(f"\n[{source['name']}]")
        print(f"  URL: {source['url']}")

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
                    "id": id_counter,
                    "title": title,
                    "summary": summary,
                    "category": "ai",
                    "categoryName": "AI/大模型",
                    "date": date_str,
                    "source": source["name"],
                    "url": link
                }
                all_articles.append(article)
                id_counter += 1
                ai_count += 1
                print(f"    ✓ [AI] {title[:50]}...")
            except Exception as e:
                print(f"    解析单条失败: {e}")

        print(f"  本源共提取 {ai_count} 条 AI 资讯")

    # ==================== 第2步：抓娱乐热搜 ====================
    print("\n" + "="*40)
    print("🔥 开始抓取娱乐热搜")
    print("="*40)

    for source in HOT_SOURCES:
        print(f"\n[{source['name']}]")

        # 先尝试 RSSHub 实例池
        feed = fetch_rsshub(source["path"])

        # RSSHub 全部失败 -> 尝试聚合API兜底
        if not feed and source["platform"] in API_TYPE_MAP:
            api_items = fetch_hot_api(API_TYPE_MAP[source["platform"]], source["platform"])
            if api_items:
                for item in api_items:
                    item["id"] = id_counter
                    all_articles.append(item)
                    id_counter += 1
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
                    "id": id_counter,
                    "title": title,
                    "summary": summary,
                    "category": "hot",
                    "categoryName": "🔥 热搜",
                    "date": date_str,
                    "source": source["platform"],
                    "url": link
                }
                all_articles.append(article)
                id_counter += 1
                hot_count += 1
                print(f"    ✓ [热搜] {title[:50]}...")
            except Exception as e:
                print(f"    解析单条失败: {e}")

        print(f"  本源共提取 {hot_count} 条热搜")

    # ==================== 第3步：去重并合并旧数据 ====================
    seen = set()
    unique = []
    for a in all_articles:
        if a["title"] not in seen:
            seen.add(a["title"])
            unique.append(a)

    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
    os.makedirs(data_dir, exist_ok=True)
    output_path = os.path.join(data_dir, "news.json")

    old_articles = []
    max_id = 0
    if os.path.exists(output_path):
        try:
            with open(output_path, "r", encoding="utf-8") as f:
                old_articles = json.load(f)
            if old_articles:
                max_id = max(a.get("id", 0) for a in old_articles)
            print(f"\n  📂 读取旧数据 {len(old_articles)} 条，最大ID={max_id}")
        except Exception as e:
            print(f"  读取旧数据失败: {e}")

    old_titles = {a["title"] for a in old_articles}

    truly_new = []
    for a in unique:
        if a["title"] not in old_titles:
            truly_new.append(a)
            old_titles.add(a["title"])

    if len(truly_new) == 0 and len(old_articles) > 0:
        print(f"\n{'='*40}")
        print(f"⚠️ 本次无新数据，保留原有 {len(old_articles)} 条")
        print(f"{'='*40}")
        return

    for i, a in enumerate(truly_new, start=max_id + 1):
        a["id"] = i

    all_combined = old_articles + truly_new
    all_combined.sort(key=lambda x: x.get("date", ""), reverse=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_combined, f, ensure_ascii=False, indent=2)

    ai_new = len([a for a in truly_new if a["category"] == "ai"])
    hot_new = len([a for a in truly_new if a["category"] == "hot"])

    print(f"\n{'='*40}")
    print(f"✅ 本次新增 {len(truly_new)} 条（AI:{ai_new} + 热搜:{hot_new}）")
    print(f"📚 累计共 {len(all_combined)} 条")
    print(f"📁 已保存到 {output_path}")
    print(f"{'='*40}")

if __name__ == "__main__":
    crawl()
