import json
import feedparser
import re
import os
import time
import requests
from datetime import datetime, timezone, timedelta

# RSS 源配置
RSS_SOURCES = [
    {
        "name": "阮一峰科技爱好者周刊",
        "url": "https://rsshub.app/ruanyifeng/blog/atom.xml",
        "category": "opensource",
        "categoryName": "开源/综合"
    },
    {
        "name": "开源中国",
        "url": "https://rsshub.app/oschina/news",
        "category": "opensource",
        "categoryName": "开源"
    },
    {
        "name": "InfoQ",
        "url": "https://rsshub.app/infoq/recommend",
        "category": "backend",
        "categoryName": "后端架构"
    },
    {
        "name": "掘金",
        "url": "https://rsshub.app/juejin/category/frontend",
        "category": "frontend",
        "categoryName": "前端"
    },
    {
        "name": "机器之心",
        "url": "https://rsshub.app/jiqizhixin",
        "category": "ai",
        "categoryName": "AI/大模型"
    },
    {
        "name": "CSDN 资讯",
        "url": "https://rsshub.app/csdn/news",
        "category": "backend",
        "categoryName": "后端架构"
    }
]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
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
            # 先用 requests 下载，再用 feedparser 解析
            response = requests.get(url, headers=HEADERS, timeout=20)
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
        for entry in feed.entries[:5]:
            try:
                title = clean_html(entry.get("title", "无标题"))
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
    
    # 去重
    seen = set()
    unique = []
    for a in all_articles:
        if a["title"] not in seen:
            seen.add(a["title"])
            unique.append(a)
    
    unique.sort(key=lambda x: x["date"], reverse=True)
    
    for i, a in enumerate(unique, 1):
        a["id"] = i
    
    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
    os.makedirs(data_dir, exist_ok=True)
    output_path = os.path.join(data_dir, "news.json")
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(unique, f, ensure_ascii=False, indent=2)
    
    print(f"\n{'='*40}")
    print(f"✅ 共抓取 {len(unique)} 条资讯")
    print(f"📁 已保存到 {output_path}")
    print(f"{'='*40}")

if __name__ == "__main__":
    crawl()
