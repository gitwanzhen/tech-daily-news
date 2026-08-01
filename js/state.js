// ===== 状态管理 =====
export const state = {
    articles: [],
    aiAll: [],
    hotAll: [],
    aiPage: 0,
    hotPage: 0,
    currentTab: 'ai',
    currentDate: getTodayStr(),
    readIds: new Set(),
    hasMoreAI: true,
    hasMoreHot: true,
    isLoadingMore: false,
    lastUpdated: null,
    observer: null,
};

export function getTodayStr() {
    const d = getBeijingDate();
    return d.getFullYear() + '-' + String(d.getMonth()+1).padStart(2,'0') + '-' + String(d.getDate()).padStart(2,'0');
}
function getBeijingDate() {
    const now = new Date();
    const utc = now.getTime() + now.getTimezoneOffset() * 60000;
    return new Date(utc + 3600000 * 8);
}

export function getTodayDisplay() {
    const d = getBeijingDate();
    const weekdays = ['日','一','二','三','四','五','六'];
    return `今天 ${d.getMonth()+1}月${d.getDate()}日 星期${weekdays[d.getDay()]}`;
}

export function formatDate(dateStr) {
    if (!dateStr) return '日期未知';
    const today = getTodayStr();
    const y = getBeijingDate();
    const yest = new Date(y.getTime()-86400000);
    const yestStr = yest.getFullYear()+'-'+String(yest.getMonth()+1).padStart(2,'0')+'-'+String(yest.getDate()).padStart(2,'0');
    if (dateStr === today) return '今天';
    if (dateStr === yestStr) return '昨天';
    return dateStr;
}
