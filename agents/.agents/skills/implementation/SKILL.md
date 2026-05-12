---
name: implementation
description: 實作 Flask 程式碼。用於所有設計文件完成後，逐一實作路由、Model 與 Jinja2 模板。
---

# Implementation Skill — 程式碼實作

這個 skill 會引導 AI agent 根據已完成的設計文件，逐步實作 Flask 後端邏輯與 Jinja2 前端模板，產出可執行的完整程式碼。

## When to use this skill

- 所有設計文件（PRD、架構、流程圖、DB、路由）都已完成
- 準備開始寫真正的程式碼
- 想針對某一個功能模組進行實作

## How to use it

### 步驟一：初始化專案

```
請根據 docs/ARCHITECTURE.md 的資料夾結構，建立專案骨架：

1. 建立所有必要的資料夾與空白 __init__.py
2. 建立 requirements.txt，內容：
   flask
   (如果用 SQLAlchemy 則加上 flask-sqlalchemy)
3. 建立 .env.example，列出需要的環境變數（如 SECRET_KEY）
4. 建立 app.py 作為入口點，包含 Flask app 初始化
5. 建立 database/schema.sql（從 docs/DB_DESIGN.md 複製 SQL）

完成後列出所有建立的檔案。
```

### 步驟二：實作 Model

```
請實作 app/models/ 裡的所有 Model 檔案。

參考 docs/DB_DESIGN.md，為每個 Model 實作：
- 資料庫連線函式（get_db_connection）
- create(data) → 新增一筆記錄
- get_all() → 取得所有記錄
- get_by_id(id) → 取得單筆記錄
- update(id, data) → 更新記錄
- delete(id) → 刪除記錄

注意事項：
- 使用 sqlite3，資料庫路徑為 instance/database.db
- row_factory = sqlite3.Row 讓查詢結果可以用欄位名稱取值
- 每個函式都要有 try/except 錯誤處理
- 函式要有 docstring 說明用途與參數
```

### 步驟三：實作路由

```
請實作 app/routes/ 裡的路由函式。

參考 docs/ROUTES.md，為每個路由實作：
- 從表單或 URL 參數取得輸入資料
- 進行基本的輸入驗證（檢查必填欄位是否為空）
- 呼叫對應的 Model 方法
- 成功時：渲染模板或重導向
- 失敗時：顯示錯誤訊息（用 flash message）

注意事項：
- 使用 Flask Blueprint 組織路由
- 表單驗證失敗時要回到表單頁並顯示錯誤
- 刪除與更新只接受 POST 方法
```

### 步驟四：實作 Jinja2 模板

```
請在 app/templates/ 建立所有 HTML 模板。

參考 docs/ROUTES.md 的模板清單：

1. 先建立 base.html（所有頁面繼承的基礎模板）：
   - 包含 <head>（引用 Bootstrap CDN）
   - 包含導覽列
   - 包含 {% block content %}{% endblock %}
   - 包含 flash message 顯示區塊

2. 為每個頁面建立對應模板：
   - extends "base.html"
   - 填寫 {% block content %}
   - 列表頁：用 for 迴圈顯示資料
   - 表單頁：有 label、input、submit 按鈕
   - 所有表單的 action 與 method 要正確

使用 Bootstrap 5 讓介面好看一點，但不用太花俏。
請確保所有 Jinja2 語法正確（變數用 {{ }}，邏輯用 {% %}）。
```

### 步驟五：整合測試

```
請確認以下項目都能正常運作：

1. 在專案根目錄執行：
   python -m venv .venv
   source .venv/bin/activate  (Windows: .venv\Scripts\activate)
   pip install -r requirements.txt

2. 初始化資料庫：
   python -c "from app import init_db; init_db()"

3. 啟動伺服器：
   flask run

4. 確認以下功能可以正常操作：
   - 開啟首頁（不會報錯）
   - 新增一筆資料（表單送出後資料出現在列表）
   - 編輯資料（修改後正確更新）
   - 刪除資料（確認後從列表消失）

如果有錯誤，請顯示錯誤訊息並說明如何修復。
```

## 注意事項

- 每個步驟完成後再進行下一步，不要一次要求全部
- 遇到錯誤要先讀懂錯誤訊息，貼給 AI 請它修復
- 實作順序很重要：Model → 路由 → 模板，不要跳步驟
