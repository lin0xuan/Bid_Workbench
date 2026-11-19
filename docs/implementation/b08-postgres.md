# B08：PostgreSQL 切流实施与回滚手册

更新：2026-11-18。已实现双数据库运行、完整 Alembic 基线、离线迁移校验、受限应用账号和 PostgreSQL 备份路径；已在独立环境验证真实队列与恢复。**没有对用户生产库执行切流，也不代表整个产品已达到上线验收。** 实测范围见 [验证记录](../verification.md)。

## 1. 实现与边界

- `DATABASE_URL` 为空时使用 SQLite（`BID_DB_PATH`）；配置 PostgreSQL 后，新工作台、旧分析、知识库、检索、认证、API／Worker／Dispatcher 全部使用 PostgreSQL。连接或 schema 错误直接失败，不回退 SQLite。
- `infrastructure/db_connection.py` 统一 SQLAlchemy／psycopg 事务、连接池和参数绑定；Celery 按进程创建池，避免 fork 后复用连接。普通语句超时 60 秒，锁等待 30 秒，连接 5 秒，每进程最多 10 个池连接。
- 首版保留整数布尔值、TEXT JSON 和 ISO 时间字符串，避免同时改变 API 类型；REAL 映射 DOUBLE PRECISION，事件序号为 BIGINT identity。类型优化须另建 revision。
- `deploy/postgres/versions/b08_0001.py` 覆盖旧业务表和 SQLite platform v9。`schema_v1.sql` 是固定基线，不能手工执行或对旧草稿库直接 stamp。基线拒绝非空 schema；API 仅核验 Alembic revision，不自行建表。
- PostgreSQL 写事务使用事务级 advisory lock 保持现有串行写语义，跨 API／Worker／Dispatcher 生效。本版不宣称高并发扩容已经完成。
- PostgreSQL 旧分片检索使用 `pg_trgm` 子串候选与既有关键词评分；SQLite 继续 FTS5。迁库重建派生检索表，不复制 FTS 内部表。工作台检索仍是关键词实现；Chroma 向量索引需另行重建。
- 原件和导出仍存于本地 `bid-data` 对象目录；本次为单主机 Compose，不因换库就获得跨主机对象共享。

## 2. 配置与账号

基础依赖和锁文件已包含 SQLAlchemy、Alembic、psycopg。默认 Compose 五服务保持 SQLite 兼容；PostgreSQL 使用 `compose.yaml` 加 `compose.postgres.yaml`，新增常驻 postgres 和一次性 migrate。

在受保护的 `.env` 中配置实际强随机密码，URL 的特殊字符需编码：

```dotenv
POSTGRES_USER=bid_owner
POSTGRES_DB=bid_agent
POSTGRES_PASSWORD=<owner-password>
BID_MIGRATION_DATABASE_URL=postgresql+psycopg://bid_owner:<encoded-owner-password>@postgres:5432/bid_agent
DATABASE_URL=postgresql+psycopg://bid_app:<encoded-app-password>@postgres:5432/bid_agent
BID_ADMIN_USERNAME=<application-admin>
BID_ADMIN_PASSWORD=<12-to-256-character-password>
BID_COOKIE_SECURE=true
```

migrate 使用 schema owner 执行升级并创建／授权应用角色。API／Worker／Dispatcher 使用独立应用角色，只能读取 schema 版本、读写业务表和使用序列，不能在 public 建表或修改 Alembic 版本。拒绝高权限、继承其他角色、持有 DDL／对象所有权或迁移版本表写权限的应用账号；已有角色的密码不会自动重置。owner URL 与 owner 密码在业务容器环境中显式清空。

overlay 强制开启应用登录；公网须先配置 HTTPS，再使用 Secure Cookie。本机隔离演练可显式设 `BID_COOKIE_SECURE=false`。数据库不发布宿主机端口，镜像固定为已验证的 PostgreSQL 17 摘要。

外部托管库可直接配置一致的 DATABASE_URL，由运维使用 owner URL 执行 `python -m bid_agent.infrastructure.db_migrations upgrade`；设置 `BID_RUNTIME_DATABASE_URL` 可同时授权应用账号。应用启动前须完成 migration。Compose 备份脚本仅支持同 Compose 的 postgres；外部库须使用对应的一致性备份流程。

## 3. 全新空环境

```bash
docker compose -f compose.yaml -f compose.postgres.yaml config --quiet
docker compose -f compose.yaml -f compose.postgres.yaml build api web
docker compose -f compose.yaml -f compose.postgres.yaml up -d --wait --wait-timeout 180
curl --fail http://127.0.0.1:8080/api/ready
```

API 在 migrate 成功后启动，Worker／Dispatcher 等待 API healthy。ready 返回 `database=postgresql`。已有 SQLite 业务卷必须按下一节导入，不能把空 PostgreSQL 当作原业务库。

## 4. SQLite 离线切流

本版采用**停写后全量导入**，不提供双写或在线增量。先在独立项目和卷上演练，正式执行需维护窗口。

1. 保存旧提交、镜像 digest 和受保护的环境配置，源库升级至 SQLite platform v9。停止 web 入口，等待 running／cancelling 任务结束，再停止 dispatcher、worker、api。迁移器拒绝仍在执行或取消中的任务；queued／retry_wait 和 outbox 可保留。
2. 保持旧 SQLite 配置，执行 `python scripts/backup_data.py`。业务服务已停时脚本不会重新启动它们。用 `python scripts/drill_recovery.py --backup-dir <cold-backup> --expect-db` 校验；备份必须包含整个 storage，不能只复制 `.db`。
3. 更新 `.env` 为 PostgreSQL 配置，构建新镜像，仅启动 PostgreSQL 和 migration，暂不启动业务服务：

