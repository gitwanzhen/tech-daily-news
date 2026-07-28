// ========================================================================
//  CONFIG & STATE
// ========================================================================
const STORAGE_KEY_READ = 'techdaily_read_ids';
const PAGE_SIZE = 20;
const DATA_DIR = 'data/';

let articles = [];
let aiAll = [], hotAll = [];
let aiPage = 0, hotPage = 0;
let currentTab = 'ai';
let currentDate = getTodayStr();
let readIds = new Set();
let currentArticle = null;
let isRefreshing = false;
let isLoadingMore = false;
let hasMoreAI = true, hasMoreHot = true;
let observer = null;

const GEEK_CODES = [
    "Llama 4 的 200 万 token 上下文相当于让 AI 一次性读完《三体》三部曲还多出 40% 容量",
    "GPT-5 的代码生成准确率 92% 已超过人类初级工程师的平均水平 (约 85%)",
    "Stable Diffusion 3.5 手部生成失败率从 37% 降至 6%，终于能画好手指了",
    "Claude 4 的思维链可视化让开发者发现模型在推理时会 '自我纠错' 平均 2.3 次",
    "DeepSeek V3 的 MoE 架构使得推理成本仅为 GPT-4 的 1/7",
];

// ========================================================================
//  UTILITY
// ========================================================================
function getBeijingDate() {
    const now = new Date();
    const utc = now.getTime() + now.getTimezoneOffset() * 60000;
    return new Date(utc + 3600000 * 8);
}
function getTodayStr() {
    const d = getBeijingDate();
    return d.getFullYear() + '-' + String(d.getMonth()+1).padStart(2,'0') + '-' + String(d.getDate()).padStart(2,'0');
}
function getTodayDisplay() {
    const d = getBeijingDate();
    const weekdays = ['日','一','二','三','四','五','六'];
    return `今天 ${d.getMonth()+1}月${d.getDate()}日 星期${weekdays[d.getDay()]}`;
}
function formatDate(dateStr) {
    if (!dateStr) return '日期未知';
    const today = getTodayStr();
    const y = getBeijingDate();
    const yest = new Date(y.getTime()-86400000);
    const yestStr = yest.getFullYear()+'-'+String(yest.getMonth()+1).padStart(2,'0')+'-'+String(yest.getDate()).padStart(2,'0');
    if (dateStr === today) return '今天';
    if (dateStr === yestStr) return '昨天';
    return dateStr;
}
function escapeHtml(text) {
    if (!text) return '';
    const d = document.createElement('div');
    d.textContent = text;
    return d.innerHTML;
}
function estimateReadTime(text) {
    if (!text) return 1;
    const words = text.replace(/\s/g,'').length;
    return Math.max(1, Math.round(words/120));
}
function generateStableId(article) {
    const key = (article.title || '') + (article.source || '');
    let hash = 0;
    for (let i = 0; i < key.length; i++) {
        hash = (hash << 5) - hash + key.charCodeAt(i);
        hash |= 0;
    }
    return Math.abs(hash);
}

// ========================================================================
//  STORAGE (仅已读)
// ========================================================================
function loadReadIds() {
    try { const raw=localStorage.getItem(STORAGE_KEY_READ); if(raw) readIds=new Set(JSON.parse(raw)); } catch(_){ readIds=new Set(); }
}
function saveReadIds() { try { localStorage.setItem(STORAGE_KEY_READ, JSON.stringify([...readIds])); } catch(_){} }

function markAsRead(id) { readIds.add(id); saveReadIds(); updateReadStatusUI(); }
function toggleReadStatus() { if(currentArticle) { const id=currentArticle.id; if(readIds.has(id)) readIds.delete(id); else readIds.add(id); saveReadIds(); updateReadStatusUI(); renderAll(); showToast(readIds.has(id)?'已标记已读':'取消已读'); } }

// ========================================================================
//  DATA LOADING
// ========================================================================
async function loadArticlesByDate(dateStr) {
    try {
        const resp = await fetch(`${DATA_DIR}${dateStr}.json`);
        if (!resp.ok) {
            if (resp.status===404) return [];
            throw new Error('HTTP '+resp.status);
        }
        return await resp.json();
    } catch(e) { console.error(e); return []; }
}
async function loadIndex() {
    try {
        const resp = await fetch(`${DATA_DIR}index.json`);
        if (!resp.ok) return {};
        return await resp.json();
    } catch(_){ return {}; }
}

