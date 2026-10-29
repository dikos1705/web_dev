# Aeron — подготовка к защите / Defense notes

## Короткая демонстрация (3–5 минут)

1. `docker compose ps`: два здоровых контейнера — backend и database. Открыть localhost:8083, показать поиск Almaty → Astana на завтра, сортировку, цены и остаток мест.
2. Выбрать рейс, Standard, место у окна, ввести Alex Morgan / alex@example.com. Создать демонстрационную бронь, скачать маршрут. Открыть My bookings, изменить имя пассажира, обновить страницу — бронь остаётся.
3. В Postman импортировать коллекцию и приватное локальное окружение. Run collection: показать полный CRUD рейса и брони, 401 без ключа, 409 занятого места, 200 при повторе запроса, отмену и удаление.
4. `python verify.py --persistence`: показать конкуренцию и сохранение данных после удаления/создания контейнеров. Данные лежат в named volume, а не в файловой системе backend.
5. Объяснить services.py, models.py и compose.yaml. Все рейсы синтетические: нет интеграции авиакомпании, платежей или выдачи настоящих билетов.

## Вопрос → ответ / Question → answer

**What is FastAPI? / Что такое FastAPI?**

Python framework for typed HTTP APIs. Pydantic validates requests and response models; OpenAPI generates Swagger documentation. Здесь main.py описывает маршруты, schemas.py — контракт входа/выхода. Невалидные данные возвращают 422 до бизнес-операции.

**Why are routes ordinary `def`, not `async def`? / Почему обычные функции?**

The SQLAlchemy/psycopg database stack is synchronous. FastAPI runs synchronous endpoints in its worker thread pool, so database calls do not run directly on the event loop. Нельзя просто добавить async к блокирующим запросам и считать, что они стали неблокирующими.

**What does `Depends` do? / Для чего Depends?**

Dependency injection provides a per-request SQLAlchemy session and header-based authorization. `get_db` закрывает сессию после запроса; require_admin сверяет ключ, authorize_booking проверяет конкретный токен брони. Одна глобальная Session между потоками не используется.

**How do you prevent double booking? / Что если два клиента выберут одно место?**

All inventory writes lock the same flight row with SELECT FOR UPDATE inside one transaction. Второй запрос ждёт, затем видит уже занятое место и получает 409. Дополнительно частичный уникальный индекс `(flight_id, seat) WHERE status='confirmed'` не позволит сохранить дубликат даже при ошибке в коде. verify.py действительно отправляет два HTTP-запроса параллельно и проверяет один 201 и один 409.

**Why lock the flight before the booking? / Зачем одинаковый порядок блокировок?**

A consistent lock order reduces deadlock risk. Создание, изменение, отмена и удаление сначала блокируют рейс. Компромисс: разные места одного рейса тоже обрабатываются последовательно; для небольшого учебного сервиса это простой и понятный способ обеспечить корректность.

**What is a transaction? / Что такое транзакция?**

A group of changes committed together or rolled back together. В `with db.begin()` изменение места и проверка доступности относятся к одной операции. Если новое место занято, исключение откатывает всю операцию, старое место не теряется.

**Why an idempotency key? / Что если ответ потерялся?**

Client generates a UUID `request_key` once per booking intent. Exact retry returns the same booking with 200 instead of creating a duplicate. Сервер хранит уникальный ключ и хеш нормализованного запроса. Тот же ключ с другими данными → 409. Ключ приватный, повтор может восстановить токен управления; после удаления брони история повтора удаляется.

**How do you calculate money? / Почему не float?**

Integer KZT avoids floating-point rounding errors. Standard = ceil(base × 125 / 100), Flex = ceil(base × 150 / 100). Цена приходит из БД и рассчитывается сервером. Поле total_kzt от клиента запрещено, его нельзя подменить.

**How is access controlled? / Кто видит чужие брони?**

An admin key protects flight writes and booking lists. Each reservation has a separate HMAC-derived management token. Браузер не знает admin key, хранит только ID и токен своих броней. Это capability-based demo без аккаунтов: владелец токена может управлять бронью. Для публичного продукта нужны полноценные аккаунты, TLS и защита от злоупотреблений.

**Why can’t an administrator edit a booked flight? / Почему рейс с бронью нельзя поменять?**

Changing a flight would silently change an existing itinerary. Сервис запрещает изменение/удаление при любой истории бронирований, включая отменённые. Сначала нужно отменить и удалить связанные записи; это явное ограничение демо.

**PUT vs PATCH? / В чём разница?**

PUT replaces the complete editable representation, PATCH changes only supplied fields. PUT рейса требует все поля; PUT брони — имя и email. PATCH брони меняет непустой набор имени/email/места. null и неизвестные поля запрещены.

**401, 404, 409, 422? / Какие ошибки?**

401 missing/wrong key; 404 resource not found; 409 conflict with current state; 422 invalid input. Занятое место — корректный запрос, но конфликт состояния (409). Неверный формат места — нарушение контракта (422).

**Image vs container? / Образ и контейнер?**

An image is a packaged filesystem and startup configuration; a container is a running instance. Dockerfile собирает backend, Compose запускает его и PostgreSQL с настройками сети, переменных и тома. Изменение исходников требует `docker compose up -d --build`.

**Why is DB_HOST `database`? / Почему не localhost?**

Compose DNS resolves service names on the shared network. Inside backend, localhost means the backend container itself. PostgreSQL доступен как database:5432. Хост публикует только backend на 127.0.0.1:8083 → 8000; база наружу не опубликована.

**What survives `docker compose down`? / Что сохраняется?**

The named PostgreSQL volume survives container recreation. `down --volumes` deletes it deliberately. Нельзя менять BOOKING_SECRET при сохранении БД без понимания последствий: старые токены перестанут проходить проверку. Пароль уже созданной БД не меняется простым изменением .env.

**Why a healthcheck and depends_on? / Зачем healthcheck?**

A container being started does not mean the database is ready. pg_isready проверяет PostgreSQL; backend зависит от service_healthy. /health дополнительно выполняет SELECT 1. `--wait` ждёт здорового состояния сервисов.

**Where are secrets? / Где пароли?**

Generated locally in ignored `.env`, passed to containers at runtime. В Git только .env.example с шаблонами. Приватное Postman-окружение тоже игнорируется Git; готовый ZIP с локальными настройками сдаётся отдельно. Docker build context исключает эти файлы; процесс запускается с UID 10001.

**What would you improve for production? / Что дальше?**

Account authentication, TLS, rate limiting, migrations, monitoring, backups, real inventory and payment integration. create_all создаёт фиксированную учебную схему, но не заменяет миграции. В демо нет multi-city, round trips, групповых пассажиров или временных holds.

## Небольшое изменение на защите

Пример: добавить фильтр `max_price` в `flights()` через `Query(default=None, gt=0)`, затем `filters.append(Flight.price_kzt <= max_price)`, обновить API.md и Postman. Другой пример: поменять багаж Standard в FARES и проверить ответ API и карточку тарифа. Бизнес-правила следует менять на сервере, не только в JS.
