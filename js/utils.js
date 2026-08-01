// ===== 工具函数 =====
// 来源元信息：图标 + 强调色（用于摸鱼指南按来源分组展示）
export const SOURCE_META = {
    '微博': { icon: '🔥', color: '#ff8200' },
    'B站': { icon: '📺', color: '#fb7299' },
    '豆瓣': { icon: '📚', color: '#2e963f' },
    '其他': { icon: '📌', color: 'var(--color-ai)' },
};

export function escapeHtml(text) {
    if (text === null || text === undefined) return '';
    return String(text)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

// 净化外部 HTML，去除脚本/事件处理器/危险协议，防止 XSS
export function sanitizeHtml(html) {
    if (!html) return '';
    const doc = new DOMParser().parseFromString(html, 'text/html');
    const FORBIDDEN = new Set(['SCRIPT', 'STYLE', 'IFRAME', 'OBJECT', 'EMBED', 'LINK', 'META', 'FORM', 'INPUT', 'BUTTON', 'BASE']);
    const walk = (node) => {
        const children = Array.from(node.childNodes);
        for (const child of children) {
            if (child.nodeType !== 1) continue; // 仅处理元素节点
            const tag = child.tagName;
            if (FORBIDDEN.has(tag)) { child.remove(); continue; }
            for (const attr of Array.from(child.attributes)) {
                const name = attr.name.toLowerCase();
                const val = String(attr.value).trim().toLowerCase();
                if (name.startsWith('on')) {
                    child.removeAttribute(attr.name);
                } else if ((name === 'href' || name === 'src') && (val.startsWith('javascript:') || val.startsWith('data:text/html'))) {
                    child.removeAttribute(attr.name);
                }
            }
            walk(child);
        }
    };
    walk(doc.body);
    return doc.body.innerHTML;
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
