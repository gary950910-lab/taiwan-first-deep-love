// Frontend Application State
const state = {
    currentSection: 'screening-section',
    industryChart: null,
    equityChart: null,
    tvCharts: {
        price: null,
        volume: null,
        kd: null,
        macd: null,
        series: {} // Stores references to active chart series
    }
};

// API Base URL
const API_BASE = window.location.origin;

// Document Ready
document.addEventListener('DOMContentLoaded', () => {
    initNavigation();
    initAccordions();
    initScreening();
    initHistory();
    initBacktesting();
    initChartSearch();
    initSync();
    
    // Check if url contains specific hash/query or default load
    loadHistorySessions();
    loadBacktestSessions();
});

// Toast Notifications Helper
function showToast(message, type = 'success') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    
    let icon = 'fa-circle-check';
    if (type === 'error') icon = 'fa-circle-exclamation';
    else if (type === 'warning') icon = 'fa-triangle-exclamation';
    
    toast.innerHTML = `
        <i class="fa-solid ${icon}"></i>
        <span>${message}</span>
    `;
    
    container.appendChild(toast);
    
    // Fade out and remove
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100%)';
        toast.style.transition = 'all 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

// 1. Sidebar Navigation
function initNavigation() {
    const navItems = document.querySelectorAll('.nav-item');
    const sections = document.querySelectorAll('.content-section');
    const sectionTitle = document.getElementById('current-section-title');
    const sectionSubtitle = document.getElementById('current-section-subtitle');
    
    const titles = {
        'screening-section': { t: '即時選股篩選', s: '客觀數據驅動，快速篩選台股強勢標的' },
        'history-section': { t: '篩選歷史紀錄', s: '管理與檢視過去儲存的選股結果' },
        'backtest-section': { t: '策略回測分析', s: '驗證選股策略的勝率、盈虧比與最大回撤' },
        'chart-section': { t: '個股技術分析', s: '互動式技術指針 K 線圖，視覺化個股走勢' },
        'sync-section': { t: '數據同步設定', s: '同步證交所與櫃買中心最新的股票名冊' }
    };
    
    navItems.forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const target = item.getAttribute('data-target');
            
            // Toggle Active Nav
            navItems.forEach(i => i.classList.remove('active'));
            item.classList.add('active');
            
            // Toggle Active Section
            sections.forEach(sec => sec.classList.remove('active'));
            const activeSec = document.getElementById(target);
            if (activeSec) activeSec.classList.add('active');
            
            // Update Header
            if (titles[target]) {
                sectionTitle.textContent = titles[target].t;
                sectionSubtitle.textContent = titles[target].s;
            }
            
            state.currentSection = target;
            
            // Trigger specific loads
            if (target === 'history-section') {
                loadHistorySessions();
            } else if (target === 'backtest-section') {
                loadBacktestSessions();
            } else if (target === 'chart-section') {
                // If chart is empty, load 2330 by default
                if (!state.tvCharts.price) {
                    loadStockKline("2330");
                } else {
                    resizeCharts();
                }
            }
        });
    });
    
    // Quick Sync Header Button
    document.getElementById('quick-sync-btn').addEventListener('click', () => {
        document.querySelector('[data-target="sync-section"]').click();
    });
}

// 2. Accordions in Screening Form
function initAccordions() {
    const headers = document.querySelectorAll('.accordion-header');
    
    headers.forEach(header => {
        // Open by default for first one
        if (header.parentElement.classList.contains('filter-card') && header === headers[0]) {
            header.parentElement.classList.add('open');
        }
        
        header.addEventListener('click', () => {
            const item = header.parentElement;
            item.classList.toggle('open');
        });
    });
    
    // Toggle Consolidation Input based on checkbox
    const consChk = document.getElementById('ma-consolidation-chk');
    const consGroup = document.getElementById('ma-consolidation-val-group');
    consChk.addEventListener('change', () => {
        consGroup.style.display = consChk.checked ? 'block' : 'none';
    });
}