// ========================================================================
//  RENDER
// ========================================================================
function renderCard(article, featured=false, index=null) {
    if (!article.id) article.id = generateStableId(article);

    const isRead = readIds.has(article.id);
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

function renderAll() {
    const containerAI = document.getElementById('content-ai');
    const containerHot = document.getElementById('content-hot');

    const aiLimit = Math.min((aiPage + 1) * PAGE_SIZE, aiAll.length);
    const hotLimit = Math.min((hotPage + 1) * PAGE_SIZE, hotAll.length);

    const aiPageData = aiAll.slice(0, aiLimit);
    const hotPageData = hotAll.slice(0, hotLimit);

    hasMoreAI = aiLimit < aiAll.length;
    hasMoreHot = hotLimit < hotAll.length;

    if (aiPageData.length===0) {
        containerAI.innerHTML = '<div class="empty">暂无 AI 资讯</div>';
    } else {
        let html = '';
        for (let i=0; i<aiPageData.length; i++) {
            const featured = (i===0);
            html += renderCard(aiPageData[i], featured, i);
        }
        html += hasMoreAI ? `<div class="loading-more" id="aiLoadingMore">加载更多...</div>` : `<div class="loading-more" style="opacity:0.5;">— 已加载全部 —</div>`;
        containerAI.innerHTML = html;
    }

    if (hotPageData.length===0) {
        containerHot.innerHTML = '<div class="empty">暂无热搜</div>';
    } else {
        let html = '';
        for (let i=0; i<hotPageData.length; i++) {
            html += renderCard(hotPageData[i], i===0, i);
        }
        html += hasMoreHot ? `<div class="loading-more" id="hotLoadingMore">加载更多...</div>` : `<div class="loading-more" style="opacity:0.5;">— 已加载全部 —</div>`;
        containerHot.innerHTML = html;
    }

    document.getElementById('badgeAI').textContent = aiAll.length;
    document.getElementById('badgeHot').textContent = hotAll.length;
    document.getElementById('dateCount').textContent = `共 ${articles.length} 条`;

    updateReadStatusUI();
    updateGeekCode();
    isLoadingMore = false;
    setupObserver();
}

// ========================================================================
//  IntersectionObserver 加载更多
// ========================================================================
function setupObserver() {
    if (observer) { observer.disconnect(); observer = null; }
    const container = currentTab === 'ai' ? document.getElementById('content-ai') : document.getElementById('content-hot');
    if (!container) return;
    const loadMoreEl = container.querySelector('.loading-more');
    if (!loadMoreEl) return;
    const hasMore = currentTab === 'ai' ? hasMoreAI : hasMoreHot;
    if (!hasMore) return;

    observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting && !isLoadingMore && (currentTab === 'ai' ? hasMoreAI : hasMoreHot)) {
                loadMore();
            }
        });
    }, { rootMargin: '0px 0px 200px 0px' });
    observer.observe(loadMoreEl);
}

function loadMore() {
    if (isLoadingMore) return;
    if (currentTab === 'ai' && !hasMoreAI) return;
    if (currentTab === 'hot' && !hasMoreHot) return;
    isLoadingMore = true;
    if (currentTab === 'ai') { aiPage++; renderAll(); }
    else { hotPage++; renderAll(); }
}

// ========================================================================
//  GEEK CODE
// ========================================================================
function updateGeekCode() {
    const el = document.getElementById('geekCode');
    const textEl = document.getElementById('geekText');
    const idx = Math.floor(Math.random() * GEEK_CODES.length);
    textEl.textContent = GEEK_CODES[idx];
    el.style.display = 'block';
}

// ========================================================================
//  READ STATUS UI
// ========================================================================
function updateReadStatusUI() {
    document.querySelectorAll('.news-card, .featured-card').forEach(el => {
        const id = parseInt(el.dataset.id);
        if (!id) return;
        const isRead = readIds.has(id);
        const dot = el.querySelector('.read-status');
        if (dot) dot.classList.toggle('read', isRead);
        el.classList.toggle('read-item', isRead);
        const title = el.querySelector('.card-title');
        if (title) title.classList.toggle('read-title', isRead);
    });
}

// ========================================================================
//  TOGGLE
// ========================================================================
function toggleHideRead() {
    const checked = document.getElementById('hideReadToggle').checked;
    document.getElementById('content-ai').classList.toggle('hide-read', checked);
    document.getElementById('content-hot').classList.toggle('hide-read', checked);
}

