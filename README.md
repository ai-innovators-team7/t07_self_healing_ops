# AI Innovators Expedition — London 2026 Hackathon Kit

> **Disclaimer:** *This is not an officially supported Google product. All datasets, companies, personas, scenarios, and mock action APIs in this repository are 100% synthetic and fictional.*

Welcome to the official participant repository for the **AI Innovators Expedition** hands-on hackathon at **Google London (29–30 October 2026)**!

Over **2 days**, around **50 technical Participants** (founders, CTOs, VPs of Engineering, and tech leads from Digital Native startups and scaleups) work across **10 pre-assigned Tables of 5** (5 different companies per Table, paired into **5 industry Tribes** of 2 Tables each) to build, evaluate, and deploy production-grade AI agents on Google Cloud—culminating in a live **5:00 Pitch** at the end of Day 2. *(Final agenda slot timings and showcase logistics will be shared by the organisers.)* The challenge cards, sample data and Starter are here to help - use them as much or as little as you like.

### Quick Links
- **[Pre-Work Checklist (`docs/PREWORK.md`)](docs/PREWORK.md)** — Mandatory laptop setup & Google Cloud path preparation before arriving in London.
- **[Challenge Cards (`challenges/README.md`)](challenges/README.md)** — Browse all 10 Table Challenge Cards (`T01`–`T10`), Sister Tables, and Security & Guardrails test vectors.
- **[Seed Packs Catalog (`seed_packs/README.md`)](seed_packs/README.md)** — Deep-dive into the 10 synthetic BigQuery datasets, read tools, and FastMCP Mock Action APIs.
- **[Starter Technical Reference (`docs/STARTER.md`)](docs/STARTER.md)** — Full ADK Starter architecture, plugin contract, and deployment workflow.
- **[Coding Agent Instructions (`AGENTS.md`)](AGENTS.md)** — Rules and conventions read automatically by **Google Antigravity**.

---

## 1. Hackathon Rules, Scoring & Awards

