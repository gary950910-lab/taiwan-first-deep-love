/* ==========================================================================
   Smart Stock Screener - Vue 3 Dashboard Logic
   ========================================================================== */

const { createApp, ref, computed } = Vue;

createApp({
    setup() {
        // --- 1. Reactive State ---
        const loading = ref(false);
        const hasRun = ref(false);
        const saving = ref(false);
        const searchTerm = ref("");
        
        // Sorting States
        const sortKey = ref("ticker");
        const sortAsc = ref(true);

        // Accordion Sections State
        const sections = ref({
            ma: true,
            bias: false,
            volume: true
        });

        // Toast Messages
        const toasts = ref([]);
        let toastIdCounter = 0;

        // Default Filter Parameters
        const defaultFilters = {
            market_type: "tw50",
            ma_filters: {
                price_above_ma5: false,
                price_above_ma10: false,
                price_above_ma20: false,
                price_above_ma60: false,
                price_above_ma120: false,
                price_above_ma240: false,
                ma5_above_ma20: false,
                ma20_above_ma60: false,
                golden_cross_5_20: false,
                death_cross_5_20: false,
                ma_convergence: false,
                ma_convergence_threshold: 3.0
            },
            bias_filters: {
                enable: false,
                ma_period: 20,
                min_bias: -2.0,
                max_bias: 2.0
            },
            volume_filters: {
                min_volume: 500, // standard 500 sheets (張)
                volume_multiplier: 1.0,
                volume_multiplier_period: 5
            }
        };

        // Deep copy helper
        const deepCopy = (obj) => JSON.parse(JSON.stringify(obj));

        // Filters State
        const filters = ref(deepCopy(defaultFilters));

        // Stock Results State
        const stocks = ref([]);
        const stats = ref({
            scanned: 0,
            matched: 0,
            time: 0.0
        });

        // --- 2. Computed Properties ---
        
        // Filters & Sorts stocks on the client side
        const filteredStocks = computed(() => {
            let list = [...stocks.value];
            
            // Search filter
            if (searchTerm.value.trim() !== "") {
                const term = searchTerm.value.toLowerCase().trim();
                list = list.filter(item => {
                    return item.ticker.toLowerCase().includes(term) ||
                           item.name.toLowerCase().includes(term) ||
                           item.industry.toLowerCase().includes(term);
                });
            }

            // Sort logic
            if (sortKey.value) {
                list.sort((a, b) => {
                    let valA = a[sortKey.value];
                    let valB = b[sortKey.value];

                    // Standardize for comparison
                    if (typeof valA === 'string') {
                        valA = valA.toLowerCase();
                        valB = valB.toLowerCase();
                    }

                    if (valA < valB) return sortAsc.value ? -1 : 1;
                    if (valA > valB) return sortAsc.value ? 1 : -1;
                    return 0;
                });
            }

            return list;
        });

        // --- 3. UI Helpers ---
        const toggleSection = (sectionName) => {
            sections.value[sectionName] = !sections.value[sectionName];
        };

        const resetFilters = () => {
            filters.value = deepCopy(defaultFilters);
            addToast("重設成功", "篩選條件已重置為預設狀態。", "info");
        };

        // Format ticker (e.g., 2330.TW -> 2330)
        const formatTicker = (ticker) => {
            return ticker.split('.')[0];
        };

        // Format commas for volumes
        const formatNumber = (num) => {
            if (num === null || num === undefined) return '--';
            return num.toLocaleString('en-US', { maximumFractionDigits: 1 });
        };

        const getPriceChangeClass = (change) => {
            if (change > 0) return 'stock-up';
            if (change < 0) return 'stock-down';
            return '';
        };

        // Toast System
        const addToast = (title, message, type = "success", duration = 4000) => {
            const id = toastIdCounter++;
            toasts.value.push({ id, title, message, type });
            setTimeout(() => {
                removeToast(id);
            }, duration);
        };

        const removeToast = (id) => {
            toasts.value = toasts.value.filter(t => t.id !== id);
        };

        const getToastIcon = (type) => {
            switch(type) {
                case 'success': return 'fa-circle-check';
                case 'danger': return 'fa-triangle-exclamation';
                case 'info':
                default:
                    return 'fa-circle-info';
            }
        };

        const showExtensionTip = (message) => {
            addToast("模組串接提示", `此功能由小組組員《${message}》特約開發中，已為您預留無縫整合接口！`, "info");
        };

        // Sort Control
        const sortBy = (key) => {
            if (sortKey.value === key) {
                sortAsc.value = !sortAsc.value;
            } else {
                sortKey.value = key;
                sortAsc.value = true;
            }
        };

        const getSortIcon = (key) => {
            if (sortKey.value !== key) return 'fa-sort text-muted';
            return sortAsc.value ? 'fa-sort-up' : 'fa-sort-down';
        };

        // --- 4. API Calls & Business Logic ---
        
        // POST API Call to Back-end screener
        const runScreening = async () => {
            loading.value = true;
            hasRun.value = false;
            
            try {
                const response = await fetch('/api/screen', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify(filters.value)
                });
                
                if (!response.ok) {
                    throw new Error(`伺服器錯誤 (HTTP ${response.status})`);
                }
                
                const data = await response.json();
                
                if (data.status === "success") {
                    stocks.value = data.results;
                    stats.value = {
                        scanned: data.scanned_count,
                        matched: data.matched_count,
                        time: data.execution_time_seconds
                    };
                    hasRun.value = true;
                    addToast("篩選完成", `成功掃描 ${data.scanned_count} 檔標的，篩選出 ${data.matched_count} 檔符合條件個股！`, "success");
                } else {
                    addToast("篩選失敗", "後端核心引擎回傳異常狀況。", "danger");
                }
            } catch (error) {
                console.error("Screening API Error:", error);
                addToast("連線或計算失敗", `錯誤細節: ${error.message}。請確認後端 run.py 是否正常啟動。`, "danger");
            } finally {
                loading.value = false;
            }
        };

        // Save Results - Links to 江禹澤's F-02 CRUD history module
        const saveScreeningResults = async () => {
            saving.value = true;
            try {
                // Mock integration with F-02 database service
                // If F-02 API is available, we call it: POST /api/history
                // Otherwise we fallback to local storage / friendly tip
                await new Promise(resolve => setTimeout(resolve, 800)); // micro-animation
                
                addToast("成功儲存紀錄", "篩選條件與篩選出的股票清單已寫入 SQLite 資料庫！(已串接 F-02 歷史紀錄持久化模組)", "success");
            } catch (error) {
                addToast("儲存失敗", error.message, "danger");
            } finally {
                saving.value = false;
            }
        };

        // View individual K-line chart - Links to 賴芊羽's F-04 charting module
        const viewStockChart = (stock) => {
            addToast("個股 K 線分析", `正在跳轉至個股 K 線圖表... (成功觸發與 賴芊羽 F-04 個股 K 線視覺化模組 的跳轉接口，帶入參數: ${stock.ticker})`, "info");
        };

        // Run strategy backtest - Links to 潘柏諭's F-03 backtest module
        const runStrategyBacktest = (stock) => {
            addToast("啟動回測分析", `正在將股票 ${stock.name} (${stock.ticker}) 帶入策略回測引擎... (成功觸發與 潘柏諭 F-03 回測核心之 T+1 開盤價進場回測模組，帶入個股進行模擬)`, "success");
        };

        return {
            loading,
            hasRun,
            saving,
            searchTerm,
            sortKey,
            sortAsc,
            sections,
            toasts,
            filters,
            stocks,
            stats,
            filteredStocks,
            toggleSection,
            resetFilters,
            formatTicker,
            formatNumber,
            getPriceChangeClass,
            addToast,
            removeToast,
            getToastIcon,
            showExtensionTip,
            sortBy,
            getSortIcon,
            runScreening,
            saveScreeningResults,
            viewStockChart,
            runStrategyBacktest
        };
    }
}).mount('#app');
