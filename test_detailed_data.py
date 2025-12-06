"""
測試取得詳細統計資料的功能
"""
import asyncio
from scraper import scrape_schools


async def test_detailed_data():
    """測試取得詳細統計資料"""
    print("=" * 60)
    print("測試取得詳細統計資料功能")
    print("=" * 60)
    
    try:
        schools = await scrape_schools()
        
        print(f"\n成功取得 {len(schools)} 筆學校資料\n")
        
        if schools:
            # 統計有詳細資料的學校
            schools_with_details = []
            schools_without_details = []
            
            for school in schools:
                has_details = any([
                    school.get('班級數'),
                    school.get('學生數'),
                    school.get('教師數'),
                    school.get('校地面積'),
                    school.get('校舍面積'),
                ])
                
                if has_details:
                    schools_with_details.append(school)
                else:
                    schools_without_details.append(school)
            
            print("=" * 60)
            print("統計結果")
            print("=" * 60)
            print(f"總學校數: {len(schools)}")
            print(f"有詳細資料的學校: {len(schools_with_details)}")
            print(f"無詳細資料的學校: {len(schools_without_details)}")
            
            if schools_with_details:
                print("\n" + "=" * 60)
                print("有詳細資料的學校（前 5 筆）:")
                print("=" * 60)
                for i, school in enumerate(schools_with_details[:5], 1):
                    print(f"\n{i}. {school.get('學校名稱', 'N/A')}")
                    print(f"   鄉鎮市區: {school.get('鄉鎮市區', 'N/A')}")
                    print(f"   班級數: {school.get('班級數', 'N/A')}")
                    print(f"   學生數: {school.get('學生數', 'N/A')}")
                    print(f"   教師數: {school.get('教師數', 'N/A')}")
                    print(f"   校地面積: {school.get('校地面積', 'N/A')}")
                    print(f"   校舍面積: {school.get('校舍面積', 'N/A')}")
            
            if schools_without_details:
                print("\n" + "=" * 60)
                print("無詳細資料的學校:")
                print("=" * 60)
                for school in schools_without_details:
                    print(f"  - {school.get('學校名稱', 'N/A')} ({school.get('鄉鎮市區', 'N/A')})")
            
            print("\n" + "=" * 60)
            print("測試完成！")
            print("=" * 60)
        else:
            print("警告：未取得任何資料")
            print("=" * 60)
            
    except Exception as e:
        print(f"\n測試失敗：{str(e)}")
        import traceback
        traceback.print_exc()
        print("=" * 60)


if __name__ == '__main__':
    asyncio.run(test_detailed_data())

