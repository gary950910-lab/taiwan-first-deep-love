document.addEventListener('DOMContentLoaded', function() {
    const backtestForm = document.getElementById('backtestForm');
    const btnSubmit = document.getElementById('btnSubmit');
    const loaderSection = document.getElementById('loaderSection');
    const guideSection = document.getElementById('guideSection');
    const resultsSection = document.getElementById('resultsSection');
    const tradesSection = document.getElementById('tradesSection');
    
    // Metrics elements
    const metricTotalReturn = document.getElementById('metricTotalReturn');
    const metricWinRate = document.getElementById('metricWinRate');
    const metricProfitLossRatio = document.getElementById('metricProfitLossRatio');
    const metricMaxDrawdown = document.getElementById('metricMaxDrawdown');
    const resultTickerHeader = document.getElementById('resultTickerHeader');
    
    // Trades table
    const tradesTableBody = document.getElementById('tradesTableBody');
    
    let equityChart = null;

    // Form submit listener
    backtestForm.addEventListener('submit', function(e) {
        e.preventDefault();
        
        // Form Data
        const formData = new FormData(backtestForm);
        const payload = {
            ticker: formData.get('ticker'),
            strategy: formData.get('strategy'),
            start_date: formData.get('start_date'),
            end_date: formData.get('end_date'),
            stop_loss_pct: formData.get('stop_loss_pct'),
            take_profit_pct: formData.get('take_profit_pct')
        };
        
        // Show Loader & Hide Sections
        guideSection.classList.add('d-none');
        resultsSection.classList.add('d-none');
        tradesSection.classList.add('d-none');
        loaderSection.classList.remove('d-none');
        btnSubmit.disabled = true;
        btnSubmit.innerHTML = `<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span> 運算中...`;
        
        // POST to backend API
        fetch('/backtest/api/run', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        })
        .then(response => {
            if (!response.ok) {
                return response.json().then(err => { throw new Error(err.error || "回測運算發生錯誤。"); });
            }
            return response.json();
        })
        .then(data => {
            // Update UI with Backtest Results
            displayResults(data);
        })
        .catch(error => {
            alert("錯誤: " + error.message);
            // Revert back to guide
            loaderSection.classList.add('d-none');
            guideSection.classList.remove('d-none');
        })
        .finally(() => {
            btnSubmit.disabled = false;
            btnSubmit.innerHTML = `<i class="bi bi-play-circle-fill me-2"></i> 啟動回測引擎`;
        });
    });

    function displayResults(data) {
        // Hide loader & Show results
        loaderSection.classList.add('d-none');
        resultsSection.classList.remove('d-none');
        tradesSection.classList.remove('d-none');
        
        // 1. Update Header Badge
        const strategyText = data.strategy === 'KD' ? 'KD Golden Cross' : data.strategy === 'MACD' ? 'MACD Golden Cross' : 'Buy & Hold';
        resultTickerHeader.textContent = `${data.ticker} - ${strategyText} (SL: ${data.stop_loss_pct}%, TP: ${data.take_profit_pct}%)`;
        
        // 2. Update Metrics Cards
        const totalReturn = data.metrics.total_return_pct;
        metricTotalReturn.textContent = `${totalReturn > 0 ? '+' : ''}${totalReturn}%`;
        if (totalReturn > 0) {
            metricTotalReturn.className = 'metric-value text-gradient-success';
        } else {
            metricTotalReturn.className = 'metric-value text-gradient-danger';
        }
        
        metricWinRate.textContent = `${data.metrics.win_rate_pct}%`;
        metricProfitLossRatio.textContent = data.metrics.profit_loss_ratio;
        metricMaxDrawdown.textContent = `-${data.metrics.max_drawdown_pct}%`;
        
        // 3. Render Chart
        renderChart(data.chart_data);
        
        // 4. Populate Trades Table
        populateTradesTable(data.trades);
    }

    function renderChart(chartData) {
        const ctx = document.getElementById('equityChart').getContext('2d');
        
        // Destroy existing chart if it exists to avoid overlapping
        if (equityChart) {
            equityChart.destroy();
        }
        
        // Create glowing gradients
        const gradientPortfolio = ctx.createLinearGradient(0, 0, 0, 400);
        gradientPortfolio.addColorStop(0, 'rgba(99, 102, 241, 0.4)');
        gradientPortfolio.addColorStop(1, 'rgba(99, 102, 241, 0.0)');
        
        const gradientStock = ctx.createLinearGradient(0, 0, 0, 400);
        gradientStock.addColorStop(0, 'rgba(168, 85, 247, 0.2)');
        gradientStock.addColorStop(1, 'rgba(168, 85, 247, 0.0)');

        equityChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: chartData.dates,
                datasets: [
                    {
                        label: '策略回測累積收益率 (%)',
                        data: chartData.portfolio_return_pct,
                        borderColor: '#6366f1',
                        borderWidth: 3,
                        backgroundColor: gradientPortfolio,
                        fill: true,
                        tension: 0.1,
                        pointRadius: 0,
                        pointHoverRadius: 6,
                        pointHoverBackgroundColor: '#6366f1'
                    },
                    {
                        label: '標的買入持有收益率 (%)',
                        data: chartData.stock_return_pct,
                        borderColor: 'rgba(168, 85, 247, 0.6)',
                        borderWidth: 2,
                        borderDash: [5, 5],
                        backgroundColor: gradientStock,
                        fill: true,
                        tension: 0.1,
                        pointRadius: 0,
                        pointHoverRadius: 4,
                        pointHoverBackgroundColor: '#a855f7'
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'top',
                        labels: {
                            color: '#94a3b8',
                            font: {
                                family: 'Inter, Noto Sans TC',
                                size: 12
                            }
                        }
                    },
                    tooltip: {
                        mode: 'index',
                        intersect: false,
                        backgroundColor: '#1e293b',
                        titleColor: '#f8fafc',
                        bodyColor: '#94a3b8',
                        borderColor: '#334155',
                        borderWidth: 1,
                        padding: 12,
                        titleFont: {
                            family: 'Inter, Noto Sans TC',
                            size: 13,
                            weight: 'bold'
                        },
                        bodyFont: {
                            family: 'Inter, Noto Sans TC',
                            size: 12
                        },
                        callbacks: {
                            label: function(context) {
                                let label = context.dataset.label || '';
                                if (label) {
                                    label += ': ';
                                }
                                if (context.parsed.y !== null) {
                                    label += (context.parsed.y > 0 ? '+' : '') + context.parsed.y.toFixed(2) + '%';
                                }
                                return label;
                            }
                        }
                    }
                ],
                scales: {
                    x: {
                        grid: {
                            color: 'rgba(255, 255, 255, 0.03)',
                            drawBorder: false
                        },
                        ticks: {
                            color: '#64748b',
                            maxTicksLimit: 12,
                            font: {
                                family: 'Inter'
                            }
                        }
                    },
                    y: {
                        grid: {
                            color: 'rgba(255, 255, 255, 0.05)',
                            drawBorder: false
                        },
                        ticks: {
                            color: '#64748b',
                            font: {
                                family: 'Inter'
                            },
                            callback: function(value) {
                                return (value > 0 ? '+' : '') + value + '%';
                            }
                        }
                    }
                }
            }
        });
    }

    function populateTradesTable(trades) {
        tradesTableBody.innerHTML = '';
        
        if (!trades || trades.length === 0) {
            tradesTableBody.innerHTML = `<tr><td colspan="7" class="text-center text-muted py-4">此回測期間內沒有任何交易觸發。</td></tr>`;
            return;
        }
        
        trades.forEach(trade => {
            const tr = document.createElement('tr');
            
            const isEntry = trade.type === 'Entry';
            
            // 1. Action Badge
            const actionBadge = isEntry 
                ? `<span class="badge badge-premium badge-info-premium"><i class="bi bi-box-arrow-in-right me-1"></i> 買入進場</span>`
                : `<span class="badge badge-premium ${trade.return_pct > 0 ? 'badge-win' : 'badge-loss'}"><i class="bi bi-box-arrow-left me-1"></i> 出場平倉</span>`;
            
            // 2. Return formatting
            let returnCell = '-';
            if (!isEntry && trade.return_pct !== undefined) {
                const isWin = trade.return_pct > 0;
                returnCell = `<span class="${isWin ? 'text-success fw-bold' : 'text-danger fw-bold'}">${isWin ? '+' : ''}${trade.return_pct}%</span>`;
            }
            
            // 3. Reason detail
            let reasonDetail = trade.reason;
            if (isEntry) {
                reasonDetail += ` (設停損: ${trade.sl_price}, 設停利: ${trade.tp_price})`;
            }
            
            tr.innerHTML = `
                <td>${actionBadge}</td>
                <td class="font-outfit">${trade.date}</td>
                <td class="font-outfit fw-medium">${trade.price}</td>
                <td class="small text-secondary">${reasonDetail}</td>
                <td class="font-outfit text-secondary">${trade.entry_date || '-'}</td>
                <td class="font-outfit text-secondary">${trade.entry_price || '-'}</td>
                <td class="font-outfit">${returnCell}</td>
            `;
            
            tradesTableBody.appendChild(tr);
        });
    }
});
