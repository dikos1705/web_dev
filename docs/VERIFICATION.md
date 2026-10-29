# Verification evidence — Aeron

Local Docker verification, 29 October 2026. These results belong to the FastAPI Aeron version, not the earlier Flask project.

- `python verify.py --persistence`: **73 checks passed** against the real PostgreSQL container. Includes two concurrent HTTP requests competing for one seat (one 201, one 409), safe retries without duplicate reservations, protected ownership/admin operations, price calculation, flight and booking CRUD, validation, cancellation, seat reuse and container recreation with the named volume retained.
- `docker compose --profile tools run --rm postman`: **28 requests, 42 assertions, 0 failures**. The collection creates and removes its own temporary flight and booking.
- Backend runs as UID **10001**. `.env` is absent from the image.
- Browser demonstration: search, fare/seat choice, reservation confirmation and management. Screenshots in `preview.png`, `booking.png`, `trips.png`.

Machine-readable API evidence: `verification-results.json`. The integration script deliberately excludes credentials and management tokens from this report. Reproduce with the commands above. CI runs the same integration and Postman checks on every push to `midterm-project`.
