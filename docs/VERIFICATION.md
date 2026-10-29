# Verification evidence

Verified locally on **29 October 2026**, using Docker Desktop with Linux
containers. The project runs independently from the Homework #2 containers.

## API and persistence

Command: `python verify.py --persistence`

- **76 HTTP status checks passed**, including GET list, GET by ID, POST, PUT,
  PATCH and DELETE; filter/search and statistics checks also passed.
- Tested invalid titles, priorities and boolean types; unknown/null fields;
  empty PATCH, incomplete PUT, malformed JSON, non-JSON content type and a
  body larger than 16 KiB; missing and out-of-range IDs.
- SQL/HTML-looking strings remain literal task titles.
- Ten concurrent inserts produced ten distinct IDs.
- Backend runs as UID 10001; `/app/.env` is absent from its image.
- Saved a completed high-priority task, removed both runtime containers with
  `docker compose down`, recreated both with `docker compose up -d --wait`, and
  verified its ID, title, priority and completion status. The named volume was kept.
- Created test tasks were removed; existing tasks were retained.

Machine-readable evidence: [verification-results.json](verification-results.json).
Retained console output: [api-verification.txt](api-verification.txt).

## Exported Postman Collection

Command: `docker compose --profile tools run --rm postman`

**17 requests, 34 assertions, zero failures.** This runs the actual exported
collection using the official Newman image, against the Compose backend over
its internal network. It verifies ID capture, CRUD, filtering, errors, operational
endpoints and automatic cleanup.

Retained console output: [postman-verification.txt](postman-verification.txt).

## Browser interface

Verified in the actual running page at `http://localhost:8083`:

- Create tasks with different priorities.
- Open the editor, change a title, save through PUT and observe the updated list.
- Mark a task complete and observe statistics.
- Filter completed tasks and return to All.
- Create and delete a temporary task.
- Reload the page and confirm the three demonstration tasks are retained.

The demonstration tasks are local database content, not automatic seed data.
A fresh database starts empty. [Screenshot](preview.png).

## Submission checks

The public branch includes source, Dockerfile, Compose, README, API docs,
OpenAPI and Postman exports. The real `.env` is Git-ignored and is included only
in the separately delivered ZIP. The archive is checked for required files and
ZIP integrity before handoff. Git metadata and database-volume contents are
excluded from it.
