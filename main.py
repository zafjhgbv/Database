import os
import sys
import io
from datetime import datetime
from connectors import get_jira_issues, get_confluence_pages
from dify_client import upload_document_to_dify
from database import get_sync_record, update_sync_record, setup_database
from dateutil import parser
import logging
from dotenv import load_dotenv

load_dotenv()

# 修复 Windows 控制台 UTF-8 编码问题 - 必须在 logging 配置之前
if sys.platform == 'win32':
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass  # 如果失败就使用默认编码

# 配置 logging - 使用 UTF-8 编码的文件处理器
file_handler = logging.FileHandler("sync.log", encoding='utf-8')
console_handler = logging.StreamHandler(sys.stdout)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[file_handler, console_handler]
)

def validate_config():
    """启动前验证必要的配置"""
    required_configs = {
        'ATLASSIAN_URL': os.getenv('ATLASSIAN_URL'),
        'ATLASSIAN_EMAIL': os.getenv('ATLASSIAN_EMAIL'),
        'ATLASSIAN_API_TOKEN': os.getenv('ATLASSIAN_API_TOKEN'),
        'DIFY_API_KEY': os.getenv('DIFY_API_KEY'),
        'DIFY_API_URL': os.getenv('DIFY_API_URL'),
        'DIFY_DATASET_ID': os.getenv('DIFY_DATASET_ID')
    }
    
    missing = []
    invalid = []
    
    for name, value in required_configs.items():
        if not value:
            missing.append(name)
        elif value.startswith('粘贴') or value.startswith('your-'):
            invalid.append(name)
    
    if missing:
        raise ValueError(f"缺少必要配置: {', '.join(missing)}\n请在 .env 文件中配置这些变量。")
    
    if invalid:
        raise ValueError(f"配置值无效（使用了默认模板值）: {', '.join(invalid)}\n请填写真实的配置信息。")
    
    logging.info("✓ 配置验证通过")

