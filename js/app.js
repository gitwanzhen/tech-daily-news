// ===== 入口：组装所有模块 =====
import { state, getTodayStr } from './state.js';
import { loadIndex } from './api.js';
import { loadAndRender } from './actions.js';
import { initUI } from './ui.js';
import { initModal } from './modal.js';
import { initScrollControls, setupObserver } from './scroll.js';
import { showToast } from './utils.js';

// 保存已读ID到localStorage
function loadReadIds() {
    try {
        const raw = localStorage.getItem('techdaily_read_ids');
        if (raw) state.readIds = new Set(JSON.parse(raw));
    } catch(_) { state.readIds = new Set(); }
}
window.saveReadIds = function() {
    try {
        localStorage.setItem('techdaily_read_ids', JSON.stringify([...state.readIds]));
    } catch(_) {}
};
loadReadIds();

// 初始化
async function init() {
    const today = getTodayStr();
    const index = await loadIndex();
    let targetDate = today;
    if (!index[today]) {
        const dates = Object.keys(index).sort();
        if (dates.length>0) targetDate = dates[dates.length-1];
    }
    state.currentDate = targetDate;
    await loadAndRender(targetDate);

    // 设置实时状态
    const now = new Date();
    document.getElementById('liveStatus').textContent = '更新于 '+String(now.getHours()).padStart(2,'0')+':'+String(now.getMinutes()).padStart(2,'0');
    setInterval(() => {
        const now = new Date();
        document.getElementById('liveStatus').textContent = '更新于 '+String(now.getHours()).padStart(2,'0')+':'+String(now.getMinutes()).padStart(2,'0');
    }, 10000);

    // 初始化UI
    initUI();
    initModal();
    initScrollControls();  // 确保调用

    // 卡片点击委托（打开模态框）
    document.addEventListener('click', function(e) {
        const card = e.target.closest('.news-card, .featured-card');
        if (card && !e.target.closest('.card-actions')) {
            const encoded = card.dataset.article;
            if (encoded) {
                try {
                    const article = JSON.parse(decodeURIComponent(encoded));
                    import('./modal.js').then(module => module.openModal(article));
                } catch(e) {
                    showToast('数据解析失败');
                }
            }
        }
    });

    // 键盘快捷键
    document.addEventListener('keydown', (e) => {
        if (e.target.tagName==='INPUT') return;
        if (e.key==='Escape') {
            import('./modal.js').then(module => module.closeModal());
        }
        if (e.key==='r' || e.key==='R') {
            document.getElementById('updateBtn').click();
        }
        if (e.key==='h' || e.key==='H') {
            const cb = document.getElementById('hideReadToggle');
            cb.checked = !cb.checked;
            cb.dispatchEvent(new Event('change'));
        }
    });

    // 暴露 saveReadIds 给 modal
    window.saveReadIds = saveReadIds;
}

init();
