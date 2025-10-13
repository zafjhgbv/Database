from datetime import datetime
import os
import logging
from sqlalchemy import create_engine, text, inspect
from dotenv import load_dotenv

# 加载 .env 文件中的配置
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

# 如果没有配置DATABASE_URL，则默认使用SQLite
if not DATABASE_URL or DATABASE_URL == "粘贴你的数据库连接字符串":
    default_db_path = os.path.join(os.path.dirname(__file__), 'sync_database.db')
    DATABASE_URL = f"sqlite:///{default_db_path}"
    logging.warning(f"DATABASE_URL not set, defaulting to SQLite database at: {default_db_path}")

engine = create_engine(DATABASE_URL)

def setup_database():
    """连接数据库并创建 sync_tracker 表 (如果不存在)"""
    if not engine:
        logging.error("Database engine could not be initialized.")
        return
        
    logging.info(f"正在连接数据库: {engine.url.drivername}...")
    try:
        with engine.connect() as connection:
            logging.info("数据库连接成功！正在检查并创建 sync_tracker 表...")
            
            # 使用更兼容的DATETIME类型替换 TIMESTAMP WITH TIME ZONE
            # 移除PostgreSQL特有的触发器逻辑
            connection.execute(text("""
            CREATE TABLE IF NOT EXISTS sync_tracker (
                source_id VARCHAR(255) PRIMARY KEY,
                source_type VARCHAR(50) NOT NULL,
                last_synced_update_time DATETIME NOT NULL,
                dify_document_id VARCHAR(255),
                last_sync_status VARCHAR(50),
                last_synced_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            """))

            # 对于SQLite，我们需要一个触发器来模拟 ON UPDATE CURRENT_TIMESTAMP
            if engine.url.drivername == 'sqlite':
                # 检查触发器是否存在 - 使用更兼容的方法
                try:
                    result = connection.execute(text(
                        "SELECT name FROM sqlite_master WHERE type='trigger' AND name='update_sync_tracker_modtime'"
                    )).fetchone()
                    trigger_exists = result is not None
                except:
                    trigger_exists = False

                if not trigger_exists:
                    logging.info("正在为SQLite创建更新时间的触发器...")
                    try:
                        connection.execute(text("""
                        CREATE TRIGGER update_sync_tracker_modtime
                        AFTER UPDATE ON sync_tracker
                        FOR EACH ROW
                        BEGIN
                            UPDATE sync_tracker
                            SET last_synced_at = CURRENT_TIMESTAMP
                            WHERE source_id = OLD.source_id;
                        END;
                        """))
                        logging.info("触发器创建成功。")
                    except Exception as trigger_error:
                        logging.warning(f"创建触发器失败（可能已存在）: {trigger_error}")

            connection.commit()
            logging.info("表 'sync_tracker' 已成功创建或已存在。")
    except Exception as e:
        logging.error(f"数据库操作失败: {e}", exc_info=True)

def get_sync_record(source_id: str):
    """根据 source_id 从 tracker 表中获取记录"""
    if not engine:
        return None
    try:
        with engine.connect() as connection:
            result = connection.execute(
                text("SELECT * FROM sync_tracker WHERE source_id = :id"),
                {'id': source_id}
            ).first()
            return result
    except Exception as e:
        logging.error(f"查询同步记录失败: {e}", exc_info=True)
        return None

def update_sync_record(source_id: str, source_type: str, updated_at: datetime, dify_doc_id: str, status: str):
    """插入或更新一条同步记录"""
    if not engine:
        return
        
    # SQLite不支持丰富的ON CONFLICT语法，需要使用INSERT OR REPLACE或分开处理
    # 为了保持通用性，我们先尝试更新，如果失败则插入
    # 但是一个更简单的UPSERT模式是先删除后插入，或者使用更具体的方言
    # 这里我们使用通用的REPLACE INTO语法，它在SQLite中是UPSERT
    upsert_stmt = None
    if engine.url.drivername == 'sqlite':
        upsert_stmt = text("""
        INSERT OR REPLACE INTO sync_tracker (source_id, source_type, last_synced_update_time, dify_document_id, last_sync_status, last_synced_at)
        VALUES (:id, :type, :time, :dify_id, :status, CURRENT_TIMESTAMP);
        """)
    else: # 假设是PostgreSQL或其他支持ON CONFLICT的数据库
         upsert_stmt = text("""
        INSERT INTO sync_tracker (source_id, source_type, last_synced_update_time, dify_document_id, last_sync_status)
        VALUES (:id, :type, :time, :dify_id, :status)
        ON CONFLICT (source_id) DO UPDATE SET
            last_synced_update_time = EXCLUDED.last_synced_update_time,
            dify_document_id = EXCLUDED.dify_document_id,
            last_sync_status = EXCLUDED.last_sync_status,
            last_synced_at = CURRENT_TIMESTAMP;
        """)

    try:
        with engine.connect() as connection:
            trans = connection.begin()
            connection.execute(upsert_stmt, {
                'id': source_id,
                'type': source_type,
                'time': updated_at,
                'dify_id': dify_doc_id,
                'status': status
            })
            trans.commit()
    except Exception as e:
        logging.error(f"更新同步记录失败: {e}", exc_info=True)


if __name__ == '__main__':
    setup_database()
