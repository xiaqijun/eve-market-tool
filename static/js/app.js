/* EVE Market Tool — 前端辅助函数 */

/**
 * 格式化 ISK 金额
 * @param {number|null} isk
 * @returns {string}
 */
function formatISK(isk) {
    if (isk == null || isk === 0) return '—';
    if (isNaN(isk) || !isFinite(isk)) return '—';

    const abs = Math.abs(isk);
    const sign = isk < 0 ? '-' : '';

    // 万亿 (trillion) = 1e12
    if (abs >= 1_000_000_000_000) {
        return sign + (isk / 1_000_000_000_000).toFixed(2) + ' 万亿';
    }
    // 亿 (100 million) = 1e8
    if (abs >= 100_000_000) {
        return sign + (isk / 100_000_000).toFixed(2) + ' 亿';
    }
    // 万 (10 thousand) = 1e4
    if (abs >= 10_000) {
        return sign + (isk / 10_000).toFixed(2) + ' 万';
    }
    return sign + isk.toLocaleString() + ' ISK';
}

window.formatISK = formatISK;

/** Format large volume numbers */
function formatVolume(vol) {
    if (vol == null || vol === 0) return '—';
    if (isNaN(vol)) return '—';
    if (vol >= 1_000_000_000) return (vol / 1_000_000_000).toFixed(1) + 'B';
    if (vol >= 1_000_000) return (vol / 1_000_000).toFixed(1) + 'M';
    if (vol >= 1_000) return (vol / 1_000).toFixed(1) + 'K';
    return vol.toLocaleString();
}
window.formatVolume = formatVolume;

/**
 * 初始化 Chart.js 价格趋势图
 */
function initPriceChart(canvasId, trendData) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;

    if (ctx.chart) { ctx.chart.destroy(); }

    const labels = trendData.data_points.map(p => p.date);
    const averages = trendData.data_points.map(p => p.average_price);
    const highs = trendData.data_points.map(p => p.highest);
    const lows = trendData.data_points.map(p => p.lowest);

    ctx.chart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: '均价',
                    data: averages,
                    borderColor: '#0172ad',
                    backgroundColor: 'rgba(1, 114, 173, 0.1)',
                    tension: 0.3,
                },
                {
                    label: '最高价',
                    data: highs,
                    borderColor: 'rgba(46, 204, 113, 0.5)',
                    borderDash: [5, 5],
                    pointRadius: 0,
                },
                {
                    label: '最低价',
                    data: lows,
                    borderColor: 'rgba(231, 76, 60, 0.5)',
                    borderDash: [5, 5],
                    pointRadius: 0,
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                tooltip: {
                    callbacks: {
                        label: (ctx) => ctx.dataset.label + ': ' + formatISK(ctx.raw),
                    },
                },
            },
            scales: {
                y: {
                    ticks: {
                        callback: (value) => formatISK(value),
                    },
                },
            },
        },
    });
}

window.initPriceChart = initPriceChart;

/**
 * Alpine.js component: item search picker
 * Usage: x-data="itemPicker()"
 * Provides: query, results, open, loading, selectedId, selectedName, search(), select()
 */
document.addEventListener('alpine:init', () => {
    Alpine.data('itemPicker', () => ({
        query: '',
        results: [],
        open: false,
        loading: false,
        selectedId: null,
        selectedName: '',
        search() {
            if (!this.query || this.query.length < 1) {
                this.results = [];
                this.open = false;
                return;
            }
            this.loading = true;
            fetch(`/api/v1/items/search?q=${encodeURIComponent(this.query)}&limit=15`)
                .then(r => r.json())
                .then(data => {
                    this.results = data;
                    this.open = data.length > 0;
                    this.loading = false;
                })
                .catch(() => { this.loading = false; });
        },
        select(item) {
            this.selectedId = item.type_id;
            this.selectedName = item.name;
            this.query = item.name;
            this.open = false;
            this.results = [];
        },
    }));
});

/**
 * Alpine.js component: station trading tracker
 */
