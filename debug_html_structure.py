"""
調試腳本：檢查搜尋結果頁面的 HTML 結構
"""
import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import re


async def debug_html_structure():
    """調試 HTML 結構"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
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
                    
                    # 取得 HTML
                    html = await page.content()
                    soup = BeautifulSoup(html, 'lxml')
                    
                    print("\n" + "=" * 60)
                    print("分析搜尋結果頁面結構")
                    print("=" * 60)
                    
                    # 檢查所有表格
                    tables = soup.find_all('table')
                    print(f"\n找到 {len(tables)} 個表格")
                    
                    for i, table in enumerate(tables):
                        rows = table.find_all('tr')
                        if len(rows) > 0:
                            print(f"\n表格 {i+1}: {len(rows)} 行")
                            
                            # 顯示前 5 行的內容
                            for j, row in enumerate(rows[:5]):
                                cells = row.find_all(['td', 'th'])
                                cell_texts = []
                                for cell in cells:
                                    text = cell.get_text(strip=True)
                                    # 檢查是否包含關鍵字
                                    has_keyword = any(kw in text for kw in ['班級', '學生', '教師', '校地', '校舍', '棟', '學校'])
                                    cell_texts.append(f"{text[:40]}{' [關鍵字]' if has_keyword else ''}")
                                print(f"  行 {j+1} ({len(cells)} 欄): {cell_texts}")
                            
                            # 檢查是否有連結
                            links = table.find_all('a', href=True)
                            if links:
                                print(f"  包含 {len(links)} 個連結")
                                for link in links[:3]:
                                    print(f"    - {link.get_text(strip=True)[:50]} -> {link.get('href', '')[:80]}")
                    
                    # 檢查 div#search
                    search_div = soup.find('div', {'id': 'search'})
                    if search_div:
                        print("\n找到 div#search")
                        text = search_div.get_text()[:500]
                        print(f"內容前 500 字元: {text}")
                        
                        # 檢查是否包含數字
                        numbers = re.findall(r'\d+', text)
                        if numbers:
                            print(f"包含 {len(numbers)} 個數字")
                    
                    # 檢查是否有 GridView
                    gridview = soup.find(id=re.compile(r'.*GridView.*', re.I))
                    if gridview:
                        print("\n找到 GridView")
                        rows = gridview.find_all('tr')
                        print(f"GridView 有 {len(rows)} 行")
                        if len(rows) > 0:
                            first_row = rows[0]
                            cells = first_row.find_all(['td', 'th'])
                            print(f"第一行有 {len(cells)} 欄")
                            for idx, cell in enumerate(cells[:10]):
                                print(f"  欄 {idx+1}: {cell.get_text(strip=True)[:50]}")
                    
                    # 檢查所有包含「班級」或「學生」的元素
                    print("\n尋找包含關鍵字的元素...")
                    keywords = ['班級', '學生', '教師', '校地', '校舍', '棟']
                    for keyword in keywords:
                        elements = soup.find_all(string=re.compile(keyword, re.I))
                        if elements:
                            print(f"  找到 {len(elements)} 個包含「{keyword}」的元素")
                            for elem in elements[:3]:
                                parent = elem.parent
                                if parent:
                                    print(f"    - {elem.strip()[:50]} (標籤: {parent.name})")
                    
                    # 嘗試使用 Playwright 尋找可點擊的元素
                    print("\n使用 Playwright 尋找可點擊的學校連結...")
                    selectors = [
                        'a:has-text("國小")',
                        'tr:has-text("國小") a',
                        'table a:has-text("國小")',
                        'td a:has-text("國小")',
                        'a[href*="javascript"]',
                    ]
                    
                    for selector in selectors:
                        try:
                            elements = await page.locator(selector).all()
                            if elements:
                                print(f"  選擇器 '{selector}': 找到 {len(elements)} 個元素")
                                if len(elements) > 0:
                                    first_elem = elements[0]
                                    text = await first_elem.text_content()
                                    href = await first_elem.get_attribute('href')
                                    print(f"    第一個元素: {text[:50]} -> {href[:80] if href else 'N/A'}")
                        except Exception as e:
                            print(f"  選擇器 '{selector}': 錯誤 - {str(e)}")
                    
                    # 檢查是否有隱藏的元素或需要點擊的資料
                    print("\n檢查隱藏元素和動態載入的資料...")
                    
                    # 檢查所有包含數字的元素
                    all_elements = soup.find_all(['div', 'span', 'td', 'th', 'p'])
                    number_elements = []
                    for elem in all_elements:
                        text = elem.get_text(strip=True)
                        if text and re.search(r'\d+', text):
                            # 檢查是否包含關鍵字
                            if any(kw in text for kw in ['班級', '學生', '教師', '校地', '校舍', '棟']):
                                number_elements.append((elem.name, text[:100]))
                    
                    if number_elements:
                        print(f"找到 {len(number_elements)} 個包含關鍵字和數字的元素:")
                        for tag, text in number_elements[:10]:
                            print(f"  <{tag}>: {text}")
                    
                    # 使用 Playwright 檢查頁面中的所有文字
                    print("\n使用 Playwright 檢查頁面文字...")
                    page_text = await page.evaluate('''() => {
                        return document.body.innerText;
                    }''')
                    
                    # 檢查是否包含關鍵字和數字
                    lines = page_text.split('\n')
                    relevant_lines = []
                    for line in lines:
                        line = line.strip()
                        if line and any(kw in line for kw in ['班級', '學生', '教師', '校地', '校舍', '棟']):
                            if re.search(r'\d+', line):
                                relevant_lines.append(line[:100])
                    
                    if relevant_lines:
                        print(f"找到 {len(relevant_lines)} 行包含關鍵字和數字:")
                        for line in relevant_lines[:10]:
                            print(f"  {line}")
                    
                    # 檢查是否有 iframe
                    iframes = soup.find_all('iframe')
                    if iframes:
                        print(f"\n找到 {len(iframes)} 個 iframe")
                    
                    # 檢查是否有 JavaScript 動態生成的表格
                    print("\n檢查 JavaScript 生成的元素...")
                    js_tables = await page.evaluate('''() => {
                        const tables = document.querySelectorAll('table');
                        const results = [];
                        for (let i = 0; i < Math.min(tables.length, 5); i++) {
                            const table = tables[i];
                            const rows = table.querySelectorAll('tr');
                            if (rows.length > 0) {
                                const firstRow = rows[0];
                                const cells = firstRow.querySelectorAll('td, th');
                                const cellTexts = Array.from(cells).map(c => c.innerText.trim().substring(0, 50));
                                results.push({
                                    index: i,
                                    rowCount: rows.length,
                                    cellCount: cells.length,
                                    firstRowCells: cellTexts
                                });
                            }
                        }
                        return results;
                    }''')
                    
                    for table_info in js_tables:
                        print(f"表格 {table_info['index']+1}: {table_info['rowCount']} 行, {table_info['cellCount']} 欄")
                        print(f"  第一行: {table_info['firstRowCells']}")
                    
        except Exception as e:
            print(f"\n發生錯誤: {str(e)}")
            import traceback
            traceback.print_exc()
        finally:
            await browser.close()


if __name__ == '__main__':
    asyncio.run(debug_html_structure())