def run_sync():
    """
    执行同步任务的核心函数
    返回同步结果的字典
    """
    logging.info("=" * 60)
    logging.info("开始 Jira-Confluence-Dify 同步任务")
    logging.info("=" * 60)
    
    result = {
        'status': 'success',
        'synced': 0,
        'skipped': 0,
        'failed': 0,
        'total': 0,
        'start_time': datetime.now().isoformat(),
        'end_time': None,
        'message': '',
        'error': None
    }
    
    try:
        # 0. 验证配置
        validate_config()
        
        # 初始化数据库
        setup_database()
        
        # 1. 从多个数据源拉取数据
        all_items = []
        
        # 1.1 从 Jira 拉取数据
        jira_project_key = os.getenv('JIRA_PROJECT_KEY', 'PROJ')
        jira_since = os.getenv('JIRA_SINCE_DAYS', '-30d')
        
        logging.info(f"\n{'='*60}")
        logging.info(f"正在同步 Jira 项目: {jira_project_key}")
        logging.info(f"{'='*60}")
        
        jira_items = get_jira_issues(project_key=jira_project_key, since=jira_since)
        all_items.extend(jira_items)
        
        # 1.2 从 Confluence 拉取数据（如果配置了）
        confluence_space_key = os.getenv('CONFLUENCE_SPACE_KEY', '')
        confluence_since_days = int(os.getenv('CONFLUENCE_SINCE_DAYS', '30'))
        
        if confluence_space_key and confluence_space_key != 'YOUR_SPACE_KEY':
            logging.info(f"\n{'='*60}")
            logging.info(f"正在同步 Confluence 空间: {confluence_space_key}")
            logging.info(f"{'='*60}")
            
            confluence_items = get_confluence_pages(
                space_key=confluence_space_key,
                since_days=confluence_since_days
            )
            all_items.extend(confluence_items)
        else:
            logging.info("\n⊗ 未配置 CONFLUENCE_SPACE_KEY，跳过 Confluence 同步。")

        if not all_items:
            logging.info("\n✓ 没有需要同步的数据。")
            result['message'] = '没有需要同步的数据'
            result['end_time'] = datetime.now().isoformat()
            return result
        
        logging.info(f"\n{'='*60}")
        logging.info(f"共获取 {len(all_items)} 条数据，开始版本控制检查...")
        logging.info(f"{'='*60}\n")

        # 2. 遍历每一条数据，执行版本控制逻辑
        synced_count = 0
        skipped_count = 0
        failed_count = 0
        
        for idx, item in enumerate(all_items, 1):
            source_id = item['id']
            source_type = item['type']
            remote_update_time = parser.isoparse(item['updated_at'])

            logging.info(f"[{idx}/{len(all_items)}] 正在处理 {source_type}: {source_id}...")

            # 3. 查询本地数据库记录
            local_record = get_sync_record(source_id)

            # 4. 核心判断逻辑：版本控制
            should_sync = False
            if not local_record:
                should_sync = True
                logging.info(f"  → 新数据，准备同步")
            else:
                # 将数据库中的字符串时间转换为 datetime 对象
                local_time = local_record.last_synced_update_time
                if isinstance(local_time, str):
                    try:
                        local_time = parser.parse(local_time)
                    except Exception as e:
                        logging.warning(f"  ⚠ 解析本地时间失败: {e}，将重新同步")
                        should_sync = True
                
                if not should_sync:
                    # 确保 remote_update_time 有时区信息，或者都转换为 naive datetime
                    if remote_update_time.tzinfo and not local_time.tzinfo:
                        # remote 有时区，local 没有，移除 remote 的时区
                        remote_update_time_naive = remote_update_time.replace(tzinfo=None)
                        should_sync = remote_update_time_naive > local_time
                    elif not remote_update_time.tzinfo and local_time.tzinfo:
                        # local 有时区，remote 没有，移除 local 的时区
                        local_time_naive = local_time.replace(tzinfo=None)
                        should_sync = remote_update_time > local_time_naive
                    else:
                        # 两者时区状态一致，直接比较
                        should_sync = remote_update_time > local_time
                    
                    if should_sync:
                        local_time_str = local_time.strftime('%Y-%m-%d %H:%M:%S') if hasattr(local_time, 'strftime') else str(local_time)
                        remote_time_str = remote_update_time.strftime('%Y-%m-%d %H:%M:%S')
                        logging.info(f"  → 检测到更新 (本地: {local_time_str}, 远程: {remote_time_str})")

            if should_sync:

                # 5. 推送到 Dify
                dify_id = upload_document_to_dify(item['id'], item['content'])

                # 6. 更新数据库记录
                if dify_id:
                    update_sync_record(
                        source_id=item['id'],
                        source_type=item['type'],
                        updated_at=remote_update_time,
                        dify_doc_id=dify_id,
                        status='SUCCESS'
                    )
                    logging.info(f"  ✓ {source_id} 同步成功 (Dify ID: {dify_id})")
                    synced_count += 1
                else:
                    logging.error(f"  ✗ {source_id} 同步失败")
                    failed_count += 1
                    update_sync_record(
                        source_id=item['id'],
                        source_type=item['type'],
                        updated_at=remote_update_time,
                        dify_doc_id='',
                        status='FAILED'
                    )

            else:
                logging.info(f"  ⊙ 内容未变化，跳过")
                skipped_count += 1
        # 输出统计信息
        logging.info(f"\n{'='*60}")
        logging.info("同步任务完成统计:")
        logging.info(f"  ✓ 成功同步: {synced_count} 条")
        logging.info(f"  ⊙ 跳过（无变化）: {skipped_count} 条")
        logging.info(f"  ✗ 失败: {failed_count} 条")
        logging.info(f"  总计: {len(all_items)} 条")
        logging.info(f"{'='*60}")
        
        result['synced'] = synced_count
        result['skipped'] = skipped_count
        result['failed'] = failed_count
        result['total'] = len(all_items)
        result['message'] = f'同步完成: 成功{synced_count}条, 跳过{skipped_count}条, 失败{failed_count}条'
        result['end_time'] = datetime.now().isoformat()
        
        return result
        
    except ValueError as e:
        error_msg = f"配置错误: {str(e)}"
        logging.error(f"\n✗ {error_msg}")
        logging.error("请检查 .env 文件中的配置信息。")
        result['status'] = 'error'
        result['error'] = error_msg
        result['end_time'] = datetime.now().isoformat()
        return result
    except Exception as e:
        error_msg = f"同步任务发生意外错误: {str(e)}"
        logging.error(f"\n✗ {error_msg}", exc_info=True)
        result['status'] = 'error'
        result['error'] = error_msg
        result['end_time'] = datetime.now().isoformat()
        return result
    finally:
        logging.info("\n任务结束\n")

def main():
    """命令行入口函数"""
    result = run_sync()
    if result['status'] == 'error':
        sys.exit(1)

if __name__ == '__main__':
    main()
