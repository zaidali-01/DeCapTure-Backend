# DeCapTure Backend

## Run locally

1. Create and activate a virtual environment.
2. Install dependencies:
   `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and fill in your own values.
4. Make sure PostgreSQL is running and the database in `DATABASE_URL` exists.
5. Start the API:
   `uvicorn app.main:app --reload`

## Useful pages

- Owner workspace: `http://localhost:8000/owner`
- Customer chat: `http://localhost:8000/customer`
- API docs: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/health`
- Registered routes: `http://localhost:8000/health/routes`

## Notes for other laptops

- The app now includes startup schema patches for missing columns used by the communications flow.
- This helps older local databases start working, but proper Alembic migrations should still be added later.
- The PDF ingestion embedding is currently a fully local deterministic fallback, so it does not require model downloads.
