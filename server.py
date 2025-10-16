"""
综合服务器启动脚本

同时启动 API 服务器和定时任务调度器
"""

import os
import sys
import io
import logging
import threading
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
file_handler = logging.FileHandler("server.log", encoding='utf-8')
console_handler = logging.StreamHandler(sys.stdout)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[file_handler, console_handler]
)

def run_api_server():
    """在独立线程中运行 API 服务器"""
    from api_server import app
    
    host = os.getenv('API_HOST', '0.0.0.0')
    port = int(os.getenv('API_PORT', '5000'))
    debug = False  # 在多线程环境中不使用 debug 模式
    
    logging.info(f"API 服务器线程启动: http://{host}:{port}")
    
    app.run(
        host=host,
        port=port,
        debug=debug,
        use_reloader=False  # 禁用重载器以避免多线程问题
    )

def run_scheduler():
    """在独立线程中运行定时任务调度器"""
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
    from main import run_sync
    
    schedule_hour = int(os.getenv('SCHEDULE_HOUR', '4'))
    schedule_minute = int(os.getenv('SCHEDULE_MINUTE', '0'))
    timezone = os.getenv('SCHEDULE_TIMEZONE', 'Asia/Shanghai')
    
    def scheduled_sync_job():
        """定时任务执行的同步作业"""
        logging.info("=" * 60)
        logging.info("定时任务触发: 开始执行同步")
        logging.info(f"触发时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logging.info("=" * 60)
        
        try:
            result = run_sync()
            
            logging.info("=" * 60)
            logging.info("定时任务执行完成")
            logging.info(f"状态: {result['status']}")
            logging.info(f"成功: {result['synced']} 条")
            logging.info(f"跳过: {result['skipped']} 条")
            logging.info(f"失败: {result['failed']} 条")
            logging.info(f"总计: {result['total']} 条")
            logging.info("=" * 60)
            
            return result
        except Exception as e:
            logging.error(f"定时任务执行失败: {e}", exc_info=True)
            return {
                'status': 'error',
                'error': str(e)
            }
    
    # 创建后台调度器
    scheduler = BackgroundScheduler(timezone=timezone)
    
    # 添加定时任务
    scheduler.add_job(
        scheduled_sync_job,
        trigger=CronTrigger(hour=schedule_hour, minute=schedule_minute),
        id='daily_sync',
        name='每日同步任务',
        replace_existing=True
    )
    
    scheduler.start()
    
    logging.info("=" * 60)
    logging.info("定时任务调度器已启动")
    logging.info(f"调度时间: 每天 {schedule_hour:02d}:{schedule_minute:02d}")
    logging.info(f"时区: {timezone}")
    logging.info("=" * 60)
    logging.info("已注册的任务:")
    for job in scheduler.get_jobs():
        logging.info(f"  - {job.name} (ID: {job.id})")
        logging.info(f"    下次运行: {job.next_run_time}")
    logging.info("=" * 60)
    
    return scheduler

def main():
    """
    主函数：同时启动 API 服务器和定时任务调度器
    """
    logging.info("=" * 80)
    logging.info(" " * 20 + "Jira-Confluence-Dify 同步服务")
    logging.info("=" * 80)
    logging.info(f"启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logging.info("=" * 80)
    
    # 启动定时任务调度器（后台模式）
    scheduler = run_scheduler()
    
    # 启动 API 服务器（阻塞模式，在主线程中运行）
    # 这样可以保证按 Ctrl+C 时能正确停止
    try:
        host = os.getenv('API_HOST', '0.0.0.0')
        port = int(os.getenv('API_PORT', '5000'))
        
        logging.info(f"API 服务器启动: http://{host}:{port}")
        logging.info("=" * 80)
        logging.info("服务运行中...（按 Ctrl+C 停止）")
        logging.info("=" * 80)
        
        from api_server import app
        app.run(
            host=host,
            port=port,
            debug=False,
            use_reloader=False
        )
    except (KeyboardInterrupt, SystemExit):
        logging.info("\n收到停止信号，正在关闭服务...")
        scheduler.shutdown()
        logging.info("服务已停止")

if __name__ == '__main__':
    main()