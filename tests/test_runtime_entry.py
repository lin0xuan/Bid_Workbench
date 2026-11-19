"""Contract checks for the workspace HTTP entry."""


def test_schema_lists_workspace_projects(client):
    schema = client.get('/openapi.json')
    assert schema.status_code == 200
    assert 'get' in schema.json()['paths']['/v1/projects']
    assert client.get('/ready').json()['database'] in {'sqlite', 'postgresql'}


def test_saved_project_is_visible_through_the_catalog(client):
    from bid_agent.apps.projects.models import Project

    created = client.post('/v1/projects', json={'title': '目录可见项目'})
    assert created.status_code == 201, created.text
    project_id = created.json()['id']
    assert Project.objects.filter(id=project_id, project_name='目录可见项目').exists()


def test_system_checks_and_migration_plan(client):
    from django.core.management import call_command

    call_command('check')
    call_command('makemigrations', '--check', '--dry-run', verbosity=0)
