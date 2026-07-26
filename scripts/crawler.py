import json
import feedparser
import re
from datetime import datetime, timezone, timedelta
from html import unescape

# RSS 源配置（国内权威技术媒体）
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
        "url": "https://www.infoq.cn/feed",
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
        "name": "机器之心",
        "url": "https://www.jiqizhixin.com/rss",
        "category": "ai",
        "categoryName": "AI/大模型"
    },
    {
        "name": "CSDN 资讯",
        "url": "https://blog.csdn.net/rss.html",
        "category": "backend",
        "categoryName": "后端架构"
    }
]

def parse_date(entry):
    """解析 RSS 日期，统一转为北京时间字符串"""
    try:
        # 尝试获取 published_parsed（UTC 时间元组）
        if hasattr(entry, 'published_parsed') and entry.published_parsed:
            dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            # UTC + 8小时 = 北京时间
            dt = dt.astimezone(timezone(timedelta(hours=8)))
            return dt.strftime("%Y-%m-%d")
    except:
        pass
    
    try:
        # 备用：从 published 字符串解析
        if hasattr(entry, 'published') and entry.published:
            # 常见格式：Mon, 26 Jul 2026 02:00:00 GMT
            text = entry.published.replace('GMT', '+0000').replace('UTC', '+0000')
            dt = datetime.strptime(text, "%a, %d %b %Y %H:%M:%S %z")
            dt = dt.astimezone(timezone(timedelta(hours=8)))
            return dt.strftime("%Y-%m-%d")
    except:
        pass
    
    # 兜底：用当前日期
    return datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")

def clean_html(text):
    """去除 HTML 标签"""
    if not text:
        return ""
    text = re.sub(r'<[^>]+>', '', text)
    text = unescape(text)
    return text.strip()

def generate_summary(content, length=120):
    """生成摘要"""
    text = clean_html(content)
    if len(text) > length:
        return text[:length] + "..."
    return text

def determine_category(title, summary):
    """根据标题和摘要智能判断分类"""
    text = (title + summary).lower()
    
    keywords = {
        "ai": ["gpt", "llm", "大模型", "openai", "claude", "gemini", "ai ", "人工智能", "深度学习", "神经网络", "transformer", "agent", "rag"],
        "frontend": ["react", "vue", "angular", "css", "html", "webpack", "vite", "前端", "javascript", "typescript", "tailwind", "bun"],
        "backend": ["go ", "golang", "rust", "java", "python", "node.js", "后端", "微服务", "数据库", "redis", "kafka", "postgresql", "spring"],
        "mobile": ["ios", "android", "flutter", "react native", "swift", "kotlin", "移动端", "app", "小程序"],
        "cloud": ["kubernetes", "docker", "云原生", "devops", "aws", "阿里云", "腾讯云", "serverless", "k8s", "terraform", "cicd"],
        "security": ["漏洞", "安全", "加密", "cve", "攻击", "渗透", "csrf", "xss", " ransomware", "零日"],
        "opensource": ["开源", "github", "linux", "git", "apache", "mozilla", "许可证", "license"]
    }
    
    scores = {cat: 0 for cat in keywords}
    for cat, words in keywords.items():
        for word in words:
            if word in text:
                scores[cat] += 1
    
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "opensource"

def crawl():
    all_articles = []
    id_counter = 1
    
    for source in RSS_SOURCES:
        print(f"正在抓取: {source['name']} ...")
        try:
            feed = feedparser.parse(source["url"])
            
            for entry in feed.entries[:5]:  # 每个源取最新5条
                title = clean_html(entry.get("title", "无标题"))
                link = entry.get("link", "")
                published = entry.get("published", "")
                content = entry.get("summary", entry.get("description", ""))
                summary = generate_summary(content)
                
                # 智能分类
                cat = determine_category(title, summary)
                cat_names = {
                    "ai": "AI/大模型", "frontend": "前端", "backend": "后端架构",
                    "mobile": "移动开发", "cloud": "云原生", "security": "安全", "opensource": "开源"
                }
                
                # 解析日期
                try:
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        dt = datetime(*entry.published_parsed[:6])
                        date_str = parse_date(entry)
                    else:
                        date_str = parse_date(entry)
                except:
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
                
        except Exception as e:
            print(f"抓取 {source['name']} 失败: {e}")
    
    # 去重（按标题）
    seen = set()
    unique = []
    for a in all_articles:
        if a["title"] not in seen:
            seen.add(a["title"])
            unique.append(a)
    
    # 按日期倒序
    unique.sort(key=lambda x: x["date"], reverse=True)
    
    # 重新编号
    for i, a in enumerate(unique, 1):
        a["id"] = i
    
    # 保存
    with open("data/news.json", "w", encoding="utf-8") as f:
        json.dump(unique, f, ensure_ascii=False, indent=2)
    
    print(f"共抓取 {len(unique)} 条资讯，已保存到 data/news.json")

if __name__ == "__main__":
    import os
    os.makedirs("data", exist_ok=True)
    crawl()
