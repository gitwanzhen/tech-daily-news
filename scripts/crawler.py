import json
import feedparser
import re
import os
import time
import requests
from datetime import datetime, timezone, timedelta

# RSS 源配置（保留所有源，但只提取 AI 相关内容）
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
    """只判断是否为 AI/大模型，不是则返回空字符串表示跳过"""
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
    return ""  # 非 AI，标记为跳过

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
        ai_count = 0
        for entry in feed.entries[:15]:  # 每个源多看几条，因为只取AI
            try:
                title = clean_html(entry.get("title", "无标题"))
                if not title or title == "无标题":
                    continue
                    
                link = entry.get("link", "")
                content = entry.get("summary", entry.get("description", ""))
                summary = generate_summary(content)
                
                # 只保留 AI 分类
                cat = determine_category(title, summary)
                if cat != "ai":
                    continue  # 跳过非 AI 内容
                
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
    
    # 去重
    seen = set()
    unique = []
    for a in all_articles:
        if a["title"] not in seen:
            seen.add(a["title"])
            unique.append(a)
    
    # 只保留 AI（二次确认）
    unique = [a for a in unique if a["category"] == "ai"]
    
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
    
    # 只保留本次真正新的数据
    truly_new = []
    for a in unique:
        if a["title"] not in old_titles:
            truly_new.append(a)
            old_titles.add(a["title"])
    
    # 如果没抓到任何新数据，且旧数据存在，就不动文件
    if len(truly_new) == 0 and len(old_articles) > 0:
        print(f"\n{'='*40}")
        print(f"⚠️ 本次无新数据，保留原有 {len(old_articles)} 条")
        print(f"{'='*40}")
        return
    
    # 给新数据分配 ID（接续旧数据）
    for i, a in enumerate(truly_new, start=max_id + 1):
        a["id"] = i
    
    # 合并：旧数据 + 新数据
    all_combined = old_articles + truly_new
    
    # 按日期倒序排列
    all_combined.sort(key=lambda x: x.get("date", ""), reverse=True)
    
    # 写入
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_combined, f, ensure_ascii=False, indent=2)
    
    print(f"\n{'='*40}")
    print(f"✅ 本次新增 {len(truly_new)} 条 AI 资讯")
    print(f"📚 累计共 {len(all_combined)} 条（旧{len(old_articles)} + 新{len(truly_new)}）")
    print(f"📁 已保存到 {output_path}")
    print(f"{'='*40}")

if __name__ == "__main__":
    crawl()
