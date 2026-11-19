-- PostgreSQL baseline matching SQLite platform v9 plus legacy business tables.

-- Managed by Alembic b08_0001. Do not apply manually or stamp a partial schema.

-- TEXT JSON/timestamps and integer flags intentionally preserve the existing API contract.

CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE projects (
                id text primary key,
                project_name text,
                project_code text,
                project_category text,
                buyer_name text,
                agency_name text,
                budget_amount DOUBLE PRECISION,
                status text default '待核对',
                created_at text not null,
                updated_at text not null
            );

CREATE TABLE source_documents (
                id text primary key,
                project_id text,
                document_type text not null,
                file_name text not null,
                file_ext text,
                file_path text,
                parse_method text,
                parse_status text default '待解析',
                page_count integer,
                created_at text not null
            );

CREATE TABLE document_sections (
                id text primary key,
                document_id text not null,
                project_id text not null,
                section_index integer not null,
                parent_section_id text,
                title text,
                level integer,
                page_start integer,
                page_end integer,
                markdown text not null,
                plain_text text,
                section_type text,
                metadata_json text default '{}',
                created_at text not null
            );

CREATE TABLE document_chunks (
                id text primary key,
                project_id text,
                document_id text,
                section_id text,
                chunk_index integer not null default 0,
                chunk_type text not null,
                module text,
                title_path text,
                content text not null,
                content_markdown text,
                page_start integer,
                page_end integer,
                source_text text,
                tags_json text default '[]',
                metadata_json text default '{}',
                confirmed_status text default '未确认',
                created_at text not null
            );

CREATE TABLE knowledge_entries (
                id text primary key,
                type text not null,
                title text not null,
                tags text default '',
                date_text text default '',
                files text default '',
                content text default '',
                notes text default '',
                created_at text not null,
                updated_at text not null
            );

CREATE INDEX idx_knowledge_type on knowledge_entries(type);

CREATE INDEX idx_sections_project on document_sections(project_id);

CREATE INDEX idx_sections_document on document_sections(document_id);

CREATE INDEX idx_chunks_project on document_chunks(project_id);

CREATE TABLE extraction_runs (
                id text primary key,
                project_id text not null,
                document_id text,
                run_type text not null,
                llm_vendor text,
                llm_model text,
                prompt_version text,
                input_chunk_ids_json text default '[]',
                status text not null,
                error_message text,
                started_at text not null,
                finished_at text
            );

CREATE TABLE project_profile (
                id text primary key,
                project_id text not null,
                project_name text,
                project_code text,
                project_category text,
                service_period text,
                package_no text,
                budget_text text,
                budget_amount DOUBLE PRECISION,
                buyer_name text,
                agency_name text,
                industry_domain text,
                timeline_summary text,
                implementation_scope text,
                technical_features text,
                other_key_requirements text,
                is_sme_reserved integer,
                is_blind_bid integer,
                source_text text,
                confidence DOUBLE PRECISION,
                confirmed_status text default '未确认',
                created_at text not null,
                updated_at text not null
            );

CREATE TABLE qualification_requirements (
                id text primary key,
                project_id text not null,
                review_type text not null,
                sequence_no text,
                requirement_text text not null,
                required_materials text,
                is_mandatory integer default 1,
                risk_level text,
                source_page_start integer,
                source_page_end integer,
                source_heading text,
                item_sequence text,
                source_text text,
                metadata_json text default '{}',
                chunk_id text,
                confirmed_status text default '未确认',
                created_at text not null
            );

CREATE TABLE rejection_items (
                id text primary key,
                project_id text not null,
                sequence_no text,
                rejection_item text not null,
                specific_behavior text,
                risk_level text default '高',
                related_module text,
                check_method text,
                source_heading text,
                item_sequence text,
                source_text text,
                metadata_json text default '{}',
                chunk_id text,
                confirmed_status text default '未确认',
                created_at text not null
            );

