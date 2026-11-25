# EventPulse AI

**Real-Time Event Feedback Analysis, Platt-Calibrated Disengagement Prediction & Explainable SHAP Attribution**

EventPulse AI replaces delayed post-event evaluation surveys with continuous, privacy-preserving live audience telemetry. During lectures, seminars, or technical workshops, attendees submit frictionless 1-tap reactions, live poll votes, and anonymous Q&A from their phones—while presenters see calibrated disengagement risk probabilities, local SHAP root-cause explanations, and NLP-classified Q&A in real time over WebSockets.

> **One-Line AI Handoff Prompt:** `Read README.md, backend/app/main.py, backend/app/api/routes.py, backend/app/services/ml_engine.py, backend/app/services/sanitizer.py, and frontend/src/App.jsx to understand EventPulse AI (FastAPI + WebSockets + SQLite + Platt-calibrated CatBoost + SHAP + VADER/Intent NLP + React/Tailwind), then help me extend or customize it while keeping all paths relative, DPDP PII masking intact, and tests passing.`

---

## 1. How to Run (Step-by-Step)

### Prerequisites
- **Python 3.10+** (`python3 --version`)
- **Node.js 18+ & npm** (`node -v`, `npm -v`)
- **No external database, API keys, or HuggingFace login required.** SQLite auto-initializes locally, and the 1,500-row dataset is bundled in `backend/data/online_lecture_feedback.csv`.

### Option A: One-Command Launcher (macOS / Linux)
```bash
git clone https://github.com/Bhagi209-dotcom/EventPulseAiDEMOProject
cd EventPulseAI
chmod +x run_all.sh
./run_all.sh
```
**What `run_all.sh` does automatically:**
1. Detects an active `$VIRTUAL_ENV` or creates `backend/.venv` automatically.
2. Installs `backend/requirements.txt` (`fastapi`, `uvicorn`, `sqlalchemy`, `catboost`, `shap`, `vaderSentiment`, `scikit-learn`, `pandas`, `numpy`).
3. Installs `frontend/node_modules` if missing.
4. Starts the FastAPI backend on `http://localhost:8000` and the Vite React frontend on `http://localhost:5173`.

Open **`http://localhost:5173`** in your browser.

---

### Option B: Manual Setup (Windows / macOS / Linux)

**Terminal 1 — Backend (FastAPI + ML Pipeline):**
```bash
cd backend
python3 -m venv .venv
# macOS/Linux:
source .venv/bin/activate
# Windows (PowerShell):
# .venv\Scripts\Activate.ps1

pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

**Terminal 2 — Frontend (React 18 + Vite + Tailwind CSS):**
```bash
cd frontend
npm install
npm run dev
```

Open **`http://localhost:5173`** in your browser.

---

### Option C: Running Without Internet & Using Mobile QR
- **Zero Internet Required:** Once dependencies are installed, the entire app—including VADER NLP, CatBoost + SHAP inference, SQLite persistence, and QR code generation (`qrcode.react` SVG)—runs **100% offline**.
- **Connecting a Phone via QR Code:**
  1. Click **Mobile QR** in the Presenter HUD header.
  2. Scan the QR code from a phone connected to the **same local Wi-Fi network** (even an offline router) or USB network link. It opens `http://<YOUR_LAN_IP>:5173/?view=attendee&session=DEMO-101` directly in the Attendee Mobile view.
  3. **No Wi-Fi / Single-Laptop Demo:** Click **Copy Link** in the QR modal and open it in a second browser window side-by-side with the Presenter HUD.

---

### Running Automated Tests
```bash
# From the EventPulseAI root directory:
python3 -m pytest backend/tests/test_eventpulse.py -v
```
Tests verify DPDP PII sanitization & Q&A NLP classification, dataset pipeline generation, CatBoost Platt calibration + SHAP attribution, REST endpoints + simulator, and the 1-vote-per-attendee poll lock.

---

## 2. What Each Page & Feature Does

### A. Presenter Telemetry HUD (Default Tab)
The speaker's real-time command center connected via `WS /ws/session/{code}`:
- **4 Live KPI Cards:** `Reactions/min` (interaction velocity), `Avg Dwell` (foreground attention in seconds), `Sentiment Score` (average VADER polarity), and `Poll Participation Rate`.
- **4-Tier Disengagement Risk Card + Pacing Tip:** Displays the Platt-calibrated disengagement probability (`0–100%`) classified into:
  - **Optimal (`0–25%`)**: Audience is engaged; keep current pace.
  - **Mild Drift (`26–50%`)**: Early hesitation; consider a quick check-in poll.
  - **Moderate Slump (`51–75%`)**: Comprehension drop detected; slow down and recap the last concept.
  - **Severe Disengagement (`76–100%`)**: High drop-off risk; pause for live Q&A or an interactive example.
- **Explainable SHAP Attribution Panel:** Shows *why* the risk score moved (top positive/negative feature drivers computed in `<30ms` by `shap.TreeExplainer`, e.g., `poll_response_latency`, `sentiment_drift_slope`, `confusion_ratio`, `active_dwell_ratio`).
- **Live Sentiment & Risk Timeline:** Real-time SVG sparkline tracking audience pulse over updates.
- **Simulate Audience Toolbar:** One-click virtual audience buttons (`Normal Flow`, `Confusion Spike`, `Drop-off Drift`) to demonstrate real-time WebSocket updates, risk tier transitions, and SHAP explanations on a single laptop.
- **Dynamic Live Poll Creator:** Create polls with `2` to `6` custom options (`+ Add Option` / remove `×`). Votes update live on both Presenter and Attendee screens.
- **Anonymous Q&A Feed (DPDP Sanitized + NLP Classified):** Every question is scrubbed of HTML/URLs/emails/phones (`[REDACTED]`), scored with VADER, and tagged with both its **Sentiment** (`Positive` / `Neutral` / `Negative`) and **Intent Type** (`Question & Clarification`, `Improvement Suggestion`, `Technical Feedback`, `Support Request`, `Positive Praise`, `General Feedback`).