// 3. Technical Screening Logic
function initScreening() {
    const form = document.getElementById('screening-form');
    const tableBody = document.querySelector('#screen-results-table tbody');
    const totalBadge = document.getElementById('screen-total-badge');
    const searchInput = document.getElementById('filter-results-table');
    
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        // Show loading state
        const submitBtn = document.getElementById('run-screening-btn');
        const origBtnText = submitBtn.innerHTML;
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> 正在下載並篩選股票...';
        
        // Compile filter object
        const filters = {
            ma60_bias_min: getNumericValue('ma60-bias-min'),
            ma60_bias_max: getNumericValue('ma60-bias-max'),
            bb_break_upper: document.getElementById('bb-break-upper-chk').checked,
            bb_within: document.getElementById('bb-within-chk').checked,
            kd_k_min: getNumericValue('kd-k-min'),
            kd_k_max: getNumericValue('kd-k-max'),
            kd_d_min: getNumericValue('kd-d-min'),
            kd_d_max: getNumericValue('kd-d-max'),
            kd_cross_up: document.getElementById('kd-cross-up-chk').checked,
            kd_cross_down: document.getElementById('kd-cross-down-chk').checked,
            macd_cross_up: document.getElementById('macd-cross-up-chk').checked,
            macd_cross_down: document.getElementById('macd-cross-down-chk').checked,
            macd_osc_positive: document.getElementById('macd-osc-pos-chk').checked,
            macd_osc_negative: document.getElementById('macd-osc-neg-chk').checked,
            is_20d_high: document.getElementById('is-20d-high-chk').checked,
            volume_mult_min: getNumericValue('volume-mult-min'),
            ma_consolidation: document.getElementById('ma-consolidation-chk').checked,
            ma_consolidation_threshold: getNumericValue('ma-consolidation-val') || 3.0
        };
        
        const payload = {
            scope: document.getElementById('scope-select').value,
            filters: filters,
            save_session: document.getElementById('save-session-chk').checked
        };
        
        try {
            const response = await fetch(`${API_BASE}/api/screen`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            
            if (!response.ok) {
                const errData = await response.json();
                throw new Error(errData.detail || 'Screening failed');
            }
            
            const data = await response.json();
            showToast(`篩選完成！共找到 ${data.matched_count} 檔符合個股。`);
            
            // Populate Results
            renderScreenResults(data.results);
            totalBadge.textContent = `${data.matched_count} 檔符合`;
            
            // Generate Industry Chart
            renderIndustryChart(data.results);
            
            // Refresh other sections
            loadHistorySessions();
            loadBacktestSessions();
            
        } catch (err) {
            console.error(err);
            showToast(err.message, 'error');
            tableBody.innerHTML = `<tr><td colspan="9" class="text-center text-rose"><i class="fa-solid fa-triangle-exclamation"></i> 篩選出錯: ${err.message}</td></tr>`;
        } finally {
            submitBtn.disabled = false;
            submitBtn.innerHTML = origBtnText;
        }
    });
    
    // Quick search in table results
    searchInput.addEventListener('input', () => {
        const text = searchInput.value.trim().toLowerCase();
        const rows = tableBody.querySelectorAll('tr');
        rows.forEach(row => {
            if (row.cells.length < 2) return; // skip no data rows
            const sym = row.cells[0].textContent.toLowerCase();
            const name = row.cells[1].textContent.toLowerCase();
            const ind = row.cells[3].textContent.toLowerCase();
            if (sym.includes(text) || name.includes(text) || ind.includes(text)) {
                row.style.display = '';
            } else {
                row.style.display = 'none';
            }
        });
    });
}

function getNumericValue(id) {
    const val = document.getElementById(id).value;
    return val === '' ? null : parseFloat(val);
}

