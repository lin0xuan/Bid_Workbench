# 后台迁移验证

环境：Windows，Python 3.11.16，仓库 `Bid_Workbench`。未调用付费模型，未启动 Compose，未连接生产库。

## 已执行

| 命令 | 结果 |
| --- | --- |
| `python -m pytest -q` | **68 passed，4 skipped**。跳过项仍是未设置 `BID_TEST_DATABASE_URL` 的 PostgreSQL 用例 |
| `python -m ruff check backend tests scripts` | 通过 |
| 测试内 `check` 与 `makemigrations --check --dry-run` | 通过 |
| 新入口契约 | `/openapi.json` 含 `/v1/projects`；创建项目后 ORM 能读到同一行 |

SQLite 业务回归覆盖健康检查、登录、CSRF、上传、知识库、检索、目录、章节、矩阵、审查和 DOCX 下载。测试客户端改为 Starlette `TestClient`，并在测试进程里关闭 `BID_AUTH_ENABLED`，避免本机 `.env` 把套件变成必须登录。

## 未验证

- 独立 PostgreSQL 上的 Django 框架迁移与全量 pytest。
- 真实 Redis、Celery、失联恢复和重复投递。
- Compose 构建、Nginx 下的 `/api/admin/` 与静态资源。
- 浏览器里从登录到导出的手工点击。
- 扫描 PDF、MinerU、Chroma、付费模型。

Mock 或规则结果不能写成外部模型集成已通过。
