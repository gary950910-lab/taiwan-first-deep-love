---
name: db-design
description: 設計資料庫 Schema。用於流程圖完成後，定義 SQLite 資料表結構與關聯。
---

# DB Design Skill — 資料庫設計

這個 skill 會引導 AI agent 根據功能需求，設計 SQLite 資料表的欄位、型別與關聯，並產出 SQL 建表語法與 Python Model 程式碼。

## When to use this skill

- 功能與流程確定後，開始設計資料要怎麼存
- 需要確認哪些欄位必要、資料型別是什麼
- 想直接產出可以執行的建表 SQL 語法

## How to use it

請在你的 prompt 裡使用以下指示：

```
請閱讀 docs/PRD.md 與 docs/FLOWCHART.md，產出資料庫設計文件，儲存為 docs/DB_DESIGN.md。

同時在專案中建立 app/models/ 資料夾，並為每個資料表產出對應的 Python Model 檔案。

資料庫設計文件需包含：

1. **ER 圖（實體關係圖）**
   - 使用 Mermaid erDiagram 語法
   - 標示資料表名稱、欄位、型別與關聯（一對多、多對多）

   範例：
   ```mermaid
   erDiagram
     TASK {
       int id PK
       string title
       string description
       string status
       date due_date
       datetime created_at
     }
   ```

2. **資料表詳細說明**
   - 每個資料表一個小節
   - 說明每個欄位的用途、型別、是否必填
   - 說明 Primary Key 與 Foreign Key

3. **SQL 建表語法**
   - 完整的 CREATE TABLE SQL（SQLite 語法）
   - 儲存在 database/schema.sql

4. **Python Model 程式碼**
   - 使用 sqlite3 或 SQLAlchemy（依架構文件決定）
   - 每個 Model 放在 app/models/ 對應的檔案
   - 包含 CRUD 方法（create, get_all, get_by_id, update, delete）

請確保：
- 每個資料表都有 id（INTEGER PRIMARY KEY AUTOINCREMENT）
- 時間戳記欄位用 TEXT 存 ISO 格式或用 DATETIME
- 欄位命名使用 snake_case
```

## 產出範例

執行後應在 `docs/DB_DESIGN.md` 看到 ER 圖，在 `app/models/` 看到 Python Model 檔案，在 `database/schema.sql` 看到建表語法。
