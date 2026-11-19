# Housekeeping: Git, .gitignore and pushing

Do this before anything else in this update. Your project folder was lost once before, and Git is the backup.

## 1. Add the new ignore rules

Run from the repo root (PowerShell). These lines keep large or local-only files out of Git:

```powershell
Add-Content .gitignore "lab/data/*.csv"
Add-Content .gitignore "models/live.json"
Add-Content .gitignore "evidence/"
Add-Content .gitignore "simulation/last_run.json"
```

- `lab/data/*.csv`: recorded lab flows and attack times (large, local).
- `models/live.json`: which model version is live on this PC.
- `evidence/`: the local evidence log.
- Model files are already ignored (`*.joblib`), so `models/versions/*.joblib` is covered.

## 2. Put the diagrams in the repo

The README links two images. Copy them into a `docs` folder:

```powershell
mkdir docs
copy "<path to>\system_architecture.png" docs\system_architecture.png
copy "<path to>\model_flowchart.png" docs\model_flowchart.png
```

## 3. Commit and push

```powershell
git status
git add .
git commit -m "Add model registry, retraining from lab traffic, model versions in the evidence log, README"
git push
```

- Read the `git status` list before committing. You should see source files, scripts and docs, and no `.csv`, `.joblib` or `.db` files.
- If `git push` complains about branches, run `git branch` to see where you are and push that branch: `git push origin <branch name>`.

## 4. Check on GitHub

Open the repo page. The README should show both diagrams. If an image is broken, the file name in `docs/` does not match the README link.
