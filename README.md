# Jira-Confluence-Dify 同步工具

自动将 Jira Issues 和 Confluence 页面同步到 Dify 知识库，支持增量更新和版本控制。

## 快速开始

### 1. 安装依赖

```bash
cd dify_sync_manager
pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `env.example` 为 `.env` 并填写：

```env
# Atlassian 配置
ATLASSIAN_URL="https://your-domain.atlassian.net"
ATLASSIAN_EMAIL="your-email@example.com"
ATLASSIAN_API_TOKEN="your-api-token"

# Jira 配置
JIRA_PROJECT_KEY="TEST"
JIRA_SINCE_DAYS="-30d"

# Confluence 配置
CONFLUENCE_SPACE_KEY="TESTSYNC"
CONFLUENCE_SINCE_DAYS="30"

# Dify 配置
DIFY_API_KEY="dataset-xxxxx"
DIFY_API_URL="https://api.dify.ai/v1"
DIFY_DATASET_ID="your-dataset-id"
```



### 3. 运行同步

```bash
python main.py
```

## 核心功能

-  **双数据源支持**：同时同步 Jira Issues 和 Confluence Pages
-  **版本控制**：数据库记录更新时间，仅同步有变化的内容
-  **增量更新**：避免重复上传，节省时间和资源
-  **自动重试**：失败记录可重新同步



## 日志查看

同步日志保存在 `sync.log` 文件中：

```bash
# Windows
type sync.log

# Linux/Mac
cat sync.log
```

## 项目结构

```
dify_sync_manager/
├── main.py              # 主程序
├── connectors.py        # Jira/Confluence 连接器
├── dify_client.py       # Dify API 客户端
├── database.py          # 数据库操作
├── requirements.txt     # Python 依赖
├── .env                 # 配置文件（需自行创建）
└── sync.log            # 运行日志
```

## 常见问题

### Q: 如何获取 Atlassian API Token？
1. 访问 https://id.atlassian.com/manage-profile/security/api-tokens
2. 点击 **Create API token**
3. 复制 token 到 `.env` 文件

### Q: 如何获取 Dify Dataset ID？
1. 在 Dify 知识库列表中打开目标知识库
2. 从 URL 复制 ID：`https://cloud.dify.ai/datasets/{ID}/documents`