// ========================================================================
//  TAB
// ========================================================================
function switchTab(tab, btn) {
    currentTab = tab;
    aiPage = 0; hotPage = 0;
    hasMoreAI = true; hasMoreHot = true;
    document.querySelectorAll('.tab-btn').forEach(b=>b.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('content-ai').style.display = tab==='ai' ? 'block' : 'none';
    document.getElementById('content-hot').style.display = tab==='hot' ? 'block' : 'none';
    renderAll();
}

// ========================================================================
//  DATE PICKER
// ========================================================================
async function setToday() {
    currentDate = getTodayStr();
    document.getElementById('datePicker').value = currentDate;
    await loadAndRender(currentDate);
    showToast('已回到今日');
}

document.getElementById('datePicker').addEventListener('change', async (e) => {
    const date = e.target.value;
    if (date) {
        currentDate = date;
        await loadAndRender(date);
    }
});

// ========================================================================
//  LOAD & RENDER BY DATE
// ========================================================================
async function loadAndRender(dateStr) {
    let data = await loadArticlesByDate(dateStr);
    data = data.map(article => {
        if (!article.id) article.id = generateStableId(article);
        return article;
    });
    articles = data;
    aiAll = articles.filter(a => a.category === 'ai').sort((a,b) => b.id - a.id);
    hotAll = articles.filter(a => a.category === 'hot').sort((a,b) => b.id - a.id);
    aiPage = 0; hotPage = 0;
    hasMoreAI = true; hasMoreHot = true;
    renderAll();
    document.getElementById('todayDate').textContent = dateStr === getTodayStr() ? getTodayDisplay() : formatDate(dateStr);
    document.getElementById('datePicker').value = dateStr;
    const hour = getBeijingDate().getHours();
    document.body.className = (hour >= 6 && hour < 18) ? 'morning' : 'evening';
}

// ========================================================================
//  MODAL
// ========================================================================
function openDetailFromCard(cardElement) {
    const encoded = cardElement.dataset.article;
    if (!encoded) { showToast('无法读取文章数据'); return; }
    try {
        const article = JSON.parse(decodeURIComponent(encoded));
        showModal(article);
    } catch(e) { showToast('数据解析失败'); console.error(e); }
}

function showModal(article) {
    currentArticle = article;
    const tag = document.getElementById('modalTag');
    tag.textContent = article.category === 'hot' ? '热搜' : (article.categoryName || 'AI/大模型');
    tag.className = 'card-tag ' + (article.category||'ai');
    tag.style.cssText = article.category==='hot' ? 'background:var(--color-hot-dim);color:var(--color-hot);' : 'background:var(--color-ai-dim);color:var(--color-ai);';
    document.getElementById('modalDate').textContent = '📅 ' + formatDate(article.date);
    document.getElementById('modalReadTime').textContent = '⏱ ' + (article.read_time||estimateReadTime(article.summary)) + ' min';
    document.getElementById('modalTitle').textContent = article.title;

    const fullContainer = document.getElementById('modalFullContent');
    const summaryContainer = document.getElementById('modalContentBox');
    const summaryText = document.getElementById('modalSummary');

    let hasValidContent = false;
    let contentHtml = article.full_content || '';
    const stripped = contentHtml.replace(/<[^>]+>/g, '').trim();
    if (stripped.length > 0) hasValidContent = true;

    if (hasValidContent) {
        fullContainer.innerHTML = contentHtml;
        fullContainer.style.display = 'block';
        summaryContainer.style.display = 'none';
        fullContainer.classList.add(article.category === 'hot' ? 'hot-border' : 'ai-border');
    } else {
        fullContainer.style.display = 'block';
        summaryContainer.style.display = 'none';
        const hot = article.hot_score || 30;
        const source = article.source || '未知来源';
        const date = formatDate(article.date);
        const url = article.url || '#';
        const summary = article.summary && article.summary.trim() ? `<p><strong>摘要：</strong>${escapeHtml(article.summary)}</p>` : '';
        fullContainer.innerHTML = `
            <div style="padding: 8px 0;">
                <p style="font-size:1.1rem; font-weight:600; color:var(--text-primary); margin-bottom:8px;">📌 热搜详情</p>
                <p><strong>标题：</strong>${escapeHtml(article.title)}</p>
                <p><strong>来源：</strong>${escapeHtml(source)}</p>
                <p><strong>热度：</strong>🔥 ${hot}</p>
                <p><strong>日期：</strong>${date}</p>
                ${summary}
                ${url && url !== '#' ? `<p><strong>链接：</strong><a href="${url}" target="_blank">查看原文</a></p>` : ''}
                <p style="margin-top:12px; color:var(--text-muted); font-size:0.9rem; border-top:1px solid var(--border-subtle); padding-top:12px;">
                    ⚠️ 当前数据源未提供完整文章内容，以上为摘要信息。
                </p>
            </div>
        `;
        fullContainer.classList.add(article.category === 'hot' ? 'hot-border' : 'ai-border');
    }

    document.getElementById('detailModal').classList.add('active');
    document.body.style.overflow = 'hidden';
    if (article.id) markAsRead(article.id);
}

function closeModal(e) {
    if (e && e.target !== e.currentTarget) return;
    document.getElementById('detailModal').classList.remove('active');
    document.body.style.overflow = '';
    currentArticle = null;
    updateReadStatusUI();
}

function openSource() {
    if (currentArticle?.url && currentArticle.url !== '#') window.open(currentArticle.url,'_blank');
    else showToast('无原文链接');
}
function copyLink() {
    if (currentArticle?.url && currentArticle.url !== '#') {
        navigator.clipboard.writeText(currentArticle.url).then(()=>showToast('链接已复制')).catch(()=>showToast('复制失败'));
    } else showToast('无链接');
}

// ========================================================================
//  UPDATE DATA
// ========================================================================
async function updateData() {
    if (isRefreshing) return;
    isRefreshing = true;
    const btn = document.getElementById('updateBtn');
    btn.classList.add('spinning');
    btn.disabled = true;
    try {
        showToast('正在触发爬虫更新...');
        await new Promise(r => setTimeout(r, 2000));
        await loadAndRender(currentDate);
        showToast('数据已刷新 (实际需触发Action)');
    } catch(e) { showToast('刷新失败'); } finally { btn.classList.remove('spinning'); btn.disabled=false; isRefreshing=false; }
}

// ========================================================================
//  TOAST
// ========================================================================
function showToast(msg) {
    const t = document.getElementById('toast');
    t.textContent = msg;
    t.classList.add('show');
    clearTimeout(t._timer);
    t._timer = setTimeout(()=>t.classList.remove('show'), 2200);
}

// ========================================================================
//  INIT
// ========================================================================
async function init() {
    loadReadIds();
    const today = getTodayStr();
    const index = await loadIndex();
    let targetDate = today;
    if (!index[today]) {
        const dates = Object.keys(index).sort();
        if (dates.length>0) targetDate = dates[dates.length-1];
    }
    currentDate = targetDate;
    await loadAndRender(targetDate);

    const now = getBeijingDate();
    document.getElementById('liveStatus').textContent = '更新于 '+String(now.getHours()).padStart(2,'0')+':'+String(now.getMinutes()).padStart(2,'0');

    document.addEventListener('click', function(e) {
        const card = e.target.closest('.news-card, .featured-card');
        if (card && !e.target.closest('.card-actions')) {
            openDetailFromCard(card);
        }
    });

    document.getElementById('hideReadToggle').addEventListener('change', toggleHideRead);
    document.getElementById('updateBtn').addEventListener('click', updateData);
    document.getElementById('modalCloseBtn').addEventListener('click', closeModal);
    document.getElementById('detailModal').addEventListener('click', (e) => { if(e.target===e.currentTarget) closeModal(); });
    document.getElementById('modalSourceBtn').addEventListener('click', openSource);
    document.getElementById('modalCopyBtn').addEventListener('click', copyLink);
    document.getElementById('modalReadToggleBtn').addEventListener('click', toggleReadStatus);

    document.addEventListener('keydown', (e) => {
        if (e.target.tagName==='INPUT') return;
        if (e.key==='Escape') closeModal();
        if (e.key==='r' || e.key==='R') updateData();
        if (e.key==='h' || e.key==='H') { const cb=document.getElementById('hideReadToggle'); cb.checked=!cb.checked; toggleHideRead(); }
    });

    setInterval(() => {
        const now = getBeijingDate();
        document.getElementById('liveStatus').textContent = '更新于 '+String(now.getHours()).padStart(2,'0')+':'+String(now.getMinutes()).padStart(2,'0');
    }, 10000);
}

init();
