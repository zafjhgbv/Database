"""
Flask API Server for Jira-Confluence-Dify Sync

提供 HTTP 接口用于触发同步任务
"""

import os
import sys
import io
from flask import Flask, jsonify, request
from flask_cors import CORS
from main import run_sync
import logging
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# 修复 Windows 控制台 UTF-8 编码问题
if sys.platform == 'win32':
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass

# 配置 logging
file_handler = logging.FileHandler("api_server.log", encoding='utf-8')
console_handler = logging.StreamHandler(sys.stdout)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[file_handler, console_handler]
)

# 创建 Flask 应用
app = Flask(__name__)
CORS(app)  # 允许跨域请求

# 存储最后一次同步的结果
last_sync_result = {
    'status': 'never_run',
    'message': '尚未执行过同步',
    'last_run_time': None
}

@app.route('/')
def index():
    """API 根路径"""
    return jsonify({
        'service': 'Jira-Confluence-Dify Sync API',
        'version': '1.0.0',
        'endpoints': {
            '/': 'API 信息',
            '/health': '健康检查',
            '/sync': 'POST - 触发同步任务',
            '/status': 'GET - 查看最后一次同步状态'
        }
    })

@app.route('/health')
def health():
    """健康检查接口"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'service': 'sync-api'
    })

@app.route('/sync', methods=['POST'])
def trigger_sync():
    """
    触发同步任务接口
    
    可选参数（JSON body）：
    - async: bool - 是否异步执行（默认 false）
    """
    global last_sync_result
    
    data = request.get_json() or {}
    is_async = data.get('async', False)
    
    logging.info(f"收到同步请求 (async={is_async})")
    
    if is_async:
        # 异步执行（在后台线程中）
        import threading
        
        def async_sync():
            global last_sync_result
            result = run_sync()
            result['last_run_time'] = datetime.now().isoformat()
            last_sync_result = result
        
        thread = threading.Thread(target=async_sync)
        thread.start()
        
        return jsonify({
            'status': 'started',
            'message': '同步任务已在后台启动',
            'async': True,
            'timestamp': datetime.now().isoformat()
        })
    else:
        # 同步执行
        try:
            result = run_sync()
            result['last_run_time'] = datetime.now().isoformat()
            last_sync_result = result
            
            return jsonify(result)
        except Exception as e:
            error_result = {
                'status': 'error',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
            logging.error(f"同步任务执行失败: {e}", exc_info=True)
            return jsonify(error_result), 500

@app.route('/status', methods=['GET'])
def get_status():
    """
    获取最后一次同步的状态
    """
    return jsonify(last_sync_result)

@app.errorhandler(404)
def not_found(error):
    """404 错误处理"""
    return jsonify({
        'error': 'Not Found',
        'message': '请求的端点不存在',
        'available_endpoints': ['/', '/health', '/sync', '/status']
    }), 404

@app.errorhandler(500)
def internal_error(error):
    """500 错误处理"""
    return jsonify({
        'error': 'Internal Server Error',
        'message': '服务器内部错误'
    }), 500

def main():
    """启动 API 服务器"""
    host = os.getenv('API_HOST', '0.0.0.0')
    port = int(os.getenv('API_PORT', '5000'))
    debug = os.getenv('API_DEBUG', 'false').lower() == 'true'
    
    logging.info("=" * 60)
    logging.info("启动 Jira-Confluence-Dify 同步 API 服务器")
    logging.info(f"监听地址: http://{host}:{port}")
    logging.info("=" * 60)
    logging.info("可用端点:")
    logging.info(f"  GET  http://{host}:{port}/        - API 信息")
    logging.info(f"  GET  http://{host}:{port}/health  - 健康检查")
    logging.info(f"  POST http://{host}:{port}/sync    - 触发同步")
    logging.info(f"  GET  http://{host}:{port}/status  - 查看状态")
    logging.info("=" * 60)
    
    app.run(
        host=host,
        port=port,
        debug=debug
    )

if __name__ == '__main__':
    main()