# Autonomous Game Developer Job Application Agent

A modular, production-quality AI agent built to discover, analyze, score, and track job applications for **Game Developers & Programmers** (specialized in Unity, C#, Gameplay Systems, UI/Tools, and AI/NPC programming).

---

## 🎯 Architecture Overview

```text
┌─────────────────────────┐
│ Candidate Profile JSON  │  <-- Single source of truth (zero fabrication)
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│       Raw JD Text       │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│     JD Analyzer         │  <-- Structured LLM extraction (Pydantic / OpenAI)
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  Hybrid Match Scorer    │  <-- Hard rule gates + weighted category scoring
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│   Resume Variant Engine │  <-- Recommends best PDF variant from registry
└───────────┬─────────────┘
            │
            ▼
┌──────────────────────────────────────────────────────────┐
│ Application Service                                      │
│  ├── Database (SQLite / SQLAlchemy)                      │
│  └── Excel Tracker (Adaptive openpyxl sync with backups) │
└──────────────────────────────────────────────────────────┘
```

---

## 🛠️ Quickstart Installation

### 1. Create and activate a virtual environment
```bash
python -m venv venv

# Windows (PowerShell)
.\venv\Scripts\Activate.ps1

# Linux / macOS
source venv/bin/activate
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure environment
```bash
cp .env.example .env
```
*(Optionally set `OPENAI_API_KEY` in `.env` if you want live OpenAI structured extraction; otherwise, the built-in heuristic parser handles offline testing without crashing).*

---

## 🧪 Running the Test Suite

Run the full pytest suite:
```bash
pytest tests/ -v
```

---

## 🚀 Running the Job Analyzer & Excel Sync CLI

### Run with the built-in Unity Gameplay Programmer sample JD:
```bash
python scripts/run_analyzer.py --sample
```

### Run with a custom job description file:
```bash
python scripts/run_analyzer.py --file path/to/job_description.txt --url https://company.com/jobs/123
```

### Inspect or initialize the Excel Tracker workbook:
```bash
python scripts/init_excel.py
```

The output Excel workbook will be automatically updated at `data/tracker.xlsx` (with timestamped backups preserved under `data/backups/`).
