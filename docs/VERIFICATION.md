# Verification — 2026-10-31

Local environment: Windows, Python 3.12.16, PostgreSQL 17.11. The database and API ran locally; SQLite was not used as a substitute.

| Check | Actual result |
| --- | --- |
| `python -m pytest -q -x --tb=short` | 45 passed, 5.41 seconds |
| `ruff check backend tests` | All checks passed |
| `ruff format --check backend tests` | 8 files already formatted |
| Uvicorn startup and `/health` | Started successfully; database query succeeds |
| Exported collection through real Newman | 26 requests, 40 assertions, 0 failures |

Pytest emitted one upstream deprecation warning: Starlette currently recommends `httpx2` instead of the supported `httpx` TestClient integration. It did not cause test failures.

Tests exercise seeded counts and data variety, individual criminal details, reward sorting in both directions, simultaneous filters (including `false`), invalid bounds and query values, complete hunt CRUD, server timestamp generation and immutability, PATCH semantics, missing and invalid IDs, invalid body data, idempotent import, PostgreSQL foreign keys and check constraints, and ORM relationships. Every test uses a temporary schema, removed afterward.

The actual exported Postman JSON was executed against the live Uvicorn API with PostgreSQL. Its temporary hunt was deleted by the collection. The initial 5 criminals and 10 logs remained afterward.

Docker/Compose were not installed on the local machine, so container checks ran on GitHub's Linux runner. [GitHub Actions run 41184887637](https://github.com/dikos1705/web_dev/actions/runs/41184887637) completed successfully for implementation commit `8db54a6`: PostgreSQL tests, lint/format, live API Newman collection, Docker image build, Compose startup, containerized Newman collection and non-root runtime user all passed.

To repeat the local database checks, configure `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, install `requirements-dev.txt`, then run the commands from README. To repeat the containerized checks, start Compose and run `docker compose run --rm postman`.
