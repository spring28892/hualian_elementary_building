"""
測試 Playwright 爬蟲功能
"""
import asyncio
from scraper import scrape_schools


async def test_scraper():
    """測試爬蟲功能"""
    print("=" * 50)
    print("開始測試 Playwright 爬蟲")
    print("=" * 50)
    
    try:
        schools = await scrape_schools()
        
        print(f"\n成功爬取 {len(schools)} 筆學校資料\n")
        
        if schools:
            print("前 5 筆資料預覽：")
            print("-" * 50)
            for i, school in enumerate(schools[:5], 1):
                print(f"\n{i}. {school.get('學校名稱', 'N/A')}")
                print(f"   鄉鎮市區: {school.get('鄉鎮市區', 'N/A')}")
                print(f"   班級數: {school.get('班級數', 'N/A')}")
                print(f"   學生數: {school.get('學生數', 'N/A')}")
                print(f"   教師數: {school.get('教師數', 'N/A')}")
            
            if len(schools) > 5:
                print(f"\n... 還有 {len(schools) - 5} 筆資料")
            
            # 統計資料
            print("\n" + "=" * 50)
            print("統計資訊：")
            print("-" * 50)
            
            districts = {}
            for school in schools:
                district = school.get('鄉鎮市區', '未知')
                districts[district] = districts.get(district, 0) + 1
            
            for district, count in districts.items():
                print(f"{district}: {count} 所學校")
            
            print("=" * 50)
            print("測試成功！")
        else:
            print("警告：未取得任何資料")
            print("=" * 50)
            
    except Exception as e:
        print(f"\n測試失敗：{str(e)}")
        import traceback
        traceback.print_exc()
        print("=" * 50)


if __name__ == '__main__':
    asyncio.run(test_scraper())