function renderScreenResults(results) {
    const tableBody = document.querySelector('#screen-results-table tbody');
    tableBody.innerHTML = '';
    
    if (results.length === 0) {
        tableBody.innerHTML = '<tr><td colspan="9" class="text-center text-muted">無符合條件的股票，請調整條件重新篩選。</td></tr>';
        return;
    }
    
    results.forEach(res => {
        const ind = res.indicators || {};
        const k = ind.k ? parseFloat(ind.k).toFixed(1) : '-';
        const d = ind.d ? parseFloat(ind.d).toFixed(1) : '-';
        const osc = ind.macd_osc ? parseFloat(ind.macd_osc).toFixed(2) : '-';
        const bias = ind.ma60_bias ? parseFloat(ind.ma60_bias).toFixed(1) : '-';
        
        // Highlight MA Bias
        const biasClass = ind.ma60_bias > 0 ? 'text-rose' : (ind.ma60_bias < 0 ? 'text-green' : '');
        const oscClass = ind.macd_osc > 0 ? 'text-rose' : (ind.macd_osc < 0 ? 'text-green' : '');
        
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td><strong>${res.symbol}</strong></td>
            <td>${res.name}</td>
            <td><span class="badge ${res.market === 'Listed' ? 'badge-primary' : 'badge-secondary'}">${res.market === 'Listed' ? '上市' : '上櫃'}</span></td>
            <td>${res.industry}</td>
            <td><strong>${res.close_price ? res.close_price.toFixed(1) : '-'}</strong></td>
            <td class="${biasClass}">${bias}%</td>
            <td>K:${k} / D:${d}</td>
            <td class="${oscClass}">${osc}</td>
            <td>
                <div class="flex gap-2">
                    <button class="btn btn-secondary btn-sm analyze-btn" data-symbol="${res.symbol}">
                        <i class="fa-solid fa-chart-candlestick"></i> 技術分析
                    </button>
                </div>
            </td>
        `;
        tableBody.appendChild(tr);
    });
    
    // Add technical chart click events
    tableBody.querySelectorAll('.analyze-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const sym = btn.getAttribute('data-symbol');
            navigateToChart(sym);
        });
    });
}

// 4. Industry Distribution Visualization
function renderIndustryChart(results) {
    const canvas = document.getElementById('industryChart');
    const placeholder = document.getElementById('no-industry-data');
    
    if (results.length === 0) {
        placeholder.style.display = 'flex';
        canvas.style.display = 'none';
        if (state.industryChart) state.industryChart.destroy();
        return;
    }
    
    placeholder.style.display = 'none';
    canvas.style.display = 'block';
    
    // Group and count
    const groups = {};
    results.forEach(res => {
        const ind = res.industry || '其他';
        groups[ind] = (groups[ind] || 0) + 1;
    });
    
    // Sort descending
    const sorted = Object.entries(groups).sort((a, b) => b[1] - a[1]);
    const labels = sorted.map(item => item[0]);
    const counts = sorted.map(item => item[1]);
    
    if (state.industryChart) {
        state.industryChart.destroy();
    }
    
    const ctx = canvas.getContext('2d');
    state.industryChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: '股票檔數',
                data: counts,
                backgroundColor: 'rgba(6, 182, 212, 0.6)',
                borderColor: 'rgba(6, 182, 212, 1)',
                borderWidth: 1,
                borderRadius: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: '#1E293B',
                    titleColor: '#F3F4F6',
                    bodyColor: '#F3F4F6'
                }
            },
            scales: {
                y: {
                    grid: { color: '#253046' },
                    ticks: { color: '#9CA3AF', stepSize: 1 }
                },
                x: {
                    grid: { display: false },
                    ticks: { color: '#9CA3AF' }
                }
            }
        }
    });
}

// 5. History Sessions Management
async function loadHistorySessions() {
    const tableBody = document.querySelector('#history-sessions-table tbody');
    try {
        const response = await fetch(`${API_BASE}/api/sessions`);
        if (!response.ok) throw new Error('Failed to load sessions');
        
        const sessions = await response.json();
        tableBody.innerHTML = '';
        
        if (sessions.length === 0) {
            tableBody.innerHTML = '<tr><td colspan="6" class="text-center text-muted">暫無任何篩選紀錄，請前往即時篩選。</td></tr>';
            return;
        }
        
        sessions.forEach(sess => {
            const dt = new Date(sess.timestamp).toLocaleString('zh-TW');
            
            // Format filters description
            const filtersDesc = Object.entries(sess.filters)
                .map(([k, v]) => {
                    if (v === true) return k.replace('_chk', '');
                    if (typeof v === 'number') return `${k}:${v}`;
                    return null;
                })
                .filter(Boolean)
                .join(', ') || '無限制';
                
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>#${sess.id}</td>
                <td><strong>${dt}</strong></td>
                <td><span class="badge badge-primary">${sess.scope}</span></td>
                <td><span class="text-muted text-xs">${filtersDesc}</span></td>
                <td><strong>${sess.matched_count}</strong></td>
                <td>
                    <div class="flex gap-2">
                        <button class="btn btn-secondary btn-sm view-session-btn" data-id="${sess.id}">
                            <i class="fa-solid fa-eye"></i> 檢視
                        </button>
                        <button class="btn btn-secondary btn-sm backtest-session-btn" data-id="${sess.id}">
                            <i class="fa-solid fa-rotate-left text-accent"></i> 回測
                        </button>
                        <button class="btn btn-danger btn-sm delete-session-btn" data-id="${sess.id}">
                            <i class="fa-solid fa-trash-can"></i> 刪除
                        </button>
                    </div>
                </td>
            `;
            tableBody.appendChild(tr);
        });
        
        // Add events
        tableBody.querySelectorAll('.view-session-btn').forEach(btn => {
            btn.addEventListener('click', () => loadSessionDetails(btn.getAttribute('data-id')));
        });
        
        tableBody.querySelectorAll('.backtest-session-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const id = btn.getAttribute('data-id');
                navigateToBacktest(id);
            });
        });
        
        tableBody.querySelectorAll('.delete-session-btn').forEach(btn => {
            btn.addEventListener('click', () => deleteSession(btn.getAttribute('data-id')));
        });
        
    } catch (err) {
        console.error(err);
        tableBody.innerHTML = `<tr><td colspan="6" class="text-center text-rose">載入失敗: ${err.message}</td></tr>`;
    }
}

