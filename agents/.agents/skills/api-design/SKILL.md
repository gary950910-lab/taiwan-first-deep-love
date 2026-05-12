---
name: api-design
description: 設計 Flask 路由與頁面規劃。用於資料庫設計後，規劃每個頁面的 URL、HTTP 方法與對應邏輯。
---

# API Design Skill — 路由與頁面設計

這個 skill 會引導 AI agent 規劃 Flask 的路由（Routes），包含每個頁面的 URL 路徑、HTTP 方法、輸入/輸出與對應的 Jinja2 模板。

## When to use this skill

- 資料庫設計完成後，開始規劃前後端的對應關係
- 想確認每個頁面需要哪些路由
- 需要產出路由對照表供團隊分工參考

## How to use it

請在你的 prompt 裡使用以下指示：

```
請閱讀 docs/PRD.md、docs/ARCHITECTURE.md 與 docs/DB_DESIGN.md，產出路由設計文件，儲存為 docs/ROUTES.md。

同時在 app/routes/ 建立對應的 Python 檔案骨架（只寫函式定義與註解，不寫實作邏輯）。

路由設計文件需包含：

1. **路由總覽表格**
   一張表格包含以下欄位：
   | 功能 | HTTP 方法 | URL 路徑 | 對應模板 | 說明 |

   範例：
   | 任務列表 | GET | /tasks | templates/tasks/index.html | 顯示所有任務 |
   | 新增任務頁面 | GET | /tasks/new | templates/tasks/new.html | 顯示表單 |
   | 建立任務 | POST | /tasks | — | 接收表單，存入 DB，重導向 |
   | 任務詳情 | GET | /tasks/<id> | templates/tasks/detail.html | 顯示單筆任務 |
   | 編輯任務頁面 | GET | /tasks/<id>/edit | templates/tasks/edit.html | 顯示編輯表單 |
   | 更新任務 | POST | /tasks/<id>/update | — | 接收表單，更新 DB |
   | 刪除任務 | POST | /tasks/<id>/delete | — | 刪除後重導向 |

2. **每個路由的詳細說明**
   - 輸入（URL 參數、表單欄位）
   - 處理邏輯（呼叫哪個 Model 方法）
   - 輸出（渲染哪個模板或重導向到哪裡）
   - 錯誤處理（404、資料驗證失敗時怎麼處理）

3. **Jinja2 模板清單**
   - 列出所有需要建立的 HTML 模板檔案
   - 說明每個模板繼承哪個 base template

4. **路由骨架程式碼**
   - 在 app/routes/ 為每個功能模組建立一個 .py 檔
   - 每個函式只寫 @app.route 裝飾器、函式名稱與 docstring，不寫實作

請確保 URL 設計符合 RESTful 慣例（盡量使用名詞，用 HTTP 方法區分操作）。
注意：由於使用 HTML 表單，刪除與更新操作用 POST 而非 DELETE/PUT。
```

## 產出範例

執行後應在 `docs/ROUTES.md` 看到完整路由表，在 `app/routes/` 看到帶有 docstring 的函式骨架。
