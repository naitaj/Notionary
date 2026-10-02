# Notionary — Project Intelligence & Reasoning Workspace

> *"Your project remembers what happened. Notionary remembers why."*

Notionary is a reasoning and memory layer built on top of Notion for research teams, hackathon teams, and capstone projects. It ingests messy project artifacts (meeting notes, research papers, experiment logs, datasets, discussions), extracts structured knowledge (claims, observations, experiments, results, decisions, tasks, owners), writes it into bidirectional, relation-linked Notion databases, and builds an evidence graph.

---

## 🚀 Key Features

- **Decision Lineage ("Why?")**: Trace decisions directly to the experiments, claims, and discussions that justified them.
- **Decision Time Machine**: Inspect how project beliefs and dependencies evolved over time.
- **Contradiction Radar**: Automatically scan claims and experiment results for conflicting findings.
- **Change-Impact Analysis**: Simulate or analyze what tasks, deliverables, and documents break when a decision is altered.
- **Bi-directional Notion Sync**: Real-time integration with Notion databases and pages.
- **Review Inbox**: Human-in-the-loop validation of AI-extracted entities and proposals.
- **Cited Q&A & Assistant**: Answers grounded in project sources with exact excerpt citations.

---

## 🛠️ Architecture

- **Frontend**: Next.js 14+ / React, Tailwind CSS, Lucide icons, React Flow / Cytoscape
- **Backend API**: FastAPI (Python 3.11+ / 3.14), Pydantic v2
- **Data & Graph**: PostgreSQL / SQLite (local dev), pgvector / semantic embeddings, recursive graph engine
- **Integration**: Notion API (REST / SDK)

---

## 💻 Local Development Setup

### Prerequisites
- Node.js (v18+) & npm
- Python (v3.10+) or `uv` / `py`

### Backend Setup
```bash
cd backend
# Create virtual environment using uv or python
uv venv
# or: py -m venv .venv

# Activate virtual environment
# Windows PowerShell:
.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Run backend server
uvicorn app.main:app --reload --port 8000
```

### Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

Frontend runs on [http://localhost:3000](http://localhost:3000) and Backend runs on [http://localhost:8000](http://localhost:8000).