### B. Attendee Mobile View (`?view=attendee`)
Zero-login, mobile-first interface for participants:
- **1-Tap Audience Pulse:** Instant `Positive`, `Neutral`, `Confused`, and `Disengaged` buttons.
- **Live Poll Voting (1-Vote Lock):** Each attendee browser receives an anonymous `voter_token` in `localStorage`. Duplicate votes on the same poll are blocked by both the backend (`409 Conflict`) and the UI (`Voted` state).
- **Ask Anonymously:** Submits feedback/questions through DPDP sanitization and immediately shows the attendee how the NLP classifier tagged their submission.

### C. Model Benchmarks Tab
Displays the live evaluation table trained on the bundled dataset, comparing:
- **Logistic Regression** (linear baseline)
- **Decision Tree (`max_depth=5`)** (white-box baseline)
- **CatBoost (Uncalibrated)** (`iterations=100, depth=6`)
- **Calibrated CatBoost (Production)** (`CalibratedClassifierCV` with `method="sigmoid"`, `cv=5`)

Metrics reported: **Accuracy, Precision, Recall, F1-Score, ROC-AUC, Brier Calibration Loss**, and the **Confusion Matrix** (`TN, FP, FN, TP`).

---

## 3. Data Science & ML Pipeline Architecture

### Dataset Provenance & Preprocessing
- **Online Source:** [`chillies/course-review-multilabel-sentiment-analysis`](https://huggingface.co/datasets/chillies/course-review-multilabel-sentiment-analysis) (HuggingFace public dataset of real student/course reviews with multi-label tags: `Questions and Answers`, `Support Request`, `Improvement Suggestions`, `Technical Feedback`, `Experience Sharing`, etc.).
- **Bundled Raw Snapshot:** `backend/data/online_lecture_feedback.csv` (`1,500` rows). You can re-fetch fresh rows anytime via:
  ```bash
  python3 backend/scripts/fetch_online_dataset.py
  ```
- **Feature Engineering (`backend/app/services/dataset.py`):** Scores review text with VADER (`compound`, `pos`, `neg`, `neu`), combines with real feedback tags and 3-minute sliding-window behavioral telemetry (`interaction_velocity`, `active_dwell_ratio`, `poll_response_latency`, `sentiment_drift_slope`, rolling volatility), and outputs `backend/data/cleaned_cohort_telemetry.csv` (`24` model-ready features).

### Why Platt Sigmoid Calibration + SHAP?
1. **Probability Calibration:** Raw gradient-boosted tree scores are often over- or under-confident near `0` and `1`. **Platt Sigmoid Calibration** (`CalibratedClassifierCV(..., method="sigmoid", cv=5)`) maps raw margins to calibrated probabilities—lowering **Brier Calibration Loss** so an `80%` disengagement alert genuinely corresponds to ~8 out of 10 at-risk intervals.
2. **Local Clinical/Instructional Explainability:** `shap.TreeExplainer` computes exact Shapley feature contributions in `<30ms` per live update so speakers know *which* behavioral or sentiment driver triggered an alert rather than staring at a black-box number.

### DPDP Act 2023 Privacy Compliance
- Zero user accounts, zero tracking cookies, and zero PII storage.
- `backend/app/services/sanitizer.py` strips HTML tags and URLs and masks email addresses and phone numbers as `[REDACTED]` before VADER scoring or SQLite persistence.

---

## 4. Repository Structure
```text
EventPulseAI/
├── run_all.sh                        # One-command launcher (auto-creates venv & starts backend + frontend)
├── README.md                         # Project documentation & evaluator reference guide
├── backend/
│   ├── requirements.txt              # Python dependencies
│   ├── scripts/
│   │   └── fetch_online_dataset.py   # Re-fetches 1,500 rows from HuggingFace API
│   ├── data/
│   │   ├── online_lecture_feedback.csv
│   │   └── cleaned_cohort_telemetry.csv
│   ├── app/
│   │   ├── main.py                   # FastAPI entry point, CORS & startup DB/ML init
│   │   ├── api/routes.py             # REST + WebSocket (/ws/session/{code}) + /network/info
│   │   ├── db/                       # SQLite + SQLAlchemy ORM models & migrations
│   │   ├── services/
│   │   │   ├── sanitizer.py          # DPDP PII masking + VADER/Intent Q&A classifier
│   │   │   ├── dataset.py            # 24-feature sliding-window dataset pipeline
│   │   │   └── ml_engine.py          # CatBoost + Platt calibration + SHAP TreeExplainer
│   │   └── ws/manager.py             # Room-scoped WebSocket broadcast manager
│   └── tests/
│       └── test_eventpulse.py        # Pytest suite (5 tests)
└── frontend/
    ├── package.json
    ├── vite.config.js                # LAN host:true + /api & /ws proxy to :8000
    └── src/App.jsx                   # Presenter HUD, Attendee Mobile, QR Modal, Benchmarks
```
