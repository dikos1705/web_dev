"""Validate JSON before executing SQL. Missing and null are different values."""
FIELDS = {'title', 'priority', 'completed'}


def parse_task(data, mode):
    if not isinstance(data, dict):
        raise ValueError('Send a JSON object')
    if set(data) - FIELDS:
        raise ValueError('Unknown task field: ' + ', '.join(sorted(set(data) - FIELDS)))
    required = FIELDS if mode == 'replace' else {'title'} if mode == 'create' else set()
    if required - set(data):
        raise ValueError('Missing required field: ' + ', '.join(sorted(required - set(data))))
    if mode == 'patch' and not data:
        raise ValueError('Provide at least one of title, priority or completed')
    result = dict(data)
    if 'title' in result:
        title = result['title']
        if not isinstance(title, str) or not 1 <= len(title.strip()) <= 120:
            raise ValueError('Title must contain 1 to 120 characters')
        result['title'] = title.strip()
    if 'priority' in result:
        if not isinstance(result['priority'], str) or result['priority'] not in ('low', 'medium', 'high'):
            raise ValueError('Priority must be low, medium or high')
    if 'completed' in result and type(result['completed']) is not bool:
        raise ValueError('completed must be a JSON boolean')
    if mode == 'create':
        result.setdefault('priority', 'medium')
        result.setdefault('completed', False)
    return result
