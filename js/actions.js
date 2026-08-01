// ===== 数据加载与渲染动作 =====
import { state, getTodayStr, getTodayDisplay, formatDate } from './state.js';
import { loadArticlesByDate, loadIndex } from './api.js';
import { renderAll } from './renderer.js';
import { setupObserver } from './scroll.js';
import { generateStableId } from './utils.js';

export async function loadAndRender(dateStr) {
    let data = await loadArticlesByDate(dateStr);
    data = data.map(article => {
        if (!article.id) article.id = generateStableId(article);
        return article;
    });
    state.articles = data;
    const byDateHot = (a, b) =>
        (b.date || '').localeCompare(a.date || '') ||
        ((b.hot_score || 0) - (a.hot_score || 0)) ||
        ((b.id || 0) - (a.id || 0));
    state.aiAll = state.articles.filter(a => a.category === 'ai').sort(byDateHot);
    state.hotAll = state.articles.filter(a => a.category === 'hot').sort(byDateHot);
    state.aiPage = 0;
    state.hotPage = 0;
    state.hasMoreAI = true;
    state.hasMoreHot = true;
    renderAll();
    setupObserver();
    document.getElementById('todayDate').textContent = dateStr === getTodayStr() ? getTodayDisplay() : formatDate(dateStr);
    document.getElementById('datePicker').value = dateStr;
    const hour = new Date().getHours();
    document.body.className = (hour >= 6 && hour < 18) ? 'morning' : 'evening';

    // 用 index.json 中的真实更新时间展示，而非伪造的实时时钟
    const idx = await loadIndex();
    const meta = idx[dateStr];
    const ls = document.getElementById('liveStatus');
    if (meta && meta.updated) {
        ls.textContent = '更新于 ' + meta.updated.slice(11);
        state.lastUpdated = meta.updated;
    } else {
        ls.textContent = '暂无更新记录';
        state.lastUpdated = null;
    }
}
