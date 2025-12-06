"""
Flask Web 應用程式
提供花蓮市和吉安鄉國小資料查詢和下載功能
"""
from flask import Flask, render_template, jsonify, send_file, Response
import pandas as pd
import io
from datetime import datetime, timedelta
from scraper import scrape_schools
import os
import asyncio

app = Flask(__name__)

# 快取資料和時間戳記
cached_data = None
cache_timestamp = None
CACHE_DURATION = timedelta(hours=1)  # 快取 1 小時


def get_school_data(force_refresh=False):
    """
    取得學校資料，使用快取機制避免頻繁爬取
    
    Args:
        force_refresh: 是否強制重新爬取
    
    Returns:
        學校資料列表
    """
    global cached_data, cache_timestamp
    
    # 檢查快取是否有效
    if not force_refresh and cached_data is not None and cache_timestamp is not None:
        if datetime.now() - cache_timestamp < CACHE_DURATION:
            return cached_data
    
    # 重新爬取資料（使用非同步函數）
    try:
        print("開始爬取資料...")
        # 使用 asyncio.run() 執行非同步函數
        # Flask 通常不在事件循環中運行，所以可以直接使用 asyncio.run()
        try:
            cached_data = asyncio.run(scrape_schools())
        except RuntimeError as e:
            # 如果已經有事件循環在運行，嘗試其他方法
            try:
                loop = asyncio.get_event_loop()
                cached_data = loop.run_until_complete(scrape_schools())
            except:
                # 最後的備用方案：在新線程中運行
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, scrape_schools())
                    cached_data = future.result()
        
        cache_timestamp = datetime.now()
        print(f"成功爬取 {len(cached_data)} 筆資料")
        return cached_data
    except Exception as e:
        print(f"爬取資料時發生錯誤: {str(e)}")
        import traceback
        traceback.print_exc()
        # 如果爬取失敗，返回快取的資料（如果有的話）
        if cached_data is not None:
            return cached_data
        return []


@app.route('/')
def index():
    """首頁"""
    return render_template('index.html')


@app.route('/api/data')
def api_data():
    """API 端點：返回 JSON 格式的學校資料"""
    try:
        data = get_school_data()
        return jsonify({
            'success': True,
            'data': data,
            'count': len(data),
            'timestamp': cache_timestamp.isoformat() if cache_timestamp else None
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
        data = get_school_data()
        
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
        filename = f'花蓮市吉安鄉國小資料_{datetime.now().strftime("%Y%m%d")}.csv'
        
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


@app.route('/api/refresh')
def refresh_data():
    """強制重新爬取資料"""
    try:
        data = get_school_data(force_refresh=True)
        return jsonify({
            'success': True,
            'data': data,
            'count': len(data),
            'timestamp': cache_timestamp.isoformat() if cache_timestamp else None
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

