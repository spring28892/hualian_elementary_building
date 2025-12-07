"""
Flask Web 應用程式
提供花蓮縣國小資料查詢和下載功能
使用 SQLite 資料庫儲存資料，並使用 APScheduler 定期更新
"""
from flask import Flask, render_template, jsonify, Response, request
import pandas as pd
import io
from datetime import datetime, timedelta
from scraper import scrape_schools
from database import Database
import os
import asyncio
import threading
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
import atexit

# 跨平台文件鎖支援
try:
    if os.name == 'nt':
        import msvcrt
    else:
        import fcntl
except ImportError:
    pass

app = Flask(__name__)

# 初始化資料庫
db = Database()

# 定時任務排程器
scheduler = BackgroundScheduler()


def run_scrape_task():
    """
    執行爬取任務（在背景執行）
    """
    print(f"[{datetime.now()}] 開始執行定時爬取任務...")
    try:
        # 執行爬取
        schools = asyncio.run(scrape_schools())
        
        # 儲存到資料庫
        saved_count = db.save_schools(schools)
        
        # 取得鄉鎮市區數量
        districts = set(school.get('鄉鎮市區', '') for school in schools)
        districts_count = len([d for d in districts if d])
        
        # 記錄爬取日誌
        db.log_scrape(saved_count, districts_count, 'success')
        
        print(f"[{datetime.now()}] 爬取任務完成：儲存 {saved_count} 筆學校資料，涵蓋 {districts_count} 個鄉鎮市區")
    except Exception as e:
        error_msg = str(e)
        print(f"[{datetime.now()}] 爬取任務失敗: {error_msg}")
        import traceback
        traceback.print_exc()
        # 記錄錯誤
        db.log_scrape(0, 0, 'error', error_msg)


def schedule_next_scrape():
    """
    排程下一次爬取（六個月後）
    """
    next_date = datetime.now() + timedelta(days=6 * 30)  # 六個月
    print(f"排程下一次爬取時間: {next_date}")
    
    # 移除現有的任務（如果有的話）
    try:
        scheduler.remove_job('scrape_job')
    except:
        pass
    
    # 新增新的定時任務
    scheduler.add_job(
        func=run_scrape_task,
        trigger=DateTrigger(run_date=next_date),
        id='scrape_job',
        name='定期爬取學校資料',
        replace_existing=True
    )


def check_and_scrape_on_startup():
    """
    應用程式啟動時檢查是否需要立即爬取
    """
    print("檢查資料庫狀態...")
    
    # 檢查是否需要爬取
    if db.should_scrape(months=6):
        schools_count = db.get_schools_count()
        if schools_count == 0:
            print("資料庫為空，立即執行首次爬取...")
        else:
            last_scrape = db.get_last_scrape_time()
            print(f"資料已過期（最後爬取時間: {last_scrape}），立即執行爬取...")
        
        # 在背景執行爬取
        run_scrape_task()
    else:
        last_scrape = db.get_last_scrape_time()
        print(f"資料庫已有資料（最後爬取時間: {last_scrape}），無需立即爬取")
    
    # 排程下一次爬取
    schedule_next_scrape()


def get_school_data(districts: list = None):
    """
    從資料庫取得學校資料
    
    Args:
        districts: 可選的鄉鎮市區列表，用於過濾
    
    Returns:
        學校資料列表
    """
    return db.get_all_schools(districts)


@app.route('/')
def index():
    """首頁"""
    return render_template('index.html')


