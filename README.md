# Homework #1 — Containerized Web Application

A small Python web server with an HTML/CSS/JavaScript interface, an interactive counter, and a configurable greeting. Author: Dias.

## Requirements

- Docker Desktop running in Linux containers mode (or Docker Engine on Linux).
- A free host port, such as 8080.

## Build and run

Open a terminal in this repository's directory:

```sh
docker build -t web-homework:1.0 .
docker run -d --name web-homework -p 127.0.0.1:8080:8000 -e APP_MESSAGE="Hello from Dias!" web-homework:1.0
```

Open **http://localhost:8080**. Click **Add one +** and **Reset** to try the counter. The greeting is loaded from the Python server, using the `APP_MESSAGE` environment variable.

`8080:8000` maps host port 8080 to container port 8000. The host binding is restricted to the local computer. The application listens on `0.0.0.0` inside the container so Docker can forward traffic to it.

## Verify and stop

```sh
docker ps --filter name=web-homework
docker logs web-homework
docker inspect --format='{{.State.Health.Status}}' web-homework
```

The health status becomes `healthy` after the health check runs. Visit http://localhost:8080/health for `{"status":"ok"}` and http://localhost:8080/api/info for the runtime greeting and port.

```sh
docker stop web-homework
docker rm web-homework
```

## Environment variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `APP_MESSAGE` | `Hello from Docker!` | Greeting displayed on the page |
| `PORT` | `8000` | Port listened to by the Python server |

To change both the greeting and the internal port, use a separate container:

```sh
docker run -d --name web-homework-custom -p 127.0.0.1:8081:9000 -e PORT=9000 -e APP_MESSAGE="My custom greeting" web-homework:1.0
```

Open http://localhost:8081. Clean up with `docker stop web-homework-custom` followed by `docker rm web-homework-custom`.

## Files and Dockerfile

- `app.py`: HTTP server and `/`, `/api/info`, `/health` routes; unknown routes return 404.
- `index.html`: responsive interface, counter, and API request.
- `Dockerfile`: image build and startup instructions.
- `.dockerignore`: allows only the application and Docker build files into the build context.
- `DEFENSE_RU.md`: explanation and live-change walkthrough in Russian.

| Instruction | Purpose |
| --- | --- |
| `FROM python:3.12-slim` | Small Python base image |
| `WORKDIR /app` | Working directory for subsequent instructions and startup |
| `ENV` | Default runtime settings, overridable with `docker run -e` |
| `RUN` | Creates a dedicated unprivileged user during the build |
| `COPY --chown` | Copies only the two required application files with appropriate ownership |
| `USER` | Runs the application without root privileges |
| `EXPOSE` | Documents the default container port; does not publish it |
| `HEALTHCHECK` | Requests the application's health endpoint |
| `CMD` | Starts Python using exec form |

Basic optimization: slim base, no third-party dependencies or package installation, minimal build context, and stable user-creation step before changing source files for build-cache reuse. A multi-stage build is unnecessary because this application has no compilation step. Python's standard-library HTTP server is sufficient for this classroom demonstration; it is not a production deployment server.

## Live change and rebuild

Change `Try the app` in `index.html` to `My updated app`, save, and run:

```sh
docker build -t web-homework:2.0 .
docker stop web-homework
docker rm web-homework
docker run -d --name web-homework -p 127.0.0.1:8080:8000 -e APP_MESSAGE="Updated version by Dias!" web-homework:2.0
```

Refresh http://localhost:8080 to see the updated heading. Source changes require rebuilding and recreating the container; changing `APP_MESSAGE` only requires recreating it with a new `-e` value.

## Automated verification

The GitHub Actions workflow in `.github/workflows/docker.yml` builds the image, runs two containers, and checks the HTML page, health endpoint, environment overrides, custom port, 404 responses, non-root user and Docker health status. See the repository's **Actions** tab for actual run results.

## Submit on GitHub

Repository: **https://github.com/dikos1705/web_dev**. To download it on another computer:

```sh
git clone https://github.com/dikos1705/web_dev.git
cd web_dev
```

Then follow the build and run commands above. Ensure the instructor can access the repository, submit **https://github.com/dikos1705/web_dev** in the homework page, then press **Turn In**.
