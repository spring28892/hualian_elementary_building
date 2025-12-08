"""
花蓮縣國小資料爬蟲模組
從教育部統計處網站爬取花蓮縣所有鄉鎮市區的學校統計資料
使用 Playwright 處理 JavaScript 動態載入內容
"""
from playwright.async_api import async_playwright, Browser, Page
from bs4 import BeautifulSoup
import re
import asyncio
from typing import List, Dict, Optional, Any


class SchoolScraper:
    """學校資料爬蟲類別（使用 Playwright）"""
    
    BASE_URL = "https://stats.moe.gov.tw/edugissys/default.aspx"
    
    def __init__(self):
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self.playwright = None
    
    async def __aenter__(self):
        """非同步上下文管理器入口"""
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """非同步上下文管理器出口"""
        await self.close()
    
    async def start(self):
        """啟動 Playwright 瀏覽器"""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox']  # 用於部署環境
        )
        self.page = await self.browser.new_page()
        # 設定 User-Agent
        await self.page.set_extra_http_headers({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
    
    async def close(self):
        """關閉瀏覽器"""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
    
    async def get_city_code(self, city_name: str) -> Optional[str]:
        """從頁面中取得縣市代碼（等待 JavaScript 載入）"""
        try:
            # 等待縣市選單載入
            await self.page.wait_for_selector('select[name="CityName"]', timeout=30000)
            
            # 等待選項載入（可能需要等待 JavaScript 執行）
            await self.page.wait_for_timeout(2000)
            
            # 取得所有縣市選項
            options = await self.page.locator('select[name="CityName"] option').all()
            
            print(f"找到 {len(options)} 個縣市選項")
            
            for option in options:
                text = await option.text_content()
                value = await option.get_attribute('value')
                if text and city_name in text:
                    print(f"找到縣市: {text} (value: {value})")
                    return value
            
            # 如果沒找到，列出所有選項以便調試
            print("所有縣市選項：")
            for option in options[:10]:  # 只顯示前10個
                text = await option.text_content()
                value = await option.get_attribute('value')
                print(f"  - {text} (value: {value})")
            
            return None
        except Exception as e:
            print(f"取得縣市代碼時發生錯誤: {str(e)}")
            return None
    
    async def get_district_code(self, district_name: str) -> Optional[str]:
        """從頁面中取得鄉鎮代碼（等待 JavaScript 動態載入）"""
        try:
            # 等待鄉鎮選單載入（可能需要等待 JavaScript 執行）
            # 嘗試多種選擇器，因為動態載入可能需要時間
            try:
                await self.page.wait_for_selector('select[name="DistName"]', timeout=10000)
            except:
                # 如果直接等待失敗，等待一段時間讓 JavaScript 執行
                await self.page.wait_for_timeout(2000)
            
            # 檢查選單是否存在
            dist_select = await self.page.query_selector('select[name="DistName"]')
            if not dist_select:
                print("無法找到鄉鎮選單")
                return None
            
            # 取得所有鄉鎮選項
            options = await self.page.locator('select[name="DistName"] option').all()
            
            for option in options:
                text = await option.text_content()
                value = await option.get_attribute('value')
                if text and district_name in text:
                    return value
            return None
        except Exception as e:
            print(f"取得鄉鎮代碼時發生錯誤: {str(e)}")
            return None
    
    async def query_all_schools_in_county(self, county: str) -> List[Dict[str, Any]]:
        """
        查詢指定縣市的所有國小資料（不指定鄉鎮）
        
        Args:
            county: 縣市名稱（例如：花蓮縣）
        
        Returns:
            學校資料列表
        """
        schools = []
        
        try:
            # 確保瀏覽器已啟動
            if not self.page:
                await self.start()
            
            # 第一步：載入初始頁面
            await self.page.goto(self.BASE_URL, wait_until='networkidle', timeout=30000)
            
            # 等待頁面完全載入
            await self.page.wait_for_load_state('domcontentloaded')
            await self.page.wait_for_timeout(2000)  # 等待 JavaScript 執行
            
            # 先點擊「行政區域查詢」按鈕以載入縣市選單
            try:
                await self.page.click('button#ptype1, button[value="1"]')
                await self.page.wait_for_timeout(2000)  # 等待選單載入
                print("已點擊行政區域查詢按鈕")
            except Exception as e:
                print(f"點擊行政區域查詢按鈕時發生錯誤: {e}")
                # 嘗試使用 JavaScript 點擊
                await self.page.evaluate('''() => {
                    const btn = document.querySelector('button#ptype1');
                    if (btn) btn.click();
                }''')
                await self.page.wait_for_timeout(2000)
            
            # 取得縣市代碼
            city_code = await self.get_city_code(county)
            if not city_code:
                print(f"無法找到縣市代碼: {county}")
                return schools
            
            # 選擇縣市（觸發 change 事件以載入鄉鎮選單）
            try:
                await self.page.wait_for_selector('select[name="CityName"]', timeout=60000, state='visible')
                await self.page.select_option('select[name="CityName"]', city_code, timeout=60000)
            except Exception as e:
                print(f"選擇縣市時發生錯誤: {e}")
                # 嘗試使用 JavaScript 設定
                await self.page.evaluate(f'''(cityCode) => {{
                    const select = document.querySelector('select[name="CityName"]');
                    if (select) {{
                        select.value = cityCode;
                        const event = new Event('change', {{ bubbles: true }});
                        select.dispatchEvent(event);
                        return true;
                    }}
                    return false;
                }}''', city_code)
                await self.page.wait_for_timeout(2000)
            
            # 觸發 change 事件（確保事件已觸發）
            await self.page.evaluate('''() => {
                const select = document.querySelector('select[name="CityName"]');
                if (select) {
                    const event = new Event('change', { bubbles: true });
                    select.dispatchEvent(event);
                }
            }''')
            
            # 等待鄉鎮選單更新（觸發 JavaScript 事件）
            await self.page.wait_for_timeout(3000)  # 等待動態載入
            
            # 選擇「全部」或「請選擇」（值為 '0' 或空）
            try:
                # 等待鄉鎮選單出現
                await self.page.wait_for_selector('select[name="DistName"]', timeout=60000, state='visible')
                await self.page.wait_for_timeout(1000)
                # 嘗試選擇值為 '0' 的選項
                await self.page.select_option('select[name="DistName"]', '0', timeout=60000)
            except Exception as e:
                print(f"選擇鄉鎮選單時發生錯誤: {e}")
                # 如果失敗，嘗試選擇第一個選項（通常是「請選擇」）
                try:
                    first_option = await self.page.locator('select[name="DistName"] option').first
                    await first_option.click(timeout=60000)
                except Exception as e2:
                    print(f"選擇第一個選項也失敗: {e2}")
                    # 嘗試使用 JavaScript 設定
                    try:
                        await self.page.evaluate('''() => {
                            const select = document.querySelector('select[name="DistName"]');
                            if (select && select.options.length > 0) {
                                select.value = select.options[0].value;
                                const event = new Event('change', { bubbles: true });
                                select.dispatchEvent(event);
                                return true;
                            }
                            return false;
                        }''')
                        await self.page.wait_for_timeout(2000)
                    except:
                        pass
            
            # 選擇學校層級（國小）- 優先使用 radio button，如果失敗再使用 select
            try:
                # 先嘗試點擊「國小」的 radio button（更常見的方式）
                await self.page.click('input[type="radio"][value="國小"]', timeout=10000)
                await self.page.wait_for_timeout(1000)  # 等待事件觸發
                print("已選擇學校層級: 國小（使用 radio button）")
            except Exception as e:
                print(f"使用 radio button 選擇學校層級失敗: {e}，嘗試使用 select...")
                # 如果找不到 radio button，嘗試使用 select（備用方案）
                try:
                    # 等待 select 元素出現
                    await self.page.wait_for_selector('select[name="lv"]', timeout=30000, state='visible')
                    await self.page.wait_for_timeout(1000)
                    # 選擇學校層級（國小）
                    await self.page.select_option('select[name="lv"]', '1', timeout=30000)
                    print("已選擇學校層級: 國小（使用 select）")
                except Exception as e2:
                    print(f"使用 select 選擇學校層級也失敗: {e2}，嘗試使用 JavaScript...")
                    # 嘗試使用 JavaScript 直接設定值
                    try:
                        result = await self.page.evaluate('''() => {
                            // 先嘗試 radio button
                            const radio = document.querySelector('input[type="radio"][value="國小"]');
                            if (radio) {
                                radio.click();
                                return {success: true, method: 'radio'};
                            }
                            // 再嘗試 select
                            const select = document.querySelector('select[name="lv"]');
                            if (select) {
                                select.value = '1';
                                const event = new Event('change', { bubbles: true });
                                select.dispatchEvent(event);
                                return {success: true, method: 'select'};
                            }
                            return {success: false};
                        }''')
                        await self.page.wait_for_timeout(2000)
                        if result.get('success'):
                            print(f"使用 JavaScript 設定學校層級成功（方法: {result.get('method')}）")
                        else:
                            print("警告：無法設定學校層級，繼續執行...")
                    except Exception as e3:
                        print(f"使用 JavaScript 設定學校層級也失敗: {e3}，繼續執行...")
            
            # 點擊查詢按鈕（使用更精確的選擇器）
            try:
                await self.page.click('input[type="submit"][value="學校搜尋"]')
            except:
                # 如果找不到，嘗試執行 JavaScript 函數
                await self.page.evaluate('BtnClick2();')
            
            # 等待結果載入
            await self.page.wait_for_load_state('networkidle', timeout=30000)
            await self.page.wait_for_timeout(5000)  # 等待表格渲染和資料載入
            
            # 首先嘗試使用新方法取得詳細資料（點擊每個學校連結）
            print("\n嘗試使用新方法取得詳細資料（點擊學校連結）...")
            schools = await self.parse_school_data_with_details(None)
            
            # 如果新方法成功取得資料，返回結果
            if schools and any(s.get('班級數') or s.get('學生數') or s.get('教師數') for s in schools):
                print(f"成功使用新方法取得 {len(schools)} 筆包含詳細資料的學校資料")
                return schools
            
            # 如果新方法失敗或沒有取得詳細資料，使用原有的解析方法
            print("\n新方法未取得詳細資料，使用基本解析方法...")
            html = await self.page.content()
            schools = await self.parse_school_data_with_district(html)
            print(f"解析到 {len(schools)} 筆學校資料")
            
        except Exception as e:
            print(f"查詢 {county} 時發生錯誤: {str(e)}")
            import traceback
            traceback.print_exc()
        
        return schools
    
    async def query_schools(self, county: str, district: str) -> List[Dict[str, Any]]:
        """
        查詢指定縣市和鄉鎮的國小資料
        
        Args:
            county: 縣市名稱（例如：花蓮縣）
            district: 鄉鎮市區名稱（例如：花蓮市、吉安鄉）
        
        Returns:
            學校資料列表
        """
        schools = []
        
        try:
            # 確保瀏覽器已啟動
            if not self.page:
                await self.start()
            
            # 載入初始頁面
            await self.page.goto(self.BASE_URL, wait_until='networkidle', timeout=30000)
            
            # 等待頁面完全載入
            await self.page.wait_for_load_state('domcontentloaded')
            await self.page.wait_for_timeout(2000)  # 等待 JavaScript 執行
            
            # 先點擊「行政區域查詢」按鈕以載入縣市選單
            try:
                await self.page.click('button#ptype1, button[value="1"]')
                await self.page.wait_for_timeout(2000)  # 等待選單載入
                print("已點擊行政區域查詢按鈕")
            except Exception as e:
                print(f"點擊行政區域查詢按鈕時發生錯誤: {e}")
                # 嘗試使用 JavaScript 點擊
                await self.page.evaluate('''() => {
                    const btn = document.querySelector('button#ptype1');
                    if (btn) btn.click();
                }''')
                await self.page.wait_for_timeout(2000)
            
            # 取得縣市代碼
            city_code = await self.get_city_code(county)
            if not city_code:
                print(f"無法找到縣市代碼: {county}")
                return schools
            
            # 選擇縣市（觸發 change 事件以載入鄉鎮選單）
            await self.page.select_option('select[name="CityName"]', city_code)
            
            # 觸發 change 事件（某些網站需要）
            await self.page.evaluate('''() => {
                const select = document.querySelector('select[name="CityName"]');
                if (select) {
                    const event = new Event('change', { bubbles: true });
                    select.dispatchEvent(event);
                }
            }''')
            
            # 等待鄉鎮選單動態載入
            await self.page.wait_for_timeout(3000)  # 等待 JavaScript 載入鄉鎮選單
            
            # 等待鄉鎮選單有選項（除了預設的「請選擇」）
            try:
                await self.page.wait_for_function(
                    'document.querySelector("select[name=\\"DistName\\"]").options.length > 1',
                    timeout=10000
                )
            except:
                print("警告：鄉鎮選單可能未完全載入")
            
            # 取得鄉鎮代碼
            district_code = await self.get_district_code(district)
            if not district_code:
                print(f"無法找到鄉鎮代碼: {district}")
                # 如果找不到特定鄉鎮，嘗試查詢整個縣市再過濾
                return await self.query_all_schools_in_county(county)
            
            print(f"找到鄉鎮代碼: {district_code}")
            
            # 選擇鄉鎮
            try:
                await self.page.wait_for_selector('select[name="DistName"]', timeout=60000, state='visible')
                await self.page.select_option('select[name="DistName"]', district_code, timeout=60000)
                await self.page.wait_for_timeout(1000)
                print(f"已選擇鄉鎮: {district}")
            except Exception as e:
                print(f"選擇鄉鎮時發生錯誤: {e}")
                # 嘗試使用 JavaScript 設定
                await self.page.evaluate(f'''(districtCode) => {{
                    const select = document.querySelector('select[name="DistName"]');
                    if (select) {{
                        select.value = districtCode;
                        const event = new Event('change', {{ bubbles: true }});
                        select.dispatchEvent(event);
                        return true;
                    }}
                    return false;
                }}''', district_code)
                await self.page.wait_for_timeout(2000)
            
            # 選擇學校層級（國小）- 使用 radio button
            try:
                # 點擊「國小」的 radio button
                await self.page.click('input[type="radio"][value="國小"]')
                await self.page.wait_for_timeout(1000)  # 等待事件觸發
                print("已選擇學校層級: 國小")
            except Exception as e:
                print(f"選擇學校層級時發生錯誤: {e}")
                # 如果找不到 radio button，嘗試使用 select（備用方案）
                try:
                    await self.page.wait_for_selector('select[name="lv"]', timeout=60000, state='visible')
                    await self.page.select_option('select[name="lv"]', '1', timeout=60000)
                    print("已選擇學校層級: 國小（使用 select）")
                except Exception as e2:
                    print(f"使用 select 選擇學校層級也失敗: {e2}")
                    # 嘗試使用 JavaScript 設定
                    try:
                        await self.page.evaluate('''() => {
                            const select = document.querySelector('select[name="lv"]');
                            if (select) {
                                select.value = '1';
                                const event = new Event('change', { bubbles: true });
                                select.dispatchEvent(event);
                                return true;
                            }
                            return false;
                        }''')
                        await self.page.wait_for_timeout(2000)
                        print("使用 JavaScript 設定學校層級成功")
                    except Exception as e3:
                        print(f"使用 JavaScript 設定學校層級也失敗: {e3}")
            
            # 點擊查詢按鈕（使用更精確的選擇器）
            print("正在點擊查詢按鈕...")
            try:
                await self.page.click('input[type="submit"][value="學校搜尋"]')
                print("已點擊查詢按鈕")
            except Exception as e:
                print(f"點擊按鈕失敗: {e}，嘗試使用 JavaScript...")
                # 如果找不到，嘗試執行 JavaScript 函數
                await self.page.evaluate('BtnClick2();')
                print("已執行 BtnClick2()")
            
            # 等待結果載入
            print("等待結果載入...")
            await self.page.wait_for_load_state('networkidle', timeout=30000)
            await self.page.wait_for_timeout(5000)  # 等待更長時間讓資料載入
            
            # 監聽網路請求，檢查是否有 AJAX 載入資料
            ajax_data_loaded = False
            async def handle_response(response):
                nonlocal ajax_data_loaded
                url = response.url
                if 'ajax' in url.lower() or 'data' in url.lower() or 'json' in url.lower():
                    try:
                        text = await response.text()
                        if any(kw in text for kw in ['班級', '學生', '教師', '校地', '校舍', '棟']):
                            print(f"檢測到包含資料的 AJAX 回應: {url[:100]}")
                            ajax_data_loaded = True
                    except:
                        pass
            
            self.page.on('response', handle_response)
            
                # 嘗試等待特定的資料元素出現（如果有 GridView 或其他表格）
            try:
                # 等待任何包含學校名稱的元素出現（包括「國小」和「實小」）
                await self.page.wait_for_selector('table tr:has-text("國小"), div:has-text("國小"), table tr:has-text("實小"), div:has-text("實小")', timeout=10000)
                print("檢測到包含學校資料的元素")
            except:
                print("未檢測到明顯的資料表格，繼續解析...")
            
            # 取得頁面 HTML
            html = await self.page.content()
            print(f"頁面 HTML 長度: {len(html)} 字元")
            
            # 檢查 HTML 中是否包含關鍵字
            if '班級' in html or '學生' in html or '教師' in html:
                print("HTML 中包含資料關鍵字")
            else:
                print("警告：HTML 中未包含資料關鍵字（班級/學生/教師）")
            
            # 首先嘗試使用新方法取得詳細資料（點擊每個學校連結）
            print("\n嘗試使用新方法取得詳細資料（點擊學校連結）...")
            
            # 嘗試點擊 div#search 中的學校名稱來觸發詳細資料顯示
            try:
                search_div = self.page.locator('div#search').first
                if await search_div.count() > 0:
                    # 使用 JavaScript 點擊第一個包含「國小」或「實小」的元素
                    click_result = await self.page.evaluate('''() => {
                        const searchDiv = document.getElementById('search');
                        if (!searchDiv) return {found: false};
                        
                        const allElements = searchDiv.querySelectorAll('*');
                        for (let elem of allElements) {
                            if (elem.textContent && (elem.textContent.includes('國小') || elem.textContent.includes('實小'))) {
                                try {
                                    elem.click();
                                    return {found: true, text: elem.textContent.trim().substring(0, 50)};
                                } catch (e) {
                                    const event = new MouseEvent('click', {
                                        bubbles: true,
                                        cancelable: true,
                                        view: window
                                    });
                                    elem.dispatchEvent(event);
                                    return {found: true, text: elem.textContent.trim().substring(0, 50), method: 'event'};
                                }
                            }
                        }
                        return {found: false};
                    }''')
                    
                    if click_result.get('found'):
                        print(f"成功觸發點擊: {click_result.get('text')}")
                        # 等待資料載入（可能需要更長時間）
                        await self.page.wait_for_timeout(5000)
                        # 重新取得 HTML（可能已經更新）
                        html = await self.page.content()
            except Exception as e:
                print(f"嘗試點擊學校名稱時發生錯誤: {e}")
            
            schools = await self.parse_school_data_with_details(district)
            
            # 如果新方法成功取得資料，返回結果
            if schools and any(s.get('班級數') or s.get('學生數') or s.get('教師數') for s in schools):
                print(f"成功使用新方法取得 {len(schools)} 筆包含詳細資料的學校資料")
                return schools
            
            # 如果新方法失敗或沒有取得詳細資料，使用原有的解析方法
            print("\n新方法未取得詳細資料，使用基本解析方法...")
            schools = await self.parse_school_data(html, district)
            print(f"解析到 {len(schools)} 筆學校資料")
            
            # 如果解析不到資料，嘗試從頁面中提取所有包含「國小」或「實小」的文字
            if len(schools) == 0:
                print("嘗試其他方法提取資料...")
                # 尋找所有包含「國小」或「實小」的文字節點
                school_names = await self.page.evaluate('''() => {
                    const results = [];
                    const walker = document.createTreeWalker(
                        document.body,
                        NodeFilter.SHOW_TEXT,
                        null,
                        false
                    );
                    let node;
                    while (node = walker.nextNode()) {
                        if ((node.textContent.includes('國小') || node.textContent.includes('實小')) && node.textContent.trim().length < 50) {
                            results.push(node.textContent.trim());
                        }
                    }
                    return results;
                }''')
                print(f"找到 {len(school_names)} 個包含「國小」或「實小」的文字：{school_names[:10]}")
            
        except Exception as e:
            print(f"查詢 {county} {district} 時發生錯誤: {str(e)}")
            import traceback
            traceback.print_exc()
        
        return schools
    
    async def parse_school_data_with_district(self, html: str) -> List[Dict[str, Any]]:
        """
        解析 HTML 中的學校資料，並從資料中提取鄉鎮資訊
        
        Args:
            html: HTML 內容
        
        Returns:
            學校資料列表
        """
        return await self.parse_school_data(html, None)
    
    async def get_school_detail(self, school_link_element) -> Dict[str, Any]:
        """
        從學校詳細頁面取得詳細統計資料
        
        流程：
        1. 點擊學校名稱（觸發地圖彈出視窗）
        2. 點擊彈出視窗中的「學校概況」按鈕
        3. 從新開啟的視窗中提取詳細資料
        
        Args:
            school_link_element: Playwright Locator，指向學校連結或元素
        
        Returns:
            包含詳細資料的字典
        """
        detail_data = {
            '班級數': None,
            '學生數': None,
            '教師數': None,
            '校地面積': None,
            '校舍面積': None,
        }
        
        detail_page = None
        original_url = None
        
        try:
            # 記錄原始 URL
            original_url = self.page.url
            
            # 步驟1: 點擊學校名稱（這會觸發地圖上的彈出視窗）
            print(f"    步驟1: 點擊學校名稱...")
            try:
                # 先檢查元素是否可見和可點擊
                is_visible = await school_link_element.is_visible()
                if not is_visible:
                    print(f"    元素不可見，嘗試滾動到元素位置...")
                    await school_link_element.scroll_into_view_if_needed()
                    await self.page.wait_for_timeout(1000)
                
                # 嘗試點擊
                await school_link_element.click(timeout=10000)
            except Exception as e:
                print(f"    直接點擊失敗: {e}，嘗試使用 JavaScript 點擊...")
                # 如果直接點擊失敗，使用 JavaScript 點擊
                try:
                    element_handle = await school_link_element.element_handle()
                    if element_handle:
                        await self.page.evaluate('''(element) => {
                            if (element) {
                                // 嘗試多種點擊方式
                                if (element.click) {
                                    element.click();
                                } else if (element.onclick) {
                                    element.onclick();
                                } else {
                                    // 觸發 click 事件
                                    const event = new MouseEvent('click', {
                                        bubbles: true,
                                        cancelable: true,
                                        view: window
                                    });
                                    element.dispatchEvent(event);
                                }
                            }
                        }''', element_handle)
                    else:
                        # 如果無法取得 element_handle，嘗試使用文字內容尋找元素
                        school_text = await school_link_element.text_content()
                        if school_text:
                            await self.page.evaluate(f'''(schoolText) => {{
                                const searchDiv = document.getElementById('search');
                                if (!searchDiv) return false;
                                
                                const allElements = searchDiv.querySelectorAll('*');
                                for (let elem of allElements) {{
                                    if (elem.textContent && elem.textContent.includes(schoolText)) {{
                                        try {{
                                            elem.click();
                                            return true;
                                        }} catch (e) {{
                                            const event = new MouseEvent('click', {{
                                                bubbles: true,
                                                cancelable: true,
                                                view: window
                                            }});
                                            elem.dispatchEvent(event);
                                            return true;
                                        }}
                                    }}
                                }}
                                return false;
                            }}''', school_text)
                except Exception as e2:
                    print(f"    JavaScript 點擊也失敗: {e2}")
                    return detail_data
            
            # 等待彈出視窗出現（增加等待時間）
            await self.page.wait_for_timeout(3000)
            
            # 步驟2: 尋找並點擊「學校概況」按鈕
            print(f"    步驟2: 尋找「學校概況」按鈕...")
            
            # 先等待彈出視窗或相關元素出現（最多等待 10 秒）
            try:
                # 嘗試等待任何包含「學校概況」的元素出現
                await self.page.wait_for_selector(
                    'button:has-text("學校概況"), a:has-text("學校概況"), input[value*="學校概況"]',
                    timeout=10000,
                    state='visible'
                )
            except:
                # 如果等待失敗，繼續嘗試尋找
                pass
            
            # 嘗試多種選擇器來找到「學校概況」按鈕
            overview_button = None
            selectors = [
                'button:has-text("學校概況")',
                'a:has-text("學校概況")',
                'input[value*="學校概況"]',
                'button[title*="學校概況"]',
                '.popup button:has-text("學校概況")',
                '.modal button:has-text("學校概況")',
                '[class*="popup"] button:has-text("學校概況")',
                '[class*="modal"] button:has-text("學校概況")',
                'div:has-text("學校概況") button',
                'div:has-text("學校概況") a',
            ]
            
            for selector in selectors:
                try:
                    button = self.page.locator(selector).first
                    count = await button.count()
                    if count > 0:
                        # 檢查元素是否可見
                        is_visible = await button.is_visible()
                        if is_visible:
                            overview_button = button
                            print(f"    找到「學校概況」按鈕（選擇器: {selector}）")
                            break
                except:
                    continue
            
            # 如果找不到，嘗試使用 JavaScript 尋找
            if not overview_button:
                button_info = await self.page.evaluate('''() => {
                    // 尋找所有按鈕和連結
                    const allButtons = document.querySelectorAll('button, a, input[type="button"], input[type="submit"]');
                    for (let btn of allButtons) {
                        const text = btn.textContent || btn.value || btn.title || '';
                        if (text.includes('學校概況')) {
                            return {
                                found: true,
                                tag: btn.tagName,
                                text: text.trim(),
                                id: btn.id || '',
                                className: btn.className || ''
                            };
                        }
                    }
                    return {found: false};
                }''')
                
                if button_info.get('found'):
                    print(f"    使用 JavaScript 找到「學校概況」按鈕: {button_info}")
                    # 使用 JavaScript 點擊
                    await self.page.evaluate('''() => {
                        const allButtons = document.querySelectorAll('button, a, input[type="button"], input[type="submit"]');
                        for (let btn of allButtons) {
                            const text = btn.textContent || btn.value || btn.title || '';
                            if (text.includes('學校概況')) {
                                btn.click();
                                return true;
                            }
                        }
                        return false;
                    }''')
                else:
                    print(f"    警告：未找到「學校概況」按鈕")
                    return detail_data
            
            # 步驟3: 點擊「學校概況」按鈕，等待新視窗開啟或頁面更新
            if overview_button:
                print(f"    步驟3: 點擊「學校概況」按鈕...")
                # 記錄點擊前的頁面數量
                pages_before = len(self.page.context.pages)
                
                try:
                    # 嘗試等待新視窗開啟（增加到 10 秒）
                    async with self.page.context.expect_page(timeout=10000) as new_page_info:
                        await overview_button.click()
                    detail_page = await new_page_info.value
                    print(f"    新視窗已開啟")
                except asyncio.TimeoutError:
                    # 沒有新視窗，可能是在同一頁面顯示
                    print(f"    沒有新視窗，檢查是否在同一頁面顯示...")
                    # 等待頁面更新（增加等待時間）
                    await self.page.wait_for_timeout(3000)
                    # 檢查是否有新分頁（可能在等待期間開啟）
                    pages_after = len(self.page.context.pages)
                    if pages_after > pages_before:
                        detail_page = self.page.context.pages[-1]
                        print(f"    找到新視窗（延遲開啟）")
                    else:
                        detail_page = self.page
                        print(f"    使用當前頁面（資料可能已更新）")
                except Exception as e:
                    print(f"    點擊「學校概況」按鈕時發生錯誤: {e}")
                    # 嘗試使用 JavaScript 點擊
                    try:
                        await self.page.evaluate('''() => {
                            const allButtons = document.querySelectorAll('button, a, input[type="button"], input[type="submit"]');
                            for (let btn of allButtons) {
                                const text = btn.textContent || btn.value || btn.title || '';
                                if (text.includes('學校概況')) {
                                    btn.click();
                                    return true;
                                }
                            }
                            return false;
                        }''')
                        await self.page.wait_for_timeout(3000)
                        pages_after = len(self.page.context.pages)
                        if pages_after > pages_before:
                            detail_page = self.page.context.pages[-1]
                            print(f"    使用 JavaScript 點擊後找到新視窗")
                        else:
                            detail_page = self.page
                            print(f"    使用 JavaScript 點擊後使用當前頁面")
                    except Exception as e2:
                        print(f"    JavaScript 點擊也失敗: {e2}")
                        return detail_data
            else:
                # 如果已經用 JavaScript 點擊了，等待新視窗
                print(f"    步驟3: 已使用 JavaScript 點擊「學校概況」按鈕，等待新視窗...")
                # 等待一小段時間讓點擊生效
                await self.page.wait_for_timeout(2000)
                # 檢查是否有新分頁
                pages = self.page.context.pages
                if len(pages) > 1:
                    # 有新分頁，使用最新的分頁
                    detail_page = pages[-1]
                    print(f"    找到新視窗")
                else:
                    # 沒有新分頁，可能是在同一頁面顯示
                    detail_page = self.page
                    print(f"    沒有新視窗，使用當前頁面")
            
            # 等待新視窗載入
            print(f"    步驟4: 等待詳細資料頁面載入...")
            try:
                await detail_page.wait_for_load_state('networkidle', timeout=40000)
                await detail_page.wait_for_timeout(3000)  # 等待資料載入
            except Exception as e:
                print(f"    等待頁面載入超時或錯誤: {e}，繼續嘗試解析...")
                # 即使超時也繼續嘗試解析
                await detail_page.wait_for_timeout(2000)
            
            # 取得詳細頁面 HTML
            detail_html = await detail_page.content()
            detail_soup = BeautifulSoup(detail_html, 'lxml')
            
            # 解析詳細資料
            # 尋找包含統計資料的表格或區域
            detail_text = detail_soup.get_text()
            
            # 方法1: 從表格中提取資料（根據實際表格結構）
            # 根據測試結果，資料分散在多個獨立表格中：
            # - 學生數：表格3，行3的欄1（總計）
            # - 班級數：表格4，行2的欄1
            # - 教師數：表格5，行3的欄1（總計）
            # - 校地面積：表格6，行3的欄1
            # - 校舍面積：表格6，行3的欄2
            tables = detail_soup.find_all('table')
            
            for table_idx, table in enumerate(tables, 1):
                rows = table.find_all('tr')
                if len(rows) < 2:
                    continue
                
                # 取得第一行的文字來判斷這是哪個表格
                first_row_text = ' '.join([cell.get_text(strip=True) for cell in rows[0].find_all(['td', 'th'])])
                
                # 學生數表格：第一行包含「學生數（人）」，第三行有數值
                if '學生' in first_row_text and '數' in first_row_text and '人' in first_row_text:
                    if len(rows) >= 3:
                        # 第三行應該有數值，第一欄是總計
                        data_row = rows[2]
                        data_cells = data_row.find_all(['td', 'th'])
                        if len(data_cells) >= 1:
                            num = self.parse_number(data_cells[0].get_text(strip=True))
                            if num is not None:
                                detail_data['學生數'] = num
                                print(f"    找到學生數: {num} (表格{table_idx}, 行3, 欄1)")
                
                # 班級數表格：第一行的第一個欄位是「班級數（班）」，第二行有數值
                if len(rows[0].find_all(['td', 'th'])) > 0:
                    first_cell_text = rows[0].find_all(['td', 'th'])[0].get_text(strip=True)
                    if '班級' in first_cell_text and ('數' in first_cell_text or '班' in first_cell_text):
                        if len(rows) >= 2:
                            # 第二行應該有數值，第一欄是班級數
                            data_row = rows[1]
                            data_cells = data_row.find_all(['td', 'th'])
                            if len(data_cells) >= 1:
                                num = self.parse_number(data_cells[0].get_text(strip=True))
                                if num is not None:
                                    detail_data['班級數'] = num
                                    print(f"    找到班級數: {num} (表格{table_idx}, 行2, 欄1)")
                
                # 教師數表格：第一行包含「教師數（人）」，第三行有數值
                if '教師' in first_row_text and '數' in first_row_text and '人' in first_row_text:
                    if len(rows) >= 3:
                        # 第三行應該有數值，第一欄是總計
                        data_row = rows[2]
                        data_cells = data_row.find_all(['td', 'th'])
                        if len(data_cells) >= 1:
                            num = self.parse_number(data_cells[0].get_text(strip=True))
                            if num is not None:
                                detail_data['教師數'] = num
                                print(f"    找到教師數: {num} (表格{table_idx}, 行3, 欄1)")
                
                # 校地面積和校舍面積表格：第一行包含「校地及學校設施」或「校地面積」
                if '校地' in first_row_text:
                    # 尋找包含「校地面積（平方公尺）」和「校舍面積（平方公尺）」的行
                    for row_idx, row in enumerate(rows):
                        row_cells = row.find_all(['td', 'th'])
                        row_text = ' '.join([cell.get_text(strip=True) for cell in row_cells])
                        
                        # 如果這一行包含「校地面積（平方公尺）」，下一行的第一欄是校地面積
                        if '校地面積' in row_text and '平方公尺' in row_text:
                            if row_idx + 1 < len(rows):
                                data_row = rows[row_idx + 1]
                                data_cells = data_row.find_all(['td', 'th'])
                                if len(data_cells) >= 1:
                                    num = self.parse_number(data_cells[0].get_text(strip=True))
                                    if num is not None:
                                        detail_data['校地面積'] = num
                                        print(f"    找到校地面積: {num} (表格{table_idx}, 行{row_idx+2}, 欄1)")
                                
                                # 第二欄是校舍面積
                                if len(data_cells) >= 2:
                                    num = self.parse_number(data_cells[1].get_text(strip=True))
                                    if num is not None:
                                        detail_data['校舍面積'] = num
                                        print(f"    找到校舍面積: {num} (表格{table_idx}, 行{row_idx+2}, 欄2)")
                                break
            
            # 輸出解析結果總結
            found_fields = [k for k, v in detail_data.items() if v is not None]
            if found_fields:
                print(f"    已解析欄位: {', '.join(found_fields)}")
            else:
                print(f"    警告：未從表格中解析到任何資料")
            
            # 方法2: 使用正則表達式從文字中提取（改進版）
            if not any(detail_data.values()):
                # 更靈活的正則表達式模式
                patterns = {
                    '班級數': [
                        r'班級數[：:]\s*(\d+(?:,\d+)*)',
                        r'班級[：:]\s*(\d+(?:,\d+)*)',
                        r'班級數[：:]\s*(\d+)',
                    ],
                    '學生數': [
                        r'學生數[：:]\s*(\d+(?:,\d+)*)',
                        r'學生[：:]\s*(\d+(?:,\d+)*)',
                        r'學生數[：:]\s*(\d+)',
                    ],
                    '教師數': [
                        r'教師數[：:]\s*(\d+(?:,\d+)*)',
                        r'教師[：:]\s*(\d+(?:,\d+)*)',
                        r'教師數[：:]\s*(\d+)',
                    ],
                    '校地面積': [
                        r'校地面積[：:]\s*(\d+(?:,\d+)*)',
                        r'校地[：:]\s*(\d+(?:,\d+)*)',
                        r'校地面積[：:]\s*(\d+)',
                    ],
                    '校舍面積': [
                        r'校舍面積[：:]\s*(\d+(?:,\d+)*)',
                        r'校舍[：:]\s*(\d+(?:,\d+)*)',
                        r'校舍面積[：:]\s*(\d+)',
                    ],
                }
                
                for key, pattern_list in patterns.items():
                    if detail_data[key] is None:
                        for pattern in pattern_list:
                            match = re.search(pattern, detail_text)
                            if match:
                                detail_data[key] = self.parse_number(match.group(1))
                                break
            
            # 方法3: 從 div 或其他元素中提取
            if not any(detail_data.values()):
                # 尋找包含數字的 div 或 span
                for elem in detail_soup.find_all(['div', 'span', 'p', 'li']):
                    text = elem.get_text(strip=True)
                    if not text:
                        continue
                    
                    # 檢查是否包含關鍵字和數字
                    if '班級' in text and '數' in text:
                        num = re.search(r'(\d+(?:,\d+)*)', text)
                        if num and detail_data['班級數'] is None:
                            detail_data['班級數'] = self.parse_number(num.group(1))
                    
                    if '學生' in text and '數' in text:
                        num = re.search(r'(\d+(?:,\d+)*)', text)
                        if num and detail_data['學生數'] is None:
                            detail_data['學生數'] = self.parse_number(num.group(1))
                    
                    if '教師' in text and '數' in text:
                        num = re.search(r'(\d+(?:,\d+)*)', text)
                        if num and detail_data['教師數'] is None:
                            detail_data['教師數'] = self.parse_number(num.group(1))
                    
                    if '校地' in text and '面積' in text:
                        num = re.search(r'(\d+(?:,\d+)*)', text)
                        if num and detail_data['校地面積'] is None:
                            detail_data['校地面積'] = self.parse_number(num.group(1))
                    
                    if '校舍' in text and '面積' in text:
                        num = re.search(r'(\d+(?:,\d+)*)', text)
                        if num and detail_data['校舍面積'] is None:
                            detail_data['校舍面積'] = self.parse_number(num.group(1))
            
            # 輸出最終解析結果總結
            final_found_fields = [k for k, v in detail_data.items() if v is not None]
            if final_found_fields:
                print(f"    最終解析結果: {', '.join([f'{k}={v}' for k, v in detail_data.items() if v is not None])}")
            else:
                print(f"    警告：最終未解析到任何詳細資料")
            
            # 如果是新分頁，關閉它；如果是同一頁面，返回原頁面
            if detail_page and detail_page != self.page:
                # 是新分頁，關閉它
                print(f"    關閉詳細資料視窗...")
                await detail_page.close()
                # 切換回原頁面（確保焦點在原頁面）
                await self.page.bring_to_front()
                await self.page.wait_for_timeout(1000)
                
                # 嘗試關閉可能打開的彈出視窗（如果有）
                try:
                    # 尋找關閉按鈕（常見的彈出視窗關閉按鈕）
                    close_selectors = [
                        'button.close',
                        '.modal .close',
                        '[aria-label*="關閉"]',
                        '[aria-label*="close"]',
                        'button:has-text("關閉")',
                        'button:has-text("×")',
                    ]
                    for selector in close_selectors:
                        try:
                            close_btn = self.page.locator(selector).first
                            if await close_btn.count() > 0 and await close_btn.is_visible():
                                await close_btn.click()
                                await self.page.wait_for_timeout(500)
                                print(f"    已關閉彈出視窗")
                                break
                        except:
                            continue
                except:
                    pass
            elif original_url and self.page.url != original_url:
                # 如果是同一頁面但 URL 改變了，返回原頁面
                print(f"    返回原始搜尋結果頁面...")
                await self.page.goto(original_url, wait_until='networkidle', timeout=30000)
                await self.page.wait_for_timeout(2000)
            
            print(f"    詳細資料取得完成")
            
        except asyncio.TimeoutError:
            print(f"  取得詳細資料超時（可能連結不是有效的詳細頁面）")
            # 嘗試清理頁面狀態
            try:
                if detail_page and detail_page != self.page:
                    await detail_page.close()
                    await self.page.bring_to_front()
                    await self.page.wait_for_timeout(1000)
            except:
                pass
        except Exception as e:
            print(f"  取得學校詳細資料時發生錯誤: {str(e)}")
            import traceback
            traceback.print_exc()
            # 嘗試返回原頁面
            try:
                if detail_page and detail_page != self.page:
                    await detail_page.close()
                    await self.page.bring_to_front()
                    await self.page.wait_for_timeout(1000)
                elif original_url and self.page.url != original_url:
                    await self.page.goto(original_url, wait_until='networkidle', timeout=30000)
                    await self.page.wait_for_timeout(2000)
            except:
                pass
        finally:
            # 確保頁面狀態正確（嘗試關閉所有彈出視窗）
            try:
                # 檢查是否有打開的新分頁需要關閉
                if self.page:
                    pages = self.page.context.pages
                    if len(pages) > 1:
                        # 關閉除主頁面外的所有分頁
                        for p in pages:
                            if p != self.page and not p.is_closed():
                                await p.close()
                        await self.page.bring_to_front()
            except:
                pass
        
        return detail_data
    
    async def _get_school_detail_from_popup(self) -> Dict[str, Any]:
        """
        從彈出視窗中點擊「學校概況」並取得詳細資料
        這個方法假設已經點擊了學校名稱，彈出視窗已經出現
        
        Returns:
            包含詳細資料的字典
        """
        detail_data = {
            '班級數': None,
            '學生數': None,
            '教師數': None,
            '校地面積': None,
            '校舍面積': None,
        }
        
        try:
            # 尋找並點擊「學校概況」按鈕
            print(f"    尋找「學校概況」按鈕...")
            
            # 嘗試多種選擇器
            overview_button = None
            selectors = [
                'button:has-text("學校概況")',
                'a:has-text("學校概況")',
                'input[value*="學校概況"]',
                'button[title*="學校概況"]',
                '.popup button:has-text("學校概況")',
                '.modal button:has-text("學校概況")',
                '[class*="popup"] button:has-text("學校概況")',
                '[class*="modal"] button:has-text("學校概況")',
            ]
            
            for selector in selectors:
                try:
                    button = self.page.locator(selector).first
                    if await button.count() > 0:
                        overview_button = button
                        print(f"    找到「學校概況」按鈕（選擇器: {selector}）")
                        break
                except:
                    continue
            
            # 如果找不到，使用 JavaScript 尋找並點擊
            if not overview_button:
                button_clicked = await self.page.evaluate('''() => {
                    const allButtons = document.querySelectorAll('button, a, input[type="button"], input[type="submit"]');
                    for (let btn of allButtons) {
                        const text = btn.textContent || btn.value || btn.title || '';
                        if (text.includes('學校概況')) {
                            btn.click();
                            return true;
                        }
                    }
                    return false;
                }''')
                
                if not button_clicked:
                    print(f"    警告：未找到「學校概況」按鈕")
                    return detail_data
                
                # 等待新視窗開啟
                await self.page.wait_for_timeout(1000)
                pages = self.page.context.pages
                if len(pages) > 1:
                    detail_page = pages[-1]
                else:
                    detail_page = self.page
            else:
                # 點擊按鈕並等待新視窗開啟
                try:
                    async with self.page.context.expect_page(timeout=15000) as new_page_info:
                        await overview_button.click()
                    detail_page = await new_page_info.value
                except asyncio.TimeoutError:
                    print(f"    等待新視窗超時")
                    pages = self.page.context.pages
                    if len(pages) > 1:
                        detail_page = pages[-1]
                    else:
                        detail_page = self.page
            
            await detail_page.wait_for_load_state('networkidle', timeout=30000)
            await detail_page.wait_for_timeout(3000)
            
            # 取得詳細頁面 HTML
            detail_html = await detail_page.content()
            detail_soup = BeautifulSoup(detail_html, 'lxml')
            
            # 解析詳細資料（使用與 get_school_detail 相同的邏輯）
            detail_text = detail_soup.get_text()
            
            # 從表格中提取資料（使用與 get_school_detail 相同的邏輯）
            tables = detail_soup.find_all('table')
            
            for table_idx, table in enumerate(tables, 1):
                rows = table.find_all('tr')
                if len(rows) < 2:
                    continue
                
                # 取得第一行的文字來判斷這是哪個表格
                first_row_text = ' '.join([cell.get_text(strip=True) for cell in rows[0].find_all(['td', 'th'])])
                
                # 學生數表格：第一行包含「學生數（人）」，第三行有數值
                if '學生' in first_row_text and '數' in first_row_text and '人' in first_row_text:
                    if len(rows) >= 3:
                        data_row = rows[2]
                        data_cells = data_row.find_all(['td', 'th'])
                        if len(data_cells) >= 1:
                            num = self.parse_number(data_cells[0].get_text(strip=True))
                            if num is not None:
                                detail_data['學生數'] = num
                
                # 班級數表格：第一行的第一個欄位是「班級數（班）」，第二行有數值
                if len(rows[0].find_all(['td', 'th'])) > 0:
                    first_cell_text = rows[0].find_all(['td', 'th'])[0].get_text(strip=True)
                    if '班級' in first_cell_text and ('數' in first_cell_text or '班' in first_cell_text):
                        if len(rows) >= 2:
                            data_row = rows[1]
                            data_cells = data_row.find_all(['td', 'th'])
                            if len(data_cells) >= 1:
                                num = self.parse_number(data_cells[0].get_text(strip=True))
                                if num is not None:
                                    detail_data['班級數'] = num
                
                # 教師數表格：第一行包含「教師數（人）」，第三行有數值
                if '教師' in first_row_text and '數' in first_row_text and '人' in first_row_text:
                    if len(rows) >= 3:
                        data_row = rows[2]
                        data_cells = data_row.find_all(['td', 'th'])
                        if len(data_cells) >= 1:
                            num = self.parse_number(data_cells[0].get_text(strip=True))
                            if num is not None:
                                detail_data['教師數'] = num
                
                # 校地面積和校舍面積表格
                if '校地' in first_row_text:
                    for row_idx, row in enumerate(rows):
                        row_cells = row.find_all(['td', 'th'])
                        row_text = ' '.join([cell.get_text(strip=True) for cell in row_cells])
                        
                        if '校地面積' in row_text and '平方公尺' in row_text:
                            if row_idx + 1 < len(rows):
                                data_row = rows[row_idx + 1]
                                data_cells = data_row.find_all(['td', 'th'])
                                if len(data_cells) >= 1:
                                    num = self.parse_number(data_cells[0].get_text(strip=True))
                                    if num is not None:
                                        detail_data['校地面積'] = num
                                if len(data_cells) >= 2:
                                    num = self.parse_number(data_cells[1].get_text(strip=True))
                                    if num is not None:
                                        detail_data['校舍面積'] = num
                                break
            
            # 如果沒有從表格取得，使用正則表達式
            if not any(detail_data.values()):
                patterns = {
                    '班級數': [r'班級數[：:]\s*(\d+(?:,\d+)*)', r'班級[：:]\s*(\d+(?:,\d+)*)'],
                    '學生數': [r'學生數[：:]\s*(\d+(?:,\d+)*)', r'學生[：:]\s*(\d+(?:,\d+)*)'],
                    '教師數': [r'教師數[：:]\s*(\d+(?:,\d+)*)', r'教師[：:]\s*(\d+(?:,\d+)*)'],
                    '校地面積': [r'校地面積[：:]\s*(\d+(?:,\d+)*)', r'校地[：:]\s*(\d+(?:,\d+)*)'],
                    '校舍面積': [r'校舍面積[：:]\s*(\d+(?:,\d+)*)', r'校舍[：:]\s*(\d+(?:,\d+)*)'],
                }
                
                for key, pattern_list in patterns.items():
                    if detail_data[key] is None:
                        for pattern in pattern_list:
                            match = re.search(pattern, detail_text)
                            if match:
                                detail_data[key] = self.parse_number(match.group(1))
                                break
            
            # 輸出最終解析結果總結
            final_found_fields = [k for k, v in detail_data.items() if v is not None]
            if final_found_fields:
                print(f"    最終解析結果: {', '.join([f'{k}={v}' for k, v in detail_data.items() if v is not None])}")
            else:
                print(f"    警告：最終未解析到任何詳細資料")
            
            # 關閉詳細頁面（如果是新分頁）
            if detail_page != self.page:
                print(f"    關閉詳細資料視窗...")
                await detail_page.close()
                await self.page.bring_to_front()
                await self.page.wait_for_timeout(1000)
            
            print(f"    詳細資料取得完成")
                
        except asyncio.TimeoutError:
            print(f"    取得詳細資料超時")
            # 嘗試清理頁面狀態
            try:
                if detail_page != self.page:
                    await detail_page.close()
                    await self.page.bring_to_front()
                    await self.page.wait_for_timeout(1000)
            except:
                pass
        except Exception as e:
            print(f"    取得詳細資料時發生錯誤: {str(e)}")
            import traceback
            traceback.print_exc()
            # 嘗試清理頁面狀態
            try:
                if detail_page != self.page:
                    await detail_page.close()
                    await self.page.bring_to_front()
                    await self.page.wait_for_timeout(1000)
            except:
                pass
        
        return detail_data
    
    async def parse_school_data_with_details(self, district: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        解析搜尋結果並取得每個學校的詳細資料
        
        Args:
            district: 鄉鎮市區名稱
        
        Returns:
            包含詳細資料的學校資料列表
        """
        schools = []
        
        if not self.page:
            print("錯誤：頁面未初始化")
            return schools
        
        try:
            # 先嘗試從搜尋結果頁面直接提取資料（改進的解析方法）
            print("嘗試從搜尋結果頁面直接提取資料...")
            html = await self.page.content()
            schools = await self.parse_school_data(html, district)
            
            # 檢查是否已經取得詳細資料
            has_details = any(
                school.get('班級數') or school.get('學生數') or school.get('教師數') 
                for school in schools
            )
            
            if has_details:
                print(f"成功從搜尋結果頁面提取到 {len(schools)} 筆包含詳細資料的學校資料")
                return schools
            
            # 如果搜尋結果頁面沒有詳細資料，嘗試點擊進入詳細頁面
            print("搜尋結果頁面沒有詳細資料，嘗試點擊進入詳細頁面...")
            soup = BeautifulSoup(html, 'lxml')
            
            # 取得學校連結和基本資訊
            school_elements = []
            
            # 方法1: 從 div#search 中提取學校名稱，然後點擊
            try:
                # 從 div#search 中解析學校名稱
                search_div = soup.find('div', {'id': 'search'})
                if search_div:
                    text = search_div.get_text()
                    # 解析格式：學校名稱 花蓮縣[鄉鎮市區][類型]
                    # 改進正則表達式以匹配所有鄉鎮（不只是花蓮市）
                    # 也匹配「國立東華大學附設實小」這樣的學校名稱
                    pattern = r'([^\s]+(?:\s+[^\s]+)*?)\s+花蓮縣([^\[]+)\[([^\]]+)\]'
                    matches = re.findall(pattern, text)
                    
                    # 如果沒有匹配到，嘗試更寬鬆的模式
                    if not matches:
                        # 嘗試匹配：學校名稱花蓮縣鄉鎮[類型]（沒有空格的情況）
                        pattern2 = r'([^縣]+?)(花蓮縣)([^\[]+)\[([^\]]+)\]'
                        matches2 = re.findall(pattern2, text)
                        if matches2:
                            # 轉換格式以匹配原有的處理邏輯（排除多餘的「花蓮縣」組）
                            matches = [(m[0], m[2], m[3]) for m in matches2]
                    
                    print(f"從 div#search 中找到 {len(matches)} 個學校")
                    
                    # 為每個學校創建可點擊的元素定位器
                    for school_name, school_district, school_type in matches:
                        try:
                            # 如果指定了 district，過濾匹配的
                            if district and district not in school_district:
                                continue
                            
                            # 嘗試多種方式找到可點擊的元素
                            # 方法1: 直接點擊包含學校名稱的元素
                            elem = self.page.locator(f'text="{school_name}"').first
                            if await elem.count() > 0:
                                school_elements.append(elem)
                                continue
                            
                            # 方法2: 使用 JavaScript 找到包含學校名稱的元素並點擊
                            # 這會在 get_school_detail 中處理
                            # 先創建一個標記，表示這個學校需要處理
                            school_elements.append(None)  # 用 None 標記，稍後用 JavaScript 處理
                            
                        except:
                            pass
                
                # 方法2: 使用 Playwright 直接尋找可點擊的學校連結
                if not school_elements:
                    # 改進選擇器，優先選擇真正的連結元素，避免選擇 label
                    # 包括「國小」和「實小」
                    selectors = [
                        'div#search a:has-text("國小")',
                        'div#search a:has-text("實小")',
                        'div#search *:has-text("國小"):not(label)',
                        'div#search *:has-text("實小"):not(label)',
                        'a:has-text("國小")',
                        'a:has-text("實小")',
                        'tr:has-text("國小") a',
                        'tr:has-text("實小") a',
                        'table a:has-text("國小")',
                        'table a:has-text("實小")',
                        'td a:has-text("國小")',
                        'td a:has-text("實小")',
                        'div#search *[onclick*="國小"]',
                        'div#search *[onclick*="實小"]',
                        'div#search *[onclick]:has-text("國小")',
                        'div#search *[onclick]:has-text("實小")',
                    ]
                    
                    for selector in selectors:
                        try:
                            clickable_schools = await self.page.locator(selector).all()
                            if clickable_schools:
                                # 過濾掉 label 元素，優先選擇可點擊的元素
                                filtered_schools = []
                                for school in clickable_schools:
                                    try:
                                        tag_name = await school.evaluate('el => el.tagName.toLowerCase()')
                                        # 跳過 label 元素，除非它是可點擊的
                                        if tag_name == 'label':
                                            # 檢查 label 是否有關聯的 input 或是否有 onclick
                                            has_onclick = await school.evaluate('el => !!el.onclick || el.hasAttribute("onclick")')
                                            if not has_onclick:
                                                continue
                                        filtered_schools.append(school)
                                    except:
                                        # 如果無法判斷，保留該元素
                                        filtered_schools.append(school)
                                
                                if filtered_schools:
                                    print(f"使用選擇器 '{selector}' 找到 {len(filtered_schools)} 個學校元素")
                                    school_elements = filtered_schools
                                    break
                        except:
                            continue
                
            except Exception as e:
                print(f"尋找學校連結時發生錯誤: {str(e)}")
                import traceback
                traceback.print_exc()
            
            # 如果找不到可點擊的連結，返回基本資料
            if not school_elements:
                print("未找到可點擊的學校連結，返回基本資料...")
                return schools
            
            print(f"找到 {len(school_elements)} 個學校連結，開始取得詳細資料...")
            
            # 去重（避免同一個學校被重複處理）
            unique_schools = {}
            for elem in school_elements:
                try:
                    school_name = await elem.text_content()
                    if school_name:
                        school_name = school_name.strip()
                        # 清理學校名稱，移除多餘的空白和特殊字元
                        school_name = re.sub(r'\s+', ' ', school_name)
                        # 如果學校名稱只是「國小」，嘗試從父元素或附近元素取得完整名稱
                        if school_name == '國小' or len(school_name) < 3:
                            # 嘗試取得更完整的文字
                            try:
                                parent_text = await elem.evaluate(r'''(el) => {
                                    // 嘗試從父元素取得文字
                                    let parent = el.parentElement;
                                    if (parent) {
                                        let text = parent.textContent || parent.innerText || '';
                                        // 尋找包含「國小」或「實小」的完整學校名稱
                                        let match = text.match(/([^\s]+(?:\s+[^\s]+)*?(?:國小|實小))/);
                                        if (match) return match[1];
                                    }
                                    return el.textContent || el.innerText || '';
                                }''')
                                if parent_text and len(parent_text) > len(school_name):
                                    school_name = parent_text.strip()
                                    school_name = re.sub(r'\s+', ' ', school_name)
                            except:
                                pass
                        
                        # 只保留有效的學校名稱（至少包含「國小」或「實小」）
                        if ('國小' in school_name or '實小' in school_name) and school_name not in unique_schools:
                            unique_schools[school_name] = elem
                except Exception as e:
                    print(f"  提取學校名稱時發生錯誤: {e}")
                    continue
            
            print(f"去重後共有 {len(unique_schools)} 個學校")
            print(f"開始逐一處理學校詳細資料...\n")
            
            # 為每個學校取得詳細資料
            for i, (school_name, elem) in enumerate(unique_schools.items(), 1):
                try:
                    print(f"正在處理 ({i}/{len(unique_schools)}): {school_name}")
                    
                    # 先檢查是否已經在基本資料中
                    existing_school = None
                    for school in schools:
                        if school.get('學校名稱') == school_name:
                            existing_school = school
                            break
                    
                    if existing_school:
                        school_data = existing_school
                    else:
                        # 取得基本資料
                        school_data = {
                            '鄉鎮市區': district or '未知',
                            '學校名稱': school_name,
                            '班級數': None,
                            '學生數': None,
                            '教師數': None,
                            '校地面積': None,
                            '校舍面積': None,
                        }
                    
                    # 如果還沒有詳細資料，點擊取得
                    if not (school_data.get('班級數') or school_data.get('學生數') or school_data.get('教師數')):
                        try:
                            # 如果 elem 是 None，使用 JavaScript 點擊學校名稱
                            if elem is None:
                                # 使用 JavaScript 找到並點擊包含學校名稱的元素
                                clicked = await self.page.evaluate(f'''(schoolName) => {{
                                    const searchDiv = document.getElementById('search');
                                    if (!searchDiv) return false;
                                    
                                    const allElements = searchDiv.querySelectorAll('*');
                                    for (let elem of allElements) {{
                                        if (elem.textContent && elem.textContent.includes(schoolName)) {{
                                            try {{
                                                elem.click();
                                                return true;
                                            }} catch (e) {{
                                                const event = new MouseEvent('click', {{
                                                    bubbles: true,
                                                    cancelable: true,
                                                    view: window
                                                }});
                                                elem.dispatchEvent(event);
                                                return true;
                                            }}
                                        }}
                                    }}
                                    return false;
                                }}''', school_name)
                                
                                if clicked:
                                    # 等待彈出視窗出現
                                    await self.page.wait_for_timeout(2000)
                                    # 創建一個虛擬元素用於 get_school_detail
                                    # 實際上我們會直接處理點擊「學校概況」的邏輯
                                    detail_data = await self._get_school_detail_from_popup()
                                else:
                                    print(f"  無法點擊學校名稱")
                                    detail_data = {}
                            else:
                                detail_data = await self.get_school_detail(elem)
                            
                            school_data.update(detail_data)
                            
                            # 統計成功取得的欄位
                            success_fields = [k for k, v in detail_data.items() if v is not None]
                            if success_fields:
                                print(f"  ✓ 成功取得詳細資料: {len(success_fields)} 個欄位 ({', '.join(success_fields)})")
                            else:
                                print(f"  ⚠ 未取得任何詳細資料")
                        except Exception as e:
                            print(f"  ✗ 取得詳細資料失敗: {str(e)}")
                            import traceback
                            traceback.print_exc()
                    
                    # 如果不在列表中，加入列表
                    if not existing_school:
                        schools.append(school_data)
                    
                    print(f"  完成處理: {school_name}")
                    
                    # 在處理下一個學校前，等待一下並確保頁面狀態正確
                    await self.page.wait_for_timeout(1500)
                    
                    # 確保我們還在搜尋結果頁面（不是在其他頁面）
                    try:
                        # 檢查是否有彈出視窗需要關閉
                        close_selectors = [
                            'button.close',
                            '.modal .close',
                            '[aria-label*="關閉"]',
                            'button:has-text("×")',
                        ]
                        for selector in close_selectors:
                            try:
                                close_btn = self.page.locator(selector).first
                                if await close_btn.count() > 0 and await close_btn.is_visible():
                                    await close_btn.click()
                                    await self.page.wait_for_timeout(500)
                                    break
                            except:
                                continue
                    except:
                        pass
                    
                except Exception as e:
                    print(f"  ✗ 處理學校 {school_name} 時發生錯誤: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    # 確保頁面狀態正確，以便繼續處理下一個學校
                    try:
                        # 關閉可能打開的新分頁
                        pages = self.page.context.pages
                        if len(pages) > 1:
                            for p in pages:
                                if p != self.page and not p.is_closed():
                                    await p.close()
                            await self.page.bring_to_front()
                            await self.page.wait_for_timeout(1000)
                    except:
                        pass
                    continue
            
            print(f"\n所有學校處理完成！共處理 {len(unique_schools)} 個學校，成功取得 {len([s for s in schools if any([s.get('班級數'), s.get('學生數'), s.get('教師數')])])} 個學校的詳細資料")
            
        except Exception as e:
            print(f"解析學校資料時發生錯誤: {str(e)}")
            import traceback
            traceback.print_exc()
        
        return schools
    
    async def parse_school_data(self, html: str, district: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        解析 HTML 中的學校資料
        
        Args:
            html: HTML 內容
            district: 鄉鎮市區名稱
        
        Returns:
            學校資料列表
        """
        schools = []
        soup = BeautifulSoup(html, 'lxml')
        
        # 方法1: 檢查 div#search（這是實際的資料容器）
        search_div = soup.find('div', {'id': 'search'})
        if search_div:
            text = search_div.get_text()
            # 格式似乎是：學校名稱 縣市鄉鎮[類型]學校名稱 縣市鄉鎮[類型]...
            # 使用正則表達式解析
            # 模式：學校名稱（可能包含空格，包括「附設實小」等） 縣市 鄉鎮[類型]
            # 改進正則表達式以匹配「國立東華大學附設實小」這樣的學校名稱
            pattern = r'([^\s]+(?:\s+[^\s]+)*?)\s+([^縣市]+縣市?)([^\[]+)\[([^\]]+)\]'
            matches = re.findall(pattern, text)
            
            # 如果沒有匹配到，嘗試更寬鬆的模式（可能學校名稱中沒有空格）
            if not matches:
                # 嘗試匹配：學校名稱花蓮縣鄉鎮[類型]（沒有空格的情況）
                pattern2 = r'([^縣]+?)(花蓮縣)([^\[]+)\[([^\]]+)\]'
                matches = re.findall(pattern2, text)
            
            for match in matches:
                school_name = match[0].strip()
                county = match[1].strip()
                dist = match[2].strip()
                school_type = match[3].strip()
                
                # 如果指定了 district，過濾匹配的
                if district and district not in dist:
                    continue
                
                school_data = {
                    '鄉鎮市區': dist or district or '未知',
                    '學校名稱': school_name,
                    '學校類型': school_type,
                    '班級數': None,  # 這些資料可能不在這個視圖中
                    '學生數': None,
                    '教師數': None,
                    '校地面積': None,
                    '校舍面積': None,
                }
                schools.append(school_data)
            
            if schools:
                return schools
        
        # 方法2: 尋找資料表格 - 嘗試多種可能的選擇器
        table = None
        
        # 方法2.1: 尋找有特定 ID 的表格
        table = soup.find('table', {'id': re.compile(r'.*GridView.*|.*gv.*|.*Grid.*', re.I)})
        
        # 方法2.2: 尋找包含資料的表格
        if not table:
            tables = soup.find_all('table')
            for t in tables:
                rows = t.find_all('tr')
                if len(rows) > 1:  # 至少有標題列和資料列
                    # 檢查是否包含學校相關的關鍵字
                    text = t.get_text()
                    if any(keyword in text for keyword in ['學校', '班級', '學生', '教師']):
                        table = t
                        break
        
        # 方法2.3: 尋找任何有資料的表格
        if not table:
            tables = soup.find_all('table')
            for t in tables:
                rows = t.find_all('tr')
                if len(rows) > 2:  # 至少有幾行資料
                    table = t
                    break
        
        if table:
            rows = table.find_all('tr')
            
            # 先找出標題行，確定欄位順序
            header_row = None
            header_indices = {
                '鄉鎮市區': None,
                '學校名稱': None,
                '班級數': None,
                '學生數': None,
                '教師數': None,
                '校地面積': None,
                '校舍面積': None,
            }
            
            # 尋找標題行
            for row in rows[:3]:  # 通常標題在前三行
                cells = row.find_all(['td', 'th'])
                cell_texts = [self.clean_text(cell.get_text()) for cell in cells]
                
                # 檢查是否包含關鍵字
                has_header_keywords = any(keyword in ' '.join(cell_texts) for keyword in ['學校', '班級', '學生', '教師', '校地', '校舍', '棟'])
                
                if has_header_keywords:
                    header_row = row
                    # 確定每個欄位的位置
                    for idx, text in enumerate(cell_texts):
                        text_lower = text.lower()
                        if '學校' in text and '名稱' in text:
                            header_indices['學校名稱'] = idx
                        elif '鄉鎮' in text or '市區' in text or '行政區' in text:
                            header_indices['鄉鎮市區'] = idx
                        elif '班級' in text and '數' in text:
                            header_indices['班級數'] = idx
                        elif '學生' in text and '數' in text:
                            header_indices['學生數'] = idx
                        elif '教師' in text and '數' in text:
                            header_indices['教師數'] = idx
                        elif '校地' in text and '面積' in text:
                            header_indices['校地面積'] = idx
                        elif '校舍' in text and '面積' in text:
                            header_indices['校舍面積'] = idx
                    break
            
            # 如果找到標題行，從下一行開始解析資料
            if header_row:
                header_index = rows.index(header_row)
                data_rows = rows[header_index + 1:]
            else:
                # 如果找不到標題行，跳過第一行
                data_rows = rows[1:] if len(rows) > 1 else rows
            
            for row in data_rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) < 2:  # 至少要有幾個欄位
                    continue
                    
                try:
                    cell_texts = [self.clean_text(cell.get_text()) for cell in cells]
                    
                    # 過濾空行
                    if not any(cell_texts):
                        continue
                    
                    # 如果有標題行，使用標題行的索引來提取資料
                    if header_row and any(header_indices.values()):
                        school_data = {
                            '鄉鎮市區': district or '未知',
                            '學校名稱': None,
                            '班級數': None,
                            '學生數': None,
                            '教師數': None,
                            '校地面積': None,
                            '校舍面積': None,
                        }
                        
                        # 根據標題行的索引提取資料
                        if header_indices['學校名稱'] is not None and header_indices['學校名稱'] < len(cell_texts):
                            school_data['學校名稱'] = cell_texts[header_indices['學校名稱']]
                        
                        if header_indices['鄉鎮市區'] is not None and header_indices['鄉鎮市區'] < len(cell_texts):
                            district_text = cell_texts[header_indices['鄉鎮市區']]
                            if district_text:
                                school_data['鄉鎮市區'] = district_text
                        
                        for field in ['班級數', '學生數', '教師數', '校地面積', '校舍面積']:
                            if header_indices[field] is not None and header_indices[field] < len(cell_texts):
                                value = cell_texts[header_indices[field]]
                                school_data[field] = self.parse_number(value)
                        
                        # 如果成功提取到學校名稱，加入列表
                        if school_data['學校名稱']:
                            schools.append(school_data)
                    else:
                        # 如果沒有標題行，使用原有的邏輯
                        # 嘗試識別學校名稱（通常是第一個非空欄位，或包含「國小」或「實小」的欄位）
                        school_name = ''
                        for text in cell_texts:
                            if '國小' in text or '實小' in text or ('學校' in text and len(text) < 50):
                                school_name = text
                                break
                        if not school_name and cell_texts[0]:
                            school_name = cell_texts[0]
                        
                        # 嘗試提取數字欄位
                        numbers = []
                        for text in cell_texts:
                            num = self.parse_number(text)
                            if num is not None:
                                numbers.append(num)
                        
                        if school_name:
                            # 嘗試從資料中提取鄉鎮資訊
                            extracted_district = district
                            if not extracted_district:
                                # 從學校名稱或其他欄位推斷鄉鎮
                                for text in cell_texts:
                                    if any(d in text for d in ['花蓮市', '吉安鄉', '新城鄉', '太魯閣', '秀林', '壽豐', '鳳林', '光復', '豐濱', '瑞穗', '玉里', '富里', '卓溪', '萬榮']):
                                        # 提取鄉鎮名稱
                                        for d_name in ['花蓮市', '吉安鄉', '新城鄉', '秀林鄉', '壽豐鄉', '鳳林鎮', '光復鄉', '豐濱鄉', '瑞穗鄉', '玉里鎮', '富里鄉', '卓溪鄉', '萬榮鄉']:
                                            if d_name in text:
                                                extracted_district = d_name
                                                break
                                        break
                            
                            # 嘗試根據常見的表格順序來分配數字
                            # 通常順序是：學校名稱、鄉鎮、班級數、學生數、教師數、校地面積、校舍面積
                            school_data = {
                                '鄉鎮市區': extracted_district or '未知',
                                '學校名稱': school_name,
                                '班級數': None,
                                '學生數': None,
                                '教師數': None,
                                '校地面積': None,
                                '校舍面積': None,
                            }
                            
                            # 如果數字數量合理，嘗試按順序分配
                            if len(numbers) >= 3:
                                # 假設前三個數字是班級數、學生數、教師數
                                school_data['班級數'] = numbers[0]
                                school_data['學生數'] = numbers[1]
                                school_data['教師數'] = numbers[2]
                                
                                if len(numbers) >= 4:
                                    school_data['校地面積'] = numbers[3]
                                if len(numbers) >= 5:
                                    school_data['校舍面積'] = numbers[4]
                            
                            schools.append(school_data)
                except Exception as e:
                    print(f"解析學校資料時發生錯誤: {str(e)}")
                    continue
        else:
            # 如果找不到表格，嘗試從其他元素提取
            print("警告：未找到資料表格，嘗試其他方法...")
            # 可以嘗試從 div 或其他元素提取資料
        
        return schools
    
    def clean_text(self, text: str) -> str:
        """清理文字內容"""
        if not text:
            return ''
        return text.strip().replace('\n', '').replace('\r', '').replace('\t', '')
    
    def parse_number(self, text: str) -> Optional[int]:
        """解析數字"""
        if not text:
            return None
        
        # 移除逗號和其他非數字字元（保留負號）
        cleaned = re.sub(r'[^\d-]', '', str(text))
        
        try:
            return int(cleaned) if cleaned else None
        except ValueError:
            return None
    
    def normalize_school_name(self, school_name: str) -> str:
        """
        標準化學校名稱，提取核心部分（去掉縣市鄉鎮和類型標記）
        
        Args:
            school_name: 原始學校名稱（可能包含「花蓮縣花蓮市[縣市立]」等後綴）
        
        Returns:
            標準化後的學校名稱（核心部分）
        """
        if not school_name:
            return ''
        
        # 移除常見的後綴模式：
        # - 「花蓮縣花蓮市[縣市立]」
        # - 「花蓮縣吉安鄉[縣市立]」
        # - 「花蓮縣[鄉鎮市區][類型]」
        # 模式：學校名稱 花蓮縣[鄉鎮市區][類型]
        pattern = r'^(.+?)\s+花蓮縣[^\[]+\[[^\]]+\]$'
        match = re.match(pattern, school_name)
        if match:
            # 提取核心學校名稱
            return match.group(1).strip()
        
        # 如果沒有匹配，返回原始名稱（可能已經是核心名稱）
        return school_name.strip()
    
    def merge_school_data(self, schools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        合併重複的學校資料
        
        如果同一個學校出現多次（例如「私立海星國小」和「私立海星國小 花蓮縣花蓮市[私立]」），
        合併它們的資料，保留有詳細資料的版本。
        
        Args:
            schools: 學校資料列表
        
        Returns:
            合併後的學校資料列表
        """
        # 使用標準化後的學校名稱作為鍵
        merged_schools = {}
        
        for school in schools:
            school_name = school.get('學校名稱', '')
            if not school_name:
                continue
            
            # 標準化學校名稱
            normalized_name = self.normalize_school_name(school_name)
            
            # 檢查是否已有這個學校
            if normalized_name in merged_schools:
                existing_school = merged_schools[normalized_name]
                
                # 檢查哪個版本有更多詳細資料
                existing_has_data = any([
                    existing_school.get('班級數'),
                    existing_school.get('學生數'),
                    existing_school.get('教師數'),
                    existing_school.get('校地面積'),
                    existing_school.get('校舍面積'),
                ])
                
                current_has_data = any([
                    school.get('班級數'),
                    school.get('學生數'),
                    school.get('教師數'),
                    school.get('校地面積'),
                    school.get('校舍面積'),
                ])
                
                # 如果當前版本有資料而現有版本沒有，或當前版本資料更完整，則替換
                if current_has_data and not existing_has_data:
                    # 使用當前版本，但保留標準化的名稱
                    school['學校名稱'] = normalized_name
                    merged_schools[normalized_name] = school
                elif current_has_data and existing_has_data:
                    # 兩個版本都有資料，合併資料（優先使用非 None 的值）
                    for field in ['班級數', '學生數', '教師數', '校地面積', '校舍面積']:
                        if existing_school.get(field) is None and school.get(field) is not None:
                            existing_school[field] = school.get(field)
                    # 確保使用標準化的名稱
                    existing_school['學校名稱'] = normalized_name
                elif not current_has_data and existing_has_data:
                    # 現有版本有資料，保持不變
                    existing_school['學校名稱'] = normalized_name
                else:
                    # 兩個版本都沒有資料，使用較完整的學校名稱（保留原始完整名稱）
                    if len(school_name) > len(existing_school.get('學校名稱', '')):
                        school['學校名稱'] = normalized_name
                        merged_schools[normalized_name] = school
                    else:
                        existing_school['學校名稱'] = normalized_name
            else:
                # 新學校，加入字典
                # 使用標準化的名稱
                school['學校名稱'] = normalized_name
                merged_schools[normalized_name] = school
        
        return list(merged_schools.values())
    
    async def get_all_schools(self) -> List[Dict[str, Any]]:
        """
        取得花蓮縣所有鄉鎮市區的國小資料
        
        Returns:
            所有學校的資料列表
        """
        all_schools = []
        
        # 花蓮縣所有鄉鎮市區列表
        districts = [
            '花蓮市', '吉安鄉', '新城鄉', '秀林鄉', '壽豐鄉', 
            '鳳林鎮', '光復鄉', '豐濱鄉', '瑞穗鄉', '玉里鎮', 
            '富里鄉', '卓溪鄉', '萬榮鄉'
        ]
        
        try:
            # 使用上下文管理器確保瀏覽器正確關閉
            async with self:
                # 先嘗試查詢整個花蓮縣（更快速）
                print("嘗試查詢整個花蓮縣...")
                try:
                    county_schools = await self.query_all_schools_in_county('花蓮縣')
                    if county_schools and len(county_schools) > 0:
                        print(f"成功查詢整個花蓮縣，取得 {len(county_schools)} 筆資料")
                        all_schools.extend(county_schools)
                    else:
                        raise Exception("查詢整個縣市未取得資料，改用逐一查詢")
                except Exception as e:
                    print(f"查詢整個縣市失敗: {str(e)}，改用逐一查詢各鄉鎮...")
                    # 如果查詢整個縣市失敗，則逐一查詢各鄉鎮
                    for district in districts:
                        try:
                            print(f"正在查詢 {district}...")
                            district_schools = await self.query_schools('花蓮縣', district)
                            if district_schools:
                                all_schools.extend(district_schools)
                                print(f"  {district}: 取得 {len(district_schools)} 筆資料")
                            else:
                                print(f"  {district}: 未取得資料")
                        except Exception as e:
                            print(f"  查詢 {district} 時發生錯誤: {str(e)}")
                            continue
        except Exception as e:
            print(f"取得所有學校資料時發生錯誤: {str(e)}")
            import traceback
            traceback.print_exc()
        
        # 合併重複的學校資料
        print(f"合併前共有 {len(all_schools)} 筆學校資料")
        all_schools = self.merge_school_data(all_schools)
        print(f"合併後共有 {len(all_schools)} 筆學校資料")
        
        return all_schools


async def scrape_schools() -> List[Dict[str, Any]]:
    """
    爬取花蓮縣所有鄉鎮市區的國小資料（非同步版本）
    
    Returns:
        學校資料列表
    """
    scraper = SchoolScraper()
    return await scraper.get_all_schools()
