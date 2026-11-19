# 运维演练（B16 草稿）

## 恢复演练

1. `python scripts/backup_data.py --output-dir backups`
2. `python scripts/drill_recovery.py --backup-dir backups/<stamp> --expect-db`
3. 在**非生产** Compose 项目中恢复 storage 卷后，检查 `/healthz` 与主流程。

本草稿只验证备份清单哈希；完整切流／RTO 需单独环境签字。

2026-11-18：PostgreSQL 使用 `backup_data.py -f compose.yaml -f compose.postgres.yaml`，备份同时包含 custom dump 和对象目录。`drill_recovery.py --expect-db` 根据 manifest 检查数据库类型，拒绝空哈希清单、越界路径或缺失／损坏 dump。独立恢复后，可用 `verify_postgres_rollout.py --state-file <state.json> --verify-state --base-url <恢复环境/api>` 比较同一合成项目的原件、解析结果与 DOCX。此次已有小规模恢复验证，不等于正式 RTO／容量验收；完整步骤见 [B08](../implementation/b08-postgres.md)。

## 容量探测

```bash
python scripts/drill_capacity.py --base-url http://127.0.0.1:8080 --rounds 20
```

仅探测网关健康接口延迟，不代表解析队列或 LLM 容量。

## 迁库准备（B08）

```bash
python scripts/sqlite_inventory.py --output storage/reports/sqlite-inventory.json
```

见 [b08-postgres](../implementation/b08-postgres.md)。
