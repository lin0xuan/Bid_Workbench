# 后台迁移方案

本文说明当前代码里后台框架、数据所有权和尚未移交的部分。目标架构不能当成已经全部完成。

## 现状

HTTP 进程入口是 `bid_agent.main:app`。进程启动时初始化业务库，再用 Django 迁移创建框架自己的表。浏览器请求由 Django 接收，DRF 视图做会话、项目权限和 JSON 校验，然后调用 `api/routes` 里的操作函数。这些函数不再引用 FastAPI。解析、要求抽取、检索、章节、审查和导出仍走原来的 service。

业务表的建表权仍在 SQLite `platform_migrations`（当前 v9）和 PostgreSQL Alembic。Django 模型使用 `managed = False`，避免第二套 DDL。schema 初始化结束后，repository SQL 改走 Django 连接，并包在 `transaction.atomic()` 里。项目创建用 ORM 插入，成员关系用同一条连接上的 SQL 插入，一起提交或回滚。

账号仍使用 `users` / `sessions`。密码是 scrypt，不改成 Django 默认哈希。未登录返回 401，CSRF 失败返回 403。本地未开启 `BID_AUTH_ENABLED` 时仍是单用户。维护界面只读，不在那里改任务状态或审批结果。

## 数据所有权

| 范围 | 所有者 | 说明 |
| --- | --- | --- |
| 项目、文档、任务、知识、标书等业务表 | 现有 schema 工具 | Django 只读映射 |
| `django_*`、`auth_*` | Django migrations | 框架内部表，不是业务用户表 |
| 原件与导出文件 | `object_store` | 不因索引或框架切换删除 |
| 任务状态 | `jobs` / `outbox_events` | Celery 结果后端不是业务库 |

Worker 和 Dispatcher 只检查库是否就绪，不在自己的进程里建业务表。PostgreSQL 不再用 SQLite 文件是否存在来判断就绪。

## 已接入与未完成

已接入：

- 现有 `/api` 剥离后的路径、状态码、上传、下载和 JSON 错误体。
- 项目级访问在带 `project_id` 的工作台路由上先过滤。
- 只读维护页，地址在反代后的 `/api/admin/`。
- 关键词检索和可选 Chroma 仍由原检索代码执行。向量不可用时保持关键词结果，不把降级写成模型成功。

未完成，不能写成已经切换完毕：

- 查询和大部分写入仍是受控 SQL，只是和 ORM 处在同一个 Django 事务里，不是每条语句都改写成 ORM。
- 业务表还没有从 Alembic / `platform_migrations` 移交成 Django 建表。同一张表不能有两套 DDL。
- 混合向量检索、引用回跳和证据生成没有在这一轮重做评测。
- 没有做双写，也没有在生产库执行迁移。

## 切换与回退

先在副本上演练：停写、排空任务、备份 PostgreSQL 与对象目录，再启动新进程。Django 框架表可以随新版本出现。业务表结构没有改，因此仅框架表的新增不表示业务数据已换成另一套模型。

若新进程写入了只被新代码识别的状态，不能把旧镜像直接说成无损回退。应停写后恢复演练过的备份。原件、数据库和向量目录都不要删除。

## 对外说明时可以写的能力

可以写：Python 后台、DRF 接口、Serializer 校验、项目权限、SQLite / PostgreSQL、Celery、Redis、Outbox、Docker Compose、Nginx、文档解析、规则抽取、关键词检索、可选向量、章节草稿、审查闸门和 DOCX 导出。

需要限定的说法：BGE、Reranker、OCR、MinerU、Chroma 只有在对应依赖和配置打开时才存在。默认基础镜像不启用向量。图谱检索不在本仓库。项目创建走 ORM，其余写入是同一 Django 事务里的 SQL，业务表仍由原 schema 工具建表。
