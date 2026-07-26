name: Daily News Crawler

on:
  schedule:
    # 每小时执行一次（UTC 整点，对应北京时间 1/2/3...点）
    - cron: '0 * * * *'
  # 保留手动点击运行
  workflow_dispatch:

jobs:
  crawl:
    runs-on: ubuntu-latest
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
        with:
          fetch-depth: 0  # 获取完整历史，以便 rebase
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install feedparser requests -i https://pypi.tuna.tsinghua.edu.cn/simple
      
      - name: Run crawler
        run: python scripts/crawler.py
      
      - name: Commit and push
        run: |
          git config user.name "GitHub Actions"
          git config user.email "actions@github.com"
          # 添加所有数据变更
          git add data/
          # 检查是否有变更
          if git diff --cached --quiet; then
            echo "无数据变更，跳过提交"
            exit 0
          fi
          # 提交
          git commit -m "Update news $(date +%Y-%m-%d-%H:%M)"
          # 拉取远程最新更改并 rebase（避免 push 冲突）
          git pull --rebase origin ${{ github.ref_name }}
          # 推送
          git push origin HEAD:${{ github.ref_name }}
