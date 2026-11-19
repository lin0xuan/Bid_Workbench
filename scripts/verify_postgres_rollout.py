"""Synthetic HTTP/queue/export and post-restore verification. Never deletes projects."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import time
from uuid import uuid4

from docx import Document
import httpx


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='http://127.0.0.1:8080/api')
    parser.add_argument('--state-file', type=Path, required=True)
    parser.add_argument('--verify-state', action='store_true')
    args = parser.parse_args()
    with httpx.Client(base_url=args.base_url.rstrip('/'), timeout=60) as client:
        def call(method, path, **kwargs):
            response = client.request(method, path, **kwargs)
            response.raise_for_status()
            return response
        ready = call('GET', '/ready').json()
        assert ready['database'] == 'postgresql', 'Expected the PostgreSQL path'
        login = call('POST', '/auth/login', json={
            'username': os.environ['BID_VERIFY_USERNAME'], 'password': os.environ['BID_VERIFY_PASSWORD'],
        }).json()
        client.headers['X-CSRF-Token'] = login['csrf_token']
        if args.verify_state:
            state = json.loads(args.state_file.read_text(encoding='utf-8'))
        else:
            project = call('POST', '/v1/projects', json={'title': 'PostgreSQL 合成切流验收 ' + uuid4().hex[:8]}).json()
            project_id = project['id']
            document = Document()
            document.add_heading('第一章 招标公告', 1)
            document.add_paragraph('项目名称：PostgreSQL 切流验收服务项目。预算金额：100万元。')
            document.add_heading('第二章 技术与评分要求', 1)
            document.add_paragraph('投标人必须提供运维技术方案，技术方案完整性20分。')
            document.add_paragraph('故障响应时间不得超过2小时，提供全天候值守。')
            document.add_paragraph('弄虚作假的投标文件作废标处理。')
            stream = io.BytesIO()
            document.save(stream)
            original = stream.getvalue()
            upload = call('POST', f'/v1/projects/{project_id}/documents', files={
                'file': ('rollout.docx', original, 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'),
            }).json()
            version_id = upload['version']['id']
            headers = {'Idempotency-Key': uuid4().hex}
            job_path = f'/v1/document-versions/{version_id}/parse-jobs'
            job = call('POST', job_path, json={'parse_method': 'docx2python'}, headers=headers).json()['job']
            assert call('POST', job_path, json={'parse_method': 'docx2python'}, headers=headers).json()['job']['id'] == job['id']
            deadline = time.monotonic() + 120
            while time.monotonic() < deadline:
                status = call('GET', f'/v1/jobs/{job["id"]}').json()
                if status['status'] in {'succeeded', 'failed', 'cancelled'}:
                    break
                time.sleep(1)
            assert status['status'] == 'succeeded', 'Background parse did not succeed'
            items = call('POST', f'/v1/document-versions/{version_id}/requirements/extract', json={'use_llm': False}).json()['items']
            assert items
            for item in items:
                call('POST', f'/v1/requirements/{item["id"]}/review', json={'review_status': 'confirmed'})
            call('POST', f'/v1/projects/{project_id}/stages/requirements', json={'status': 'passed', 'notes': '合成测试确认'})
            bid = call('POST', f'/v1/projects/{project_id}/outline/from-requirements', json={'document_version_id': version_id}).json()['bid_version']
            for section in bid['sections']:
                call('PATCH', f'/v1/bid-sections/{section["id"]}', json={'body_markdown': '合成验收正文：提供全天候值守与两小时故障响应。', 'mark_generate_gate': True})
            call('POST', f'/v1/bid-versions/{bid["id"]}/response-matrix/rebuild')
            review = call('POST', f'/v1/projects/{project_id}/review-runs', json={'bid_version_id': bid['id']}).json()
            for finding in review['findings']:
                if finding['severity'] in {'high', 'critical'}:
                    call('POST', f'/v1/review-findings/{finding["id"]}/decide', json={'decision_status': 'accepted', 'notes': '仅合成回归验证，不作真实投标批准'})
            call('POST', f'/v1/review-runs/{review["id"]}/approve', json={'notes': '合成测试'})
            call('POST', f'/v1/projects/{project_id}/stages/check', json={'status': 'passed'})
            artifact = call('POST', f'/v1/projects/{project_id}/export-jobs', json={'bid_version_id': bid['id']}).json()['artifact']
            result = call('GET', f'/v1/jobs/{job["id"]}/result').json()
            state = {'project_id': project_id, 'version_id': version_id, 'job_id': job['id'],
                     'artifact_id': artifact['id'], 'original_sha256': hashlib.sha256(original).hexdigest(),
                     'export_sha256': artifact['sha256'], 'result_id': result['id']}
            args.state_file.parent.mkdir(parents=True, exist_ok=True)
            args.state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
        original = call('GET', f'/v1/document-versions/{state["version_id"]}/download').content
        exported = call('GET', f'/v1/exports/{state["artifact_id"]}/download').content
        assert hashlib.sha256(original).hexdigest() == state['original_sha256']
        assert hashlib.sha256(exported).hexdigest() == state['export_sha256']
        assert call('GET', f'/v1/jobs/{state["job_id"]}/result').json()['id'] == state['result_id']
        assert '合成验收正文' in '\n'.join(p.text for p in Document(io.BytesIO(exported)).paragraphs)
        print(json.dumps({'ok': True, 'database': 'postgresql', 'restored_state_verified': args.verify_state,
                          'project_id': state['project_id'], 'state_file': str(args.state_file)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
