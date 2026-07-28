// ===== 滚动控制：返回顶部、滑块、加载更多 =====
import { state } from './state.js';
import { renderAll } from './renderer.js';

let isDragging = false;
let dragStartY = 0;
let dragStartScroll = 0;
let observer = null;

// 挂载全局函数供 onclick 调用
window.scrollToTop = function() {
    window.scrollTo({ top: 0, behavior: 'smooth' });
};

export function initScrollControls() {
    const backBtn = document.getElementById('backToTop');
    if (backBtn) {
        backBtn.removeEventListener('click', window.scrollToTop);
        backBtn.addEventListener('click', window.scrollToTop);
    }

    initSlider();
    window.addEventListener('scroll', function() {
        updateBackToTop();
        updateScrollThumb();
    });

    updateBackToTop();
    setTimeout(updateScrollThumb, 100);
}

function updateBackToTop() {
    const btn = document.getElementById('backToTop');
    if (!btn) return;
    if (window.scrollY > 300) {
        btn.classList.add('visible');
    } else {
        btn.classList.remove('visible');
    }
}

function initSlider() {
    const track = document.getElementById('scrollSliderTrack');
    const thumb = document.getElementById('scrollSliderThumb');
    const container = document.getElementById('scrollSliderContainer');
    if (!track || !thumb || !container) return;

    track.addEventListener('click', function(e) {
        const rect = track.getBoundingClientRect();
        const y = e.clientY - rect.top;
        const pct = y / rect.height;
        const docHeight = document.documentElement.scrollHeight - window.innerHeight;
        window.scrollTo({ top: pct * docHeight, behavior: 'smooth' });
    });

    thumb.addEventListener('mousedown', startDrag);
    thumb.addEventListener('touchstart', startDragTouch, { passive: false });
    document.addEventListener('mousemove', moveDrag);
    document.addEventListener('touchmove', moveDragTouch, { passive: false });
    document.addEventListener('mouseup', endDrag);
    document.addEventListener('touchend', endDrag);
}

function startDrag(e) {
    e.preventDefault();
    isDragging = true;
    dragStartY = e.clientY;
    dragStartScroll = window.scrollY;
    const thumb = document.getElementById('scrollSliderThumb');
    if (thumb) thumb.style.cursor = 'grabbing';
    document.body.style.userSelect = 'none';
}
function startDragTouch(e) {
    e.preventDefault();
    const touch = e.touches[0];
    isDragging = true;
    dragStartY = touch.clientY;
    dragStartScroll = window.scrollY;
    document.body.style.userSelect = 'none';
}
function moveDrag(e) {
    if (!isDragging) return;
    e.preventDefault();
    const deltaY = e.clientY - dragStartY;
    applyDragDelta(deltaY);
}
function moveDragTouch(e) {
    if (!isDragging) return;
    e.preventDefault();
    const touch = e.touches[0];
    const deltaY = touch.clientY - dragStartY;
    applyDragDelta(deltaY);
}
function applyDragDelta(deltaY) {
    const track = document.getElementById('scrollSliderTrack');
    const thumb = document.getElementById('scrollSliderThumb');
    if (!track || !thumb) return;
    const trackHeight = track.offsetHeight;
    const thumbHeight = thumb.offsetHeight;
    const maxDelta = trackHeight - thumbHeight;
    const docHeight = document.documentElement.scrollHeight - window.innerHeight;
    if (docHeight <= 0) return;
    const pct = Math.max(0, Math.min(1, (deltaY / maxDelta) + (dragStartScroll / docHeight)));
    window.scrollTo({ top: pct * docHeight });
}
function endDrag() {
    if (isDragging) {
        isDragging = false;
        document.body.style.userSelect = '';
        const thumb = document.getElementById('scrollSliderThumb');
        if (thumb) thumb.style.cursor = 'grab';
    }
}

function updateScrollThumb() {
    const thumb = document.getElementById('scrollSliderThumb');
    const container = document.getElementById('scrollSliderContainer');
    if (!thumb || !container) return;
    const scrollTop = window.scrollY;
    const docHeight = document.documentElement.scrollHeight - window.innerHeight;
    const track = container.querySelector('.scroll-slider-track');
    if (!track) return;
    const trackHeight = track.offsetHeight;
    const thumbHeight = thumb.offsetHeight || 40;
    const maxTop = trackHeight - thumbHeight;
    if (docHeight <= 0) { thumb.style.top = '0px'; return; }
    const progress = Math.min(scrollTop / docHeight, 1);
    thumb.style.top = (progress * maxTop) + 'px';
    if (docHeight > window.innerHeight * 0.8) {
        container.classList.add('visible');
    } else {
        container.classList.remove('visible');
    }
}

export function setupObserver() {
    if (observer) { observer.disconnect(); observer = null; }
    const container = state.currentTab === 'ai' ? document.getElementById('content-ai') : document.getElementById('content-hot');
    if (!container) return;
    const loadMoreEl = container.querySelector('.loading-more');
    if (!loadMoreEl) return;
    const hasMore = state.currentTab === 'ai' ? state.hasMoreAI : state.hasMoreHot;
    if (!hasMore) return;

    observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting && !state.isLoadingMore && (state.currentTab === 'ai' ? state.hasMoreAI : state.hasMoreHot)) {
                loadMore();
            }
        });
    }, { rootMargin: '0px 0px 200px 0px' });
    observer.observe(loadMoreEl);
}

function loadMore() {
    if (state.isLoadingMore) return;
    if (state.currentTab === 'ai' && !state.hasMoreAI) return;
    if (state.currentTab === 'hot' && !state.hasMoreHot) return;
    state.isLoadingMore = true;
    if (state.currentTab === 'ai') {
        state.aiPage++;
        renderAll();
        setupObserver();
    } else {
        state.hotPage++;
        renderAll();
        setupObserver();
    }
}
