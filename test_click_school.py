"""
測試點擊學校名稱取得詳細資料
"""
import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import re


async def test_click_school():
    """測試點擊學校名稱"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)  # 使用 headless 模式
        page = await browser.new_page()
        
        base_url = "https://stats.moe.gov.tw/edugissys/default.aspx"
        
        try:
            print("載入初始頁面...")
            await page.goto(base_url, wait_until='networkidle', timeout=30000)
            await page.wait_for_load_state('domcontentloaded')
            await page.wait_for_timeout(2000)
            
            # 點擊行政區域查詢按鈕
            try:
                await page.click('button#ptype1, button[value="1"]')
                await page.wait_for_timeout(2000)
            except:
                await page.evaluate('''() => {
                    const btn = document.querySelector('button#ptype1');
                    if (btn) btn.click();
                }''')
                await page.wait_for_timeout(2000)
            
            # 選擇縣市
            city_code = None
            city_options = await page.locator('select[name="CityName"] option').all()
            for option in city_options:
                text = await option.text_content()
                value = await option.get_attribute('value')
                if text and '花蓮' in text:
                    city_code = value
                    break
            
            if city_code:
                await page.select_option('select[name="CityName"]', city_code)
                await page.evaluate('''() => {
                    const select = document.querySelector('select[name="CityName"]');
                    if (select) {
                        const event = new Event('change', { bubbles: true });
                        select.dispatchEvent(event);
                    }
                }''')
                await page.wait_for_timeout(3000)
                
                # 選擇鄉鎮
                dist_options = await page.locator('select[name="DistName"] option').all()
                district_code = None
                for option in dist_options:
                    text = await option.text_content()
                    value = await option.get_attribute('value')
                    if text and '花蓮市' in text:
                        district_code = value
                        break
                
                if district_code:
                    await page.select_option('select[name="DistName"]', district_code)
                    await page.wait_for_timeout(1000)
                    
                    # 選擇學校層級
                    try:
                        await page.click('input[type="radio"][value="國小"]')
                        await page.wait_for_timeout(1000)
                    except:
                        await page.select_option('select[name="lv"]', '1')
                    
                    # 點擊查詢
                    try:
                        await page.click('input[type="submit"][value="學校搜尋"]')
                    except:
                        await page.evaluate('BtnClick2();')
                    
                    await page.wait_for_load_state('networkidle', timeout=30000)
                    await page.wait_for_timeout(5000)
                    
                    # 嘗試點擊第一個學校名稱
                    print("\n嘗試點擊第一個學校名稱...")
                    
                    # 方法1: 從 div#search 中找到學校名稱並點擊
                    search_div = page.locator('div#search').first
                    if await search_div.count() > 0:
                        text = await search_div.text_content()
                        print(f"div#search 內容: {text[:200]}")
                        
                        # 嘗試點擊 div#search 中的文字
                        try:
                            # 尋找包含「國小」的文字節點
                            result = await page.evaluate('''() => {
                                const searchDiv = document.getElementById('search');
                                if (!searchDiv) return null;
                                
                                const walker = document.createTreeWalker(
                                    searchDiv,
                                    NodeFilter.SHOW_TEXT,
                                    null,
                                    false
                                );
                                
                                let node;
                                while (node = walker.nextNode()) {
                                    if (node.textContent.includes('國小')) {
                                        // 找到父元素
                                        let parent = node.parentElement;
                                        while (parent && parent !== searchDiv) {
                                            // 檢查是否可以點擊
                                            const style = window.getComputedStyle(parent);
                                            if (style.cursor === 'pointer' || 
                                                parent.onclick || 
                                                parent.getAttribute('onclick') ||
                                                parent.tagName === 'A') {
                                                return {
                                                    text: node.textContent.trim(),
                                                    tag: parent.tagName,
                                                    hasClick: !!parent.onclick || !!parent.getAttribute('onclick'),
                                                    cursor: style.cursor
                                                };
                                            }
                                            parent = parent.parentElement;
                                        }
                                    }
                                }
                                return null;
                            }''')
                            
                            if result:
                                print(f"找到可點擊的學校: {result}")
                            else:
                                print("未找到可點擊的學校元素")
                        except Exception as e:
                            print(f"檢查可點擊元素時發生錯誤: {e}")
                    
                    # 方法2: 嘗試直接點擊 div#search
                    try:
                        print("\n嘗試點擊 div#search...")
                        await search_div.click()
                        await page.wait_for_timeout(2000)
                        print("已點擊 div#search")
                    except Exception as e:
                        print(f"點擊 div#search 失敗: {e}")
                    
                    # 方法3: 檢查是否有彈出視窗或詳細資料顯示
                    print("\n檢查是否有彈出視窗...")
                    modals = await page.locator('.modal, .popup, [role="dialog"]').all()
                    if modals:
                        print(f"找到 {len(modals)} 個彈出視窗")
                    
                    # 方法4: 檢查 URL 是否改變
                    current_url = page.url
                    print(f"當前 URL: {current_url}")
                    
                    # 方法5: 嘗試使用 JavaScript 觸發點擊事件
                    print("\n嘗試使用 JavaScript 觸發點擊...")
                    result = await page.evaluate('''() => {
                        const searchDiv = document.getElementById('search');
                        if (!searchDiv) return {found: false};
                        
                        // 尋找所有包含「國小」的元素
                        const allElements = searchDiv.querySelectorAll('*');
                        for (let elem of allElements) {
                            if (elem.textContent && elem.textContent.includes('國小')) {
                                // 嘗試觸發點擊
                                try {
                                    elem.click();
                                    return {found: true, text: elem.textContent.trim().substring(0, 50)};
                                } catch (e) {
                                    // 如果直接點擊失敗，嘗試觸發事件
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
                    
                    if result.get('found'):
                        print(f"成功觸發點擊: {result}")
                        await page.wait_for_timeout(3000)
                        
                        # 檢查頁面是否改變
                        new_url = page.url
                        if new_url != current_url:
                            print(f"URL 已改變: {new_url}")
                        
                        # 檢查是否有新分頁
                        try:
                            # 等待可能的頁面變化
                            await page.wait_for_timeout(2000)
                            
                            # 檢查 URL 是否改變
                            new_url = page.url
                            if new_url != current_url:
                                print(f"URL 已改變: {new_url}")
                            
                            # 檢查當前頁面的內容
                            current_html = await page.content()
                            current_soup = BeautifulSoup(current_html, 'lxml')
                            current_text = current_soup.get_text()
                            
                            if '班級' in current_text or '學生' in current_text or '教師' in current_text:
                                print("當前頁面包含資料關鍵字")
                                
                                # 尋找表格
                                tables = current_soup.find_all('table')
                                print(f"當前頁面有 {len(tables)} 個表格")
                                for i, table in enumerate(tables[:5]):
                                    rows = table.find_all('tr')
                                    if len(rows) > 0:
                                        print(f"表格 {i+1}: {len(rows)} 行")
                                        for j, row in enumerate(rows[:3]):
                                            cells = row.find_all(['td', 'th'])
                                            cell_texts = [cell.get_text(strip=True)[:40] for cell in cells]
                                            if any(cell_texts):  # 只顯示非空行
                                                print(f"  行 {j+1}: {cell_texts}")
                            
                            # 檢查是否有彈出視窗（可能在點擊後出現）
                            modals = await page.locator('.modal, .popup, [role="dialog"], .dialog').all()
                            if modals:
                                print(f"找到 {len(modals)} 個彈出視窗")
                                for i, modal in enumerate(modals):
                                    text = await modal.text_content()
                                    print(f"  彈出視窗 {i+1}: {text[:200]}")
                            
                        except Exception as e:
                            print(f"檢查頁面變化時發生錯誤: {e}")
                    else:
                        print("未找到可點擊的學校元素")
                    
                    print("\n保持瀏覽器開啟 10 秒以便觀察...")
                    await page.wait_for_timeout(10000)
                    
        except Exception as e:
            print(f"\n發生錯誤: {str(e)}")
            import traceback
            traceback.print_exc()
        finally:
            await browser.close()


if __name__ == '__main__':
    asyncio.run(test_click_school())