CREATE TABLE business_requirements (
                id text primary key,
                project_id text not null,
                requirement_type text not null,
                item_name text,
                requirement_text text not null,
                amount DOUBLE PRECISION,
                ratio DOUBLE PRECISION,
                deadline_text text,
                is_mandatory integer,
                source_heading text,
                item_sequence text,
                source_text text,
                metadata_json text default '{}',
                chunk_id text,
                confirmed_status text default '未确认',
                created_at text not null
            );

CREATE TABLE technical_requirements (
                id text primary key,
                project_id text not null,
                requirement_group text,
                item_name text,
                parameter_name text,
                parameter_value text,
                requirement_text text not null,
                acceptance_criteria text,
                is_mandatory integer,
                importance_level text,
                source_heading text,
                item_sequence text,
                source_text text,
                metadata_json text default '{}',
                chunk_id text,
                confirmed_status text default '未确认',
                created_at text not null
            );

CREATE TABLE scoring_items (
                id text primary key,
                project_id text not null,
                score_type text not null,
                parent_item_id text,
                item_name text not null,
                scoring_standard text not null,
                score_value DOUBLE PRECISION,
                score_text text,
                evidence_required text,
                self_assessment text,
                source_heading text,
                item_sequence text,
                source_text text,
                metadata_json text default '{}',
                chunk_id text,
                confirmed_status text default '未确认',
                created_at text not null
            );

CREATE TABLE review_findings (
                id text primary key,
                project_id text not null,
                review_type text not null,
                module text not null,
                risk_level text not null,
                finding_title text not null,
                finding_detail text not null,
                source_text text,
                suggestion text,
                status text default '待处理',
                created_by text default '系统',
                created_at text not null
            );

CREATE TABLE chunk_embeddings (
                id text primary key,
                chunk_id text not null,
                embedding_model text not null,
                embedding_dim integer not null,
                vector_store text not null,
                vector_id text not null,
                indexed_at text not null
            );

CREATE TABLE companies (
                id text primary key,
                company_name text not null,
                short_name text,
                credit_code text,
                legal_representative text,
                registered_capital text,
                business_scope text,
                address text,
                contact_person text,
                contact_phone text,
                company_profile text,
                status text default '有效',
                created_at text not null,
                updated_at text not null
            );

CREATE TABLE company_qualifications (
                id text primary key,
                company_id text,
                qualification_type text not null,
                qualification_name text not null,
                certificate_no text,
                issuer text,
                issue_date text,
                expire_date text,
                valid_status text default '待核对',
                file_path text,
                applicable_scope text,
                notes text,
                created_at text not null
            );

CREATE TABLE company_personnel (
                id text primary key,
                company_id text,
                name text not null,
                role text,
                title text,
                certificates_json text default '[]',
                education text,
                years_experience DOUBLE PRECISION,
                project_experience text,
                file_path text,
                availability_status text default '可用',
                created_at text not null
            );

CREATE TABLE financial_records (
                id text primary key,
                company_id text,
                record_type text not null,
                fiscal_year integer,
                revenue DOUBLE PRECISION,
                net_profit DOUBLE PRECISION,
                total_assets DOUBLE PRECISION,
                tax_status text,
                social_security_status text,
                file_path text,
                notes text,
                created_at text not null
            );

CREATE TABLE performance_records (
                id text primary key,
                company_id text,
                project_name text not null,
                client_name text,
                industry_domain text,
                contract_amount DOUBLE PRECISION,
                contract_date text,
                acceptance_date text,
                project_scope text,
                proof_files_json text default '[]',
                reusable_points text,
                tags_json text default '[]',
                created_at text not null
            );

CREATE TABLE historical_cases (
                id text primary key,
                case_title text not null,
                related_project_id text,
                industry_domain text,
                case_type text not null,
                summary text not null,
                success_factors text,
                failure_reasons text,
                risk_points text,
                reuse_suggestion text,
                tags_json text default '[]',
                created_at text not null
            );

CREATE TABLE historical_bid_files (
                id text primary key,
                related_project_id text,
                file_type text not null,
                file_name text not null,
                file_path text,
                version text,
                project_name text,
                bid_result text,
                reusable_sections text,
                tags_json text default '[]',
                created_at text not null
            );

