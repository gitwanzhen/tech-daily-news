
// ===== UI 交互（Tab、日期、隐藏已读） =====
import { state, getTodayStr } from './state.js';
import { renderAll, updateReadStatusUI } from './renderer.js';
import { setupObserver } from './scroll.js';
import { loadAndRender } from './actions.js';
import { loadIndex } from './api.js';
import { showToast } from './utils.js';

export function initUI() {
    // Tab 切换
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const tab = this.dataset.tab;
            state.currentTab = tab;
            state.aiPage = 0;
            state.hotPage = 0;
            state.hasMoreAI = true;
            state.hasMoreHot = true;
            document.querySelectorAll('.tab-btn').forEach(b=>b.classList.remove('active'));
            this.classList.add('active');
            const aiEl = document.getElementById('content-ai');
            const hotEl = document.getElementById('content-hot');
            const hotTabs = document.getElementById('hotSourceTabs');
            if (tab === 'ai') {
                aiEl.style.display = 'block';
                hotEl.style.display = 'none';
                if (hotTabs) hotTabs.style.display = 'none';
            } else {
                aiEl.style.display = 'none';
                hotEl.style.display = 'block';
                if (hotTabs) hotTabs.style.display = 'flex';
            }
            renderAll();
            setupObserver();
        });
    });

    // 摸鱼指南：来源切换页签（全部 / 各来源）
    const hotTabsEl = document.getElementById('hotSourceTabs');
    if (hotTabsEl) {
        hotTabsEl.addEventListener('click', function(e) {
            const btn = e.target.closest('.hs-tab');
            if (!btn) return;
            const src = btn.dataset.source;
            if (src === state.hotSourceTab) return;
            state.hotSourceTab = src;
            hotTabsEl.querySelectorAll('.hs-tab').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            state.hotPage = 0;
            state.hasMoreHot = true;
            state.hotGroupRendered = {};
            renderAll();
            setupObserver();
            window.scrollTo({ top: 0, behavior: 'smooth' });
        });
    }

    // 日期选择器
    document.getElementById('datePicker').addEventListener('change', async (e) => {
        const date = e.target.value;
        if (date) {
            state.currentDate = date;
            await loadAndRender(date);
        }
    });

    // 今日按钮
    document.getElementById('todayBtn').addEventListener('click', async function() {
        const today = getTodayStr();
        state.currentDate = today;
        document.getElementById('datePicker').value = today;
        await loadAndRender(today);
        showToast('已回到今日');
    });

    // 隐藏已读
    document.getElementById('hideReadToggle').addEventListener('change', function() {
        const checked = this.checked;
        document.getElementById('content-ai').classList.toggle('hide-read', checked);
        document.getElementById('content-hot').classList.toggle('hide-read', checked);
    });

    // 刷新按钮：对比 index.json 的真实更新时间，有新版才重载数据
    document.getElementById('updateBtn').addEventListener('click', async function() {
        if (window.isRefreshing) return;
        window.isRefreshing = true;
        this.classList.add('spinning');
        this.disabled = true;
        try {
            const idx = await loadIndex();
            const meta = idx[state.currentDate];
            const latest = meta ? meta.updated : null;
            if (state.lastUpdated && latest && state.lastUpdated === latest) {
                showToast('已是最新（' + (latest ? latest.slice(11) : '') + '）');
            } else {
                await loadAndRender(state.currentDate);
                showToast('已刷新数据');
            }
        } catch(e) {
            showToast('刷新失败');
        } finally {
            this.classList.remove('spinning');
            this.disabled = false;
            window.isRefreshing = false;
        }
    });
}
