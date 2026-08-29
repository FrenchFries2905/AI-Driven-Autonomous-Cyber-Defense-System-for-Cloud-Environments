# AI-Based Autonomous Threat Detection and Mitigation System for Cloud Environments

A prototype system that combines a Random Forest classifier (trained on the NSL-KDD benchmark dataset) with an AI Decision Agent to autonomously detect and respond to cybersecurity threats in cloud environments.

## Architecture

Six-layer pipeline:

```
Input Box
  → Data / Threat Analysis Layer
    → Infrastructure Layer
      → AI Decision Agent Layer
        → Automated Mitigation Layer
          → Evidence Aggregation & Reliability Engine
            → Output Box
```

Traffic is classified into 5 categories — **Normal, Probe, DoS, U2R, R2L** — and can trigger 4 mitigation actions: **Block IP, Trigger Alert, Restart Instance, Isolate Service**.

## Tech Stack

- **ML:** Python, Scikit-learn (Random Forest), NSL-KDD dataset
- **Backend:** FastAPI
- **Dashboard:** Streamlit
- **Containerization:** Docker / Docker Compose
- **Target deployment:** AWS / GCP

## Target Metrics

| Metric | Target |
|---|---|
| Classification accuracy | ≥ 96% |
| Precision/Recall (DoS, Probe) | ≥ 95% |
| Mean Time to Detect (MTTD) | < 5s |
| Mean Time to Respond (MTTR) | < 30s |
| False Positive Rate | < 3% |
| System uptime | ≥ 99.5% |

## Project Structure

```
.
├── data/                   # NSL-KDD raw & processed data (gitignored)
├── models/                 # Trained model artifacts (gitignored)
├── src/
│   ├── preprocessing/      # Encoding, scaling, pipeline
│   ├── model/               # Training & evaluation scripts
│   ├── api/                 # FastAPI backend
│   ├── agent/                # AI decision agent / policy engine
│   ├── mitigation/          # Mitigation action modules
│   └── reliability/         # Evidence logging & metrics tracking
├── dashboard/               # Streamlit app
├── tests/                   # Unit & integration tests
├── docker/                  # Dockerfiles per service
├── docker-compose.yml
├── requirements.txt
└── README.md
```

## Setup

```bash
# Clone and enter the repo
git clone <repo-url>
cd <repo-name>

# Create virtual environment
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Running Locally

```bash
# Run the API
uvicorn src.api.main:app --reload

# Run the dashboard (separate terminal)
streamlit run dashboard/app.py
```

## Running with Docker

```bash
docker-compose up --build
```

## Implementation Roadmap

See `implementation_todo.md` for the full 11-phase checklist. Critical path: **Phase 1 (Data Preparation) → Phase 2 (Model Training)** — all other components depend on a working classifier and preprocessing pipeline.

## Branching Strategy

- `main` — always deployable/stable
- `develop` — integration branch; feature branches merge here first
- `feature/<name>` — one per component (see table below)
- `fix/<name>` — bug fixes
- `test/<name>` — standalone testing work

| Branch | Phase |
|---|---|
| `feature/data-preprocessing` | 1 |
| `feature/model-training` | 2 |
| `feature/inference-pipeline` | 3 |
| `feature/api-backend` | 4 |
| `feature/decision-agent` | 5 |
| `feature/mitigation-layer` | 6 |
| `feature/evidence-reliability` | 7 |
| `feature/dashboard` | 8 |
| `feature/simulation-testing` | 9 |
| `feature/docker-deploy` | 10 |

Merge each feature branch into `develop` via PR once its checklist items are complete. Merge `develop` → `main` after end-to-end integration testing (Phase 9) passes.

## Dataset

[NSL-KDD](https://www.unb.ca/cic/datasets/nsl.html) — benchmark dataset for network intrusion detection, used for training and evaluating the classifier.

## License

TBD