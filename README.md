# DeepSeek Scraper

爬蟲方式使用 DeepSeek，無需付費 API。

## 架構
- **後端**: Flask (Python)
- **爬蟲**: Selenium headless Chrome
- **前端**: HTML + JS (單頁)

## 流程
1. 前端輸入市場資訊（或自動抓取）
2. 後端用 Selenium 開啟 DeepSeek chat，JSON 注入到輸入框
3. 等待回應，擷取文字
4. 回傳給前端顯示

## 快速啟動
```bash
pip install -r requirements.txt
python app.py
```
瀏覽器開啟 http://localhost:5000

## 注意
- 需要已登入 DeepSeek 帳號的 Chrome profile，或在 scraper.py 設定 cookies
- 高頻使用可能被限速，建議加 delay
