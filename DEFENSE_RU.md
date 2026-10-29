# Dayboard: preparation for the online defense / Подготовка к защите

## A 5-minute demonstration / Демонстрация

1. Open this branch in your editor. Show `compose.yaml`, `Dockerfile` and `app.py`.
   / Открой эту ветку в редакторе, покажи файлы конфигурации и маршруты.
2. Run `docker compose up`. Open another terminal for `docker compose ps`.
   / Запусти приложение и покажи, что оба контейнера healthy.
3. Open `http://localhost:8083` and add/edit/complete a task.
   / Покажи, что интерфейс работает с реальной базой.
4. Import the Postman Collection and run requests 01-17 in order.
   / В Postman покажи GET списка, POST, GET по ID, PUT, PATCH и DELETE.
5. Show `python verify.py --persistence` if asked to prove persistent storage.
   / Этот скрипт пересоздаёт контейнеры проекта и проверяет сохранённую запись.

## Questions and answers / Вопросы и ответы

**What does the project do? / Что делает проект?**

EN: Dayboard is a task board. Flask provides REST endpoints, PostgreSQL stores
tasks, and Docker Compose starts the services together.

RU: Это планировщик задач. Flask обрабатывает HTTP, PostgreSQL хранит задачи,
а Compose запускает приложение и базу одной командой.

**Image vs container? / Образ и контейнер?**

EN: An image is a packaged filesystem and startup configuration. A container
is a running instance created from that image.

RU: Образ - шаблон файлов и настроек запуска; контейнер - запущенный экземпляр.

**What does the Dockerfile do? / Зачем Dockerfile?**

EN: It starts from Python slim, installs dependencies, copies source, switches
to a non-root user, declares the container port and starts Gunicorn.

RU: Описывает сборку backend: Python, зависимости, исходники, пользователь,
проверка здоровья и команда Gunicorn. EXPOSE сам не публикует порт на компьютере.

**What is Compose? / Что такое Compose?**

EN: A declarative configuration for services, networks, volumes and environment
variables. `docker compose up` builds/starts the complete application.

RU: YAML-конфигурация связанных сервисов, сетей, томов и переменных окружения.

**Why database:5432 instead of localhost? / Почему такой адрес базы?**

EN: Compose provides DNS for service names on the bridge network. In the backend,
localhost is the backend itself, so PostgreSQL is reached as database:5432.

RU: Имена сервисов работают как DNS внутри сети. localhost backend-контейнера
не указывает на контейнер базы.

**What does 8083:8000 mean? / Что означают два порта?**

EN: Host port 8083 forwards to container port 8000. The browser uses 8083;
another container calls backend:8000. PostgreSQL has no published host port.

RU: Слева порт компьютера, справа порт внутри контейнера. База наружу не открыта.

**Why a named volume? / Зачем именованный том?**

EN: The writable container filesystem is disposable. The named volume stores
PostgreSQL data separately and is reused after container recreation.

RU: Контейнер можно удалить, а том с данными остаётся. `down` сохраняет его,
`down -v` удаляет вместе с данными этого проекта.

**Why environment variables? / Зачем переменные окружения?**

EN: They separate configuration from source. The password is read at runtime;
the real .env is not committed or copied into the backend image.

RU: Пароль, порт и название базы можно менять без правки исходников. `.env`
передаётся отдельно, `.env.example` показывает только формат.

**What is CRUD? / Что такое CRUD?**

EN: Create = POST; read = GET; update = PUT/PATCH; delete = DELETE. PostgreSQL
executes INSERT, SELECT, UPDATE and DELETE behind those routes.

RU: Четыре операции с ресурсом. ID генерирует база; клиент берёт его из POST.

**PUT vs PATCH? / В чём разница?**

EN: Our PUT requires all editable fields. PATCH changes supplied fields and
keeps the rest. Both return 404 for a missing task; neither silently creates it.

RU: PUT заменяет все изменяемые поля, PATCH меняет только переданные.

**Why 201, 204, 400 and 404? / Зачем разные HTTP-коды?**

EN: 201 means created; 204 means successful deletion with no body; 400 is an
invalid request; 404 means the resource does not exist.

RU: HTTP-код описывает результат. В отрицательных тестах 400/404 ожидаемы.

**How are SQL injection and HTML titles handled? / Как обрабатываются SQL и HTML?**

EN: Values are bound through Psycopg placeholders. The frontend uses textContent
for task titles, so HTML-looking input is displayed as text.

RU: SQL-команды не склеиваются с пользовательскими значениями. Текст задачи
не вставляется в DOM как HTML.

**What does depends_on guarantee? / Что гарантирует depends_on?**

EN: With service_healthy, backend starts after the database healthcheck passes.
It does not guarantee permanent availability, so connection errors return 503.

RU: Ожидание готовности при старте; база всё ещё может стать недоступной позже.

## Live modification / Изменение на защите

- Change `APP_MESSAGE` in `.env`, run `docker compose up -d --force-recreate backend`,
  then refresh the page. Explain why `restart` alone does not inject new environment values.
- Add a simple `/api/version` GET route to `app.py` returning a JSON object, rebuild
  with `docker compose up -d --build --wait`, and call it in Postman.
- If port 8083 is busy, edit `APP_PORT`, recreate the backend, and update Postman's
  `baseUrl`. The internal port stays 8000.
- If you change the database password after first startup, explain that an existing
  volume already has initialized credentials; changing `.env` does not run initialization again.

Do not promise features that do not exist: this demo has no accounts,
authentication or public hosting. The assignment requires backend and database
containerization, documented CRUD and a working Postman Collection.
