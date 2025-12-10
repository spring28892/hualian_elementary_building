"""
測試增量儲存功能
確保每處理完一間學校就立即存入資料庫，避免記憶體累積
"""
import asyncio
from scraper import SchoolScraper
from database import Database
import os


async def test_incremental_save():
    """測試增量儲存功能"""
    print("=" * 60)
    print("測試增量儲存功能")
    print("=" * 60)
    
    # 使用測試資料庫
    test_db_path = 'test_schools.db'
    db = Database(db_path=test_db_path)
    
    # 清除測試資料
    db.clear_all_data()
    
    # 追蹤已儲存的學校
    saved_schools = []
    saved_count = 0
    
    def save_callback(school_data):
        """回調函數：每處理完一間學校就立即儲存"""
        nonlocal saved_count
        saved_schools.append(school_data.copy())
        success = db.save_school(school_data)
        if success:
            saved_count += 1
            print(f"  [{saved_count}] 已儲存: {school_data.get('學校名稱', '未知')}")
        else:
            print(f"  警告：儲存失敗: {school_data.get('學校名稱', '未知')}")
    
    try:
        print("\n開始爬取學校資料（使用增量儲存）...")
        scraper = SchoolScraper()
        
        # 使用回調函數進行增量儲存
        schools = await scraper.get_all_schools(on_school_scraped=save_callback)
        
        print(f"\n爬取完成！")
        print(f"回調函數被調用次數: {saved_count}")
        print(f"回調中收集的學校數: {len(saved_schools)}")
        
        # 驗證資料已存入資料庫
        db_schools_count = db.get_schools_count()
        print(f"資料庫中的學校總數: {db_schools_count}")
        
        # 驗證
        assert db_schools_count == saved_count, f"資料庫中的學校數量 ({db_schools_count}) 與回調儲存數量 ({saved_count}) 不一致"
        assert len(saved_schools) == saved_count, f"回調收集的學校數量 ({len(saved_schools)}) 與儲存數量 ({saved_count}) 不一致"
        
        # 驗證資料完整性
        if saved_schools:
            print("\n驗證資料完整性...")
            sample_school = saved_schools[0]
            print(f"範例學校: {sample_school.get('學校名稱')}")
            print(f"  鄉鎮市區: {sample_school.get('鄉鎮市區')}")
            print(f"  班級數: {sample_school.get('班級數')}")
            print(f"  學生數: {sample_school.get('學生數')}")
            print(f"  教師數: {sample_school.get('教師數')}")
            
            # 從資料庫讀取驗證
            db_schools = db.get_all_schools()
            assert len(db_schools) == saved_count, "資料庫讀取的學校數量與儲存數量不一致"
            
            # 檢查範例學校是否在資料庫中
            sample_found = False
            for db_school in db_schools:
                if db_school.get('學校名稱') == sample_school.get('學校名稱'):
                    sample_found = True
                    print(f"  驗證成功：範例學校已存在於資料庫中")
                    break
            
            assert sample_found, "範例學校未在資料庫中找到"
        
        print("\n" + "=" * 60)
        print("測試成功！增量儲存功能正常運作")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n測試失敗：{str(e)}")
        import traceback
        traceback.print_exc()
        print("=" * 60)
        raise
    finally:
        # 清理測試資料庫
        try:
            if os.path.exists(test_db_path):
                os.remove(test_db_path)
                print(f"\n已清理測試資料庫: {test_db_path}")
        except Exception as e:
            print(f"清理測試資料庫時發生錯誤: {e}")


async def test_callback_without_scraper():
    """測試回調函數本身（不實際爬取）"""
    print("\n" + "=" * 60)
    print("測試回調函數（模擬）")
    print("=" * 60)
    
    test_db_path = 'test_callback.db'
    db = Database(db_path=test_db_path)
    db.clear_all_data()
    
    callback_called = []
    
    def test_callback(school_data):
        callback_called.append(school_data)
        db.save_school(school_data)
    
    # 模擬學校資料
    test_schools = [
        {
            '鄉鎮市區': '花蓮市',
            '學校名稱': '測試國小1',
            '班級數': 10,
            '學生數': 200,
            '教師數': 15,
        },
        {
            '鄉鎮市區': '吉安鄉',
            '學校名稱': '測試國小2',
            '班級數': 8,
            '學生數': 150,
            '教師數': 12,
        },
    ]
    
    # 模擬調用回調
    for school in test_schools:
        test_callback(school)
    
    # 驗證
    assert len(callback_called) == 2, f"回調應被調用 2 次，實際 {len(callback_called)} 次"
    assert db.get_schools_count() == 2, f"資料庫應有 2 筆資料，實際 {db.get_schools_count()} 筆"
    
    print("回調函數測試成功！")
    
    # 清理
    try:
        if os.path.exists(test_db_path):
            os.remove(test_db_path)
    except:
        pass


if __name__ == '__main__':
    # 先測試回調函數本身
    asyncio.run(test_callback_without_scraper())
    
    # 再測試完整的增量儲存功能
    # 注意：這個測試會實際爬取資料，可能需要較長時間
    # 如果只想測試回調機制，可以註解掉下面這行
    # asyncio.run(test_incremental_save())



