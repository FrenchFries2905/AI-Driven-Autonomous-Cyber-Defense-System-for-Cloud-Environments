# Retraining from lab traffic

What this does: the lab records every flow the sensor sees, and the attack scripts record the exact start and end time of each attack. That gives every flow a true label without guessing. A new Random Forest is trained on NSL-KDD plus those labeled flows, compared with the live model, and promoted only if it is better.

- **Champion:** the model that is live now.
- **Challenger:** the newly trained model.
- **Promote:** make the challenger the live model. The old one is kept, so you can roll back.

Total time: about 6 minutes of capture and 3 minutes of training.

## 0. Install the update (once)

1. Unzip `retraining_loop.zip` into your repo root and allow it to overwrite files.
2. Open `docker-compose.lab.yml`. In the `attacker:` service, add a `volumes:` block, so the attack scripts can record their times:
   ```yaml
     attacker:
       build:
         context: ./lab/attacker
       command: ["sleep", "infinity"]
       volumes:
         - ./lab/data:/data
       depends_on:
         - victim
   ```
3. Rebuild everything that changed:
   ```powershell
   $env:COMPOSE_FILE = "docker-compose.yml;docker-compose.lab.yml"
   docker compose up -d --build
   ```
4. Wait until `api` and `dashboard` show `healthy` in `docker compose ps`.

## 1. Start a fresh recording

```powershell
Remove-Item lab\data\flows.csv -ErrorAction SilentlyContinue
Remove-Item lab\data\attack_windows.csv -ErrorAction SilentlyContinue
docker compose restart sensor
```

- Old flows have no attack times, so they cannot be labeled. Starting fresh keeps the data clean.

## 2. Run the labeled session (about 6 minutes)

```powershell
docker compose exec attacker /attacks/session.sh
```

- It runs two rounds of: port scan, SYN flood on one port, SYN flood over many ports, with quiet periods in between. The benign visitor keeps running the whole time.
- Why two rounds: the second round of each attack becomes the lab test set, which the new model never trains on.
- Shorter pauses: `/attacks/session.sh 20`.

Check that the attack times were recorded:
```powershell
Import-Csv lab\data\attack_windows.csv | Format-Table
```
You should see 6 rows: 2 `portscan`, 2 `synflood_single_port`, 2 `synflood_random`.

## 3. Retrain and compare

Run this on your PC, in the environment you trained in, from the repo root:

```powershell
python -m src.model.retrain
```

What you will see:
- The benign visitor's address, and how many flows were labeled per class.
- A comparison table for KDDTest+ (the benchmark) and for the lab test flows: accuracy, macro-F1, attack detection rate, false positive rate, and recall per class, for the champion and the challenger.
- A list of promotion rules with PASS or FAIL.
- A result line: PROMOTED or REJECTED.

The rules the new model must pass:
- Lab macro-F1 improves.
- Lab attack detection does not drop.
- Lab false positives stay under 3%.
- KDDTest+ macro-F1 does not fall by more than 0.03. This stops the new model from forgetting what it learned from NSL-KDD.
- KDDTest+ false positives stay under 3.5%, or no worse than the champion.

Options:
- `--no-promote`: compare only.
- `--force`: promote even if a rule fails (not recommended).
- `--lab-weight 10`: make lab flows count more. The default is 5.

## 4. If it was promoted

```powershell
docker compose restart api
```

- Open http://localhost:8501. The mitigation log now has a **Model** column showing `v2`.
- Run the attack the old model missed:
  ```powershell
  docker compose exec attacker /attacks/synflood.sh 15
  ```
- Watch the detected threats and mitigated incidents tiles. Compare with before, when this flood was labeled Normal.

## 5. If it was rejected

- Read which rule failed.
- If the lab test is too small, run the session again (step 2) without deleting the files, to add more data.
- If KDDTest+ fell too much, try `--lab-weight 2`.
- Rejected models are kept as numbered files and never go live.

## 6. Roll back

```powershell
python -m src.model.registry list
python -m src.model.registry set 1
docker compose restart api
```

## What to paste back to me

- The full output of `python -m src.model.retrain`.
- The output of `Import-Csv lab\data\attack_windows.csv | Format-Table`.
- Any red error text.

## Notes

- Labels come from the attack times, so nothing is guessed. Flows outside attack windows that did not come from the benign visitor are dropped.
- This is the retraining half of the feedback loop. The analyst review tab will add human verdicts as another source of labels later.
- The challenger is saved as `models/versions/rf_vN.joblib`, with a report `rf_vN_report.json` next to it.