CREATE TABLE solution_materials (
                id text primary key,
                material_type text not null,
                title text not null,
                content text not null,
                applicable_domain text,
                applicable_project_type text,
                quality_level text,
                source_case_id text,
                source_bid_file_id text,
                tags_json text default '[]',
                confirmed_status text default '未确认',
                created_at text not null,
                updated_at text not null
            );

CREATE TABLE bid_generation_tasks (
                id text primary key,
                project_id text,
                task_type text not null,
                input_requirements_json text default '{}',
                retrieved_knowledge_ids_json text default '[]',
                output_markdown text,
                status text default '生成中',
                created_at text not null,
                updated_at text not null
            );

CREATE TABLE platform_migrations (
            version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL
        );

CREATE TABLE users (
            id TEXT PRIMARY KEY, username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL, is_admin INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );

CREATE TABLE sessions (
            token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED,
            expires_at DOUBLE PRECISION NOT NULL, created_at TEXT NOT NULL
        );

CREATE INDEX ix_sessions_expiry ON sessions(expires_at);

CREATE TABLE project_members (
            project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED,
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED,
            role TEXT NOT NULL CHECK(role IN ('owner','editor','viewer')),
            PRIMARY KEY(project_id,user_id)
        );

CREATE TABLE documents (
            id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED,
            title TEXT NOT NULL, kind TEXT NOT NULL,
            parent_document_id TEXT REFERENCES documents(id) ON DELETE SET NULL DEFERRABLE INITIALLY DEFERRED, created_at TEXT NOT NULL
        );

CREATE INDEX ix_documents_project ON documents(project_id);

CREATE TABLE document_versions (
            id TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED,
            version INTEGER NOT NULL, file_name TEXT NOT NULL, media_type TEXT NOT NULL,
            object_key TEXT NOT NULL, sha256 TEXT NOT NULL, size_bytes INTEGER NOT NULL,
            created_by TEXT NOT NULL REFERENCES users(id) DEFERRABLE INITIALLY DEFERRED, created_at TEXT NOT NULL,
            UNIQUE(document_id,version), UNIQUE(document_id,sha256)
        );

CREATE TABLE jobs (
            id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED,
            document_version_id TEXT NOT NULL REFERENCES document_versions(id) ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED,
            kind TEXT NOT NULL DEFAULT 'parse', status TEXT NOT NULL,
            options_json TEXT NOT NULL, idempotency_key TEXT NOT NULL, request_hash TEXT NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0, max_attempts INTEGER NOT NULL DEFAULT 3,
            available_at DOUBLE PRECISION NOT NULL DEFAULT 0, lease_token TEXT, lease_expires_at DOUBLE PRECISION,
            progress INTEGER NOT NULL DEFAULT 0, stage TEXT NOT NULL DEFAULT 'queued',
            error_code TEXT, error_message TEXT, retryable INTEGER NOT NULL DEFAULT 0,
            created_by TEXT NOT NULL REFERENCES users(id) DEFERRABLE INITIALLY DEFERRED, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            UNIQUE(project_id,idempotency_key)
        );

CREATE INDEX ix_jobs_recovery ON jobs(status,lease_expires_at,available_at);

CREATE INDEX ix_jobs_project ON jobs(project_id,created_at);

CREATE TABLE parsed_documents (
            id TEXT PRIMARY KEY, job_id TEXT NOT NULL UNIQUE REFERENCES jobs(id) ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED,
            document_version_id TEXT NOT NULL REFERENCES document_versions(id) ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED,
            parser_version TEXT NOT NULL, result_json TEXT NOT NULL, created_at TEXT NOT NULL
        );

CREATE TABLE job_events (
            sequence BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
            job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED,
            event_type TEXT NOT NULL, payload_json TEXT NOT NULL, created_at TEXT NOT NULL
        );

CREATE INDEX ix_job_events_cursor ON job_events(job_id,sequence);

