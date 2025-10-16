"""
定时任务调度器 for Jira-Confluence-Dify Sync

使用 APScheduler 实现定时任务调度
默认每天凌晨 4:00 执行同步
"""

import os
import sys
import io
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from main import run_sync
import logging
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
file_handler = logging.FileHandler("scheduler.log", encoding='utf-8')
console_handler = logging.StreamHandler(sys.stdout)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[file_handler, console_handler]
)

def scheduled_sync_job():
    """
    定时任务执行的同步作业
    """
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

def main():
    """
    启动定时任务调度器
    """
    # 从环境变量读取调度配置
    schedule_hour = int(os.getenv('SCHEDULE_HOUR', '4'))
    schedule_minute = int(os.getenv('SCHEDULE_MINUTE', '0'))
    timezone = os.getenv('SCHEDULE_TIMEZONE', 'Asia/Shanghai')
    
    # 创建调度器
    scheduler = BlockingScheduler(timezone=timezone)
    
    # 添加定时任务：每天指定时间执行
    scheduler.add_job(
        scheduled_sync_job,
        trigger=CronTrigger(hour=schedule_hour, minute=schedule_minute),
        id='daily_sync',
        name='每日同步任务',
        replace_existing=True
    )
    
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
    logging.info("调度器运行中...（按 Ctrl+C 停止）")
    logging.info("=" * 60)
    
    try:
        # 启动调度器（阻塞模式）
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logging.info("\n收到停止信号，正在关闭调度器...")
        scheduler.shutdown()
        logging.info("调度器已停止")

if __name__ == '__main__':
    main()