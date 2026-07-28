// ===== 数据加载 =====
const DATA_DIR = 'data/';

export async function loadArticlesByDate(dateStr) {
    try {
        const resp = await fetch(`${DATA_DIR}${dateStr}.json`);
        if (!resp.ok) {
            if (resp.status===404) return [];
            throw new Error('HTTP '+resp.status);
        }
        return await resp.json();
    } catch(e) {
        console.error(e);
        return [];
    }
}

export async function loadIndex() {
    try {
        const resp = await fetch(`${DATA_DIR}index.json`);
        if (!resp.ok) return {};
        return await resp.json();
    } catch(_) {
        return {};
    }
}
