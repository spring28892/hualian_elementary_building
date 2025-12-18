"""
研究網站結構，找出如何取得詳細統計資料
"""
import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import re


async def research_site_structure():
    """研究網站結構，找出取得詳細資料的方法"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)  # 使用非 headless 模式以便觀察
        page = await browser.new_page()
        
        base_url = "https://stats.moe.gov.tw/edugissys/default.aspx"
        
        try:
            print("=" * 60)
            print("步驟 1: 載入初始頁面")
            print("=" * 60)
            await page.goto(base_url, wait_until='networkidle', timeout=30000)
            await page.wait_for_load_state('domcontentloaded')
            await page.wait_for_timeout(3000)
            
            # 截圖以便觀察
            await page.screenshot(path='screenshot_1_initial.png', full_page=True)
            print("已截圖: screenshot_1_initial.png")
            
            print("\n" + "=" * 60)
            print("步驟 2: 點擊行政區域查詢按鈕")
            print("=" * 60)
            
            # 點擊行政區域查詢按鈕
            try:
                await page.click('button#ptype1, button[value="1"]')
                await page.wait_for_timeout(2000)
                print("已點擊行政區域查詢按鈕")
            except Exception as e:
                print(f"點擊按鈕失敗: {e}，嘗試使用 JavaScript...")
                await page.evaluate('''() => {
                    const btn = document.querySelector('button#ptype1');
                    if (btn) btn.click();
                }''')
                await page.wait_for_timeout(2000)
            
            await page.screenshot(path='screenshot_2_after_click.png', full_page=True)
            print("已截圖: screenshot_2_after_click.png")
            
            print("\n" + "=" * 60)
            print("步驟 3: 選擇縣市和鄉鎮")
            print("=" * 60)
            
            # 取得所有縣市選項
            city_options = await page.locator('select[name="CityName"] option').all()
            city_code = None
            for option in city_options:
                text = await option.text_content()
                value = await option.get_attribute('value')
                if text and '花蓮' in text:
                    print(f"找到縣市: {text} (value: {value})")
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
                        print(f"找到鄉鎮: {text} (value: {value})")
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
                    
                    await page.screenshot(path='screenshot_3_before_search.png', full_page=True)
                    print("已截圖: screenshot_3_before_search.png")
                    
                    print("\n" + "=" * 60)
                    print("步驟 4: 點擊查詢按鈕")
                    print("=" * 60)
                    
                    # 點擊查詢
                    try:
                        await page.click('input[type="submit"][value="學校搜尋"]')
                    except:
                        await page.evaluate('BtnClick2();')
                    
                    await page.wait_for_load_state('networkidle', timeout=30000)
                    await page.wait_for_timeout(5000)
                    
                    await page.screenshot(path='screenshot_4_after_search.png', full_page=True)
                    print("已截圖: screenshot_4_after_search.png")
                    
                    # 取得頁面 HTML
                    html = await page.content()
                    
                    print("\n" + "=" * 60)
                    print("步驟 5: 分析搜尋結果頁面")
                    print("=" * 60)
                    
                    soup = BeautifulSoup(html, 'lxml')
                    
                    # 檢查是否有學校連結
                    links = soup.find_all('a', href=True)
                    school_links = []
                    for link in links:
                        href = link.get('href', '')
                        text = link.get_text(strip=True)
                        if '國小' in text or 'javascript' in href.lower():
                            school_links.append({
                                'text': text,
                                'href': href,
                                'full_link': link
                            })
                    
                    print(f"\n找到 {len(school_links)} 個可能的學校連結:")
                    for i, link_info in enumerate(school_links[:10], 1):
                        print(f"{i}. {link_info['text'][:50]} -> {link_info['href'][:100]}")
                    
                    # 檢查表格結構
                    tables = soup.find_all('table')
                    print(f"\n找到 {len(tables)} 個表格")
                    for i, table in enumerate(tables):
                        rows = table.find_all('tr')
                        if len(rows) > 1:
                            print(f"\n表格 {i+1}: {len(rows)} 行")
                            # 顯示前幾行的內容
                            for j, row in enumerate(rows[:3]):
                                cells = row.find_all(['td', 'th'])
                                cell_texts = [cell.get_text(strip=True)[:30] for cell in cells]
                                print(f"  行 {j+1}: {cell_texts}")
                    
                    # 檢查是否有詳細資料的按鈕或連結
                    print("\n" + "=" * 60)
                    print("步驟 6: 檢查是否有取得詳細資料的方式")
                    print("=" * 60)
                    
                    # 尋找包含「詳細」、「詳情」、「資料」等關鍵字的元素
                    detailed_elements = soup.find_all(string=re.compile(r'詳細|詳情|資料|點擊|查看', re.I))
                    print(f"\n找到 {len(detailed_elements)} 個包含詳細資料關鍵字的元素")
                    for elem in detailed_elements[:5]:
                        parent = elem.parent
                        print(f"  - {elem.strip()[:50]} (標籤: {parent.name if parent else 'None'})")
                    
                    # 檢查是否有可點擊的學校名稱
                    print("\n" + "=" * 60)
                    print("步驟 7: 嘗試點擊第一個學校（如果有的話）")
                    print("=" * 60)
                    
                    # 使用 Playwright 尋找可點擊的學校連結
                    clickable_schools = await page.locator('a:has-text("國小"), tr:has-text("國小") a').all()
                    print(f"找到 {len(clickable_schools)} 個可點擊的學校元素")
                    
                    if clickable_schools:
                        print("\n嘗試點擊第一個學校連結...")
                        first_school = clickable_schools[0]
                        school_name = await first_school.text_content()
                        print(f"學校名稱: {school_name}")
                        
                        # 在新頁面或同一頁面打開
                        async with page.context.expect_page() as new_page_info:
                            await first_school.click()
                        
                        new_page = await new_page_info.value
                        await new_page.wait_for_load_state('networkidle', timeout=30000)
                        await new_page.wait_for_timeout(3000)
                        
                        await new_page.screenshot(path='screenshot_5_detail_page.png', full_page=True)
                        print("已截圖: screenshot_5_detail_page.png")
                        
                        detail_html = await new_page.content()
                        detail_soup = BeautifulSoup(detail_html, 'lxml')
                        
                        print("\n詳細頁面分析:")
                        print("-" * 60)
                        
                        # 檢查詳細頁面中的資料
                        detail_text = detail_soup.get_text()
                        if '班級' in detail_text:
                            print("✓ 包含「班級」關鍵字")
                        if '學生' in detail_text:
                            print("✓ 包含「學生」關鍵字")
                        if '教師' in detail_text:
                            print("✓ 包含「教師」關鍵字")
                        
                        # 尋找包含數字的表格或區域
                        detail_tables = detail_soup.find_all('table')
                        print(f"\n詳細頁面有 {len(detail_tables)} 個表格")
                        for i, table in enumerate(detail_tables):
                            rows = table.find_all('tr')
                            if len(rows) > 0:
                                print(f"\n詳細表格 {i+1}: {len(rows)} 行")
                                for j, row in enumerate(rows[:5]):
                                    cells = row.find_all(['td', 'th'])
                                    cell_texts = [cell.get_text(strip=True)[:40] for cell in cells]
                                    print(f"  行 {j+1}: {cell_texts}")
                        
                        await new_page.close()
                    else:
                        print("\n未找到可點擊的學校連結，可能資料在搜尋結果頁面中")
                        
                        # 分析搜尋結果表格中的資料
                        print("\n分析搜尋結果表格...")
                        result_table = soup.find('table')
                        if result_table:
                            rows = result_table.find_all('tr')
                            print(f"結果表格有 {len(rows)} 行")
                            for i, row in enumerate(rows[:5]):
                                cells = row.find_all(['td', 'th'])
                                cell_texts = []
                                for cell in cells:
                                    text = cell.get_text(strip=True)
                                    # 檢查是否包含數字
                                    numbers = re.findall(r'\d+', text)
                                    cell_texts.append(f"{text[:30]}{' [有數字]' if numbers else ''}")
                                print(f"  行 {i+1}: {cell_texts}")
            
            print("\n" + "=" * 60)
            print("研究完成！請查看截圖檔案了解網站結構")
            print("=" * 60)
            
            # 保持瀏覽器開啟一段時間以便觀察
            print("\n瀏覽器將在 30 秒後關閉...")
            await page.wait_for_timeout(30000)
            
        except Exception as e:
            print(f"\n發生錯誤: {str(e)}")
            import traceback
            traceback.print_exc()
            await page.screenshot(path='screenshot_error.png', full_page=True)
        finally:
            await browser.close()


if __name__ == '__main__':
    asyncio.run(research_site_structure())






