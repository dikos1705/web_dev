"""Create local demo credentials without committing a password to Git."""
import argparse
from pathlib import Path
import secrets

parser = argparse.ArgumentParser()
parser.add_argument('--port', type=int, default=8083)
args = parser.parse_args()
if not 1024 <= args.port <= 65535:
    parser.error('Choose a port between 1024 and 65535')
target = Path(__file__).with_name('.env')
if target.exists():
    raise SystemExit('.env already exists; kept your settings unchanged.')
target.write_text(
    'POSTGRES_PASSWORD=' + secrets.token_urlsafe(32) + '\n'
    'POSTGRES_DB=dayboard\nPOSTGRES_USER=dayboard\n'
    f'APP_PORT={args.port}\nAPP_MESSAGE=Make room for good work.\n', encoding='utf8')
print(f'Created .env with a random local password. Open http://localhost:{args.port}')
