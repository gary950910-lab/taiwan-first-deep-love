document.addEventListener("DOMContentLoaded", () => {
    // 取得 DOM 節點
    const tickerInput = document.getElementById("ticker-input");
    const searchBtn = document.getElementById("search-btn");
    const tagBtns = document.querySelectorAll(".tag-btn");
    const periodBtns = document.querySelectorAll(".period-btn");
    const errorBanner = document.getElementById("error-banner");
    const errorText = document.getElementById("error-text");
    const chartLoader = document.getElementById("chart-loader");
    const chartContainer = document.getElementById("chart-container");
    
    // 即時股價看板節點
    const displayName = document.getElementById("display-name");
    const displayTicker = document.getElementById("display-ticker");
    const displayPrice = document.getElementById("display-price");
    const displayChange = document.getElementById("display-change");
    const displayVolume = document.getElementById("display-volume");

    // 懸浮提示 (Tooltip) 節點
    const tipDate = document.getElementById("tip-date");
    const tipOpen = document.getElementById("tip-open");
    const tipHigh = document.getElementById("tip-high");
    const tipLow = document.getElementById("tip-low");
    const tipClose = document.getElementById("tip-close");
    const tipVol = document.getElementById("tip-vol");

    // 均線開關節點
    const toggleMa5 = document.getElementById("toggle-ma5");
    const toggleMa20 = document.getElementById("toggle-ma20");
    const toggleMa60 = document.getElementById("toggle-ma60");

    // 歷史明細表格節點
    const detailsTableBody = document.getElementById("details-table-body");

    // 全域變數定義
    let chart = null;
    let candlestickSeries = null;
    let volumeSeries = null;
    let ma5Series = null;
    let ma20Series = null;
    let ma60Series = null;
    
    let currentTicker = "2330";
    let currentPeriod = "1y";
    let globalChartData = []; // 儲存當前繪圖數據

    // ==========================================
    // 1. 初始化 TradingView Lightweight Chart
    // ==========================================
    function initChart() {
        if (chart) {
            chart.remove();
        }

        // 創建圖表物件
        chart = LightweightCharts.createChart(chartContainer, {
            width: chartContainer.clientWidth,
            height: chartContainer.clientHeight || 480,
            layout: {
                background: { type: 'vertical', color: '#090e1a' },
                textColor: '#94a3b8',
                fontSize: 12,
                fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, sans-serif",
            },
            grid: {
                vertLines: { color: 'rgba(255, 255, 255, 0.03)' },
                horzLines: { color: 'rgba(255, 255, 255, 0.03)' },
            },
            crosshair: {
                mode: LightweightCharts.CrosshairMode.Normal,
                vertLine: {
                    color: 'rgba(0, 242, 254, 0.4)',
                    width: 1,
                    style: LightweightCharts.LineStyle.Solid,
                },
                horzLine: {
                    color: 'rgba(0, 242, 254, 0.4)',
                    width: 1,
                    style: LightweightCharts.LineStyle.Solid,
                },
            },
            rightPriceScale: {
                borderColor: 'rgba(255, 255, 255, 0.1)',
                visible: true,
                autoScale: true,
            },
            timeScale: {
                borderColor: 'rgba(255, 255, 255, 0.1)',
                timeVisible: false,
                secondsVisible: false,
            },
        });

        // 創建 K 線序列
        candlestickSeries = chart.addCandlestickSeries({
            upColor: '#00e676', // 陽線 (綠色)
            downColor: '#ff1744', // 陰線 (紅色)
            borderUpColor: '#00e676',
            borderDownColor: '#ff1744',
            wickUpColor: '#00e676',
            wickDownColor: '#ff1744',
        });

        // 設置 K 線圖價格邊界，保留 25% 底部空間給成交量直條圖
        candlestickSeries.priceScale().applyOptions({
            scaleMargins: {
                top: 0.1,
                bottom: 0.25,
            },
        });

        // 創建成交量直條圖序列 (主圖疊加模式)
        volumeSeries = chart.addHistogramSeries({
            color: 'rgba(79, 172, 254, 0.25)',
            priceFormat: {
                type: 'volume',
            },
            priceScaleId: '', // 空字串代表使用獨立的無刻度 Y 軸
        });

        // 限制成交量圖在底部 20% 的範圍內
        volumeSeries.priceScale().applyOptions({
            scaleMargins: {
                top: 0.8,
                bottom: 0,
            },
        });

        // 創建均線系列 (黃/橘/淺藍)
        ma5Series = chart.addLineSeries({
            color: '#ffb703',
            lineWidth: 1.5,
            title: 'MA5',
            visible: toggleMa5.checked
        });

        ma20Series = chart.addLineSeries({
            color: '#fb8500',
            lineWidth: 2,
            title: 'MA20',
            visible: toggleMa20.checked
        });

        ma60Series = chart.addLineSeries({
            color: '#8ecae6',
            lineWidth: 2,
            title: 'MA60',
            visible: toggleMa60.checked
        });

        // ==========================================
        // 2. 滑鼠懸停與交互 (Crosshair Move)
        // ==========================================
        chart.subscribeCrosshairMove((param) => {
            if (
                param.time === undefined ||
                param.point === undefined ||
                param.point.x < 0 ||
                param.point.x > chartContainer.clientWidth ||
                param.point.y < 0 ||
                param.point.y > chartContainer.clientHeight
            ) {
                // 滑鼠移出，還原顯示最新一筆價格數據
                showLatestDataInTooltip();
            } else {
                // 讀取當前滑鼠懸停點的數據
                const dateStr = param.time;
                const candleData = param.seriesData.get(candlestickSeries);
                const volData = param.seriesData.get(volumeSeries);
                
                if (candleData) {
                    updateTooltipValues(
                        dateStr,
                        candleData.open,
                        candleData.high,
                        candleData.low,
                        candleData.close,
                        volData ? volData.value : null
                    );
                }
            }
        });

        // 讓圖表隨視窗大小自適應
        const resizeObserver = new ResizeObserver((entries) => {
            if (entries.length === 0) return;
            const { width, height } = entries[0].contentRect;
            chart.resize(width, height || 480);
        });
        resizeObserver.observe(chartContainer);
    }

    // ==========================================
    // 3. 輔助函數：更新 Tooltip 數值
    // ==========================================
    function updateTooltipValues(date, open, high, low, close, volume) {
        tipDate.innerText = date || "--";
        tipOpen.innerText = open !== undefined && open !== null ? open.toFixed(2) : "--";
        tipHigh.innerText = high !== undefined && high !== null ? high.toFixed(2) : "--";
        tipLow.innerText = low !== undefined && low !== null ? low.toFixed(2) : "--";
        tipClose.innerText = close !== undefined && close !== null ? close.toFixed(2) : "--";
        
        if (volume !== undefined && volume !== null) {
            // 成交量格式化 (轉換為張數，台股 1 張 = 1000 股)
            const volumeInShares = volume;
            if (volumeInShares >= 1000) {
                tipVol.innerText = (volumeInShares / 1000).toLocaleString(undefined, { maximumFractionDigits: 0 }) + " 張";
            } else {
                tipVol.innerText = volumeInShares.toLocaleString() + " 股";
            }
        } else {
            tipVol.innerText = "--";
        }
    }

    // 顯示最新的一筆數據
    function showLatestDataInTooltip() {
        if (globalChartData.length > 0) {
            const latest = globalChartData[globalChartData.length - 1];
            updateTooltipValues(
                latest.time,
                latest.open,
                latest.high,
                latest.low,
                latest.close,
                latest.volume
            );
        } else {
            updateTooltipValues();
        }
    }

    // ==========================================
    // 4. API 數據獲取與畫面更新
    // ==========================================
    async function fetchChartData(ticker, period) {
        // 顯示載入動畫，隱藏錯誤橫幅
        chartLoader.classList.add("active");
        errorBanner.classList.remove("active");

        try {
            const response = await fetch(`/api/chart/${ticker}?period=${period}`);
            if (!response.ok) {
                const errData = await response.json();
                throw new Error(errData.detail || "無法載入此股票的數據");
            }

            const resData = await response.json();
            const data = resData.data;

            if (!data || data.length === 0) {
                throw new Error("此股無歷史數據記錄");
            }

            globalChartData = data;
            currentTicker = resData.ticker;

            // --- 4.1 更新股價即時看板 ---
            const latestCandle = data[data.length - 1];
            const prevCandle = data.length > 1 ? data[data.length - 2] : latestCandle;
            
            // 決定顯示名稱（台股加上代碼）
            displayName.innerText = resData.resolved_ticker.includes(".TW") || resData.resolved_ticker.includes(".TWO") 
                ? `${getTaiwanStockName(resData.ticker)}`
                : resData.ticker;
            displayTicker.innerText = resData.resolved_ticker;

            const closePrice = latestCandle.close;
            const prevClose = prevCandle.close;
            const priceChange = closePrice - prevClose;
            const priceChangePercent = (priceChange / prevClose) * 100;

            displayPrice.innerText = closePrice.toFixed(2);
            
            // 設定漲跌顏色與箭頭
            displayChange.className = "quote-change";
            if (priceChange > 0) {
                displayChange.classList.add("up");
                displayChange.innerText = `▲ +${priceChange.toFixed(2)} (+${priceChangePercent.toFixed(2)}%)`;
                displayPrice.style.color = "var(--bullish)";
            } else if (priceChange < 0) {
                displayChange.classList.add("down");
                displayChange.innerText = `▼ ${priceChange.toFixed(2)} (${priceChangePercent.toFixed(2)}%)`;
                displayPrice.style.color = "var(--bearish)";
            } else {
                displayChange.innerText = `  0.00 (0.00%)`;
                displayPrice.style.color = "#ffffff";
            }

            // 成交量格式化
            const latestVol = latestCandle.volume;
            if (latestVol >= 1000) {
                displayVolume.innerText = (latestVol / 1000).toLocaleString(undefined, { maximumFractionDigits: 0 }) + " 張";
            } else {
                displayVolume.innerText = latestVol.toLocaleString() + " 股";
            }

            // --- 4.2 載入圖表數據 ---
            const candles = [];
            const volumes = [];
            const ma5 = [];
            const ma20 = [];
            const ma60 = [];

            data.forEach((item) => {
                const time = item.time;
                
                // K 線數據
                candles.push({
                    time: time,
                    open: item.open,
                    high: item.high,
                    low: item.low,
                    close: item.close,
                });

                // 成交量直條圖顏色（上漲綠色，下跌紅色）
                const isUp = item.close >= item.open;
                volumes.push({
                    time: time,
                    value: item.volume,
                    color: isUp ? 'rgba(0, 230, 118, 0.3)' : 'rgba(255, 23, 68, 0.3)',
                });

                // 均線數據 (只填寫有數值的點)
                if (item.ma5 !== null) ma5.push({ time: time, value: item.ma5 });
                if (item.ma20 !== null) ma20.push({ time: time, value: item.ma20 });
                if (item.ma60 !== null) ma60.push({ time: time, value: item.ma60 });
            });

            // 寫入序列
            candlestickSeries.setData(candles);
            volumeSeries.setData(volumes);
            ma5Series.setData(ma5);
            ma20Series.setData(ma20);
            ma60Series.setData(ma60);

            // 還原 Tooltip
            showLatestDataInTooltip();

            // 自適應調整可見範圍
            chart.timeScale().fitContent();

            // --- 4.3 渲染最下方歷史明細表格 (近 10 日) ---
            renderDetailsTable(data);

        } catch (err) {
            console.error(err);
            errorText.innerText = `錯誤：${err.message}`;
            errorBanner.classList.add("active");
        } finally {
            chartLoader.classList.remove("active");
        }
    }

    // ==========================================
    // 5. 渲染歷史明細表格 (近 10 日)
    // ==========================================
    function renderDetailsTable(data) {
        detailsTableBody.innerHTML = "";
        
        // 取得最後 10 天的資料並反轉（最新的排前面）
        const displayData = [...data].slice(-10).reverse();
        
        displayData.forEach((item, index, arr) => {
            const tr = document.createElement("tr");
            
            // 計算當日漲跌幅
            let pctChangeStr = "--";
            let pctClass = "";
            
            // 需要尋找原陣列中，此天前一天的收盤價來算漲跌
            const origIndex = data.findIndex(x => x.time === item.time);
            if (origIndex > 0) {
                const prev = data[origIndex - 1];
                const change = item.close - prev.close;
                const pct = (change / prev.close) * 100;
                
                if (change > 0) {
                    pctChangeStr = `+${pct.toFixed(2)}%`;
                    pctClass = "up";
                } else if (change < 0) {
                    pctChangeStr = `${pct.toFixed(2)}%`;
                    pctClass = "down";
                } else {
                    pctChangeStr = "0.00%";
                }
            }

            const volInTons = item.volume >= 1000 ? (item.volume / 1000).toFixed(0) : 0;

            tr.innerHTML = `
                <td><strong>${item.time}</strong></td>
                <td>${item.open.toFixed(2)}</td>
                <td>${item.high.toFixed(2)}</td>
                <td>${item.low.toFixed(2)}</td>
                <td class="${pctClass}">${item.close.toFixed(2)}</td>
                <td class="${pctClass}">${pctChangeStr}</td>
                <td>${volInTons >= 1 ? Number(volInTons).toLocaleString() + " 張" : item.volume.toLocaleString() + " 股"}</td>
                <td style="color: #ffb703">${item.ma5 ? item.ma5.toFixed(2) : "--"}</td>
                <td style="color: #fb8500">${item.ma20 ? item.ma20.toFixed(2) : "--"}</td>
                <td style="color: #8ecae6">${item.ma60 ? item.ma60.toFixed(2) : "--"}</td>
            `;
            detailsTableBody.appendChild(tr);
        });
    }

    // ==========================================
    // 6. 台股常用簡稱對照表
    // ==========================================
    function getTaiwanStockName(ticker) {
        const names = {
            "2330": "台積電",
            "2317": "鴻海",
            "2454": "聯發科",
            "8069": "元太",
            "3008": "大立光",
            "2308": "台達電",
            "2881": "富邦金",
            "2882": "國泰金",
            "2603": "長榮",
            "^TWII": "台股加權指數"
        };
        return names[ticker] ? `${names[ticker]} (${ticker})` : `${ticker}`;
    }

    // ==========================================
    // 7. 綁定事件監聽器 (UI 互動)
    // ==========================================

    // 7.1 搜尋按鈕點擊與 Enter 鍵
    searchBtn.addEventListener("click", () => {
        const val = tickerInput.value.trim();
        if (val) {
            // 清除標籤的 active 狀態
            tagBtns.forEach(b => b.classList.remove("active"));
            
            // 檢查搜尋的股號是否為常用推薦
            tagBtns.forEach(b => {
                if (b.getAttribute("data-ticker") === val) {
                    b.classList.add("active");
                }
            });

            currentTicker = val;
            fetchChartData(currentTicker, currentPeriod);
        }
    });

    tickerInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
            searchBtn.click();
        }
    });

    // 7.2 快速股票標籤 (Quick Select)
    tagBtns.forEach((btn) => {
        btn.addEventListener("click", () => {
            tagBtns.forEach((b) => b.classList.remove("active"));
            btn.classList.add("active");
            
            const ticker = btn.getAttribute("data-ticker");
            tickerInput.value = ticker;
            currentTicker = ticker;
            fetchChartData(currentTicker, currentPeriod);
        });
    });

    // 7.3 歷史區間選擇 (Period Selector)
    periodBtns.forEach((btn) => {
        btn.addEventListener("click", () => {
            periodBtns.forEach((b) => b.classList.remove("active"));
            btn.classList.add("active");
            
            currentPeriod = btn.getAttribute("data-period");
            fetchChartData(currentTicker, currentPeriod);
        });
    });

    // 7.4 均線 (MA) 顯示切換
    toggleMa5.addEventListener("change", () => {
        ma5Series.applyOptions({ visible: toggleMa5.checked });
    });

    toggleMa20.addEventListener("change", () => {
        ma20Series.applyOptions({ visible: toggleMa20.checked });
    });

    toggleMa60.addEventListener("change", () => {
        ma60Series.applyOptions({ visible: toggleMa60.checked });
    });

    // ==========================================
    // 8. 系統初始啟動
    // ==========================================
    initChart();
    fetchChartData(currentTicker, currentPeriod);
});
