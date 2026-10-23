# Attack lab: run guide

A small network inside Docker, with real traffic and real attacks, that your model classifies live.

```
benign (curl) ----\
                   >---->  victim (nginx)  <---- sensor (shares the victim's network, watches every packet)
attacker (nmap,   /                                  |
 hping3) ---------                                    v  features of each connection
                                       api:8000 /respond  ->  dashboard:8501
```

- **Sensor:** a program that watches packets, groups them into connections ("flows"), and computes the model's features.
- **Safety:** the attacker only targets the `victim` container inside this lab. Never aim these tools at any other machine or network.
- **Honest limit:** about 28 of the model's 41 features can be computed from packets. The 13 "content" features (failed logins, root shell and so on) are set to 0. This suits DoS and Probe attacks, which your model handles best. R2L and U2R cannot be shown live.

## 0. Before you start

- Docker Desktop is running: `docker run hello-world` prints a welcome message.
- Your trained model files exist in `models/` (`rf_classifier.joblib`, `encoders.joblib`, `scaler.joblib`, `feature_cols.joblib`).
- The Phase 10 files are in the repo (`docker-compose.yml`, `docker/`, `requirements-api.txt`, `requirements-dashboard.txt`). Run `python scripts/make_requirements.py` once if you have not.
- Stop any local `uvicorn` or `streamlit` terminals. The containers use ports 8000 and 8501.

## 1. Start the lab (Terminal 1)

```powershell
cd "<path to>\AI-Driven-Autonomous-Cyber-Defense-System-for-Cloud-Environments"
$env:COMPOSE_FILE = "docker-compose.yml;docker-compose.lab.yml"
docker compose up --build
```

- The first build takes a few minutes (it downloads nginx, Python and the attacker tools).
- `$env:COMPOSE_FILE` only lasts for this PowerShell window. Set it again in every new terminal, or the lab commands will not find the lab services.
- Wait until the log shows `sensor up:` and `sniffing...`.

## 2. Check everything is running (Terminal 2)

```powershell
cd "<path to>\AI-Driven-Autonomous-Cyber-Defense-System-for-Cloud-Environments"
$env:COMPOSE_FILE = "docker-compose.yml;docker-compose.lab.yml"
docker compose ps
docker compose logs -f sensor
```

- You should see 6 services: `api`, `dashboard`, `victim`, `sensor`, `benign`, `attacker`, all running (api and dashboard `healthy`).
- Open the dashboard at http://localhost:8501. Normal events start appearing within seconds, from the benign visitor.
- In the sensor log, normal traffic looks like `... -> http/SF ... | Normal 0.9x ... action=none`.
- Every 5 seconds the sensor prints a `STATS` line with packet, flow, posted and dropped counts.

## 3. Launch attacks (Terminal 3)

```powershell
cd "<path to>\AI-Driven-Autonomous-Cyber-Defense-System-for-Cloud-Environments"
$env:COMPOSE_FILE = "docker-compose.yml;docker-compose.lab.yml"

docker compose exec attacker /attacks/portscan.sh          # port scan, about 10 seconds
docker compose exec attacker /attacks/synflood.sh 20       # SYN flood for 20 seconds
docker compose exec attacker /attacks/demo.sh              # quiet period, then scan, then flood
docker compose exec attacker /attacks/icmpflood.sh         # optional ping flood
```

- Watch the sensor log and the dashboard while an attack runs.
- Port scan: many flows with service `private` and flag `REJ` or `RSTO`. Expected class: Probe.
- SYN flood: many flows with flag `S0`. Expected class: DoS.
- During a flood the sensor posts only what the API can keep up with. `dropped` in the STATS line counts the rest. They still count toward the windowed features.

## 4. What to paste back to me if something is off

- Output of `docker compose ps`
- The first 40 lines of `docker compose logs sensor`
- The sensor lines produced by one attack (the `STATS` lines before and after are helpful)
- The last 30 lines of `docker compose logs api` if the API returns errors
- Any red error text from the build step

## 5. See the features the model receives

```powershell
$env:SENSOR_VERBOSE = "1"
docker compose up -d --force-recreate sensor
docker compose logs -f sensor
```

- It prints the 41 features of the first 30 flows. These tell us whether the live features look like the ones the model learned.
- Set `$env:SENSOR_VERBOSE = "0"` and recreate the sensor to turn it off.
- `$env:SENSOR_DRY_RUN = "1"` computes features without posting to the API, which is useful to debug the sensor on its own.

## 6. Recorded flows

- The sensor appends the features of every flow to `lab/data/flows.csv`, with the source address and a timestamp.
- Because you know which container attacks and when, these flows can be labeled afterwards and used to retrain the model if live classification needs help.
- The file is not tracked by Git. Add `lab/data/*.csv` to `.gitignore`.

## 7. Settings you can change

Set them under `sensor: environment:` in `docker-compose.lab.yml`, then `docker compose up -d --force-recreate sensor`.

- `FLOW_TIMEOUT` (default 1.5): seconds of silence before a flow ends. Higher means longer flows and slower detection.
- `HOST_WINDOW` (default 255): how many recent connections the `dst_host_*` features look at.
- `TIME_WINDOW` (default 2.0): seconds for the `count` style features.
- `POST_WORKERS` (default 6) and `QUEUE_SIZE` (default 300): how fast flows are posted, and how many wait before being dropped.

## 8. Stop

```powershell
docker compose down        # stop the lab, keep the evidence log
docker compose down -v     # stop and delete the evidence log
```

## Troubleshooting

- **Sensor exits right away:** run `docker compose logs sensor`. Typical causes: the API was not healthy yet (it retries for 60 seconds), or the interface name is not `eth0` (set `SENSOR_IFACE`).
- **`service "api" ... depends_on`/not found:** the `$env:COMPOSE_FILE` variable is not set in this terminal.
- **Attack commands say the service is not running:** run them from the folder with the compose files, with `$env:COMPOSE_FILE` set.
- **No events on the dashboard:** check the STATS line. If `flows` stays at 0, the sensor sees no packets. If `posted` stays at 0, look for `post failed` or `API returned` lines.
- **Every attack comes out as Normal:** send me the verbose features (section 5). The fix is usually feature tuning or retraining on the recorded flows.
- **Sensor lost after the victim restarts:** restart it with `docker compose restart sensor`. It shares the victim's network, which changes when the victim restarts.
- **Scripts fail with `not found` or `^M`:** Windows line endings. The attacker image strips them on build. Rebuild with `docker compose build attacker`.