@app.route('/api/data')
def api_data():
    """API 端點：返回 JSON 格式的學校資料"""
    try:
        # 取得查詢參數中的區域過濾
        districts_param = request.args.get('districts')
        districts = None
        if districts_param is not None:
            # 如果參數存在（即使是空字串），解析為列表
            # 如果有多個區域，用逗號分隔
            districts = [d.strip() for d in districts_param.split(',') if d.strip()]
            # 如果解析後是空列表，保持為空列表（表示要返回空結果）
            # 如果解析後有內容，使用該列表
        
        data = get_school_data(districts)
        
        # 取得最後爬取時間
        last_scrape = db.get_last_scrape_time()
        
        return jsonify({
            'success': True,
            'data': data,
            'count': len(data),
            'timestamp': last_scrape.isoformat() if last_scrape else None
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/districts')
def api_districts():
    """API 端點：返回所有可用的鄉鎮市區列表"""
    try:
        districts = db.get_districts()
        return jsonify({
            'success': True,
            'districts': districts,
            'count': len(districts)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/download/csv')
def download_csv():
    """下載 CSV 檔案"""
    try:
        # 取得查詢參數中的區域過濾
        districts_param = request.args.get('districts')
        districts = None
        if districts_param is not None:
            # 如果參數存在（即使是空字串），解析為列表
            districts = [d.strip() for d in districts_param.split(',') if d.strip()]
            # 如果解析後是空列表，保持為空列表（表示要返回空結果）
        
        data = get_school_data(districts)
        
        if not data:
            return jsonify({
                'success': False,
                'error': '沒有可用的資料'
            }), 404
        
        # 建立 DataFrame
        df = pd.DataFrame(data)
        
        # 確保欄位順序
        columns_order = ['鄉鎮市區', '學校名稱', '班級數', '學生數', '教師數', 
                        '校地面積', '校舍面積']
        # 只包含存在的欄位
        columns_order = [col for col in columns_order if col in df.columns]
        df = df[columns_order]
        
        # 轉換為 CSV
        output = io.StringIO()
        df.to_csv(output, index=False, encoding='utf-8-sig')  # 使用 utf-8-sig 以支援 Excel
        output.seek(0)
        
        # 建立檔案名稱
        filename = f'花蓮縣國小資料_{datetime.now().strftime("%Y%m%d")}.csv'
        
        return Response(
            output.getvalue(),
            mimetype='text/csv; charset=utf-8-sig',
            headers={
                'Content-Disposition': f'attachment; filename="{filename}"',
                'Content-Type': 'text/csv; charset=utf-8-sig'
            }
        )
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/refresh', methods=['POST'])
def refresh_data():
    """強制重新爬取資料（在背景執行）"""
    try:
        print("收到手動刷新請求...")
        
        # 在背景線程中執行爬取任務，避免阻塞 HTTP 響應
        thread = threading.Thread(target=run_scrape_task, daemon=True)
        thread.start()
        
        # 重新排程下一次爬取
        schedule_next_scrape()
        
        # 立即返回響應，不等待爬取完成
        return jsonify({
            'success': True,
            'message': '資料已開始在背景更新，請稍後重新載入頁面查看最新資料'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# 模組級變數：保存鎖檔案引用
_scheduler_lock_file = None
_scheduler_lock_file_path = None

def init_scheduler():
    """
    初始化並啟動排程器
    使用文件鎖確保只有一個進程啟動排程器（防止多個 WSGI worker 同時啟動）
    """
    global _scheduler_lock_file, _scheduler_lock_file_path
    
    _scheduler_lock_file_path = os.path.join(os.path.dirname(__file__), '.scheduler.lock')
    
    try:
        # 嘗試取得文件鎖（非阻塞模式）
        _scheduler_lock_file = open(_scheduler_lock_file_path, 'w')
        
        # 在 Windows 上使用不同的鎖定機制
        if os.name == 'nt':
            try:
                import msvcrt
                # Windows 上嘗試鎖定檔案的第一個位元組
                msvcrt.locking(_scheduler_lock_file.fileno(), msvcrt.LK_NBLCK, 1)
            except (IOError, OSError):
                # 無法取得鎖，表示已有其他進程啟動了調度器
                _scheduler_lock_file.close()
                _scheduler_lock_file = None
                print("排程器已在其他進程中運行，跳過初始化")
                return False
            except ImportError:
                # msvcrt 不可用，使用簡單的檔案存在檢查
                _scheduler_lock_file.close()
                _scheduler_lock_file = None
                if os.path.exists(_scheduler_lock_file_path):
                    print("排程器鎖檔案已存在，跳過初始化")
                    return False
                _scheduler_lock_file = open(_scheduler_lock_file_path, 'w')
        else:
            # Unix/Linux 上使用 fcntl
            try:
                import fcntl
                fcntl.flock(_scheduler_lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except (IOError, OSError):
                # 無法取得鎖，表示已有其他進程啟動了調度器
                _scheduler_lock_file.close()
                _scheduler_lock_file = None
                print("排程器已在其他進程中運行，跳過初始化")
                return False
            except ImportError:
                # fcntl 不可用，使用簡單的檔案存在檢查
                _scheduler_lock_file.close()
                _scheduler_lock_file = None
                if os.path.exists(_scheduler_lock_file_path):
                    print("排程器鎖檔案已存在，跳過初始化")
                    return False
                _scheduler_lock_file = open(_scheduler_lock_file_path, 'w')
        
        # 成功取得鎖，啟動排程器
        print("啟動排程器...")
        scheduler.start()
        
        # 註冊關閉時清理排程器和釋放鎖
        def cleanup():
            try:
                scheduler.shutdown()
            except:
                pass
            try:
                global _scheduler_lock_file, _scheduler_lock_file_path
                if _scheduler_lock_file:
                    if os.name == 'nt':
                        try:
                            import msvcrt
                            msvcrt.locking(_scheduler_lock_file.fileno(), msvcrt.LK_UNLCK, 1)
                        except:
                            pass
                    else:
                        try:
                            import fcntl
                            fcntl.flock(_scheduler_lock_file.fileno(), fcntl.LOCK_UN)
                        except:
                            pass
                    _scheduler_lock_file.close()
                    _scheduler_lock_file = None
                if _scheduler_lock_file_path and os.path.exists(_scheduler_lock_file_path):
                    os.remove(_scheduler_lock_file_path)
            except:
                pass
        
        atexit.register(cleanup)
        return True
        
    except Exception as e:
        if _scheduler_lock_file:
            try:
                _scheduler_lock_file.close()
            except:
                pass
            _scheduler_lock_file = None
        print(f"初始化排程器時發生錯誤: {str(e)}")
        # 如果無法使用文件鎖，仍然嘗試啟動（單進程環境）
        try:
            if not scheduler.running:
                scheduler.start()
                atexit.register(lambda: scheduler.shutdown())
            return True
        except Exception as e2:
            print(f"啟動排程器失敗: {str(e2)}")
            return False


# 應用程式啟動時檢查並執行爬取
if __name__ == '__main__':
    # 初始化排程器（單進程模式，總是啟動）
    scheduler.start()
    atexit.register(lambda: scheduler.shutdown())
    
    # 檢查並執行爬取
    check_and_scrape_on_startup()
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
else:
    # 如果是使用 gunicorn 等 WSGI 伺服器，使用文件鎖保護
    scheduler_initialized = init_scheduler()
    
    # 只有成功初始化排程器的進程才執行啟動檢查
    if scheduler_initialized:
        check_and_scrape_on_startup()
    else:
        print("跳過啟動檢查（排程器由其他進程管理）")
