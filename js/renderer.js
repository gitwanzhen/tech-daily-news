// ===== 渲染引擎 =====
import { state, formatDate } from './state.js';
import { escapeHtml, estimateReadTime, generateStableId, SOURCE_META } from './utils.js';

export function renderCard(article, featured=false, index=null, hideSource=false) {
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
                ${hideSource ? '' : `<span class="source-inline">· ${escapeHtml(article.source||'未知')}</span>`}
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

// 渲染一组（已切片）热搜：遇 groupStart 插入来源分组头，组内序号连续（跨页连续）
export function renderHotSlice(slice) {
    let html = '';
    for (let i = 0; i < slice.length; i++) {
        const a = slice[i];
        const src = a.source || '其他';
        if (a.groupStart) {
            const meta = SOURCE_META[src] || SOURCE_META['其他'];
            const count = state.hotGroupCounts[src] || 0;
            html += `<div class="source-group-header" data-source="${escapeHtml(src)}" style="--sg-color:${meta.color}">`
                + `<span class="sg-icon">${meta.icon}</span>`
                + `<span class="sg-name">${escapeHtml(src)}</span>`
                + `<span class="sg-count">${count}</span>`
                + `</div>`;
            state.hotGroupRendered[src] = 0;
        }
        const gi = state.hotGroupRendered[src] || 0;
        html += renderCard(a, false, gi, true);
        state.hotGroupRendered[src] = gi + 1;
    }
    return html;
}

// 单来源（页签筛选）扁平渲染：全局连续序号 1..N
export function renderFlatHot(slice, startIndex) {
    let html = '';
    for (let i = 0; i < slice.length; i++) {
        html += renderCard(slice[i], false, startIndex + i, true);
    }
    return html;
}

// 当前来源页签对应的数据视图
export function getHotListForView() {
    if (state.hotSourceTab === 'all') return { all: state.hotOrdered, grouped: true };
    return { all: state.hotBySource[state.hotSourceTab] || [], grouped: false };
}

// 渲染摸鱼指南的来源切换页签（全部 + 各来源，带数量）
export function renderHotSourceTabs() {
    const el = document.getElementById('hotSourceTabs');
    if (!el) return;
    const order = state.hotSourceOrder || [];
    const tabs = [];
    for (const s of order) {
        if (s && s !== '其他') tabs.push(s);
    }
    if ((state.hotGroupCounts['其他'] || 0) > 0) tabs.push('其他');
    if (tabs.length === 0) tabs.push('全部');  // 无任何来源数据时的兜底
    let html = '';
    for (const t of tabs) {
        const isAll = t === '全部';
        const key = isAll ? 'all' : t;
        const active = (isAll && state.hotSourceTab === 'all') || (!isAll && state.hotSourceTab === t);
        const meta = isAll ? { icon: '📋', color: 'var(--color-ai)' } : (SOURCE_META[t] || SOURCE_META['其他']);
        const count = isAll ? state.hotAll.length : (state.hotGroupCounts[t] || 0);
        html += `<button class="hs-tab ${active?'active':''}" data-source="${escapeHtml(key)}">`
            + `<span class="hs-icon">${meta.icon}</span>`
            + `<span class="hs-name">${escapeHtml(t)}</span>`
            + `<span class="hs-count">${count}</span>`
            + `</button>`;
    }
    el.innerHTML = html;
}

export function renderAll() {
    const containerAI = document.getElementById('content-ai');
    const containerHot = document.getElementById('content-hot');

    const PAGE_SIZE = 20;
    state.hotPage = 0; state.aiPage = 0;  // renderAll 只渲染首屏，后续交给 loadMore 分页
    const aiLimit = Math.min((state.aiPage + 1) * PAGE_SIZE, state.aiAll.length);
    const { all: hotViewAll, grouped: hotGrouped } = getHotListForView();
    const hotLimit = Math.min((state.hotPage + 1) * PAGE_SIZE, hotViewAll.length);

    const aiPageData = state.aiAll.slice(0, aiLimit);
    const hotPageData = hotViewAll.slice(0, hotLimit);

    state.hasMoreAI = aiLimit < state.aiAll.length;
    state.hasMoreHot = hotLimit < hotViewAll.length;

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
        state.hotGroupRendered = {};
        let html = hotGrouped ? renderHotSlice(hotPageData) : renderFlatHot(hotPageData, 0);
        html += state.hasMoreHot ? `<div class="loading-more" id="hotLoadingMore">加载更多...</div>` : `<div class="loading-more" style="opacity:0.5;">— 已加载全部 —</div>`;
        containerHot.innerHTML = html;
    }

    document.getElementById('badgeAI').textContent = state.aiAll.length;
    document.getElementById('badgeHot').textContent = state.hotAll.length;
    document.getElementById('dateCount').textContent = `共 ${state.articles.length} 条`;

    updateReadStatusUI();
    updateGeekCode();
    state.hotPage = 1; state.aiPage = 1;  // 首屏已渲染，loadMore 应从第二页起，避免重复前 20 条
    state.isLoadingMore = false;
}

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
