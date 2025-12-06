# 花蓮市和吉安鄉國小資料查詢系統

這是一個 Web 應用程式，從教育部統計處網站爬取花蓮市和吉安鄉各國小的統計資料，並提供網頁介面讓使用者查看和下載 CSV 檔案。

## 功能特色

- 📊 顯示花蓮市和吉安鄉各國小的統計資料
- 📥 提供 CSV 檔案下載功能
- 🔄 資料快取機制，避免頻繁爬取
- 📱 響應式設計，支援各種裝置

## 資料欄位

- 鄉鎮市區
- 學校名稱
- 班級數
- 學生數
- 教師數
- 校地面積（平方公尺）
- 校舍面積（平方公尺）
- 棟數

## 本地開發設置

### 1. 安裝依賴

```bash
pip install -r requirements.txt
```

### 2. 執行應用程式

```bash
python app.py
```

或使用 gunicorn：

```bash
gunicorn app:app
```

### 3. 訪問應用程式

開啟瀏覽器訪問：http://localhost:5000

## Zeabur 部署步驟

### 方法一：透過 Git 部署

1. 將專案推送到 GitHub、GitLab 或 Bitbucket

2. 在 Zeabur 建立新專案

3. 連接您的 Git 儲存庫

4. Zeabur 會自動偵測 Python 專案並安裝依賴

5. 部署完成後，Zeabur 會提供一個網址

### 方法二：直接上傳

1. 在 Zeabur 建立新專案

2. 選擇「上傳程式碼」或「從檔案部署」

3. 上傳專案檔案

4. Zeabur 會自動偵測並部署

### 環境變數

目前不需要額外的環境變數設定。如果需要調整快取時間或其他設定，可以在 `app.py` 中修改。

## 專案結構

```
hualian_elementary_building/
├── app.py               # Flask 應用程式主檔
├── scraper.py           # 爬蟲邏輯模組
├── requirements.txt     # Python 套件依賴
├── Procfile             # Zeabur 部署配置
├── runtime.txt          # Python 版本指定
├── templates/
│   └── index.html       # 前端頁面
├── static/
│   └── style.css        # CSS 樣式
└── README.md            # 說明文件
```

## 技術棧

- **後端**: Flask (Python)
- **爬蟲**: requests + BeautifulSoup4
- **資料處理**: pandas
- **部署**: Gunicorn + Zeabur

## 測試結果

已進行基本功能測試：
- ✓ 模組導入正常
- ✓ Flask 應用程式可正常啟動
- ✓ 網站連接成功
- ✓ ViewState 提取功能正常
- ✓ 文字處理和數字解析功能正常

**注意**：由於目標網站大量使用 JavaScript 動態載入內容（特別是鄉鎮選單和查詢結果），目前的爬蟲程式可能需要進一步調整才能成功爬取資料。建議的解決方案：

1. **使用 Selenium**：處理 JavaScript 動態內容
2. **使用網站的下載功能**：直接下載 CSV 檔案後處理
3. **手動提供資料**：如果爬蟲無法正常工作，可以手動下載資料並上傳

## 注意事項

- 資料快取時間為 1 小時，可透過「重新載入資料」按鈕強制更新
- 爬蟲程式需要根據實際網站結構進行調整
- 請遵守網站的使用條款，避免過度頻繁的請求
- 如果爬蟲無法正常工作，可能需要使用 Selenium 或其他工具處理 JavaScript 動態內容

## 授權

本專案僅供學習和研究使用。

