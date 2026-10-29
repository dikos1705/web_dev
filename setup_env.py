"""Generate local-only credentials and a private Postman environment. No dependencies."""
import argparse
import json
from pathlib import Path
import secrets

ROOT = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument('--port', type=int, default=8083)
args = parser.parse_args()
if not 1024 <= args.port <= 65535:
    parser.error('Choose a port between 1024 and 65535')
target = ROOT / '.env'
if not target.exists():
    target.write_text('POSTGRES_PASSWORD='+secrets.token_urlsafe(32)+'\n'
        'POSTGRES_DB=aeron\nPOSTGRES_USER=aeron\n'+f'APP_PORT={args.port}\n'
        'ADMIN_API_KEY='+secrets.token_urlsafe(32)+'\n'
        'BOOKING_SECRET='+secrets.token_urlsafe(48)+'\nSEED_DEMO=true\n', encoding='utf8')
    print('Created .env with random local credentials.')
else:
    print('Kept existing .env settings.')
settings = dict(line.split('=',1) for line in target.read_text(encoding='utf8').splitlines() if line and not line.startswith('#'))
if not settings.get('ADMIN_API_KEY') or not settings.get('BOOKING_SECRET'):
    raise SystemExit('Existing .env needs ADMIN_API_KEY and BOOKING_SECRET; see .env.example.')
environment = {'name':'Aeron local (PRIVATE)', 'values':[
    {'key':'baseUrl','value':'http://localhost:'+settings.get('APP_PORT','8083'),'enabled':True},
    {'key':'adminKey','value':settings['ADMIN_API_KEY'],'type':'secret','enabled':True}],
    '_postman_variable_scope':'environment'}
folder=ROOT/'postman'
folder.mkdir(exist_ok=True)
(folder/'Aeron.local.private.postman_environment.json').write_text(json.dumps(environment,indent=2)+'\n',encoding='utf8')
print('Created ignored private Postman environment. Do not commit or share it publicly.')
print('Open http://localhost:'+settings.get('APP_PORT','8083'))
