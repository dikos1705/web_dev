# Aeron API reference

Base URL: `http://localhost:8083`. JSON request/response bodies unless stated otherwise. Live interactive specification: `/docs`; ReDoc: `/redoc`; OpenAPI: `/openapi.json`. All IDs and samples represent synthetic data.

## Authentication

Public: health, airports, flight search/details/seats and creation of a reservation.

- Admin routes: `X-Admin-Key: <ADMIN_API_KEY from local .env>`.
- Booking-specific routes: `X-Booking-Token: <manage_token returned at creation>`.
- Missing or incorrect keys return **401**. An admin key does not substitute for a booking token.
- Management token and private `request_key` are not URL parameters. Do not share them. Booking responses use `Cache-Control: no-store`. Admin lists never include management tokens.

## Endpoints

| Method | Path | Access | Success and behavior |
|---|---|---|---|
| GET | `/` | Public | 200 browser app (HTML) |
| GET | `/static/{asset}` | Public | 200 CSS, JavaScript or SVG |
| GET | `/health` | Public | 200 database connectivity; 503 if unavailable |
| GET | `/docs` | Public | 200 Swagger UI |
| GET | `/redoc` | Public | 200 ReDoc |
| GET | `/openapi.json` | Public | 200 generated API contract |
| GET | `/api/airports` | Public | 200 array of airport records |
| GET | `/api/flights` | Public | 200 `{flights: [...], total: n}` |
| GET | `/api/flights/{id}` | Public | 200 flight or 404 |
| GET | `/api/flights/{id}/seats` | Public | 200 seat map or 404 |
| POST | `/api/flights` | Admin | 201 created flight; 409 duplicate flight number/departure |
| PUT | `/api/flights/{id}` | Admin | 200 full flight replacement; 409 if booking history exists |
| DELETE | `/api/flights/{id}` | Admin | 204 empty body; 409 if booking history exists |
| POST | `/api/bookings` | Public | 201 created reservation + token; 200 exact retry |
| GET | `/api/bookings` | Admin | 200 `{bookings: [...], total: n}` |
| GET | `/api/bookings/{uuid}` | Owner token | 200 reservation or 404 |
| PUT | `/api/bookings/{uuid}` | Owner token | 200 replace passenger name and email |
| PATCH | `/api/bookings/{uuid}` | Owner token | 200 change supplied name/email/seat fields |
| POST | `/api/bookings/{uuid}/cancel` | Owner token | 200 cancelled reservation; repeat is safe |
| DELETE | `/api/bookings/{uuid}` | Owner token | 204 empty body; requires cancelled status |
| GET | `/api/bookings/{uuid}/itinerary` | Owner token | 200 downloadable UTF-8 text itinerary |

All missing resources return 404 after authorization where applicable. Invalid path IDs or bodies return 422. Integrity conflicts return 409. Database availability errors return 503. Unexpected properties in input JSON are rejected (422), rather than silently accepted. Successful deletes have no JSON body.

## Airport and search

Airport fields: `code`, `city`, `name`, `country`, IANA `timezone`. Supported codes: ALA, NQZ, CIT, SCO, DXB, IST.

`GET /api/flights?origin=ALA&destination=NQZ&departure_date=2026-10-30&sort=price&limit=10&offset=0`

All parameters optional. `origin` and `destination` are uppercase known IATA codes; when both are supplied, they must differ. Date format: YYYY-MM-DD, interpreted in the origin airport's timezone (Asia/Almaty if no origin filter). Only future departures are listed. The example date must be replaced with a date in the current demo horizon. `sort`: `departure` (default) or `price`. `limit`: 1–100, default 100; `offset`: nonnegative, default 0. Total counts records matching filters before pagination. Price ordering uses departure as a secondary sort; departure ordering uses ID to break ties.

Flight response: `id`, `number`, nested `origin` and `destination` airport objects, `departure_at`, `arrival_at` (timezone-aware), `duration_minutes`, `price_kzt`, `currency: "KZT"`, `available_seats`, `total_seats: 24`, `fares`. Seat response: `{flight_id, seats: [{label: "1A", available: true}, ...]}`. Rows 1–6, columns A/B/C/D; the GUI places an aisle between B and C. A snapshot of availability does not reserve a seat.

