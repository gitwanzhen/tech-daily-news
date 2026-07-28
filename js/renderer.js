// ===== 渲染引擎 =====
import { state } from './state.js';
import { formatDate, escapeHtml, estimateReadTime, generateStableId } from './utils.js';

export function renderCard(article, featured=false, index=null) {
    if (!article.id) article.id = generateStableId(article);
    const isRead = state.readIds.has(article.id);
    const hot = article.hot_score || 30;
    const readTime = article.read_time || estimateReadTime(article.summary || article.title);
    const summary = article.summary && article.summary.trim() ? article.summary : (article.title ? article.title.slice(0,60)+'…' : '点击查看详情');
    const catClass = article.category === 'hot' ? 'hot' : 'ai';
    const catName = article.category === 'hot' ? '热搜' : 'AI/大模型';

    const indexHtml = (index !== null) ? `<span class="index">${index+1}.</span>` : '';
    const readTitleClass = isRead ? 'read-title' : '';
    const articleData = encodeURIComponent(JSON.stringify(article));

    let html = `<div class="${featured?'featured-card':'news-card'} ${catClass} read-item" data-article="${articleData}" data-id="${article.id}">`;
    if (!featured) {
        html += `<div class="card-header">
                    <span class="card-tag ${catClass}">${catName}</span>
                    <span style="display:flex;align-items:center;gap:6px;">
                        <span style="font-size:11px;color:var(--text-muted);">${readTime} min</span>
                        <span class="card-date">${formatDate(article.date)}</span>
                        <span class="read-status ${isRead?'read':''}"></span>
                    </span>
                </div>`;
    } else {
        html += `<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">
                    <span class="card-tag ${catClass}" style="background:var(--color-ai-dim);color:var(--color-ai);">🌟 精选</span>
                    <span style="display:flex;align-items:center;gap:6px;">
                        <span style="font-size:11px;color:var(--text-muted);">${readTime} min</span>
                        <span class="card-date">${formatDate(article.date)}</span>
                        <span class="read-status ${isRead?'read':''}"></span>
                    </span>
                </div>`;
    }
    html += `<div class="card-title ${readTitleClass}">
                <span>${indexHtml}${escapeHtml(article.title)}</span>
                <span class="source-inline">· ${escapeHtml(article.source||'未知')}</span>
            </div>`;
    html += `<div class="card-summary"><span class="core">💡 核心：</span>${escapeHtml(summary)}</div>`;
    html += `<div class="card-footer">
                <span class="hot-score">
                    <span>🔥 ${hot}</span>
                    <span class="bar"><span class="fill" style="width:${Math.min(100, 30+hot*0.7)}%;"></span></span>
                </span>
            </div>`;
    html += `</div>`;
    return html;
}

export function renderAll() {
    const containerAI = document.getElementById('content-ai');
    const containerHot = document.getElementById('content-hot');

    const PAGE_SIZE = 20;
    const aiLimit = Math.min((state.aiPage + 1) * PAGE_SIZE, state.aiAll.length);
    const hotLimit = Math.min((state.hotPage + 1) * PAGE_SIZE, state.hotAll.length);

    const aiPageData = state.aiAll.slice(0, aiLimit);
    const hotPageData = state.hotAll.slice(0, hotLimit);

    state.hasMoreAI = aiLimit < state.aiAll.length;
    state.hasMoreHot = hotLimit < state.hotAll.length;

    if (aiPageData.length===0) {
        containerAI.innerHTML = '<div class="empty">暂无 AI 资讯</div>';
    } else {
        let html = '';
        for (let i=0; i<aiPageData.length; i++) {
            const featured = (i===0);
            html += renderCard(aiPageData[i], featured, i);
        }
        html += state.hasMoreAI ? `<div class="loading-more" id="aiLoadingMore">加载更多...</div>` : `<div class="loading-more" style="opacity:0.5;">— 已加载全部 —</div>`;
        containerAI.innerHTML = html;
    }

    if (hotPageData.length===0) {
        containerHot.innerHTML = '<div class="empty">暂无热搜</div>';
    } else {
        let html = '';
        for (let i=0; i<hotPageData.length; i++) {
            html += renderCard(hotPageData[i], i===0, i);
        }
        html += state.hasMoreHot ? `<div class="loading-more" id="hotLoadingMore">加载更多...</div>` : `<div class="loading-more" style="opacity:0.5;">— 已加载全部 —</div>`;
        containerHot.innerHTML = html;
    }

    document.getElementById('badgeAI').textContent = state.aiAll.length;
    document.getElementById('badgeHot').textContent = state.hotAll.length;
    document.getElementById('dateCount').textContent = `共 ${state.articles.length} 条`;

    updateReadStatusUI();
    updateGeekCode();
    state.isLoadingMore = false;
}

// ===== 更新已读状态 UI =====
export function updateReadStatusUI() {
    document.querySelectorAll('.news-card, .featured-card').forEach(el => {
        const id = parseInt(el.dataset.id);
        if (!id) return;
        const isRead = state.readIds.has(id);
        const dot = el.querySelector('.read-status');
        if (dot) dot.classList.toggle('read', isRead);
        el.classList.toggle('read-item', isRead);
        const title = el.querySelector('.card-title');
        if (title) title.classList.toggle('read-title', isRead);
    });
}

// ===== 技术暗号 =====
const GEEK_CODES = [
    "Llama 4 的 200 万 token 上下文相当于让 AI 一次性读完《三体》三部曲还多出 40% 容量",
    "GPT-5 的代码生成准确率 92% 已超过人类初级工程师的平均水平 (约 85%)",
    "Stable Diffusion 3.5 手部生成失败率从 37% 降至 6%，终于能画好手指了",
    "Claude 4 的思维链可视化让开发者发现模型在推理时会 '自我纠错' 平均 2.3 次",
    "DeepSeek V3 的 MoE 架构使得推理成本仅为 GPT-4 的 1/7",
];
function updateGeekCode() {
    const el = document.getElementById('geekCode');
    const textEl = document.getElementById('geekText');
    const idx = Math.floor(Math.random() * GEEK_CODES.length);
    textEl.textContent = GEEK_CODES[idx];
    el.style.display = 'block';
}
