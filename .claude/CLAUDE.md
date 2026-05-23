# Music Discovery Engine

## Project Overview

Personalized music discovery platform that finds recommendations through meaningful connections (shared producers, session musicians, label relationships) rather than similarity-based algorithms. Two deliverables: weekly recommendation email and web-based knowledge graph explorer.

## Required Reading

Before working on recommendation logic, graph traversal queries, or data-source integration, read `docs/music-discovery-project-context.md`. It contains the core algorithm (multi-path intersection), signal quality by connection type, traversal depth findings, validated MusicBrainz SQL patterns, key tables, and data-source licensing constraints (Last.fm commercial use, Spotify/Bandcamp limits).

## Tech Stack

- **Backend**: FastAPI (Python 3.14)
- **Databases**: Dual Postgres on one instance (`tbc_postgresql_db`)
  - `musicbrainz` — read-only mirror, reflected via SQLAlchemy automap
  - `music_discovery` — read-write app DB, declarative models + Alembic
- **Driver**: psycopg (v3)
- **Package manager**: uv
- **Infrastructure**: Docker, Traefik reverse proxy, devcontainer for development

## Development Environment

- Devcontainer runs on the `proxy` Docker network alongside Postgres and Traefik
- App URL (from host): `https://music-discovery-api.localhost`
- Postgres host (from containers): `tbc_postgresql_db:5432`, credentials `root`/`root`
- Dependencies install to `/usr/local` (not `.venv`) — `UV_PROJECT_ENVIRONMENT=/usr/local`
- Use `sudo uv sync --link-mode=copy` to sync deps in the devcontainer
- Task runner: `Taskfile.yml` (e.g., `task up`, `task test`, `task migrate`)

## Project Structure

```
app/                  # Application package
  config.py           # Pydantic Settings (DB URLs from env vars)
  database.py         # Engines, session factories, DB bootstrap
  models/
    app.py            # Declarative models (Base + User)
    musicbrainz.py    # Automap reflection wrapper
main.py               # FastAPI app, lifespan handler, health endpoint
alembic/              # Migrations (app DB only)
tests/                # pytest
```

## Conventions

- Router/service/repository pattern for domain logic (not yet implemented)
- MusicBrainz DB: use automap for simple lookups, raw SQL for complex graph traversal queries
- MBIDs (UUIDs) are the join key between the two databases
- Never run migrations against the MusicBrainz database

## Running Tests

```
pytest tests/ -v
```

## Key Commands

```
task up        # Build and start containers
task test      # Run tests in container
task migrate   # Run Alembic migrations
task migration -- 'description'  # Create new migration
```
