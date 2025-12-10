"""
資料庫操作模組：優先使用 Postgres（DATABASE_URL），沒有時回退到本機 SQLite。
"""
import os
import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any

import psycopg2
import psycopg2.extras


POSTGRES_DSN = os.getenv("DATABASE_URL")


class Database:
    """資料庫操作類別"""

    def __init__(self, db_path: str = "schools.db"):
        """
        初始化資料庫連線

        Args:
            db_path: SQLite 資料庫檔案路徑（未設定 DATABASE_URL 時使用）
        """
        self.db_path = db_path
        self.use_postgres = bool(POSTGRES_DSN)
        self.init_database()

    def get_connection(self):
        """取得資料庫連線"""
        if self.use_postgres:
            conn = psycopg2.connect(POSTGRES_DSN, cursor_factory=psycopg2.extras.RealDictCursor)
            conn.autocommit = False
            return conn
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_database(self):
        """初始化資料庫表結構"""
        conn = self.get_connection()
        cursor = conn.cursor()

        if self.use_postgres:
            # Pre-create sequence to avoid duplicate-name errors when table is recreated
            cursor.execute(
                """
                CREATE SEQUENCE IF NOT EXISTS schools_id_seq AS INTEGER;
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS schools (
                    id INTEGER PRIMARY KEY DEFAULT nextval('schools_id_seq'),
                    "鄉鎮市區" TEXT NOT NULL,
                    "學校名稱" TEXT NOT NULL,
                    "班級數" INTEGER,
                    "學生數" INTEGER,
                    "教師數" INTEGER,
                    "校地面積" INTEGER,
                    "校舍面積" INTEGER,
                    "學校類型" TEXT,
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE("鄉鎮市區", "學校名稱")
                )
                """
            )
            cursor.execute(
                """
                ALTER SEQUENCE schools_id_seq OWNED BY schools.id;
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS scrape_log (
                    id SERIAL PRIMARY KEY,
                    scrape_time TIMESTAMPTZ NOT NULL,
                    schools_count INTEGER NOT NULL,
                    districts_count INTEGER,
                    status TEXT DEFAULT 'success',
                    error_message TEXT
                )
                """
            )
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_district ON schools("鄉鎮市區")')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_school_name ON schools("學校名稱")')
        else:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS schools (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    "鄉鎮市區" TEXT NOT NULL,
                    "學校名稱" TEXT NOT NULL,
                    "班級數" INTEGER,
                    "學生數" INTEGER,
                    "教師數" INTEGER,
                    "校地面積" INTEGER,
                    "校舍面積" INTEGER,
                    "學校類型" TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE("鄉鎮市區", "學校名稱")
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS scrape_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scrape_time TIMESTAMP NOT NULL,
                    schools_count INTEGER NOT NULL,
                    districts_count INTEGER,
                    status TEXT DEFAULT 'success',
                    error_message TEXT
                )
                """
            )
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_district ON schools("鄉鎮市區")')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_school_name ON schools("學校名稱")')

        # Ensure legacy columns are migrated to the current schema
        try:
            self._ensure_schema_columns(cursor)
        except RuntimeError as e:
            # 如果遷移失敗（例如 SQLite 版本過舊），回滾並重新拋出異常
            # 這會阻止應用程式啟動，但提供清晰的錯誤訊息
            conn.rollback()
            conn.close()
            raise RuntimeError(
                f"資料庫初始化失敗：{str(e)}\n"
                "請檢查 SQLite 版本（需要 3.25.0+）或檢查資料庫連接設定。"
            ) from e

        conn.commit()
        conn.close()

    def _placeholders(self, count: int) -> str:
        return ",".join(["%s"] * count) if self.use_postgres else ",".join(["?"] * count)

    def _upsert_sql(self) -> str:
        # Postgres uses ON CONFLICT DO UPDATE; SQLite also supports ON CONFLICT with same syntax.
        return """
            INSERT INTO schools
            ("鄉鎮市區", "學校名稱", "班級數", "學生數", "教師數", "校地面積", "校舍面積", "學校類型", updated_at)
            VALUES ({placeholders})
            ON CONFLICT ("鄉鎮市區", "學校名稱") DO UPDATE SET
                "班級數" = EXCLUDED."班級數",
                "學生數" = EXCLUDED."學生數",
                "教師數" = EXCLUDED."教師數",
                "校地面積" = EXCLUDED."校地面積",
                "校舍面積" = EXCLUDED."校舍面積",
                "學校類型" = EXCLUDED."學校類型",
                updated_at = EXCLUDED.updated_at
        """

    def _column_exists(self, cursor, column_name: str) -> bool:
        """Check whether the given column exists on the schools table."""
        if self.use_postgres:
            cursor.execute(
                """
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'schools' AND column_name = %s
                """,
                (column_name,),
            )
            return cursor.fetchone() is not None

        cursor.execute("PRAGMA table_info(schools)")
        return any(row["name"] == column_name for row in cursor.fetchall())

    def _check_sqlite_version(self) -> tuple[bool, str]:
        """
        檢查 SQLite 版本是否支援 RENAME COLUMN（需要 3.25.0+）
        
        Returns:
            (is_supported, version_string): 是否支援和版本字串
        """
        if self.use_postgres:
            return True, "PostgreSQL"  # PostgreSQL 支援 RENAME COLUMN
        
        try:
            version_info = sqlite3.sqlite_version_info
            version_str = sqlite3.sqlite_version
            # RENAME COLUMN 需要 SQLite 3.25.0 或更高版本
            is_supported = version_info >= (3, 25, 0)
            return is_supported, version_str
        except Exception as e:
            # 如果無法取得版本資訊，假設不支援
            return False, "未知版本"

    def _ensure_schema_columns(self, cursor):
        """
        Migrate legacy column names to the current schema so scraper data matches
        the stored column names (校地面積、校舍面積).
        """
        migrations = [
            ("特殊教育", "校地面積"),
            ("原住民學生", "校舍面積"),
        ]

        sqlite_supports_rename, version_str = self._check_sqlite_version()

        for old_name, new_name in migrations:
            # Skip if target column already exists
            if self._column_exists(cursor, new_name):
                continue

            if self._column_exists(cursor, old_name):
                # Rename old columns to new names to preserve existing data
                if sqlite_supports_rename or self.use_postgres:
                    try:
                        rename_sql = f'ALTER TABLE schools RENAME COLUMN "{old_name}" TO "{new_name}"'
                        cursor.execute(rename_sql)
                    except Exception as e:
                        error_msg = (
                            f"無法重新命名欄位 '{old_name}' 為 '{new_name}': {str(e)}"
                        )
                        if not self.use_postgres:
                            error_msg += f"\nSQLite 版本: {version_str}（需要 3.25.0+）"
                        raise RuntimeError(error_msg) from e
                else:
                    # SQLite 版本太舊，無法使用 RENAME COLUMN
                    error_msg = (
                        f"SQLite 版本過舊（當前: {version_str}，需要 3.25.0+），"
                        f"無法自動遷移欄位 '{old_name}' 為 '{new_name}'。"
                        "請升級 SQLite 或手動遷移資料。"
                    )
                    raise RuntimeError(error_msg)
            else:
                # Column missing entirely; create it to keep schema complete
                try:
                    add_sql = f'ALTER TABLE schools ADD COLUMN "{new_name}" INTEGER'
                    cursor.execute(add_sql)
                except Exception as e:
                    print(f"警告：無法新增欄位 '{new_name}': {str(e)}")

    def save_schools(self, schools: List[Dict[str, Any]]) -> int:
        """批次儲存學校資料到資料庫"""
        if not schools:
            return 0

        conn = self.get_connection()
        cursor = conn.cursor()
        saved_count = 0
        current_time = datetime.now().isoformat()

        placeholder_str = self._placeholders(9)
        sql = self._upsert_sql().format(placeholders=placeholder_str)

        # 對於 PostgreSQL，使用保存點來實現部分成功
        # 對於 SQLite，錯誤處理較寬鬆，可以繼續處理後續記錄
        use_savepoints = self.use_postgres

        try:
            for idx, school in enumerate(schools):
                if use_savepoints:
                    # 為每個記錄創建保存點，允許部分成功
                    savepoint_name = f"sp_{idx}"
                    try:
                        cursor.execute(f"SAVEPOINT {savepoint_name}")
                        cursor.execute(
                            sql,
                            (
                                school.get("鄉鎮市區", ""),
                                school.get("學校名稱", ""),
                                school.get("班級數"),
                                school.get("學生數"),
                                school.get("教師數"),
                                school.get("校地面積"),
                                school.get("校舍面積"),
                                school.get("學校類型"),
                                current_time,
                            ),
                        )
                        cursor.execute(f"RELEASE SAVEPOINT {savepoint_name}")
                        saved_count += 1
                    except Exception as e:
                        print(f"儲存學校資料時發生錯誤: {school.get('學校名稱', '未知')} - {str(e)}")
                        try:
                            # 回滾到保存點，繼續處理下一個記錄
                            cursor.execute(f"ROLLBACK TO SAVEPOINT {savepoint_name}")
                        except Exception:
                            # 如果保存點回滾失敗，回滾整個事務
                            conn.rollback()
                            raise
                else:
                    # SQLite：直接執行，錯誤時跳過該記錄
                    try:
                        cursor.execute(
                            sql,
                            (
                                school.get("鄉鎮市區", ""),
                                school.get("學校名稱", ""),
                                school.get("班級數"),
                                school.get("學生數"),
                                school.get("教師數"),
                                school.get("校地面積"),
                                school.get("校舍面積"),
                                school.get("學校類型"),
                                current_time,
                            ),
                        )
                        saved_count += 1
                    except Exception as e:
                        print(f"儲存學校資料時發生錯誤: {school.get('學校名稱', '未知')} - {str(e)}")
                        # SQLite 在錯誤後可以繼續處理下一個記錄
                        continue

            conn.commit()
        except Exception as e:
            print(f"批次儲存時發生嚴重錯誤: {str(e)}")
            conn.rollback()
        finally:
            conn.close()
        
        return saved_count

    def save_school(self, school: Dict[str, Any]) -> bool:
        """單筆儲存學校資料到資料庫（用於即時儲存）"""
        if not school:
            return False

        conn = self.get_connection()
        cursor = conn.cursor()
        current_time = datetime.now().isoformat()

        placeholder_str = self._placeholders(9)
        sql = self._upsert_sql().format(placeholders=placeholder_str)

        try:
            cursor.execute(
                sql,
                (
                    school.get("鄉鎮市區", ""),
                    school.get("學校名稱", ""),
                    school.get("班級數"),
                    school.get("學生數"),
                    school.get("教師數"),
                    school.get("校地面積"),
                    school.get("校舍面積"),
                    school.get("學校類型"),
                    current_time,
                ),
            )
            conn.commit()
            return True
        except Exception as e:
            print(f"儲存學校資料時發生錯誤: {school.get('學校名稱', '未知')} - {str(e)}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def get_all_schools(self, districts: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """從資料庫取得所有學校資料"""
        conn = self.get_connection()
        cursor = conn.cursor()

        if districts is None:
            query = 'SELECT * FROM schools ORDER BY "鄉鎮市區", "學校名稱"'
            cursor.execute(query)
        elif len(districts) == 0:
            conn.close()
            return []
        else:
            placeholders = self._placeholders(len(districts))
            query = f'''
                SELECT * FROM schools
                WHERE "鄉鎮市區" IN ({placeholders})
                ORDER BY "鄉鎮市區", "學校名稱"
            '''
            cursor.execute(query, districts)

        rows = cursor.fetchall()
        schools = []

        for row in rows:
            school = {
                "鄉鎮市區": row["鄉鎮市區"],
                "學校名稱": row["學校名稱"],
                "班級數": row["班級數"],
                "學生數": row["學生數"],
                "教師數": row["教師數"],
                "校地面積": row["校地面積"],
                "校舍面積": row["校舍面積"],
                "學校類型": row["學校類型"],
            }
            schools.append(school)

        conn.close()
        return schools

    def get_districts(self) -> List[str]:
        """取得所有可用的鄉鎮市區列表"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT DISTINCT "鄉鎮市區"
            FROM schools
            WHERE "鄉鎮市區" IS NOT NULL AND "鄉鎮市區" != ''
            ORDER BY "鄉鎮市區"
            '''
        )

        rows = cursor.fetchall()
        districts = [row["鄉鎮市區"] for row in rows]

        conn.close()
        return districts

    def get_last_scrape_time(self) -> Optional[datetime]:
        """取得最後一次爬蟲時間"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT scrape_time FROM scrape_log
            WHERE status = 'success'
            ORDER BY scrape_time DESC
            LIMIT 1
            """
        )

        row = cursor.fetchone()
        conn.close()

        if row and row.get("scrape_time"):
            # psycopg2 RealDictCursor returns datetime; sqlite returns string
            return row["scrape_time"] if self.use_postgres else datetime.fromisoformat(row["scrape_time"])
        return None

    def log_scrape(
        self,
        schools_count: int,
        districts_count: Optional[int] = None,
        status: str = "success",
        error_message: Optional[str] = None,
    ):
        """記錄爬蟲狀態"""
        conn = self.get_connection()
        cursor = conn.cursor()

        placeholder = "%s, %s, %s, %s, %s" if self.use_postgres else "?, ?, ?, ?, ?"
        sql = f"""
            INSERT INTO scrape_log (scrape_time, schools_count, districts_count, status, error_message)
            VALUES ({placeholder})
        """

        cursor.execute(
            sql,
            (
                datetime.now().isoformat(),
                schools_count,
                districts_count,
                status,
                error_message,
            ),
        )

        conn.commit()
        conn.close()

    def should_scrape(self, months: int = 6) -> bool:
        """檢查是否需要重新爬蟲"""
        last_scrape = self.get_last_scrape_time()
        if last_scrape is None:
            return True
        expire_date = last_scrape + timedelta(days=months * 30)
        return datetime.now() > expire_date

    def get_schools_count(self) -> int:
        """取得資料庫中所有學校總數"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) as count FROM schools")
        row = cursor.fetchone()
        count = row["count"] if row else 0

        conn.close()
        return count

    def clear_all_data(self):
        """清除所有資料（用於測試或重新爬蟲）"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM schools")
        cursor.execute("DELETE FROM scrape_log")

        conn.commit()
        conn.close()