```bash
docker compose -f compose.yaml -f compose.postgres.yaml build api web
docker compose -f compose.yaml -f compose.postgres.yaml up -d --wait postgres
docker compose -f compose.yaml -f compose.postgres.yaml run --rm migrate
```

4. 替换下面宿主机绝对目录 `<cold-backup>`、`<reports>`；报告目录须提前创建。凭据继承 migrate 环境，不写进命令行：

```bash
docker compose -f compose.yaml -f compose.postgres.yaml run --rm --no-deps --user 0 \
  -v <cold-backup>:/backup:ro -v <reports>:/reports migrate \
  python /app/scripts/migrate_sqlite_to_postgres.py \
  --source /backup/storage/data/bid_agent.db --objects-root /backup/storage/objects \
  --report /reports/dry-run.json
```

Windows PowerShell 请写成单行或使用其续行语法。默认 dry-run 在事务内试导入、逐表验证后回滚，目标仍为空。报告 `ok=true` 后，在同一停写窗口重复该命令，改报告名并追加 `--apply --writers-stopped`。每次必须使用新的报告文件；工具在导入前验证可写并预留文件，拒绝覆盖既有报告或写入对象目录。若中途断连／进程终止，报告可能为 `applied=null` 或仅有 started 状态，此时先核验目标库，不能认定没有提交，也不能直接重跑。

迁移器检查 SQLite integrity／外键、全部表与字段、空目标库；未知表／列、原件或导出缺失、SHA-256／大小不符均拒绝。逐表比对行数和全部列的有序摘要，保留 ID、来源、权限、会话、任务、outbox、审批及导出元数据；失败整体回滚，不覆盖既有目标数据。报告不含业务行或密码。提交后修正 job_events 序列，避免新事件撞号。

5. 确认正式报告 `ok=true, applied=true`，保留原 bid-data 对象卷；使用新卷时按下一节恢复 storage 和权限，再启动全栈。检查 ready 类型、原用户登录、项目隔离、原件哈希、解析结果、历史导出与新解析，人工抽样签字后才开放业务入口。

工具不会恢复旧分析入口已删除的临时原件，也不迁移机器外 `file_path` 的实际文件；这些路径随记录保留，须单独盘点。不能因分析文字已迁移就宣称所有历史原件可用。

## 5. PostgreSQL 备份恢复

```bash
python scripts/backup_data.py -f compose.yaml -f compose.postgres.yaml
```

支持 `--env-file`、`-p/--project-name` 和 `--output-dir`。脚本停止此前运行的业务服务，执行 `pg_dump --format=custom --no-owner --no-acl`，复制 storage，生成包含 postgres.dump 的 SHA-256 manifest，再恢复此前服务。不是本 Compose 数据库或三业务进程 URL 不一致时拒绝。仅有 storage 的备份不算 PostgreSQL 完整备份。

恢复使用新项目、新卷和空数据库：

1. 校验 manifest 所有哈希，另行准备账号密码和部署环境。
2. 仅启动新 postgres，复制 dump 到容器，由 owner 执行 `pg_restore --single-transaction --exit-on-error --no-owner --no-acl`；不得向已有业务库使用 `--clean`。
3. `docker compose ... create api` 创建对象卷，`docker compose ... cp <backup>/storage/. api:/app/storage/` 复制对象，然后一次性修正权限：

```bash
docker compose -f compose.yaml -f compose.postgres.yaml run --rm --no-deps \
  --user 0 --cap-add CHOWN --cap-add DAC_OVERRIDE api chown -R 10001:10001 /app/storage
```

应用默认 `cap_drop: ALL`，仅 user 0 不足以 chown；上述能力只授予维护容器。

4. 运行 migrate 为恢复库重新授权应用角色，再启动全栈。

`scripts/verify_postgres_rollout.py` 使用 `BID_VERIFY_USERNAME`／`BID_VERIFY_PASSWORD` 登录，创建合成项目并验证队列、要求、审查、DOCX；不调用 LLM、不删除项目。先用 `--state-file <state.json>` 记录 ID／哈希，恢复后使用同一文件加 `--verify-state` 校验。可用 `--base-url` 指定独立验收环境；它不替代真实项目签字。

备份脚本已在 Linux 容器中实际执行成功，并将其产物恢复至另一独立 Compose 项目，通过原件／导出哈希、解析结果 ID 与 DOCX 正文比对。本机 Windows 的 Python 子进程仍存在 Docker 命名管道访问拒绝，脚本自身的 Windows 全程执行尚未通过；不能忽略退出码或把空目录当作备份。Windows 直接 PowerShell 执行同一组命令的独立恢复也已通过，详见验证记录。

## 6. 回滚边界与放行条件

- 尚未开放 PostgreSQL 写入：停止新业务服务，恢复旧环境配置和镜像，确认 DATABASE_URL 为空，用保留的 SQLite 冷备／对象卷重启旧部署并核验。保留 PostgreSQL 失败现场，不执行 `down -v`。
- PostgreSQL 已接受写入：不能直接指回旧 SQLite，否则丢失新增数据。本版没有反向增量迁移；应停止业务、修复 PostgreSQL或恢复最新一致备份，再制定经校验的数据补偿方案。
- Alembic baseline 禁止破坏性 downgrade，回滚不等于删除新库。
- 正式切流须具备真实源库迁移报告、对象校验、业务抽样、目标容量／锁等待／连接数检查、可接受恢复时间、HTTPS、密钥保管、异地备份与监控告警。此次小规模合成数据不代替这些签字。
- 迁库不修复其他模块既有缺口；本轮识别的审查与正文变更绑定问题另行处理，不能把 B08 验证通过视作整个产品上线许可。