### Scoring
- **Score = Core (max 14) + Bonuses (no maximum).**
- **Core:** Agent & creativity 0–6 · Evaluation quality 0–4 · Pitch & timing 0–4 (timing deductions come out of Pitch & timing).
- **Bonuses:** 1 whole point per capability that works live in your demo and adds real value to your agent (shown, not just mentioned). Suggested menu: governance, security & guardrails, CI/CD pipeline, Agentic SDLC practices, Gemini Enterprise App, MCP App, Gemma, Tribe A2A (connect with your sister Table's agent), BigQuery, Cloud Run, Knowledge Graph, model routing, multimodality (voice, image), memory — or any other capability that clearly adds value. Each distinct capability counts once; the jury decides what counts.
- **Must-Haves (ADK, Agent Runtime, Antigravity, a Gemini model, an evaluation pipeline):** your bonus points only count once all 5 are shown working; otherwise you keep your core score (max 14).
- **Jury score:** average of the jurors' totals (ties broken by **Agent & creativity**).
- **Quality beats quantity:** we reward things that work well, not boxes ticked.

### The 5 Must-Haves

| # | Must-Have | What Your Table Must Demonstrate |
| :--- | :--- | :--- |
| **1** | **ADK (Agent Development Kit)** | Your agent is built and orchestrated using Google's open-source **ADK** (`google-adk`). |
| **2** | **Agent Runtime** | Your agent is deployed to and running live on Vertex AI **Agent Runtime** (`reasoningEngines`) in your Table's **Scored Deployment** project (`make deploy` + `make test-remote`, not running only on `localhost`). |
| **3** | **Google Antigravity** | Your Table builds its solution using **Google Antigravity** (every participant has a pre-configured `@gcplab.me` sandbox account with Agent Platform Pay-As-You-Go, or uses their company account). |
| **4** | **A Gemini Model (`gemini-3.8-flash`)** | Your agent is powered by a Google **Gemini** model (**Gemini 3.8 Flash**, `gemini-3.8-flash` on `GOOGLE_CLOUD_LOCATION=global`), with the model ID and location read from environment variables (`GEMINI_MODEL`, `GOOGLE_CLOUD_LOCATION`) and never hardcoded. **Anthropic Claude is not allowed.** |
| **5** | **An Evaluation Pipeline** | Your Table runs an automated evaluation pipeline (`make eval`, expanding on the Starter harness and `.test.json` golden cases) measuring tool trajectories and response quality. |

### Team Git Workflow
- Every Participant has their own pre-configured Google Cloud sandbox account (`@gcplab.me` with Agent Platform Pay-As-You-Go) or company Google Cloud account, so all 5 Table members can run **Antigravity 2.0** in parallel.
- Each Table appoints a **Repo Captain** to create **one shared private GitHub repository** from this Starter and invite the other 4 Table members so everyone can collaborate on architecture, tools, evaluation cases, security guardrails, and the Pitch.
- **Unlock up to +2 Bonus Points for Engineering Rigor:**
  - **CI/CD Pipeline (`+1 pt`):** Automate quality gates (`make test` + `make eval-validate`/`make eval`) and deployment to Agent Runtime (`make deploy`) via **GitHub Actions** and/or **Google Cloud Build**, verified by showing a green pipeline run to a Mentor or live during your Pitch.
  - **Agentic SDLC Practices (`+1 pt`):** Demonstrate at least **2 of the 3 Agentic SDLC pillars** in your repo and workflow: **(1)** Custom Antigravity rules/skills/subagents or a domain-tailored `AGENTS.md`, **(2)** Spec/Eval-first development (Plan-Act-Verify / TDD by adding `.test.json` golden cases or `pytest` tests before implementing tools), and **(3)** Parallel Git workflow (feature branches, `git worktree` isolation, and Pull Requests). See [`docs/STARTER.md`](docs/STARTER.md) for copy-paste recipes.

### Pitch Format (5:00 Hard Stop + 0:30 Changeover)
- **5:00 Pitch (Hard Stop):**
  - **Maximum 2 slides:** **Slide 1 (Presentation)** covering the user persona, problem, and value proposition; **Slide 2 (Architecture & Evaluation)** covering your ADK topology, Agent Runtime deployment, MCP / Google Cloud stack, Bonuses, and evaluation pipeline results.
  - **Live Demo:** Demonstrate your live agent running on your Table's **Scored Deployment**.
- **0:30 Changeover:** Quick transition to the next Table on stage.
- *(Final showcase schedule and logistics will be shared by the organisers.)*

### Awards & People's Choice Voting
There are **two official hackathon awards**:
1. **Jury Award** — Won by the Table with the highest jury **Score** (mean of jurors' totals; ties broken by **Agent & creativity**).
2. **People's Choice Award** — Voted live by all Participants: **each Participant gives 3 votes to 3 different Tables, never their own** (voting opens at the first Pitch, remains editable until 3 minutes after the last Pitch, and stays hidden until the reveal).

---

## 2. Get Started in 15 Minutes

> Completing setup before the event? Follow the full **[Pre-Work Checklist (`docs/PREWORK.md`)](docs/PREWORK.md)**.

### Step 1 — Prerequisites
- **Google Antigravity 2.0 App** — Install the **Antigravity 2.0 app** (https://antigravity.google/download) - not the Antigravity IDE (the IDE has no Agent Platform plan). Don't sign in with your personal Gmail. On Day 1 you'll sign in with the sandbox Business account we give you (or your company's Google Cloud account): choose **'Use business account'** (not 'Continue with Google'), pick your project and keep **'Use Agent Platform instead'**. Step-by-step guide: https://medium.com/google-cloud/unlock-antigravity-2-0-logins-plans-cost-and-quota-9165725685be
- **Python 3.12** (required for `cloudpickle` parity with Vertex AI Agent Runtime containers)
- **[`uv`](https://docs.astral.sh/uv/)** (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- **[Google Cloud SDK (`gcloud`)](https://cloud.google.com/sdk/docs/install)** authenticated against your Table's **Scored Deployment** project (either a **Google-provided Sandbox Project** or your own company's Google Cloud project):
  ```bash
  gcloud auth login
  gcloud auth application-default login
  gcloud config set project YOUR_GCP_PROJECT_ID
  gcloud auth application-default set-quota-project YOUR_GCP_PROJECT_ID
  ```
- Enable the required APIs in your project (once per project):
  ```bash
  gcloud services enable aiplatform.googleapis.com bigquery.googleapis.com \
    storage.googleapis.com cloudresourcemanager.googleapis.com --project=YOUR_GCP_PROJECT_ID
  ```
- **macOS or Linux** with GNU Make and bash (**Windows:** run inside WSL2 Ubuntu).

### Step 2 — Clone & Create the Python 3.12 Environment (`uv`)
```bash
git clone https://github.com/papelamineG/ai-innovators-london-hackathon.git
cd ai-innovators-london-hackathon
make setup
```

### Step 3 — Configure `.env` & Staging Bucket
```bash
cp .env.example .env
```
Edit `.env` (plain `KEY=value` lines, no quotes, no spaces around `=`):
```dotenv
GOOGLE_CLOUD_PROJECT=your-gcp-project-id
GOOGLE_GENAI_USE_VERTEXAI=1
GOOGLE_CLOUD_LOCATION=global
GEMINI_MODEL=gemini-3.8-flash
AGENT_RUNTIME_LOCATION=europe-west1
STAGING_BUCKET=
SEED_PACK=t08
BQ_LOCATION=EU
```
When `STAGING_BUCKET` is left empty, the Starter defaults to `gs://<GOOGLE_CLOUD_PROJECT>-hackathon-staging`. Create your staging bucket once:
```bash
gcloud storage buckets create gs://$(grep '^GOOGLE_CLOUD_PROJECT=' .env | cut -d= -f2)-hackathon-staging \
  --location=europe-west1
```

### Step 4 — Seed Your Table's Synthetic Data (`make seed PACK=tNN`)
Load your Table's bundled synthetic CSV files (`seed_packs/tNN_<slug>/data/*.csv`) into BigQuery (`seed_tNN`) in your `GOOGLE_CLOUD_PROJECT`:
```bash
make seed PACK=t08
```
*(Or test with the reference roastery pack via `make seed PACK=t00_example`.)*

> **Optional Cloud Storage Mirror (`gs://ai-innovators-london-2026-data`):**
> All CSV datasets are already bundled inside this repository under `seed_packs/tNN_<slug>/data/*.csv`, so `make seed PACK=tNN` works out of the box without any external download. As an optional mirror—available once the organisers open public access—the seed CSVs and a full zip archive of this kit are also staged in `gs://ai-innovators-london-2026-data`:
> - Seed CSV pattern: `https://storage.googleapis.com/ai-innovators-london-2026-data/seed/tNN/<table_name>.csv` (e.g. `https://storage.googleapis.com/ai-innovators-london-2026-data/seed/t08/disrupted_itineraries.csv`)
> - Kit archive: `https://storage.googleapis.com/ai-innovators-london-2026-data/kit/ai-innovators-london-hackathon.zip`

### Step 5 — Run Offline Tests & Launch the Local ADK Web UI
```bash
make test
make dev
```
Open **`http://127.0.0.1:8000`** in your browser, select `app` from the top-left agent dropdown, and inspect tool calls and traces.

### Step 6 — Run the Evaluation Pipeline (`make eval`)
```bash
make eval
```
Validates your pack's `.test.json` golden cases against the ADK `EvalSet` schema, runs each turn against your agent, scores tool trajectories (`tool_trajectory_avg_score`) and response grounding (`response_match_score`), and prints `EVAL_SUMMARY: x/y cases passed`. *(Use `make eval-validate` for offline schema validation without calling Gemini.)*

### Step 7 — Deploy to Agent Runtime, Test Remotely & Clean Up
```bash
make deploy
make test-remote
make delete
```
- `make deploy` packages `app/` and `seed_packs/` on Python 3.12, deploys (or updates in-place) your agent on **Vertex AI Agent Runtime** (`europe-west1`), and writes `.deployed_agent.json`.
- `make test-remote` creates a live session on your remote `ReasoningEngine` and streams a verification prompt (`make test-remote PROMPT="..."`).
- `make delete` deletes the deployed `ReasoningEngine` recorded in `.deployed_agent.json` (or `make delete RESOURCE=projects/.../reasoningEngines/<id>`).

---

## 3. Find Your Challenge (Tables T01–T10)

Every Table has a **Challenge Card** in [`challenges/`](challenges/README.md) (also inside `seed_packs/tNN_<slug>/CHALLENGE_CARD.md`) with its persona, dataset schema, read tools, FastMCP Mock Action APIs, Sister Table for the **Tribe A2A Bonus**, and **Security & Guardrails Test Vector (Optional +1 Bonus)**:

| Table | Tribe | Collaborative Challenge Title | Sister Table (A2A) | Challenge Card | Seed Pack |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **T01** | Creative AI & AdTech | **Autonomous Creative Campaign Orchestrator** | **T02** (`t02_dynamic_storefronts`) | [`challenges/T01-campaign_orchestrator.md`](challenges/T01-campaign_orchestrator.md) | [`seed_packs/t01_campaign_orchestrator`](seed_packs/t01_campaign_orchestrator/) |
| **T02** | Creative AI & AdTech | **Visual Content Creator & Dynamic Storefronts** | **T01** (`t01_campaign_orchestrator`) | [`challenges/T02-dynamic_storefronts.md`](challenges/T02-dynamic_storefronts.md) | [`seed_packs/t02_dynamic_storefronts`](seed_packs/t02_dynamic_storefronts/) |
| **T03** | Content Intelligence | **Conversational Catalog Discovery Assistant** | **T04** (`t04_b2b_sourcing`) | [`challenges/T03-catalog_discovery.md`](challenges/T03-catalog_discovery.md) | [`seed_packs/t03_catalog_discovery`](seed_packs/t03_catalog_discovery/) |
| **T04** | Content Intelligence | **Dynamic B2B Integration & Sourcing Agent** | **T03** (`t03_catalog_discovery`) | [`challenges/T04-b2b_sourcing.md`](challenges/T04-b2b_sourcing.md) | [`seed_packs/t04_b2b_sourcing`](seed_packs/t04_b2b_sourcing/) |
| **T05** | FinTech & Analytics | **Autonomous B2B Financial Auditor & Reconciler** | **T06** (`t06_climate_risk`) | [`challenges/T05-financial_auditor.md`](challenges/T05-financial_auditor.md) | [`seed_packs/t05_financial_auditor`](seed_packs/t05_financial_auditor/) |
| **T06** | FinTech & Analytics | **Dynamic Climate & Regulatory Risk Assessor** | **T05** (`t05_financial_auditor`) | [`challenges/T06-climate_risk.md`](challenges/T06-climate_risk.md) | [`seed_packs/t06_climate_risk`](seed_packs/t06_climate_risk/) |
| **T07** | Cross-functional Ops & CX | **Self-Healing Infrastructure & Security Copilot** | **T08** (`t08_travel_concierge`) | [`challenges/T07-self_healing_ops.md`](challenges/T07-self_healing_ops.md) | [`seed_packs/t07_self_healing_ops`](seed_packs/t07_self_healing_ops/) |
| **T08** | Cross-functional Ops & CX | **Hyper-Personalized Travel Concierge & Incident Management Agent** | **T07** (`t07_self_healing_ops`) | [`challenges/T08-travel_concierge.md`](challenges/T08-travel_concierge.md) | [`seed_packs/t08_travel_concierge`](seed_packs/t08_travel_concierge/) |
| **T09** | Smart Mobility & UX | **Smart Mobility & Energy Optimizer Agent** | **T10** (`t10_retention_matcher`) | [`challenges/T09-mobility_energy.md`](challenges/T09-mobility_energy.md) | [`seed_packs/t09_mobility_energy`](seed_packs/t09_mobility_energy/) |
| **T10** | Smart Mobility & UX | **Predictive Retention & Resource Matcher** | **T09** (`t09_mobility_energy`) | [`challenges/T10-retention_matcher.md`](challenges/T10-retention_matcher.md) | [`seed_packs/t10_retention_matcher`](seed_packs/t10_retention_matcher/) |

---

## 4. Repository Layout

```text
ai-innovators-london-hackathon/
├── app/
│   ├── agent.py                  # Root ADK LlmAgent (reads GEMINI_MODEL & GOOGLE_CLOUD_LOCATION from env)
│   ├── loader.py                 # Seed Pack plugin loader (YAML + BigQuery TOOLS + MCP stdio/fallback)
│   └── preflight.py              # Actionable "do this next" hints for common Google Cloud errors
├── challenges/
│   ├── README.md                 # Index of all 10 Table Challenge Cards
│   └── T01 .. T10-*.md           # Per-Table Challenge Cards (same content as seed_packs/tNN_*/CHALLENGE_CARD.md)
├── deploy/
│   ├── deploy.py                 # One-command deploy/update to Vertex AI Agent Runtime (Python 3.12)
│   ├── test_remote.py            # Live session + stream_query verification against Agent Runtime
│   └── delete.py                 # Clean up deployed ReasoningEngine resource
├── docs/
│   ├── PREWORK.md                # Participant Pre-Work checklist (Path 1 Sandbox & Path 2 Own-Org)
│   └── STARTER.md                # Detailed Starter quickstart & plugin contract reference
├── eval/
│   ├── run_eval.py               # Golden evaluation runner & ADK EvalSet validator
│   ├── test_config.json          # Default tool trajectory & response match thresholds
│   └── hello_fallback.test.json  # Baseline evalset when SEED_PACK is unset
├── seed_packs/
│   ├── README.md                 # Full Seed Pack catalog & tool index
│   ├── check_packs.py            # Structural & cross-reference validator for all 10 Seed Packs
│   ├── t00_example/              # Reference pack (London Specialty Roastery)
│   └── t01 .. t10/               # Per-Table Seed Packs (pack.yaml, data/*.csv, tools.py, mcp_server.py, load.py, eval/, CHALLENGE_CARD.md)
├── tests/
│   └── test_starter.py           # Offline pytest suite
├── .env.example                  # Environment variable template (GOOGLE_CLOUD_PROJECT, GEMINI_MODEL, SEED_PACK)
├── AGENTS.md                     # Rules & coding conventions for Google Antigravity
├── LICENSE                       # Apache License 2.0
├── Makefile                      # One-command workflow targets
├── pyproject.toml                # Pinned Python 3.12 dependencies
└── README.md                     # This participant guide
```

---

## 5. Troubleshooting

| Symptom | Cause | Fix |
| :--- | :--- | :--- |
| `DefaultCredentialsError` or `403 PERMISSION_DENIED` | ADC credentials missing or quota project unset | Run `gcloud auth application-default login` and `gcloud auth application-default set-quota-project $GOOGLE_CLOUD_PROJECT`. |
| `SERVICE_DISABLED` / `API ... has not been used in project` | Required API not enabled | Run the `gcloud services enable ...` command from Step 1, wait ~1 minute, and retry. |
| `Staging bucket gs://... does not exist` | Staging bucket not created yet | Run `gcloud storage buckets create gs://${GOOGLE_CLOUD_PROJECT}-hackathon-staging --location=europe-west1`. |
| `Not found: Dataset ...` in a tool result | Seed data not loaded into BigQuery | Run `make seed PACK=<your pack>`. |
| `.venv/bin/python not found` | Virtualenv setup skipped | Run `make setup`. |
| `404 Not Found` calling `gemini-3.8-flash` | Regional endpoint used instead of `global` | Keep `GOOGLE_CLOUD_LOCATION=global` in `.env` (`AGENT_RUNTIME_LOCATION=europe-west1` is used separately for Agent Runtime). |
| Blank reply or `KeyError` on turn 1 | Unescaped `{variable}` in `instruction` | ADK treats `{foo}` in `instruction` as a session-state placeholder. Replace `{foo}` with `[foo]`. |
| Tool spinner hangs or stream dies mid-turn | Tool raised an unhandled Python exception | ADK tools must never raise; catch exceptions and return `json.dumps({"status": "ERROR", "error": str(exc)})`. |
| Deserialization error in Agent Runtime | Deployed from Python 3.13 instead of 3.12 | Always deploy via `make deploy` (which enforces `.venv/bin/python` on Python 3.12). |

---

## 6. Official Documentation Links

- **Google Agent Development Kit (ADK):** [https://adk.dev](https://adk.dev)
  - [ADK Custom & Multi-Agent Orchestration](https://adk.dev/agents/custom-agents/)
  - [ADK Model Context Protocol (MCP) Tools](https://adk.dev/tools-custom/mcp-tools/)
  - [ADK Safety & Callbacks](https://adk.dev/callbacks/)
  - [ADK CLI & A2A Deployment Reference](https://adk.dev/api-reference/cli/)
- **Google Antigravity:** [https://antigravity.google](https://antigravity.google) ([Download](https://antigravity.google/download) · [Getting Started Docs](https://antigravity.google/docs/getting-started) · [Antigravity 2.0 Login & Quota Guide](https://medium.com/google-cloud/unlock-antigravity-2-0-logins-plans-cost-and-quota-9165725685be))
- **Google Cloud & Vertex AI:** [https://cloud.google.com](https://cloud.google.com)
  - [Vertex AI Agent Engine (Agent Runtime) Documentation](https://cloud.google.com/vertex-ai/generative-ai/docs/agent-engine/overview)
  - [Register and Manage an ADK Agent in Gemini Enterprise](https://cloud.google.com/gemini/enterprise/docs/register-and-manage-an-adk-agent)
  - [Model Armor Overview](https://cloud.google.com/security-command-center/docs/model-armor-overview)
  - [BigQuery Python Client Reference](https://cloud.google.com/python/docs/reference/bigquery/latest)
  - [Google Cloud CLI (`gcloud`) Installation](https://cloud.google.com/sdk/docs/install)
- **Gemma Open Models:** [https://ai.google.dev/gemma/docs](https://ai.google.dev/gemma/docs)