CREATE TABLE outbox_events (
            id TEXT PRIMARY KEY, job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED,
            status TEXT NOT NULL DEFAULT 'pending', available_at DOUBLE PRECISION NOT NULL DEFAULT 0,
            attempts INTEGER NOT NULL DEFAULT 0, lease_token TEXT, lease_expires_at DOUBLE PRECISION,
            last_error TEXT, created_at TEXT NOT NULL, published_at TEXT
        );

CREATE INDEX ix_outbox_delivery ON outbox_events(status,available_at,lease_expires_at);

CREATE TABLE requirement_items (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED,
            document_version_id TEXT NOT NULL REFERENCES document_versions(id) ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED,
            job_id TEXT,
            category TEXT NOT NULL,
            field_key TEXT,
            title TEXT NOT NULL,
            raw_text TEXT NOT NULL,
            normalized_value TEXT,
            confidence DOUBLE PRECISION NOT NULL,
            review_status TEXT NOT NULL DEFAULT 'draft',
            source_refs_json TEXT NOT NULL,
            extractor_version TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

CREATE INDEX ix_requirements_version
            ON requirement_items(document_version_id, category, created_at);

CREATE INDEX ix_requirements_project
            ON requirement_items(project_id, review_status);

CREATE TABLE project_stages (
            project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED,
            stage TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending'
                CHECK(status IN ('pending','passed','skipped')),
            reviewer_id TEXT REFERENCES users(id) DEFERRABLE INITIALLY DEFERRED,
            notes TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL,
            PRIMARY KEY(project_id, stage)
        );

CREATE TABLE bid_versions (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED,
            document_version_id TEXT REFERENCES document_versions(id) ON DELETE SET NULL DEFERRABLE INITIALLY DEFERRED,
            title TEXT NOT NULL,
            outline_markdown TEXT NOT NULL,
            outline_json TEXT NOT NULL,
            score_coverage_json TEXT NOT NULL,
            created_by TEXT NOT NULL REFERENCES users(id) DEFERRABLE INITIALLY DEFERRED,
            created_at TEXT NOT NULL
        );

CREATE INDEX ix_bid_versions_project
            ON bid_versions(project_id, created_at);

CREATE TABLE bid_sections (
            id TEXT PRIMARY KEY,
            bid_version_id TEXT NOT NULL REFERENCES bid_versions(id) ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED,
            section_key TEXT NOT NULL,
            title TEXT NOT NULL,
            level INTEGER NOT NULL DEFAULT 1,
            sort_order INTEGER NOT NULL DEFAULT 0,
            body_markdown TEXT NOT NULL DEFAULT '', updated_at TEXT, updated_by TEXT,
            UNIQUE(bid_version_id, section_key)
        );

CREATE INDEX ix_bid_sections_version
            ON bid_sections(bid_version_id, sort_order);

CREATE TABLE compliance_runs (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED,
            bid_version_id TEXT REFERENCES bid_versions(id) ON DELETE SET NULL DEFERRABLE INITIALLY DEFERRED,
            document_version_id TEXT REFERENCES document_versions(id) ON DELETE SET NULL DEFERRABLE INITIALLY DEFERRED,
            checker_version TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'completed',
            summary_json TEXT NOT NULL,
            created_by TEXT NOT NULL REFERENCES users(id) DEFERRABLE INITIALLY DEFERRED,
            created_at TEXT NOT NULL
        , approval_status TEXT NOT NULL DEFAULT 'pending', approved_by TEXT, approved_at TEXT, approval_notes TEXT NOT NULL DEFAULT '');

CREATE INDEX ix_compliance_runs_project
            ON compliance_runs(project_id, created_at);

CREATE TABLE compliance_findings (
            id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL REFERENCES compliance_runs(id) ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED,
            project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED,
            check_name TEXT NOT NULL,
            severity TEXT NOT NULL CHECK(severity IN ('info','low','medium','high','critical')),
            title TEXT NOT NULL,
            detail TEXT NOT NULL,
            requirement_item_id TEXT,
            section_key TEXT,
            evidence_json TEXT NOT NULL DEFAULT '[]',
            decision_status TEXT NOT NULL DEFAULT 'open'
                CHECK(decision_status IN ('open','accepted','waived','fixed')),
            decision_notes TEXT NOT NULL DEFAULT '',
            decided_by TEXT REFERENCES users(id) DEFERRABLE INITIALLY DEFERRED,
            decided_at TEXT,
            created_at TEXT NOT NULL
        );

CREATE INDEX ix_compliance_findings_run
            ON compliance_findings(run_id, severity);

CREATE INDEX ix_compliance_findings_project
            ON compliance_findings(project_id, decision_status);

CREATE TABLE export_artifacts (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED,
            bid_version_id TEXT NOT NULL REFERENCES bid_versions(id) ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED,
            kind TEXT NOT NULL DEFAULT 'docx',
            file_name TEXT NOT NULL,
            object_key TEXT NOT NULL,
            sha256 TEXT NOT NULL,
            size_bytes INTEGER NOT NULL,
            created_by TEXT NOT NULL REFERENCES users(id) DEFERRABLE INITIALLY DEFERRED,
            created_at TEXT NOT NULL,
            force_skip_gate INTEGER NOT NULL DEFAULT 0,
            notes TEXT NOT NULL DEFAULT ''
        , template_id TEXT NOT NULL DEFAULT 'full', template_version TEXT NOT NULL DEFAULT 'export-template-v1', checklist_json TEXT NOT NULL DEFAULT '{}', parent_artifact_id TEXT);

CREATE INDEX ix_export_artifacts_project
            ON export_artifacts(project_id, created_at);

CREATE TABLE requirement_responses (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED,
            bid_version_id TEXT NOT NULL REFERENCES bid_versions(id) ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED,
            requirement_item_id TEXT NOT NULL REFERENCES requirement_items(id) ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED,
            section_id TEXT REFERENCES bid_sections(id) ON DELETE SET NULL DEFERRABLE INITIALLY DEFERRED,
            response_status TEXT NOT NULL DEFAULT 'uncovered'
                CHECK(response_status IN (
                    'uncovered','mapped','drafted','responded','waived','missing_material'
                )),
            is_mandatory INTEGER NOT NULL DEFAULT 0,
            response_summary TEXT NOT NULL DEFAULT '',
            missing_materials_json TEXT NOT NULL DEFAULT '[]',
            notes TEXT NOT NULL DEFAULT '',
            created_by TEXT NOT NULL REFERENCES users(id) DEFERRABLE INITIALLY DEFERRED,
            created_at TEXT NOT NULL,
            updated_by TEXT REFERENCES users(id) DEFERRABLE INITIALLY DEFERRED,
            updated_at TEXT NOT NULL,
            UNIQUE(bid_version_id, requirement_item_id)
        );

CREATE INDEX ix_requirement_responses_bid
            ON requirement_responses(bid_version_id, response_status);

CREATE INDEX ix_requirement_responses_project
            ON requirement_responses(project_id, is_mandatory);

CREATE TABLE compliance_decision_events (
            id TEXT PRIMARY KEY,
            finding_id TEXT NOT NULL REFERENCES compliance_findings(id) ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED,
            project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED,
            run_id TEXT NOT NULL REFERENCES compliance_runs(id) ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED,
            from_status TEXT,
            to_status TEXT NOT NULL,
            notes TEXT NOT NULL DEFAULT '',
            actor_id TEXT NOT NULL REFERENCES users(id) DEFERRABLE INITIALLY DEFERRED,
            created_at TEXT NOT NULL
        );

CREATE INDEX ix_compliance_decision_events_finding
            ON compliance_decision_events(finding_id, created_at);

CREATE TABLE audit_logs (
            id TEXT PRIMARY KEY,
            project_id TEXT REFERENCES projects(id) ON DELETE SET NULL DEFERRABLE INITIALLY DEFERRED,
            actor_id TEXT NOT NULL REFERENCES users(id) DEFERRABLE INITIALLY DEFERRED,
            action TEXT NOT NULL,
            object_type TEXT NOT NULL,
            object_id TEXT NOT NULL,
            summary TEXT NOT NULL,
            detail_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL
        );

CREATE INDEX ix_audit_logs_project
            ON audit_logs(project_id, created_at);

CREATE INDEX ix_audit_logs_object
            ON audit_logs(object_type, object_id, created_at);

CREATE TABLE enterprise_assets (
            id TEXT PRIMARY KEY,
            organization_key TEXT NOT NULL DEFAULT 'default',
            category TEXT NOT NULL CHECK(category IN (
                'qualification','personnel','financial','performance','case','template','other'
            )),
            title TEXT NOT NULL,
            subject_name TEXT NOT NULL DEFAULT '',
            certificate_no TEXT NOT NULL DEFAULT '',
            issuer TEXT NOT NULL DEFAULT '',
            issued_on TEXT,
            expires_on TEXT,
            status TEXT NOT NULL DEFAULT 'draft'
                CHECK(status IN ('draft','pending_review','active','expired','disabled')),
            review_notes TEXT NOT NULL DEFAULT '',
            tags_json TEXT NOT NULL DEFAULT '[]',
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_by TEXT NOT NULL REFERENCES users(id) DEFERRABLE INITIALLY DEFERRED,
            created_at TEXT NOT NULL,
            updated_by TEXT REFERENCES users(id) DEFERRABLE INITIALLY DEFERRED,
            updated_at TEXT NOT NULL
        );

CREATE INDEX ix_enterprise_assets_org_status
            ON enterprise_assets(organization_key, status, category);

CREATE INDEX ix_enterprise_assets_expires
            ON enterprise_assets(expires_on, status);

CREATE TABLE enterprise_asset_versions (
            id TEXT PRIMARY KEY,
            asset_id TEXT NOT NULL REFERENCES enterprise_assets(id) ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED,
            version INTEGER NOT NULL,
            file_name TEXT NOT NULL,
            media_type TEXT NOT NULL,
            object_key TEXT NOT NULL,
            sha256 TEXT NOT NULL,
            size_bytes INTEGER NOT NULL,
            created_by TEXT NOT NULL REFERENCES users(id) DEFERRABLE INITIALLY DEFERRED,
            created_at TEXT NOT NULL,
            notes TEXT NOT NULL DEFAULT '',
            UNIQUE(asset_id, version),
            UNIQUE(asset_id, sha256)
        );

CREATE INDEX ix_enterprise_asset_versions_asset
            ON enterprise_asset_versions(asset_id, version);

CREATE TABLE project_asset_links (
            project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED,
            asset_id TEXT NOT NULL REFERENCES enterprise_assets(id) ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED,
            linked_by TEXT NOT NULL REFERENCES users(id) DEFERRABLE INITIALLY DEFERRED,
            linked_at TEXT NOT NULL,
            PRIMARY KEY(project_id, asset_id)
        );

CREATE INDEX ix_project_asset_links_asset
            ON project_asset_links(asset_id);

CREATE TABLE index_versions (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED,
            kind TEXT NOT NULL DEFAULT 'keyword'
                CHECK(kind IN ('keyword','hybrid')),
            status TEXT NOT NULL DEFAULT 'ready'
                CHECK(status IN ('building','ready','failed','retired')),
            corpus_stats_json TEXT NOT NULL DEFAULT '{}',
            built_by TEXT NOT NULL REFERENCES users(id) DEFERRABLE INITIALLY DEFERRED,
            built_at TEXT NOT NULL,
            notes TEXT NOT NULL DEFAULT ''
        );

CREATE INDEX ix_index_versions_project
            ON index_versions(project_id, built_at);

CREATE TABLE document_chunks_fts (chunk_id TEXT PRIMARY KEY, project_id TEXT, module TEXT, item_type TEXT, section_id TEXT, title_path TEXT, content TEXT, metadata_text TEXT);

CREATE INDEX ix_chunks_fts_content ON document_chunks_fts USING gin (content gin_trgm_ops);

CREATE INDEX ix_chunks_fts_title ON document_chunks_fts USING gin (title_path gin_trgm_ops);

CREATE INDEX ix_chunks_fts_project ON document_chunks_fts(project_id);