document.addEventListener('alpine:init', () => {
    Alpine.data('tradingApp', () => ({
        // Item picker
        itemQuery: '',
        itemResults: [],
        itemOpen: false,
        itemLoading: false,
        selectedId: null,
        selectedName: '',
        // Form
        form: { region_id: 10000002, buy_price: 0, sell_price: 0, quantity: 1, notes: '' },
        // State
        trades: [],
        summary: {},
        error: '',
        success: '',

        get canCreate() {
            return this.selectedId && this.form.buy_price > 0 && this.form.sell_price > 0 && this.form.quantity > 0;
        },

        // Item search
        searchItem() {
            if (!this.itemQuery || this.itemQuery.length < 1) {
                this.itemResults = []; this.itemOpen = false; return;
            }
            this.itemLoading = true;
            fetch('/api/v1/items/search?q=' + encodeURIComponent(this.itemQuery) + '&limit=10')
                .then(r => r.json())
                .then(data => { this.itemResults = data; this.itemOpen = data.length > 0; this.itemLoading = false; })
                .catch(() => { this.itemLoading = false; });
        },
        selectItem(item) {
            this.selectedId = item.type_id;
            this.selectedName = item.name;
            this.itemQuery = item.name;
            this.itemOpen = false;
            this.itemResults = [];
        },

        // Set station from region
        setStation() {
            const stations = { 10000002: 60003760, 10000043: 60008494, 10000032: 60011866, 10000030: 60004588, 10000042: 60005686 };
            this.form.station_id = stations[this.form.region_id] || null;
        },

        // Create trade
        createTrade() {
            if (!this.canCreate) return;
            this.error = ''; this.success = '';
            this.setStation();
            fetch('/api/v1/trading/trades', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    type_id: this.selectedId,
                    region_id: parseInt(this.form.region_id),
                    station_id: this.form.station_id,
                    buy_price: parseFloat(this.form.buy_price),
                    sell_price: parseFloat(this.form.sell_price),
                    quantity: parseInt(this.form.quantity),
                    notes: this.form.notes || null,
                }),
            })
            .then(r => { if (!r.ok) return r.json().then(e => { throw new Error(e.detail || 'Failed'); }); return r.json(); })
            .then(() => {
                this.success = '交易已创建！';
                this.selectedId = null; this.selectedName = ''; this.itemQuery = '';
                this.form.buy_price = 0; this.form.sell_price = 0; this.form.quantity = 1;
                this.form.notes = '';
                this.loadTrades(); this.loadSummary();
            })
            .catch(e => { this.error = e.message; });
        },

        // Load trades
        loadTrades() {
            fetch('/api/v1/trading/trades?limit=50')
                .then(r => r.json()).then(data => { this.trades = data; })
                .catch(() => {});
        },

        // Load summary
        loadSummary() {
            fetch('/api/v1/trading/summary')
                .then(r => r.json()).then(data => { this.summary = data; })
                .catch(() => {});
        },

        // Complete trade
        completeTrade(id) {
            fetch('/api/v1/trading/trades/' + id, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ status: 'completed' }),
            }).then(() => { this.loadTrades(); this.loadSummary(); });
        },

        // Cancel trade
        cancelTrade(id) {
            fetch('/api/v1/trading/trades/' + id, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ status: 'cancelled' }),
            }).then(() => { this.loadTrades(); this.loadSummary(); });
        },

        // Status helpers
        statusLabel(s) { return { active: '进行中', completed: '已完成', cancelled: '已取消', scouting: '侦察中' }[s] || s; },
        statusColor(s) { return { active: 'var(--cyan)', completed: 'var(--profit)', cancelled: 'var(--loss)', scouting: 'var(--warn)' }[s] || 'var(--text-dim)'; },
    }));
});

/**
 * Alpine.js component: price alerts manager
 */
document.addEventListener('alpine:init', () => {
    Alpine.data('alertsApp', () => ({
        itemQuery: '', itemResults: [], itemOpen: false, selectedId: null, selectedName: '',
        form: { region_id: 10000002, condition: 'below', threshold: 0 },
        alerts: [], error: '',

        get canCreate() { return this.selectedId && this.form.threshold > 0; },

        searchItem() {
            if (!this.itemQuery || this.itemQuery.length < 1) { this.itemResults = []; this.itemOpen = false; return; }
            fetch('/api/v1/items/search?q=' + encodeURIComponent(this.itemQuery) + '&limit=10')
                .then(r => r.json()).then(data => { this.itemResults = data; this.itemOpen = data.length > 0; });
        },
        selectItem(item) {
            this.selectedId = item.type_id; this.selectedName = item.name;
            this.itemQuery = item.name; this.itemOpen = false; this.itemResults = [];
        },

        loadAlerts() {
            fetch('/api/v1/alerts/').then(r => r.json()).then(data => {
                this.alerts = data;
                this.alerts.forEach(a => this.fetchCurrentPrice(a));
            });
        },

        fetchCurrentPrice(a) {
            fetch('/api/v1/arbitrage/items/' + a.type_id + '/comparison')
                .then(r => r.json())
                .then(data => {
                    const match = data.find(d => d.region_id === a.region_id);
                    if (match && match.min_sell_price) {
                        a.current_price = match.min_sell_price;
                    }
                }).catch(() => {});
        },

        createAlert() {
            if (!this.canCreate) return;
            this.error = '';
            fetch('/api/v1/alerts/', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    type_id: this.selectedId, region_id: parseInt(this.form.region_id),
                    condition: this.form.condition, threshold: parseFloat(this.form.threshold),
                    is_active: true,
                }),
            }).then(r => { if (!r.ok) throw new Error('Failed'); return r.json(); })
              .then(() => {
                  this.selectedId = null; this.selectedName = ''; this.itemQuery = '';
                  this.form.threshold = 0; this.loadAlerts();
              }).catch(e => { this.error = e.message; });
        },

        toggleAlert(a) {
            fetch('/api/v1/alerts/' + a.id, {
                method: 'PUT', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ is_active: !a.is_active }),
            }).then(() => this.loadAlerts());
        },

        deleteAlert(id) {
            fetch('/api/v1/alerts/' + id, { method: 'DELETE' })
                .then(() => this.loadAlerts());
        },

        regionName(id) {
            const m = { 10000002: 'Jita', 10000043: 'Amarr', 10000032: 'Dodixie', 10000030: 'Rens', 10000042: 'Hek' };
            return m[id] || '#' + id;
        },
    }));
});

// Wait for DOM before attaching event listeners
document.addEventListener('DOMContentLoaded', () => {
    document.body.addEventListener('htmx:afterSwap', (evt) => {
        const target = evt.detail.target;
        const chartEl = target.querySelector('[data-trend]');
        if (chartEl) {
            const trendData = JSON.parse(chartEl.getAttribute('data-trend'));
            initPriceChart(chartEl.id, trendData);
        }
    });
});
