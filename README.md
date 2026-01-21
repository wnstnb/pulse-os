# Pulse OS (X Agent OS)

Pulse OS is a two-part system that shares a single SQLite database:

- `agent-service/` — Python pipeline for research, content generation, and daily briefs
- `x-dashboard/` — Next.js UI for today’s brief, posts, conversations, and skills

## Requirements

- Python 3.10+
- Node.js 18+

## Shared SQLite

Default DB location: `data/x_agent_os.db` (created automatically)  
Override: set `X_AGENT_OS_DB_PATH`

## Environment Variables

Create a `.env` file in `agent-service/` (do not commit):

```
PERPLEXITY_API_KEY=...
GOOGLE_API_KEY=...
RAPIDAPI_API_KEY=...
TYPEFULLY_API_KEY_TUON=...
```

Optional (override DB path):

```
X_AGENT_OS_DB_PATH=/absolute/path/to/x_agent_os.db
```

## Agent Service (Python)

Install dependencies:

```
cd agent-service
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run daily pipeline + brief:

```
python run.py daily
```

Run metrics update (stubbed for now):

```
python run.py metrics
```

## Dashboard (Next.js)

Install and start:

```
cd x-dashboard
npm install
npm run dev
```

Then open:

```
http://localhost:3000
```

## First Run Checklist

1. Add API keys to `agent-service/.env`.
2. Run `python run.py daily` to generate initial data.
3. Start the dashboard and visit `/today` and `/skills`.
4. Edit skill configs in `/skills/[slug]` as needed.

## Repo Structure

```
agent-service/
  src/x_agent_os/
  skills_seed.json
  requirements.txt
x-dashboard/
docs/
data/ (local SQLite)
```