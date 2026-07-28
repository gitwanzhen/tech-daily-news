// ===== 模态框逻辑 =====
import { state, formatDate } from './state.js';
import { escapeHtml, estimateReadTime, showToast } from './utils.js';
import { renderAll, updateReadStatusUI } from './renderer.js';

let currentArticle = null;

export function initModal() {
    const modal = document.getElementById('detailModal');
    const closeBtn = document.getElementById('modalCloseBtn');
    const copyBtn = document.getElementById('modalCopyBtn');
    const sourceBtn = document.getElementById('modalSourceBtn');
    const readToggleBtn = document.getElementById('modalReadToggleBtn');

    closeBtn.addEventListener('click', closeModal);
    modal.addEventListener('click', (e) => { if(e.target===e.currentTarget) closeModal(); });
    document.addEventListener('keydown', (e) => { if(e.key==='Escape') closeModal(); });

    copyBtn.addEventListener('click', copyLink);
    sourceBtn.addEventListener('click', openSource);
    readToggleBtn.addEventListener('click', toggleReadStatus);
}

export function openModal(article) {
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
    // 标记已读
    if (article.id) {
        state.readIds.add(article.id);
        if (window.saveReadIds) window.saveReadIds();
        updateReadStatusUI();
    }
}

export function closeModal() {
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

function toggleReadStatus() {
    if (currentArticle) {
        const id = currentArticle.id;
        if (state.readIds.has(id)) state.readIds.delete(id);
        else state.readIds.add(id);
        if (window.saveReadIds) window.saveReadIds();
        updateReadStatusUI();
        renderAll();
        showToast(state.readIds.has(id)?'已标记已读':'取消已读');
    }
}
