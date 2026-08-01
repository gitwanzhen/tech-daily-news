// ===== 数据加载与渲染动作 =====
import { state, getTodayStr, getTodayDisplay, formatDate } from './state.js';
import { loadArticlesByDate, loadIndex } from './api.js';
import { renderAll, renderHotSourceTabs } from './renderer.js';
import { setupObserver } from './scroll.js';
import { generateStableId } from './utils.js';

// 摸鱼指南（热搜）展示顺序：固定顺序，未知来源追加末尾
const HOT_SOURCE_ORDER = ['微博', 'B站', '豆瓣'];

// 将热搜按来源分组：固定顺序 + 组内按热度降序，拍平为带 groupStart 标记的数组
function buildHotGroups(hot) {
    const groups = new Map();
    for (const a of hot) {
        const s = a.source || '其他';
        if (!groups.has(s)) groups.set(s, []);
        groups.get(s).push(a);
    }
    const order = [];
    for (const s of HOT_SOURCE_ORDER) {
        if (groups.has(s)) {
            groups.get(s).sort((x, y) => (y.hot_score || 0) - (x.hot_score || 0));
            order.push(s);
        }
    }
    for (const [s, arr] of groups) {
        if (!HOT_SOURCE_ORDER.includes(s)) {
            arr.sort((x, y) => (y.hot_score || 0) - (x.hot_score || 0));
            order.push(s);
        }
    }
    const ordered = [];
    const counts = {};
    for (const s of order) {
        const arr = groups.get(s);
        counts[s] = arr.length;
        arr.forEach(a => { a.groupStart = true; ordered.push(a); });
    }
    return { ordered, counts, order };
}

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
    const grp = buildHotGroups(state.hotAll);
    state.hotOrdered = grp.ordered;
    state.hotGroupCounts = grp.counts;
    state.hotGroupOrder = grp.order;
    state.hotSourceOrder = state.hotGroupOrder;  // 供来源切换页签使用（含固定顺序+未知来源）
    state.hotGroupRendered = {};
    // 按来源分组（无 groupStart），供来源切换页签独立展示
    const bySource = {};
    for (const a of state.hotAll) {
        const s = a.source || '其他';
        if (!bySource[s]) bySource[s] = [];
        bySource[s].push(a);
    }
    for (const s in bySource) bySource[s].sort((x, y) => (y.hot_score || 0) - (x.hot_score || 0));
    state.hotBySource = bySource;
    state.hotSourceTab = (state.hotSourceOrder && state.hotSourceOrder.length) ? state.hotSourceOrder[0] : 'all';  // 去掉"全部"页签后默认展示第一个来源
    state.aiPage = 0;
    state.hotPage = 0;
    state.hasMoreAI = true;
    state.hasMoreHot = true;
    renderAll();
    renderHotSourceTabs();
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
