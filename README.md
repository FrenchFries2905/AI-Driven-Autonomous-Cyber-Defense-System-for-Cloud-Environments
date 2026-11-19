# AI-Based Autonomous Threat Detection and Mitigation System for Cloud Environments

A prototype that detects network attacks with a Random Forest classifier, decides a response with an explainable rule table, carries out the response (simulated), and records everything in a log that cannot be edited. It can be demonstrated on real attack traffic inside a Docker lab.

- **Detect:** a Random Forest trained on NSL-KDD classifies each connection as Normal, Probe, DoS, R2L or U2R.
- **Decide:** a decision agent turns the class and the model's confidence into an action using `src/agent/policies.yaml`.
- **Respond:** four actions: block IP, trigger alert, isolate service, restart instance. They are simulated, logged and timed.
- **Prove it:** an append-only SQLite evidence log, plus MTTD, MTTR, SLO compliance and uptime.
- **Show it:** a FastAPI service, a Streamlit dashboard, and a Docker lab with a victim, benign traffic, an attacker and a live packet sensor.

![System architecture](docs/system_architecture.png)

How the model works step by step: [docs/model_flowchart.png](docs/model_flowchart.png)

## Results

| Measure | Value |
|---|---|
| Validation accuracy (20% of the training file) | 99.88% |
| Test accuracy on KDDTest+ | 74.7% |
| Weighted F1 / macro F1 on KDDTest+ | 0.70 / 0.51 |
| False positive rate on KDDTest+ | 2.87% |
| DoS precision / recall | 96.0% / 77.3% |
| Probe precision / recall | 84.7% / 66.8% |
| R2L recall | 0.9% |
| U2R recall | 10.4% |
| Simulated mitigation time | alert about 95 ms, isolate about 209 ms, restart about 784 ms |

The official test file contains attack types that are not in the training file, which is the most likely reason for the gap between validation and test accuracy. Most mistakes are attacks labeled Normal.

## Quick start (local, Windows PowerShell)

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
pip install matplotlib seaborn
```

1. Put `KDDTrain+.txt` and `KDDTest+.txt` in `data/raw/`. The dataset is not stored in Git. It is available from the [NSL-KDD page](https://www.unb.ca/cic/datasets/nsl.html).
2. Train and evaluate:
   ```powershell
   python -m src.model.train
   python -m src.model.evaluate
   ```
3. Run the API and the dashboard in two terminals:
   ```powershell
   uvicorn src.api.main:app --reload
   streamlit run dashboard/app.py
   ```
   API docs: http://127.0.0.1:8000/docs. Dashboard: http://localhost:8501.
4. Send traffic from a dataset replay in a third terminal:
   ```powershell
   python -m simulation.replay_stream --count 100
   ```

## Run everything with Docker, including the attack lab

```powershell
python scripts/make_requirements.py
$env:COMPOSE_FILE = "docker-compose.yml;docker-compose.lab.yml"
docker compose up -d --build
docker compose exec attacker /attacks/portscan.sh
docker compose exec attacker /attacks/synflood_random.sh 15
```

- Full guides: [DOCKER.md](DOCKER.md), [LAB_GUIDE.md](LAB_GUIDE.md), [DEMO_RUNBOOK.md](DEMO_RUNBOOK.md).
- The attacks only target the `victim` container. Never aim these tools at any other machine or network.

## Retraining from lab traffic

The lab records every flow and the exact time of every attack, so flows get ground-truth labels. `python -m src.model.retrain` trains a challenger model and promotes it only if it beats the live one. Models are versioned and can be rolled back. See [RETRAINING_GUIDE.md](RETRAINING_GUIDE.md).

## Tests

```powershell
pip install pytest httpx requests
python -m pytest
```

The API tests are skipped if the trained model files are missing.

## Project layout

```
src/
  preprocessing/   loader, encoding and scaling, inference pipeline
  model/           train, evaluate, retrain, model registry
  agent/           risk scoring and the policy engine (policies.yaml)
  mitigation/      the four actions and the dispatcher
  reliability/     evidence log and metrics
  api/             FastAPI app and routes
  orchestrator.py  classify, decide, mitigate, log in one call
dashboard/         Streamlit dashboard
simulation/        dataset replay and load test
lab/               sensor, attacker, benign traffic, recorded flows
docker/            Dockerfiles for the API and dashboard
tests/             pytest suite
scripts/           helper scripts
docs/              diagrams
```

## Limitations

- NSL-KDD is 1990s traffic, so results may not transfer to modern traffic.
- The live sensor computes about 28 of the 41 features. The content features (failed logins, root shell) need payload inspection, so they are 0, except `logged_in`, which is a simple guess. R2L and U2R attacks cannot be shown live.
- Mitigation actions are simulated by default and do not change the network.
- The API has no authentication yet.

## Planned work

- An analyst review tab, with an append-only reviews table, whose verdicts feed retraining.
- Real mitigation in the lab (firewall rule, container network cut) and alert webhooks.
- CICIDS2017 as a second, modern dataset.
- Deployment on a cloud platform.

## Team

Mohammed Adeen Khurshid, Mohammed Zuber Mulla, Mohammed Aziz Khazi, Moomin Mukhtar, Mohammed Zain I, Juliet Johny. HKBK College of Engineering, Bengaluru (VTU).

## License

See [LICENSE](LICENSE).
