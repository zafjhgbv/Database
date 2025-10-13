import os
import requests
import logging
from dotenv import load_dotenv

load_dotenv()
DIFY_API_KEY = os.getenv("DIFY_API_KEY")
DIFY_API_URL = os.getenv("DIFY_API_URL")
DIFY_DATASET_ID = os.getenv("DIFY_DATASET_ID")

def upload_document_to_dify(doc_name: str, doc_content: str):
    """
    将单个文档上传到指定的Dify知识库
    :param doc_name: 文档名称 (如 Jira issue Key 'PROJ-123')
    :param doc_content: 文档的文本内容
    :return: 成功则返回 Dify 文档 ID，失败则返回 None
    """
    if not all([DIFY_API_KEY, DIFY_API_URL, DIFY_DATASET_ID]) or DIFY_API_KEY == "粘贴你的Dify API Key":
        logging.warning("Dify client not initialized. Skipping document upload.")
        return None

    logging.info(f"正在上传文档 '{doc_name}' 到 Dify...")
    
    # Dify API 使用 multipart/form-data 格式上传文件
    url = f"{DIFY_API_URL}/datasets/{DIFY_DATASET_ID}/document/create_by_text"
    headers = {"Authorization": f"Bearer {DIFY_API_KEY}"}

    # 准备表单数据
    data = {
        "name": doc_name,
        "text": doc_content,
        "indexing_technique": "high_quality",  # 或 "economy"
        "process_rule": {
            "mode": "automatic"
        }
    }

    try:
        # 尝试方法1：create_by_text 端点
        response = requests.post(url, headers=headers, json=data)
        
        if response.status_code == 404 or response.status_code == 405:
            # 如果方法1失败，尝试方法2：使用文件上传格式
            logging.info("尝试使用文件上传格式...")
            url = f"{DIFY_API_URL}/datasets/{DIFY_DATASET_ID}/document/create_by_file"
            
            # 创建一个临时文本文件
            files = {
                'file': (f'{doc_name}.txt', doc_content.encode('utf-8'), 'text/plain')
            }
            form_data = {
                'indexing_technique': 'high_quality',
                'process_rule': '{"mode":"automatic"}'
            }
            
            response = requests.post(url, headers=headers, files=files, data=form_data)
        
        response.raise_for_status()
        result = response.json()
        
        # Dify API 返回的文档 ID 可能在不同字段
        doc_id = result.get('document', {}).get('id') or result.get('id') or result.get('document_id')
        
        if doc_id:
            logging.info(f"文档上传成功！Dify Document ID: {doc_id}")
            return doc_id
        else:
            logging.warning(f"文档可能上传成功，但未获取到 ID。响应: {result}")
            return "uploaded_without_id"
            
    except requests.exceptions.RequestException as e:
        logging.error(f"上传到 Dify 失败: {e}")
        if hasattr(e, 'response') and e.response is not None:
            logging.error(f"状态码: {e.response.status_code}")
            logging.error(f"响应内容: {e.response.text}")
        return None

if __name__ == '__main__':
    logging.info("--- 测试 Dify 连接 ---")
    test_name = "TEST-001"
    test_content = "这是一个来自Python脚本的测试内容，用于验证Dify API连接。"
    document_id = upload_document_to_dify(test_name, test_content)
    if document_id:
        logging.info("测试成功！请到你的 Dify 知识库中查看是否存在 'TEST-001'。")
