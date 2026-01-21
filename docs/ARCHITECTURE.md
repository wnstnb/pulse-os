# X Agent OS Architecture

## Overview
Pulse OS hosts a shared SQLite database and two runtimes:

- `agent-service/`: Python pipeline for research, content generation, and daily briefs.
- `x-dashboard/`: Next.js + shadcn UI that reads/writes the same SQLite file.

## Data flow
1. `x_agent_os.orchestrator.run_daily_pipeline` runs skills through Perplexity/X/Gemini.
2. Results are stored in legacy tables (`sessions`, `search_results`, `twitter_results`, etc.).
3. New entities (`skills`, `posts`, `conversations`, `daily_briefs`, `metrics_snapshots`) are written for the dashboard.
4. The dashboard reads the shared DB and updates approvals or conversation statuses.

## Post + Reply Generation Diagram

```mermaid
flowchart TD
  A["Run daily pipeline (python run.py daily)"] --> B["Seed skills (skills_seed.json)"]
  B --> C["Active skills (skills table)"]
  C --> D["Build query (last 30 days)"]
  D --> E["Perplexity search agent"]
  D --> F["RapidAPI Twitter search agent"]

  E --> G["search_results table"]
  F --> H["twitter_results table"]
  H --> I["Filter tweets (last 30 days)"]

  I --> J["Reviewer agent distills topics"]
  G --> J

  K["Creator personas (active)"] --> L["Persona summaries + top posts"]
  M["Personal brand skill"] --> N["Brand manifesto + voice rules"]

  L --> J
  N --> J

  J --> O["reviewer_outputs table"]
  O --> P["Editor agent crafts posts"]
  L --> P
  N --> P

  P --> Q["posts table (draft_content)"]
  I --> R["conversations table (suggested_reply)"]
  Q --> S["Daily brief generator"]
  R --> S
  S --> T["daily_briefs table"]

  subgraph ReplyGeneration["On-demand reply generation (UI button)"]
    U["UI: Generate Reply button"] --> V["POST /api/conversations/{id}/generate"]
    V --> W["run_generate_reply.py"]
    W --> X["ReplyAgent (Gemini)"]
    X --> Y["Personal brand + recent posts + creator personas"]
    Y --> Z["Update conversations.suggested_reply"]
  end
```

## Shared SQLite
- Default path: `data/x_agent_os.db`
- Override with `X_AGENT_OS_DB_PATH`

## Future extensions
- Add a metrics provider in `x_agent_os/metrics.py`.
- Build `/sessions` and `/analytics` pages in `x-dashboard`.
