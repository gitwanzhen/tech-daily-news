// ===== 工具函数 =====
export function escapeHtml(text) {
    if (!text) return '';
    const d = document.createElement('div');
    d.textContent = text;
    return d.innerHTML;
}

export function estimateReadTime(text) {
    if (!text) return 1;
    const words = text.replace(/\s/g,'').length;
    return Math.max(1, Math.round(words/120));
}

export function generateStableId(article) {
    const key = (article.title || '') + (article.source || '');
    let hash = 0;
    for (let i = 0; i < key.length; i++) {
        hash = (hash << 5) - hash + key.charCodeAt(i);
        hash |= 0;
    }
    return Math.abs(hash);
}

export function showToast(msg) {
    const t = document.getElementById('toast');
    t.textContent = msg;
    t.classList.add('show');
    clearTimeout(t._timer);
    t._timer = setTimeout(()=>t.classList.remove('show'), 2200);
}
