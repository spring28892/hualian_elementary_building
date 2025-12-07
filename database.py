"""
資料庫操作模組
處理 SQLite 資料庫的初始化、讀寫操作
"""
import sqlite3
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
import os


class Database:
    """資料庫操作類別"""
    
    def __init__(self, db_path: str = 'schools.db'):
        """
        初始化資料庫連接
        
        Args:
            db_path: 資料庫檔案路徑
        """
        self.db_path = db_path
        self.init_database()
    
    def get_connection(self):
        """取得資料庫連接"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # 讓查詢結果可以像字典一樣存取
        return conn
    
    def init_database(self):
        """初始化資料庫表結構"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # 建立 schools 表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS schools (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                鄉鎮市區 TEXT NOT NULL,
                學校名稱 TEXT NOT NULL,
                班級數 INTEGER,
                學生數 INTEGER,
                教師數 INTEGER,
                校地面積 INTEGER,
                校舍面積 INTEGER,
                學校類型 TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(鄉鎮市區, 學校名稱)
            )
        ''')
        
        # 建立 scrape_log 表記錄爬取時間
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scrape_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scrape_time TIMESTAMP NOT NULL,
                schools_count INTEGER NOT NULL,
                districts_count INTEGER,
                status TEXT DEFAULT 'success',
                error_message TEXT
            )
        ''')
        
        # 建立索引以提升查詢效能
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_district ON schools(鄉鎮市區)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_school_name ON schools(學校名稱)
        ''')
        
        conn.commit()
        conn.close()
    
    def save_schools(self, schools: List[Dict[str, Any]]) -> int:
        """
        儲存學校資料到資料庫
        
        Args:
            schools: 學校資料列表
        
        Returns:
            儲存的資料筆數
        """
        if not schools:
            return 0
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        saved_count = 0
        current_time = datetime.now().isoformat()
        
        for school in schools:
            try:
                cursor.execute('''
                    INSERT OR REPLACE INTO schools 
                    (鄉鎮市區, 學校名稱, 班級數, 學生數, 教師數, 校地面積, 校舍面積, 學校類型, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    school.get('鄉鎮市區', ''),
                    school.get('學校名稱', ''),
                    school.get('班級數'),
                    school.get('學生數'),
                    school.get('教師數'),
                    school.get('校地面積'),
                    school.get('校舍面積'),
                    school.get('學校類型'),
                    current_time
                ))
                saved_count += 1
            except Exception as e:
                print(f"儲存學校資料時發生錯誤: {school.get('學校名稱', '未知')} - {str(e)}")
                continue
        
        conn.commit()
        conn.close()
        return saved_count
    
    def get_all_schools(self, districts: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        從資料庫取得所有學校資料
        
        Args:
            districts: 可選的鄉鎮市區列表，用於過濾
                      - None: 返回所有資料
                      - []: 返回空結果
                      - ['區域1', '區域2']: 返回指定區域的資料
        
        Returns:
            學校資料列表
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # 如果 districts 是 None，返回所有資料
        if districts is None:
            query = '''
                SELECT * FROM schools 
                ORDER BY 鄉鎮市區, 學校名稱
            '''
            cursor.execute(query)
        # 如果 districts 是空列表，返回空結果
        elif len(districts) == 0:
            conn.close()
            return []
        # 如果 districts 有內容，使用 IN 子句過濾
        else:
            placeholders = ','.join(['?'] * len(districts))
            query = f'''
                SELECT * FROM schools 
                WHERE 鄉鎮市區 IN ({placeholders})
                ORDER BY 鄉鎮市區, 學校名稱
            '''
            cursor.execute(query, districts)
        
        rows = cursor.fetchall()
        schools = []
        
        for row in rows:
            school = {
                '鄉鎮市區': row['鄉鎮市區'],
                '學校名稱': row['學校名稱'],
                '班級數': row['班級數'],
                '學生數': row['學生數'],
                '教師數': row['教師數'],
                '校地面積': row['校地面積'],
                '校舍面積': row['校舍面積'],
                '學校類型': row['學校類型'],
            }
            schools.append(school)
        
        conn.close()
        return schools
    
    def get_districts(self) -> List[str]:
        """
        取得所有不重複的鄉鎮市區列表
        
        Returns:
            鄉鎮市區列表
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT DISTINCT 鄉鎮市區 
            FROM schools 
            WHERE 鄉鎮市區 IS NOT NULL AND 鄉鎮市區 != ''
            ORDER BY 鄉鎮市區
        ''')
        
        rows = cursor.fetchall()
        districts = [row['鄉鎮市區'] for row in rows]
        
        conn.close()
        return districts
    
    def get_last_scrape_time(self) -> Optional[datetime]:
        """
        取得最後一次爬取的時間
        
        Returns:
            最後爬取時間，如果沒有記錄則返回 None
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT scrape_time FROM scrape_log 
            WHERE status = 'success'
            ORDER BY scrape_time DESC 
            LIMIT 1
        ''')
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return datetime.fromisoformat(row['scrape_time'])
        return None
    
    def log_scrape(self, schools_count: int, districts_count: Optional[int] = None, 
                   status: str = 'success', error_message: Optional[str] = None):
        """
        記錄爬取日誌
        
        Args:
            schools_count: 爬取的學校數量
            districts_count: 爬取的鄉鎮市區數量
            status: 爬取狀態（success 或 error）
            error_message: 錯誤訊息（如果有）
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO scrape_log (scrape_time, schools_count, districts_count, status, error_message)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            datetime.now().isoformat(),
            schools_count,
            districts_count,
            status,
            error_message
        ))
        
        conn.commit()
        conn.close()
    
    def should_scrape(self, months: int = 6) -> bool:
        """
        檢查是否需要重新爬取資料
        
        Args:
            months: 資料有效期（月數）
        
        Returns:
            如果需要爬取返回 True，否則返回 False
        """
        last_scrape = self.get_last_scrape_time()
        
        # 如果沒有爬取記錄，需要爬取
        if last_scrape is None:
            return True
        
        # 檢查資料是否過期
        expire_date = last_scrape + timedelta(days=months * 30)
        return datetime.now() > expire_date
    
    def get_schools_count(self) -> int:
        """
        取得資料庫中的學校總數
        
        Returns:
            學校總數
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) as count FROM schools')
        row = cursor.fetchone()
        count = row['count'] if row else 0
        
        conn.close()
        return count
    
    def clear_all_data(self):
        """清除所有資料（用於測試或重新爬取）"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM schools')
        cursor.execute('DELETE FROM scrape_log')
        
        conn.commit()
        conn.close()

