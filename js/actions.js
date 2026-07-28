// ===== 数据加载与渲染动作 =====
import { state, getTodayStr, getTodayDisplay, formatDate } from './state.js';
import { loadArticlesByDate } from './api.js';
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
    state.aiAll = state.articles.filter(a => a.category === 'ai').sort((a,b) => b.id - a.id);
    state.hotAll = state.articles.filter(a => a.category === 'hot').sort((a,b) => b.id - a.id);
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
}
