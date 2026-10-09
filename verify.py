"""Black-box API + Compose persistence checks. Python standard library only."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import subprocess
import urllib.request
import urllib.error
import uuid


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-url', default='http://127.0.0.1:8082')
    parser.add_argument('--persistence', action='store_true', help='Recreate this Compose project without removing its volume')
    args = parser.parse_args()

    def api(path, method='GET', data=None, expected=200, raw=None):
        body = raw if raw is not None else json.dumps(data).encode() if data is not None else None
        request = urllib.request.Request(args.base_url+path, data=body, method=method,
                                         headers={'Content-Type': 'application/json'})
        try:
            response = urllib.request.urlopen(request, timeout=10)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            assert response.status == expected, (method, path, response.status, expected)
            payload = response.read()
            return json.loads(payload) if payload else None

    def compose(*commands, capture=False):
        result = subprocess.run(['docker', 'compose', *commands], check=True, text=True,
                                capture_output=capture)
        return result.stdout.strip() if capture else None

    with urllib.request.urlopen(args.base_url+'/') as response:
        assert b'dayboard' in response.read()
    assert api('/health') == {'status': 'ok', 'database': 'connected'}
    assert api('/api/info')['port'] == 8000
    api('/missing', expected=404)
    before = api('/api/stats')
    marker = 'Test '+uuid.uuid4().hex
    task = api('/api/tasks', 'POST', {'title': '  '+marker+'  ', 'priority': 'high'}, 201)
    task_id = task['id']
    assert task['title'] == marker and not task['completed'] and task['created_at']
    assert any(t['id'] == task_id for t in api('/api/tasks')['tasks'])
    after = api('/api/stats')
    assert after['total'] == before['total']+1 and after['urgent'] == before['urgent']+1
    changed = api(f'/api/tasks/{task_id}', 'PATCH', {'completed': True})
    assert changed['completed'] and api('/api/stats')['completed'] == before['completed']+1
    assert api(f'/api/tasks/{task_id}', 'PATCH', {'completed': False})['completed'] is False
    for data in [{'title': ''}, {'title': ' '*4}, {'title': 'a'*121}, {'title': 42},
                 {'title': 'x', 'priority': 'urgent'}, {'title': 'x', 'priority': []}, []]:
        api('/api/tasks', 'POST', data, 400)
    api('/api/tasks', 'POST', raw=b'null', expected=400)
    api('/api/tasks', 'POST', raw=b'{broken', expected=400)
    api(f'/api/tasks/{task_id}', 'PATCH', {'completed': 'true'}, 400)
    api('/api/tasks/2147483647', 'PATCH', {'completed': True}, 404)
    api('/api/tasks/2147483647', 'DELETE', expected=404)
    # Parameterized SQL must store this as ordinary text, not execute it.
    text = "x'); DROP TABLE tasks; -- <script>alert(1)</script>"
    literal = api('/api/tasks', 'POST', {'title': text}, 201)
    assert literal['title'] == text
    api(f"/api/tasks/{literal['id']}", 'DELETE', expected=204)
    api(f'/api/tasks/{task_id}', 'DELETE', expected=204)
    api(f'/api/tasks/{task_id}', 'DELETE', expected=404)
    with ThreadPoolExecutor(max_workers=5) as pool:
        created = list(pool.map(lambda i: api('/api/tasks', 'POST', {'title': f'{marker} concurrent {i}'}, 201), range(10)))
    assert len({t['id'] for t in created}) == 10
    for task in created:
        api(f"/api/tasks/{task['id']}", 'DELETE', expected=204)
    assert api('/api/stats') == before
    print('PASS: HTML, health, API create/read/update/delete, statistics, validation, SQL literal and 10 concurrent writes')

    if args.persistence:
        assert compose('exec', '-T', 'backend', 'id', '-u', capture=True) == '10001'
        compose('exec', '-T', 'backend', 'sh', '-c', 'test ! -e /app/.env')
        task = api('/api/tasks', 'POST', {'title': marker+' persistence', 'priority': 'high'}, 201)
        api(f"/api/tasks/{task['id']}", 'PATCH', {'completed': True})
        old_ids = set(compose('ps', '-q', capture=True).splitlines())
        assert len(old_ids) == 2
        compose('down')  # Keep the named volume. No --volumes option.
        compose('up', '-d', '--wait', '--wait-timeout', '180')
        new_ids = set(compose('ps', '-q', capture=True).splitlines())
        assert len(new_ids) == 2 and not (old_ids & new_ids)
        restored = next(t for t in api('/api/tasks')['tasks'] if t['id'] == task['id'])
        assert restored['title'] == task['title'] and restored['priority'] == 'high' and restored['completed']
        api(f"/api/tasks/{task['id']}", 'DELETE', expected=204)
        assert api('/api/stats') == before
        print('PASS: non-root backend, no .env in image; data survives removal and recreation of BOTH containers')


if __name__ == '__main__':
    main()
