
// ===== UI 交互（Tab、日期、隐藏已读） =====
import { state, getTodayStr } from './state.js';
import { renderAll, updateReadStatusUI } from './renderer.js';
import { setupObserver } from './scroll.js';
import { loadAndRender } from './actions.js';
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
            document.getElementById('content-ai').style.display = tab==='ai' ? 'block' : 'none';
            document.getElementById('content-hot').style.display = tab==='hot' ? 'block' : 'none';
            renderAll();
            setupObserver();
        });
    });

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

    // 刷新按钮
    document.getElementById('updateBtn').addEventListener('click', async function() {
        if (window.isRefreshing) return;
        window.isRefreshing = true;
        this.classList.add('spinning');
        this.disabled = true;
        try {
            showToast('正在触发爬虫更新...');
            await new Promise(r => setTimeout(r, 2000));
            await loadAndRender(state.currentDate);
            showToast('数据已刷新 (实际需触发Action)');
        } catch(e) {
            showToast('刷新失败');
        } finally {
            this.classList.remove('spinning');
            this.disabled = false;
            window.isRefreshing = false;
        }
    });
}
