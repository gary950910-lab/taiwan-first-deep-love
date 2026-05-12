---
name: flowchart
description: 產生使用者流程圖與系統流程圖。用於架構設計後，視覺化使用者操作路徑與資料流。
---

# Flowchart Skill — 流程圖設計

這個 skill 會引導 AI agent 產出兩種流程圖：**使用者流程圖**（User Flow，描述使用者如何操作系統）與**系統流程圖**（System Flow，描述資料如何在系統內流動）。

## When to use this skill

- 架構設計完成，想視覺化確認使用者的操作路徑
- 想確認每個功能的前後步驟是否有遺漏
- 需要產出可以放進報告的流程圖

## How to use it

請在你的 prompt 裡使用以下指示：

```
請閱讀 docs/PRD.md 與 docs/ARCHITECTURE.md，產出流程圖文件，儲存為 docs/FLOWCHART.md。

需要包含以下兩種流程圖，請使用 Mermaid 語法撰寫：

1. **使用者流程圖（User Flow）**
   - 從使用者進入網站開始
   - 涵蓋所有主要功能的操作路徑（例如：新增、查看、編輯、刪除）
   - 用 Mermaid flowchart LR 語法

   範例格式：
   ```mermaid
   flowchart LR
     A([使用者開啟網頁]) --> B[首頁 - 任務列表]
     B --> C{要執行什麼操作？}
     C -->|新增| D[填寫表單]
     ...
   ```

2. **系統序列圖（Sequence Diagram）**
   - 描述「使用者點擊新增」到「資料存入資料庫」的完整流程
   - 角色包含：使用者瀏覽器 / Flask Route / Model / SQLite
   - 用 Mermaid sequenceDiagram 語法

   範例格式：
   ```mermaid
   sequenceDiagram
     actor User as 使用者
     participant Browser
     participant Flask
     participant DB as SQLite
     User->>Browser: 填寫表單並送出
     Browser->>Flask: POST /tasks
     Flask->>DB: INSERT INTO tasks
     DB-->>Flask: 成功
     Flask-->>Browser: 重導向到列表頁
   ```

3. **功能清單對照表**
   - 一張表格列出每個功能、對應的 URL 路徑與 HTTP 方法

請用繁體中文加上適當說明文字。
```

## 產出範例

執行後應在 `docs/FLOWCHART.md` 看到可渲染的 Mermaid 流程圖，可直接貼到 GitHub 或 Notion 預覽。
