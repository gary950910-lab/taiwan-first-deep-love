---
name: architecture
description: 設計系統架構文件。用於 PRD 完成後，規劃專案的技術架構、資料夾結構與元件職責。
---

# Architecture Skill — 系統架構設計

這個 skill 會引導 AI agent 根據 PRD 產出系統架構設計，包含技術選型說明、資料夾結構、以及各元件之間的關係。

## When to use this skill

- PRD 已完成，準備開始設計技術方案
- 想確認 Flask 專案應該怎麼組織資料夾
- 需要決定哪些部分用哪個技術處理

## How to use it

請在你的 prompt 裡使用以下指示：

```
請閱讀 docs/PRD.md，根據其中的功能需求，產出系統架構文件，儲存為 docs/ARCHITECTURE.md。

技術限制：
- 後端：Python + Flask
- 模板引擎：Jinja2（負責 HTML 頁面渲染）
- 資料庫：SQLite（透過 sqlite3 或 SQLAlchemy）
- 不需要前後端分離，頁面由 Flask + Jinja2 一起渲染

架構文件需包含：

1. **技術架構說明**
   - 選用技術與原因
   - Flask MVC 模式說明（Model / View / Controller 各自負責什麼）

2. **專案資料夾結構**
   - 完整的資料夾樹狀圖（含說明每個資料夾/檔案的用途）
   - 建議結構：
     app/
       models/      ← 資料庫模型
       routes/      ← Flask 路由（Controller）
       templates/   ← Jinja2 HTML 模板（View）
       static/      ← CSS / JS 靜態資源
     instance/
       database.db  ← SQLite 資料庫
     app.py         ← 入口

3. **元件關係圖**（用 ASCII 圖或 Mermaid 語法）
   - 瀏覽器 → Flask Route → Model → SQLite
   - Flask Route → Jinja2 Template → 瀏覽器

4. **關鍵設計決策**
   - 說明 3–5 個重要的設計選擇與原因

請用繁體中文，格式適合初學者閱讀。
```

## 產出範例

執行後應在 `docs/ARCHITECTURE.md` 看到清楚的資料夾結構圖與元件說明。
