import json
import feedparser
import re
import os
from datetime import datetime, timezone, timedelta

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

def clean_html(text):
    """去除 HTML 标签"""
    if not text:
        return ""
    text = re.sub(r'<[^>]+>', '', text)
    import html
    text = html.unescape(text)
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
        "ai": ["gpt", "llm", "大模型", "openai", "claude", "gemini", "ai ", "人工智能", "深度学习", "神经网络", "transformer", "agent", "rag", "mistral", "千问", "通义", "文心"],
        "frontend": ["react", "vue", "angular", "css", "html", "webpack", "vite", "前端", "javascript", "typescript", "tailwind", "bun", "next.js", "svelte"],
        "backend": ["go ", "golang", "rust", "java", "python", "node.js", "后端", "微服务", "数据库", "redis", "kafka", "postgresql", "spring", "mysql", "mongodb", "nginx"],
        "mobile": ["ios", "android", "flutter", "react native", "swift", "kotlin", "移动端", "app", "小程序", "uni-app", "harmonyos"],
        "cloud": ["kubernetes", "docker", "云原生", "devops", "aws", "阿里云", "腾讯云", "serverless", "k8s", "terraform", "cicd", "helm", "prometheus", "grafana"],
        "security": ["漏洞", "安全", "加密", "cve", "攻击", "渗透", "csrf", "xss", "ransomware", "零日", "后门", "防火墙", "ssl", "https"],
        "opensource": ["开源", "github", "linux", "git", "apache", "mozilla", "许可证", "license", "kernel", "基金会"]
    }
    
    scores = {cat: 0 for cat in keywords}
    for cat, words in keywords.items():
        for word in words:
            if word in text:
                scores[cat] += 1
    
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "opensource"

def parse_date(entry):
    """解析 RSS 日期，统一转为北京时间字符串"""
    try:
        # 优先使用 published_parsed（UTC 时间元组）
        if hasattr(entry, 'published_parsed') and entry.published_parsed:
            dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            # UTC + 8小时 = 北京时间
            dt = dt.astimezone(timezone(timedelta(hours=8)))
            return dt.strftime("%Y-%m-%d")
    except Exception as e:
        print(f"  published_parsed 解析失败: {e}")
        pass
    
    try:
        # 备用：从 published 字符串解析
        if hasattr(entry, 'published') and entry.published:
            text = entry.published.replace('GMT', '+0000').replace('UTC', '+0000')
            # 尝试多种格式
            for fmt in ["%a, %d %b %Y %H:%M:%S %z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S"]:
                try:
                    dt = datetime.strptime(text, fmt)
                    dt = dt.astimezone(timezone(timedelta(hours=8)))
                    return dt.strftime("%Y-%m-%d")
                except:
                    continue
    except Exception as e:
        print(f"  published 字符串解析失败: {e}")
        pass
    
    # 兜底：用当前北京时间
    return datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")

def crawl():
    all_articles = []
    id_counter = 1
    
    for source in RSS_SOURCES:
        print(f"正在抓取: {source['name']} ...")
        try:
            feed = feedparser.parse(
                source["url"],
                request_headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'},
                timeout=15
            )
            
            print(f"  获取到 {len(feed.entries)} 条原始数据")
            
            for entry in feed.entries[:5]:  # 每个源取最新5条
                title = clean_html(entry.get("title", "无标题"))
                link = entry.get("link", "")
                content = entry.get("summary", entry.get("description", ""))
                summary = generate_summary(content)
                
                # 智能分类
                cat = determine_category(title, summary)
                cat_names = {
                    "ai": "AI/大模型", "frontend": "前端", "backend": "后端架构",
                    "mobile": "移动开发", "cloud": "云原生", "security": "安全", "opensource": "开源"
                }
                
                # 解析日期（修复时区）
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
    
    # 确保 data 目录存在
    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
    os.makedirs(data_dir, exist_ok=True)
    
    # 保存
    output_path = os.path.join(data_dir, "news.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(unique, f, ensure_ascii=False, indent=2)
    
    print(f"共抓取 {len(unique)} 条资讯，已保存到 {output_path}")

if __name__ == "__main__":
    crawl()
