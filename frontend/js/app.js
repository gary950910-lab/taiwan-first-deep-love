const API_BASE_URL = 'http://127.0.0.1:8000/api/records';

// Formatter utilities
const formatDate = (dateString) => {
    const d = new Date(dateString);
    return d.toLocaleString('zh-TW', { hour12: false });
};

// Fetch and render the list of records (index.html)
async function fetchRecords() {
    const loading = document.getElementById('loading');
    const tableBody = document.getElementById('recordsBody');
    const emptyState = document.getElementById('emptyState');
    
    if (!loading || !tableBody || !emptyState) return;

    try {
        loading.style.display = 'block';
        tableBody.innerHTML = '';
        emptyState.style.display = 'none';

        const response = await fetch(API_BASE_URL);
        const data = await response.json();

        if (data.status === 'success') {
            const records = data.data;
            if (records.length === 0) {
                emptyState.style.display = 'block';
            } else {
                records.forEach((record, index) => {
                    const tr = document.createElement('tr');
                    tr.className = 'fade-in';
                    tr.style.animationDelay = `${index * 0.05}s`;
                    tr.innerHTML = `
                        <td>#${record.id}</td>
                        <td>${record.scan_date}</td>
                        <td><span class="badge">${record.strategy_name}</span></td>
                        <td>${formatDate(record.created_at)}</td>
                        <td>
                            <a href="detail.html?id=${record.id}" class="btn btn-primary btn-icon" style="margin-right: 0.5rem;" title="查看明細">
                                <svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path><path d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"></path></svg>
                            </a>
                            <button class="btn btn-danger btn-icon" onclick="deleteRecord(${record.id})" title="刪除">
                                <svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg>
                            </button>
                        </td>
                    `;
                    tableBody.appendChild(tr);
                });
            }
        } else {
            alert('取得紀錄失敗');
        }
    } catch (error) {
        console.error('Error fetching records:', error);
        alert('無法連接伺服器，請確認後端已啟動。');
    } finally {
        loading.style.display = 'none';
    }
}

// Delete a record
async function deleteRecord(id) {
    if (!confirm(`確定要刪除紀錄 #${id} 嗎？此操作無法復原。`)) {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}/${id}`, {
            method: 'DELETE'
        });
        const data = await response.json();
        
        if (data.status === 'success') {
            fetchRecords(); // Refresh table
        } else {
            alert(data.detail || '刪除失敗');
        }
    } catch (error) {
        console.error('Error deleting record:', error);
        alert('刪除時發生錯誤');
    }
}

// Fetch and render the details of a specific record (detail.html)
async function fetchRecordDetail(id) {
    const loading = document.getElementById('loading');
    const content = document.getElementById('detailContent');
    
    if (!loading || !content) return;

    try {
        const response = await fetch(`${API_BASE_URL}/${id}`);
        
        if (!response.ok) {
            throw new Error('Record not found');
        }
        
        const data = await response.json();
        
        if (data.status === 'success') {
            const record = data.data;
            
            // Populate meta details
            document.getElementById('lblId').textContent = `#${record.id}`;
            document.getElementById('lblDate').textContent = record.scan_date;
            document.getElementById('lblStrategy').textContent = record.strategy_name;
            document.getElementById('lblCreated').textContent = formatDate(record.created_at);
            document.getElementById('lblConditions').textContent = JSON.stringify(record.conditions, null, 2);
            
            // Populate results table
            const resultsBody = document.getElementById('resultsBody');
            document.getElementById('resultCount').textContent = record.results.length;
            
            if (record.results.length === 0) {
                resultsBody.innerHTML = '<tr><td colspan="4" style="text-align: center;">沒有符合條件的標的</td></tr>';
            } else {
                record.results.forEach((res, index) => {
                    const tr = document.createElement('tr');
                    tr.className = 'fade-in';
                    tr.style.animationDelay = `${index * 0.05}s`;
                    tr.innerHTML = `
                        <td style="font-weight: 600; color: var(--accent);">${res.ticker}</td>
                        <td>${res.price ? res.price.toFixed(2) : '-'}</td>
                        <td>${res.volume ? res.volume.toLocaleString() : '-'}</td>
                        <td>
                            <pre style="background: rgba(0,0,0,0.1); padding: 0.5rem; margin: 0; font-size: 0.75rem; color: var(--text-secondary); border: none;">${JSON.stringify(res.indicators, null, 1).replace(/[{}"]/g, '')}</pre>
                        </td>
                    `;
                    resultsBody.appendChild(tr);
                });
            }
            
            loading.style.display = 'none';
            content.style.display = 'block';
        }
    } catch (error) {
        console.error('Error fetching details:', error);
        alert('無法取得紀錄明細或紀錄不存在');
        window.location.href = 'index.html';
    }
}