async function loadSessionDetails(sessionId) {
    const panel = document.getElementById('session-details-panel');
    const tableBody = document.querySelector('#session-detail-stocks-table tbody');
    
    try {
        const response = await fetch(`${API_BASE}/api/sessions/${sessionId}`);
        if (!response.ok) throw new Error('Failed to load session details');
        
        const sess = await response.json();
        
        panel.style.display = 'block';
        document.getElementById('detail-timestamp').textContent = new Date(sess.timestamp).toLocaleString('zh-TW');
        document.getElementById('detail-scope').textContent = sess.scope;
        
        // Render filter badges
        const badgesContainer = document.getElementById('detail-filters-list');
        badgesContainer.innerHTML = '';
        
        Object.entries(sess.filters).forEach(([k, v]) => {
            const badge = document.createElement('span');
            badge.className = 'filter-badge';
            badge.innerHTML = `<i class="fa-solid fa-tag"></i> ${k}: ${v}`;
            badgesContainer.appendChild(badge);
        });
        
        // Populate detail stocks table
        tableBody.innerHTML = '';
        if (sess.results.length === 0) {
            tableBody.innerHTML = '<tr><td colspan="8" class="text-center text-muted">本紀錄無任何符合個股。</td></tr>';
        } else {
            sess.results.forEach(res => {
                const ind = res.indicators || {};
                const k = ind.k ? parseFloat(ind.k).toFixed(1) : '-';
                const d = ind.d ? parseFloat(ind.d).toFixed(1) : '-';
                const osc = ind.macd_osc ? parseFloat(ind.macd_osc).toFixed(2) : '-';
                const bias = ind.ma60_bias ? parseFloat(ind.ma60_bias).toFixed(1) : '-';
                
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td><strong>${res.symbol}</strong></td>
                    <td>${res.name}</td>
                    <td>${res.industry}</td>
                    <td><strong>${res.close_price ? res.close_price.toFixed(1) : '-'}</strong></td>
                    <td>${bias}%</td>
                    <td>K:${k} / D:${d}</td>
                    <td>${osc}</td>
                    <td>
                        <button class="btn btn-secondary btn-sm analyze-btn" data-symbol="${res.symbol}">
                            <i class="fa-solid fa-chart-candlestick"></i> 技術分析
                        </button>
                    </td>
                `;
                tableBody.appendChild(tr);
            });
            
            // Add kline triggers
            tableBody.querySelectorAll('.analyze-btn').forEach(btn => {
                btn.addEventListener('click', () => {
                    navigateToChart(btn.getAttribute('data-symbol'));
                });
            });
        }
        
        // Link the Backtest button inside panel
        const backtestBtn = document.getElementById('detail-run-backtest-btn');
        // Recreate event listener to avoid duplicates
        const newBacktestBtn = backtestBtn.cloneNode(true);
        backtestBtn.parentNode.replaceChild(newBacktestBtn, backtestBtn);
        newBacktestBtn.addEventListener('click', () => {
            navigateToBacktest(sessionId);
        });
        
        // Scroll to details
        panel.scrollIntoView({ behavior: 'smooth' });
        
    } catch (err) {
        showToast(err.message, 'error');
    }
}

// Close Session details panel
document.getElementById('close-detail-btn').addEventListener('click', () => {
    document.getElementById('session-details-panel').style.display = 'none';
});

async function deleteSession(id) {
    if (!confirm(`確定要刪除篩選紀錄 #${id} 嗎？`)) return;
    
    try {
        const response = await fetch(`${API_BASE}/api/sessions/${id}`, { method: 'DELETE' });
        if (!response.ok) throw new Error('Delete failed');
        
        showToast(`篩選紀錄 #${id} 刪除成功。`);
        
        // If the details panel is currently displaying the deleted session, hide it
        const panel = document.getElementById('session-details-panel');
        if (panel.style.display !== 'none') {
            panel.style.display = 'none';
        }
        
        loadHistorySessions();
        loadBacktestSessions();
    } catch (err) {
        showToast(err.message, 'error');
    }
}

// 6. Strategy Backtesting
function initBacktesting() {
    const form = document.getElementById('backtest-form');
    
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const sessionId = document.getElementById('backtest-session-select').value;
        if (!sessionId) {
            showToast('請選擇要回測的篩選紀錄！', 'warning');
            return;
        }
        
        // Show loading state
        const submitBtn = document.getElementById('run-backtest-btn');
        const origText = submitBtn.innerHTML;
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> 回測模擬計算中...';
        
        const payload = {
            session_id: parseInt(sessionId),
            stop_loss_pct: parseFloat(document.getElementById('stop-loss-input').value),
            take_profit_pct: parseFloat(document.getElementById('take-profit-input').value),
            max_holding_days: parseInt(document.getElementById('holding-days-input').value)
        };
        
        try {
            const response = await fetch(`${API_BASE}/api/backtest`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            
            if (!response.ok) {
                const errData = await response.json();
                throw new Error(errData.detail || 'Backtest failed');
            }
            
            const data = await response.json();
            showToast(`回測計算完成！勝率 ${data.win_rate}%.`);
            
            // Populate Metrics
            document.getElementById('bt-winrate').textContent = `${data.win_rate}%`;
            document.getElementById('bt-pl-ratio').textContent = data.profit_loss_ratio.toFixed(2);
            document.getElementById('bt-avg-return').textContent = `${data.avg_return > 0 ? '+' : ''}${data.avg_return.toFixed(2)}%`;
            document.getElementById('bt-mdd').textContent = `${data.strategy_mdd.toFixed(2)}%`;
            
            // Metrics color
            toggleTextColors(document.getElementById('bt-avg-return'), data.avg_return);
            toggleTextColors(document.getElementById('bt-winrate'), data.win_rate - 50.0);
            
            // Equity curve chart
            renderEquityChart(data.equity_curve);
            
            // Populate trades table
            renderBacktestTrades(data.trades);
            
        } catch (err) {
            console.error(err);
            showToast(err.message, 'error');
        } finally {
            submitBtn.disabled = false;
            submitBtn.innerHTML = origText;
        }
    });
}

function toggleTextColors(element, value) {
    element.classList.remove('text-rose', 'text-green');
    if (value > 0) element.classList.add('text-rose');
    else if (value < 0) element.classList.add('text-green');
}

async function loadBacktestSessions() {
    const select = document.getElementById('backtest-session-select');
    try {
        const response = await fetch(`${API_BASE}/api/sessions`);
        if (!response.ok) return;
        const sessions = await response.json();
        
        // Save current selection value
        const currentVal = select.value;
        
        select.innerHTML = '<option value="">請選擇一個篩選紀錄...</option>';
        sessions.forEach(sess => {
            const dt = new Date(sess.timestamp).toLocaleString('zh-TW');
            const opt = document.createElement('option');
            opt.value = sess.id;
            opt.textContent = `紀錄 #${sess.id} - ${dt} (${sess.scope}, ${sess.matched_count}檔)`;
            select.appendChild(opt);
        });
        
        // Restore if still exists
        if (currentVal && Array.from(select.options).some(o => o.value === currentVal)) {
            select.value = currentVal;
        }
    } catch (e) {
        console.error("Error loading backtest sessions", e);
    }
}

function renderBacktestTrades(trades) {
    const tableBody = document.querySelector('#backtest-trades-table tbody');
    document.getElementById('bt-trades-count').textContent = `${trades.length} 筆交易`;
    tableBody.innerHTML = '';
    
    if (trades.length === 0) {
        tableBody.innerHTML = '<tr><td colspan="11" class="text-center text-muted">無交易明細。</td></tr>';
        return;
    }
    
    trades.forEach(t => {
        const retClass = t.return_pct > 0 ? 'text-rose' : (t.return_pct < 0 ? 'text-green' : '');
        const benchClass = t.benchmark_return_pct > 0 ? 'text-rose' : (t.benchmark_return_pct < 0 ? 'text-green' : '');
        
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td><strong>${t.symbol}</strong></td>
            <td>${t.name}</td>
            <td>${t.entry_date}</td>
            <td>${t.entry_price.toFixed(1)}</td>
            <td>${t.exit_date}</td>
            <td>${t.exit_price.toFixed(1)}</td>
            <td class="${retClass}"><strong>${t.return_pct > 0 ? '+' : ''}${t.return_pct.toFixed(2)}%</strong></td>
            <td class="${benchClass}">${t.benchmark_return_pct > 0 ? '+' : ''}${t.benchmark_return_pct.toFixed(2)}%</td>
            <td>
                <span class="badge ${t.exit_reason === 'Stop Loss' ? 'badge-primary' : (t.exit_reason === 'Take Profit' ? 'badge-secondary' : '')}">
                    ${t.exit_reason}
                </span>
            </td>
            <td class="text-green">${t.max_drawdown_pct.toFixed(2)}%</td>
            <td>
                <button class="btn btn-secondary btn-sm analyze-btn" data-symbol="${t.symbol}">
                    <i class="fa-solid fa-chart-candlestick"></i> 技術分析
                </button>
            </td>
        `;
        tableBody.appendChild(tr);
    });
    
    tableBody.querySelectorAll('.analyze-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            navigateToChart(btn.getAttribute('data-symbol'));
        });
    });
}

function renderEquityChart(curve) {
    const canvas = document.getElementById('equityChart');
    const placeholder = document.getElementById('no-backtest-data');
    
    if (curve.length === 0) {
        placeholder.style.display = 'flex';
        canvas.style.display = 'none';
        if (state.equityChart) state.equityChart.destroy();
        return;
    }
    
    placeholder.style.display = 'none';
    canvas.style.display = 'block';
    
    const labels = curve.map(item => item.date);
    const strategyVals = curve.map(item => item.strategy);
    const benchmarkVals = curve.map(item => item.benchmark);
    
    if (state.equityChart) {
        state.equityChart.destroy();
    }
    
    const ctx = canvas.getContext('2d');
    state.equityChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: '策略資產淨值',
                    data: strategyVals,
                    borderColor: 'rgba(99, 102, 241, 1)',
                    backgroundColor: 'rgba(99, 102, 241, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.1,
                    pointRadius: 1
                },
                {
                    label: '^TWII 大盤基準',
                    data: benchmarkVals,
                    borderColor: 'rgba(156, 163, 175, 1)',
                    borderWidth: 1.5,
                    borderDash: [4, 4],
                    fill: false,
                    tension: 0.1,
                    pointRadius: 0
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                tooltip: {
                    mode: 'index',
                    intersect: false,
                    backgroundColor: '#1E293B',
                    titleColor: '#F3F4F6',
                    bodyColor: '#F3F4F6'
                },
                legend: {
                    labels: { color: '#F3F4F6' }
                }
            },
            scales: {
                y: {
                    grid: { color: '#253046' },
                    ticks: { color: '#9CA3AF' }
                },
                x: {
                    grid: { display: false },
                    ticks: { color: '#9CA3AF' }
                }
            }
        }
    });
}

// 7. Navigation redirection helpers
function navigateToBacktest(sessionId) {
    const navItem = document.querySelector('[data-target="backtest-section"]');
    navItem.click();
    
    setTimeout(() => {
        const select = document.getElementById('backtest-session-select');
        select.value = sessionId;
    }, 100);
}

function navigateToChart(symbol) {
    const navItem = document.querySelector('[data-target="chart-section"]');
    navItem.click();
    
    setTimeout(() => {
        loadStockKline(symbol);
    }, 100);
}

// 8. Individual Stock K-Line Charting (TradingView Lightweight Charts)
function initChartSearch() {
    const searchBtn = document.getElementById('chart-search-btn');
    const searchInput = document.getElementById('chart-search-input');
    
    const performSearch = () => {
        const sym = searchInput.value.trim();
        if (sym) {
            loadStockKline(sym);
        } else {
            showToast('請輸入股票代碼！', 'warning');
        }
    };
    
    searchBtn.addEventListener('click', performSearch);
    searchInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') performSearch();
    });
}

async function loadStockKline(symbol) {
    try {
        const response = await fetch(`${API_BASE}/api/kline/${symbol}`);
        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || 'Failed to fetch K-line data');
        }
        
        const data = await response.json();
        
        // Update Titles
        document.getElementById('chart-stock-title').textContent = `${data.symbol} ${data.name}`;
        document.getElementById('chart-stock-market').textContent = data.market === 'Listed' ? '上市' : '上櫃';
        document.getElementById('chart-stock-industry').textContent = data.industry;
        
        // Destroy existing charts to build fresh
        destroyLightweightCharts();
        
        // Render
        renderTechnicalChart(data.klines);
        
    } catch (err) {
        showToast(err.message, 'error');
    }
}

function destroyLightweightCharts() {
    const chartPanes = ['price', 'volume', 'kd', 'macd'];
    chartPanes.forEach(pane => {
        if (state.tvCharts[pane]) {
            try {
                state.tvCharts[pane].remove();
            } catch (e) {
                console.error(`Error deleting pane chart ${pane}`, e);
            }
            state.tvCharts[pane] = null;
        }
    });
    state.tvCharts.series = {};
}

function renderTechnicalChart(klines) {
    if (klines.length === 0) return;
    
    // Formatting data for series
    const candleData = klines.map(k => ({
        time: k.time,
        open: k.open,
        high: k.high,
        low: k.low,
        close: k.close
    }));
    
    const volumeData = klines.map(k => ({
        time: k.time,
        value: k.volume,
        color: k.close >= k.open ? 'rgba(239, 68, 68, 0.5)' : 'rgba(16, 185, 129, 0.5)' // Red UP, Green DOWN
    }));
    
    // 1. Price Chart (Candlesticks + MA + Bollinger Bands)
    const priceContainer = document.getElementById('tv-price-chart');
    const width = priceContainer.clientWidth;
    
    const commonChartOptions = {
        width: width,
        layout: {
            background: { color: '#111827' },
            textColor: '#9CA3AF',
        },
        grid: {
            vertLines: { color: '#1F2937' },
            horzLines: { color: '#1F2937' },
        },
        timeScale: {
            borderColor: '#374151',
            visible: false // hide X axis for top panels to save vertical space
        },
        rightPriceScale: {
            borderColor: '#374151',
        }
    };
    
    const priceChart = LightweightCharts.createChart(priceContainer, {
        ...commonChartOptions,
        height: 350
    });
    state.tvCharts.price = priceChart;
    
    const mainCandlestick = priceChart.addCandlestickSeries({
        upColor: '#EF4444',
        downColor: '#10B981',
        borderUpColor: '#EF4444',
        borderDownColor: '#10B981',
        wickUpColor: '#EF4444',
        wickDownColor: '#10B981',
    });
    mainCandlestick.setData(candleData);
    
    // Overlays: Moving Averages
    const maConfigs = [
        { key: 'ma5', color: '#FBBF24', label: 'MA5' },
        { key: 'ma10', color: '#F97316', label: 'MA10' },
        { key: 'ma20', color: '#10B981', label: 'MA20' },
        { key: 'ma60', color: '#8B5CF6', label: 'MA60' }
    ];
    
    maConfigs.forEach(conf => {
        const maSeries = priceChart.addLineSeries({
            color: conf.color,
            lineWidth: 1.5,
            title: conf.label
        });
        
        const maData = klines
            .map(k => ({ time: k.time, value: k.indicators[conf.key] }))
            .filter(item => item.value !== null && item.value !== undefined);
            
        maSeries.setData(maData);
    });
    
    // Overlays: Bollinger Bands
    const bbColors = { bb_upper: '#4B5563', bb_mid: '#4B5563', bb_lower: '#4B5563' };
    Object.entries(bbColors).forEach(([key, color]) => {
        const bbSeries = priceChart.addLineSeries({
            color: color,
            lineWidth: 1,
            lineStyle: key !== 'bb_mid' ? LightweightCharts.LineStyle.Dashed : LightweightCharts.LineStyle.Solid,
            title: key.toUpperCase().replace('_', ' ')
        });
        
        const bbData = klines
            .map(k => ({ time: k.time, value: k.indicators[key] }))
            .filter(item => item.value !== null && item.value !== undefined);
            
        bbSeries.setData(bbData);
    });
    
    // 2. Volume Chart
    const volContainer = document.getElementById('tv-volume-chart');
    const volChart = LightweightCharts.createChart(volContainer, {
        ...commonChartOptions,
        height: 120
    });
    state.tvCharts.volume = volChart;
    
    const volSeries = volChart.addHistogramSeries({
        priceFormat: { type: 'volume' },
        priceScaleId: '', // overlay
    });
    volSeries.setData(volumeData);
    
    // 3. KD Chart (9,3,3)
    const kdContainer = document.getElementById('tv-kd-chart');
    const kdChart = LightweightCharts.createChart(kdContainer, {
        ...commonChartOptions,
        height: 120
    });
    state.tvCharts.kd = kdChart;
    
    const kSeries = kdChart.addLineSeries({ color: '#F59E0B', lineWidth: 1.5, title: 'K' });
    const dSeries = kdChart.addLineSeries({ color: '#3B82F6', lineWidth: 1.5, title: 'D' });
    
    const kData = klines.map(k => ({ time: k.time, value: k.indicators.k })).filter(item => item.value !== null);
    const dData = klines.map(k => ({ time: k.time, value: k.indicators.d })).filter(item => item.value !== null);
    
    kSeries.setData(kData);
    dSeries.setData(dData);
    
    // Add KD reference lines at 20 and 80
    const kdRefOptions = { color: '#374151', lineWidth: 1, lineStyle: LightweightCharts.LineStyle.Dotted };
    const k80Ref = kdChart.addLineSeries(kdRefOptions);
    const k20Ref = kdChart.addLineSeries(kdRefOptions);
    k80Ref.setData(klines.map(k => ({ time: k.time, value: 80.0 })));
    k20Ref.setData(klines.map(k => ({ time: k.time, value: 20.0 })));
    
    // 4. MACD Chart (12, 26, 9)
    const macdContainer = document.getElementById('tv-macd-chart');
    const macdChart = LightweightCharts.createChart(macdContainer, {
        ...commonChartOptions,
        height: 140,
        timeScale: {
            borderColor: '#374151',
            visible: true // Show X axis on the final bottom pane only!
        }
    });
    state.tvCharts.macd = macdChart;
    
    const difSeries = macdChart.addLineSeries({ color: '#F97316', lineWidth: 1.5, title: 'DIF' });
    const demSeries = macdChart.addLineSeries({ color: '#3B82F6', lineWidth: 1.5, title: 'DEM' });
    const oscSeries = macdChart.addHistogramSeries({ title: 'OSC' });
    
    const difData = klines.map(k => ({ time: k.time, value: k.indicators.macd_dif })).filter(item => item.value !== null);
    const demData = klines.map(k => ({ time: k.time, value: k.indicators.macd_dem })).filter(item => item.value !== null);
    const oscData = klines.map(k => ({
        time: k.time,
        value: k.indicators.macd_osc,
        color: k.indicators.macd_osc >= 0 ? 'rgba(239, 68, 68, 0.6)' : 'rgba(16, 185, 129, 0.6)'
    })).filter(item => item.value !== null);
    
    difSeries.setData(difData);
    demSeries.setData(demData);
    oscSeries.setData(oscData);
    
    // Link and Synchronize Visible Ranges
    // When the visible range of one chart changes, apply it to all other sub-charts
    const chartsToSync = [priceChart, volChart, kdChart, macdChart];
    
    chartsToSync.forEach(c => {
        c.timeScale().subscribeVisibleTimeRangeChange((range) => {
            if (!range) return;
            chartsToSync.forEach(otherChart => {
                if (otherChart !== c) {
                    otherChart.timeScale().setVisibleRange(range);
                }
            });
        });
    });
}

function resizeCharts() {
    const priceContainer = document.getElementById('tv-price-chart');
    if (!priceContainer) return;
    const width = priceContainer.clientWidth;
    
    const panes = ['price', 'volume', 'kd', 'macd'];
    panes.forEach(pane => {
        if (state.tvCharts[pane]) {
            state.tvCharts[pane].resize(width, state.tvCharts[pane].options.height);
        }
    });
}

window.addEventListener('resize', resizeCharts);

// 9. Database Sync Settings Panel
function initSync() {
    const syncBtn = document.getElementById('start-sync-btn');
    const statusArea = document.getElementById('sync-status-area');
    
    syncBtn.addEventListener('click', async () => {
        if (!confirm('同步台股名冊通常需要 10 秒左右，確定開始同步？')) return;
        
        syncBtn.disabled = true;
        statusArea.style.display = 'block';
        
        try {
            const response = await fetch(`${API_BASE}/api/sync`, { method: 'POST' });
            if (!response.ok) throw new Error('Database sync request failed');
            
            showToast('同步工作已在背景啟動。系統正更新 SQLite 資料庫，請稍候約 10-15 秒。');
            
            // Poll for sync completion (we check stocks count in db)
            let checkCount = 0;
            const interval = setInterval(async () => {
                checkCount++;
                try {
                    const res = await fetch(`${API_BASE}/api/stocks`);
                    if (res.ok) {
                        const stocks = await res.json();
                        // If we can read stocks and count > 1000, consider sync done
                        if (stocks.length > 100) {
                            clearInterval(interval);
                            showToast(`資料同步成功！已成功載入 ${stocks.length} 檔證券。`);
                            statusArea.style.display = 'none';
                            syncBtn.disabled = false;
                        }
                    }
                } catch (e) {
                    console.error("Polling error", e);
                }
                
                if (checkCount > 15) {
                    // Timeout after 30 seconds
                    clearInterval(interval);
                    showToast('同步可能已在背景完成，請刷新頁面檢查。', 'warning');
                    statusArea.style.display = 'none';
                    syncBtn.disabled = false;
                }
            }, 2000);
            
        } catch (err) {
            showToast(err.message, 'error');
            statusArea.style.display = 'none';
            syncBtn.disabled = false;
        }
    });
}
