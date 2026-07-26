import json
import feedparser
import re
import os
import time
import requests
from datetime import datetime, timezone, timedelta

# 使用各网站官方 RSS
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
    text = (title + summary).lower()
    keywords = {
        "ai": ["gpt", "llm", "大模型", "openai", "claude", "gemini", "ai ", "人工智能", "深度学习", "神经网络", "transformer", "agent", "rag", "mistral", "千问", "通义", "文心", "deepseek", "llama"],
        "frontend": ["react", "vue", "angular", "css", "html", "webpack", "vite", "前端", "javascript", "typescript", "tailwind", "bun", "next.js", "svelte", "dom", "浏览器"],
        "backend": ["go ", "golang", "rust", "java", "python", "node.js", "后端", "微服务", "数据库", "redis", "kafka", "postgresql", "spring", "mysql", "mongodb", "nginx", "api"],
        "mobile": ["ios", "android", "flutter", "react native", "swift", "kotlin", "移动端", "app", "小程序", "uni-app", "harmonyos", "鸿蒙"],
        "cloud": ["kubernetes", "docker", "云原生", "devops", "aws", "阿里云", "腾讯云", "serverless", "k8s", "terraform", "cicd", "helm", "prometheus", "grafana", "容器"],
        "security": ["漏洞", "安全", "加密", "cve", "攻击", "渗透", "csrf", "xss", "ransomware", "零日", "后门", "防火墙", "ssl", "https", "入侵"],
        "opensource": ["开源", "github", "linux", "git", "apache", "mozilla", "许可证", "license", "kernel", "基金会", "发布", "版本"]
    }
    scores = {cat: 0 for cat in keywords}
    for cat, words in keywords.items():
        for word in words:
            if word in text:
                scores[cat] += 1
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "opensource"

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

def crawl():
    all_articles = []
    id_counter = 1
    
    for source in RSS_SOURCES:
        print(f"\n[{source['name']}]")
        print(f"  URL: {source['url']}")
        
        feed = fetch_feed(source["url"])
        if not feed:
            print(f"  ❌ 抓取失败，跳过")
            continue
        
        print(f"  解析中...")
        for entry in feed.entries[:8]:
            try:
                title = clean_html(entry.get("title", "无标题"))
                if not title or title == "无标题":
                    continue
                    
                link = entry.get("link", "")
                content = entry.get("summary", entry.get("description", ""))
                summary = generate_summary(content)
                
                cat = determine_category(title, summary)
                cat_names = {
                    "ai": "AI/大模型", "frontend": "前端", "backend": "后端架构",
                    "mobile": "移动开发", "cloud": "云原生", "security": "安全", "opensource": "开源"
                }
                
                date_str = parse_date(entry)
                
                article = {
                    "id": id_counter,
                    "title": title,
                    "summary": summary,
                    "category": cat,
                    "categoryName": cat_names.get(cat, "综合"),
                    "date": date_str,
                    "source": source["name"],
                    "url": link
                }
                all_articles.append(article)
                id_counter += 1
                print(f"    ✓ {title[:50]}...")
            except Exception as e:
                print(f"    解析单条失败: {e}")
    
    # 本次抓取的去重（同一批内可能重复）
    seen = set()
    unique = []
    for a in all_articles:
        if a["title"] not in seen:
            seen.add(a["title"])
            unique.append(a)
    
    # 读取已有的旧数据
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
            print(f"  📂 读取旧数据 {len(old_articles)} 条，最大ID={max_id}")
        except Exception as e:
            print(f"  读取旧数据失败: {e}")
    
    # 用旧数据的标题做去重判断
    old_titles = {a["title"] for a in old_articles}
    
    # 只保留本次真正新的数据（标题不在旧数据里）
    truly_new = []
    for a in unique:
        if a["title"] not in old_titles:
            truly_new.append(a)
            old_titles.add(a["
