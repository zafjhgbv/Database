import os
import logging
import re
from datetime import datetime, timedelta
from jira import JIRA
from atlassian import Confluence
from dotenv import load_dotenv
from dateutil import parser

load_dotenv()
ATLASSIAN_URL = os.getenv("ATLASSIAN_URL")
ATLASSIAN_EMAIL = os.getenv("ATLASSIAN_EMAIL")
ATLASSIAN_API_TOKEN = os.getenv("ATLASSIAN_API_TOKEN")

jira_client = None
confluence_client = None

if ATLASSIAN_URL and ATLASSIAN_EMAIL and ATLASSIAN_API_TOKEN and ATLASSIAN_API_TOKEN != "粘贴你从Atlassian官网获取的API Token":
    jira_client = JIRA(
        server=ATLASSIAN_URL,
        basic_auth=(ATLASSIAN_EMAIL, ATLASSIAN_API_TOKEN)
    )
    
    confluence_client = Confluence(
        url=ATLASSIAN_URL,
        username=ATLASSIAN_EMAIL,
        password=ATLASSIAN_API_TOKEN
    )

def get_jira_issues(project_key: str, since: str = "-7d"):
    """
    获取指定Jira项目中在特定时间后有更新的issues
    :param project_key: 项目的Key, 如 'PROJ'
    :param since: 时间范围, 如 '-1d', '-8h'
    :return: 一个包含issue信息的列表
    """
    if not jira_client:
        logging.warning("Jira client not initialized. Skipping Jira issue fetch.")
        return []

    logging.info(f"正在从 Jira 项目 {project_key} 中拉取数据...")
    try:
        # JQL: Jira Query Language
        jql_query = f"project = '{project_key}' AND updated >= '{since}' ORDER BY updated DESC"
        issues = jira_client.search_issues(jql_query, maxResults=100) # 注意分页问题，这里简化为最多100条

        formatted_issues = []
        for issue in issues:
            formatted_issues.append({
                'id': issue.key,
                'type': 'JIRA',
                'updated_at': issue.fields.updated,
                'content': f"标题: {issue.fields.summary}\n\n描述: {issue.fields.description or '无'}\n\n状态: {issue.fields.status.name}"
            })
        logging.info(f"成功拉取 {len(formatted_issues)} 条 Jira issues。")
        return formatted_issues
    except Exception as e:
        logging.error(f"从 Jira 拉取数据失败: {e}")
        return []

def get_confluence_pages(space_key: str, since_days: int = 7):
    """
    获取指定 Confluence 空间中最近更新的页面
    :param space_key: 空间的 Key，如 'TEAM'
    :param since_days: 获取最近 N 天更新的页面
    :return: 一个包含页面信息的列表
    """
    if not confluence_client:
        logging.warning("Confluence client not initialized. Skipping Confluence page fetch.")
        return []
    
    logging.info(f"正在从 Confluence 空间 {space_key} 中拉取数据...")
    try:
        # 计算起始日期
        since_date = datetime.now() - timedelta(days=since_days)
        
        # 获取空间中的所有页面
        pages = confluence_client.get_all_pages_from_space(
            space=space_key,
            start=0,
            limit=100,
            expand='version,body.storage'
        )
        
        formatted_pages = []
        for page in pages:
            # 解析更新时间
            updated_at = page['version']['when']
            updated_time = parser.isoparse(updated_at)
            
            # 只包含最近更新的页面
            if updated_time >= since_date.replace(tzinfo=updated_time.tzinfo):
                # 获取页面正文（HTML 格式）
                content_html = page.get('body', {}).get('storage', {}).get('value', '')
                
                # 简单的 HTML 清理（移除标签）
                content_text = re.sub(r'<[^>]+>', ' ', content_html)
                # 清理多余空白
                content_text = re.sub(r'\s+', ' ', content_text).strip()
                
                formatted_pages.append({
                    'id': str(page['id']),
                    'type': 'CONFLUENCE',
                    'updated_at': updated_at,
                    'content': f"标题: {page['title']}\n\n内容: {content_text[:5000]}"  # 限制长度
                })
        
        logging.info(f"成功拉取 {len(formatted_pages)} 个 Confluence 页面。")
        return formatted_pages
    except Exception as e:
        logging.error(f"从 Confluence 拉取数据失败: {e}")
        return []

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    
    logging.info("--- 测试 Jira 连接 ---")
    # 替换 'PROJ' 为你自己的真实项目 Key
    jira_data = get_jira_issues(project_key='PROJ', since='-30d')
    if jira_data:
        logging.info("成功获取到第一条 Jira issue:")
        logging.info(jira_data[0])
    
    logging.info("\n--- 测试 Confluence 连接 ---")
    # 替换 'TEAM' 为你自己的真实空间 Key
    confluence_space = os.getenv("CONFLUENCE_SPACE_KEY", "")
    if confluence_space:
        confluence_data = get_confluence_pages(space_key=confluence_space, since_days=30)
        if confluence_data:
            logging.info("成功获取到第一个 Confluence 页面:")
            logging.info(confluence_data[0])
    else:
        logging.warning("未配置 CONFLUENCE_SPACE_KEY，跳过 Confluence 测试。")