## Flight writes

POST and PUT use the same complete body:

```json
{
  "number": "AE9999",
  "origin_code": "ALA",
  "destination_code": "NQZ",
  "departure_at": "2030-10-30T07:00:00+05:00",
  "arrival_at": "2030-10-30T08:40:00+05:00",
  "price_kzt": 40000
}
```

Number: `AE` followed by 3–4 digits. Airports must exist and differ. Departure must be in the future, arrival later than departure, both timezone-aware. Price must be an integer in 1–5,000,000 KZT (booleans/fractions/strings rejected). Flight number plus departure timestamp is unique. PUT requires every field. PUT/DELETE refuse to alter a flight with any confirmed **or cancelled** booking history; cancel then delete the associated reservations first.

## Create and safely retry a reservation

```json
{
  "flight_id": 1,
  "seat": "2A",
  "fare": "standard",
  "passenger_name": "Alex Morgan",
  "email": "alex@example.com",
  "request_key": "8c29fd81-721a-463f-827e-93c92abf9500"
}
```

Use an actual future flight ID and a newly generated UUID for each new booking intent. `flight_id` is a positive integer. Fare is `light` (default), `standard` or `flex`. Name length 2–100 after trimming; email must be valid. Seat matches `^[1-6][A-D]$`.

201 returns `id` (UUID), eight-character `reference`, full `flight`, `seat`, `fare`, `passenger_name`, `email`, `total_kzt`, `currency`, `status: "confirmed"`, `created_at` and **`manage_token`**. `Location` points to the booking endpoint. Save ID and token privately. Token is omitted from ordinary GET/list responses.

Server calculates price from the stored flight: Light 100%, Standard 125%, Flex 150%, rounded **up** to whole KZT using integer arithmetic. Cabin/checked baggage: Light 7/0 kg, Standard 7/23 kg, Flex 10/32 kg. All three fares permit cancellation in this demo; none charges a fee or initiates a refund.

**Retry semantics:** send exactly the same normalized payload and `request_key` after a transport error. Response is 200 with the original reservation and token; no second seat is consumed. A reused key with different details returns 409. A replay after cancellation returns the existing cancelled record; it does not reactivate it. Deleting the record removes its replay history, so do not reuse an old key after deletion. Keep the key private because an exact replay recovers management access.

Booking an occupied seat or an already-departed flight returns 409. A flight row lock serializes inventory changes; a partial unique PostgreSQL index additionally enforces one confirmed booking per flight/seat. Confirmed inventory is permanent until cancellation, with no timed holds in this demo.

## Manage a reservation

Send the owner header on every request. PUT replaces both contact fields:

```json
{"passenger_name": "Alex Taylor", "email": "taylor@example.com"}
```

PATCH accepts any nonempty subset of `passenger_name`, `email`, `seat`:

```json
{"seat": "2D"}
```

Explicit nulls and unknown fields return 422. Flight and fare cannot be changed. Updates require a confirmed booking and a future departure (409 otherwise). Changing to an occupied seat returns 409; the old seat remains reserved because the transaction rolls back. An accepted change releases the old seat and keeps the original price/token/reference.

Cancellation uses POST with no body. Status becomes `cancelled` and inventory is released in the same transaction; repeating it returns the cancelled reservation. DELETE is permitted only after cancellation and permanently removes that record. A valid token for a deleted record returns 404. Itinerary is a text attachment with passenger, route, UTC departure, seat, fare, amount, status and demo disclosure; no email or actual ticket is sent.

Admin booking list: `limit` 1–100 (default 25), `offset` nonnegative (default 0), newest records first; no tokens or request keys are exposed.

## Error shape

Business/auth/not-found errors: `{"detail": "This seat was just booked. Please choose another seat."}`. Validation errors use FastAPI's `detail` array with `loc`, `msg`, `type` and optional context. Clients should inspect status + detail, not depend on an exact English message. 422 means the request violates the API contract; 409 means a valid request conflicts with current state.

The runnable exported Postman collection covers every domain endpoint, both update methods, authorization failures, seat conflict, idempotency, cancellation and deletion. It uses its own future test flight and removes it at the end.
