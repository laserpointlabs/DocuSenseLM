# Starting the UI

The UI can be run locally (recommended for development) or via Docker.

## Option 1: Run Locally (Recommended)

```bash
cd ui
npm install
npm run dev
```

Then access the UI at: **http://localhost:3000**

## Option 2: Run via Docker

If you prefer Docker, uncomment the `ui` service in `docker-compose.yml` and run:

```bash
docker-compose build ui
docker-compose up ui
```

## Environment Variable

Make sure `NEXT_PUBLIC_API_URL=http://localhost:8000` is set (either in `.env` or as an environment variable).
