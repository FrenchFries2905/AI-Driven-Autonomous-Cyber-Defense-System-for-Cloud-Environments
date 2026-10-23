# Running the system with Docker

One command starts the API and the dashboard. Models stay on your machine and are mounted into the API container.

## Before the first run

1. **Pin the packages to your versions.** From the repo root, inside the virtual environment you trained the model with:
   ```powershell
   python scripts/make_requirements.py
   ```
   - It writes `requirements-api.txt`, `requirements-dashboard.txt` and `requirements.txt`, and a `.env` file with your Python version.
   - Why this matters: the trained model only loads reliably with the same scikit-learn and numpy versions that created it.
2. **Make sure the trained model exists.** These four files must be in `models/`: `rf_classifier.joblib`, `encoders.joblib`, `scaler.joblib`, `feature_cols.joblib`. If not, run `python -m src.model.train`.
3. **Stop the local copies.** Close the terminals running `uvicorn` and `streamlit`, because the containers use the same ports (8000 and 8501).

## Start

```powershell
docker compose up --build
```

- **API docs:** http://localhost:8000/docs
- **Dashboard:** http://localhost:8501
- The dashboard waits until the API reports healthy, which can take up to about 40 seconds while the model loads.

## Send traffic

Run these from your normal terminal, not inside a container. The API port is published, so they work unchanged:
```powershell
python -m simulation.replay_stream --count 100
```

## Stop

```powershell
docker compose down        # stop, keep the evidence log
docker compose down -v     # stop AND delete the evidence log
```

## Useful commands

- `docker compose logs -f api`: watch the API log
- `docker compose ps`: see whether each service is healthy
- `docker compose up --build`: rebuild after you change code
- After retraining the model, restart only the API: `docker compose restart api`. No rebuild is needed, because models are mounted, not baked in.

## What lives where

- **`docker/api/Dockerfile`:** installs the API packages and copies `src/`. Runs as a non-root user.
- **`docker/dashboard/Dockerfile`:** installs Streamlit and copies `dashboard/`.
- **`docker-compose.yml`:** wires them together. The dashboard reaches the API at `http://api:8000` (the service name), through the `API_URL` environment variable.
- **`./models`:** mounted read-only into the API container.
- **`evidence_data`:** a Docker-managed volume for the SQLite evidence log, so events survive restarts.

## Troubleshooting

- **Build says a package version is not found:** your `.env` has a Python version that does not match your pinned packages. Edit `PYTHON_VERSION` in `.env`, or re-run the script from the environment you trained in.
- **API stays unhealthy:** run `docker compose logs api`. The usual causes are missing files in `models/` or a scikit-learn version mismatch.
- **Port already in use:** another copy of the API or dashboard is still running. Stop it, or change the left-hand port numbers in `docker-compose.yml`.
- **Dashboard shows "Cannot reach the API":** wait for the API to become healthy, then refresh.
- **Uptime figure:** Docker's own health check calls `/health` every 30 seconds, and every call is stored as a health check, so uptime now includes that monitoring.
