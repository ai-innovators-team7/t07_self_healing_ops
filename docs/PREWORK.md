# Pre-Work Checklist — AI Innovators Expedition London

Welcome to the hands-on hackathon of the **AI Innovators Expedition** at **Google London (29–30 October 2026)**! Please complete this **Pre-Work** checklist before travelling to London so that you and your **Table** can spend 100% of **Build Time** building, evaluating, and red-teaming your agent rather than installing tools or waiting on cloud permissions.

## 1. Why This Matters & What to Expect

- **Two-Day Hands-On Hackathon (29–30 Oct 2026, Google London, 6 Pancras Square):** Around 50 technical **Participants** (founders, CTOs, VPs of Engineering, and tech leads from Digital Native startups and scaleups) will build production-grade AI agents across hands-on **Build Time** (final agenda slot timings and showcase logistics will be shared by the organisers).
- **Pre-Assigned Tables & Tribes:** You are pre-assigned to a **Table** of 5 **Participants** from 5 different companies (no company is duplicated at a Table). There are **10 Tables** in total, paired into **5 Tribes** of 2 Tables sharing an industry focus (*Creative AI & AdTech*, *Content Intelligence*, *FinTech & Analytics*, *Cross-functional Ops & CX*, and *Smart Mobility & UX*).
- **Starter + Seed Pack from Minute One:** Every Table starts from a common **Starter** repository (an **ADK** agent skeleton, one-command deployment to Vertex AI **Agent Runtime**, and an evaluation harness) plus a Table-specific **Seed Pack** (synthetic data in BigQuery / Cloud Storage, 2–3 domain tools, and a **Mock Action API** exposed as an MCP server).
- **Pitch & Live VAR / Red Team Minute (End of Day 2):** Every Table delivers a **5:00 Pitch** (maximum 2 slides + live demo on your Table's **Scored Deployment**), immediately followed by a **0:30 VAR / Red Team Minute** where a Google mentor attempts a live prompt-injection attack against your agent (final showcase logistics will be shared by the organisers).
- **What to Bring:** Bring your **laptop** (with the Section 2 setup completed), your **laptop charger**, and a **UK power plug adapter (Type G)**.

## 2. Mandatory Local Setup for Everyone (Both Paths)

Every **Participant** must complete these 6 steps on their laptop before arriving—whether you plan to use a **Google-provided Sandbox Project** (Path 1) or your own company's Google Cloud organisation as an **Own-Org Participant** (Path 2).

### Step 2.1 — Install Google Antigravity & Sign In with a Personal Google Account

**Google Antigravity** is a **Must-Have** tool for the hackathon.

1. Download and install the standalone **Google Antigravity** app for your operating system from [https://antigravity.google/download](https://antigravity.google/download) (or [https://antigravity.google](https://antigravity.google)):
    - **macOS:** macOS 12 (Monterey) or later (Apple Silicon or Intel). Open `Antigravity.dmg` and drag **Antigravity** to `Applications`.
    - **Windows:** Windows 10 (64-bit) or Windows 11. Run the `.exe` installer.
    - **Linux:** Ubuntu 20+, Debian 10+, Fedora 36+, or RHEL 8+ (`glibc >= 2.28`, `glibcxx >= 3.4.25`). Extract `Antigravity.tar.gz` and launch `./Antigravity`.
    - *(Optional CLI)* You can also install the Antigravity CLI (`agy`) following the CLI instructions at [https://antigravity.google/docs/getting-started](https://antigravity.google/docs/getting-started).
2. Launch **Antigravity**, click **Sign in**, and complete the browser sign-in flow using a **personal Google account** (`@gmail.com`, 18+ age-verified).
3. **Important Note on Antigravity Access & Pilot Rotation:** During **Build Time**, Tables follow the **Pilot** rotation rule (one Pilot actively drives Antigravity at a time, swapping roughly every 35 minutes). Final account access details will be confirmed on the **Thursday 22 October** pre-event briefing call (call time and meeting link shared by the organisers). Installing Antigravity and verifying sign-in with your personal `@gmail.com` account now guarantees you are ready.

### Step 2.2 — Install the Google Cloud CLI (`gcloud`)

1. Download and install the **Google Cloud CLI (`gcloud`)** for your operating system (macOS, Windows, or Linux) from the official installation page: [https://cloud.google.com/sdk/docs/install](https://cloud.google.com/sdk/docs/install)
2. Restart your terminal and verify that `gcloud` is on your `PATH` by running `gcloud --version`.

### Step 2.3 — Install Python (3.12 Recommended) & `uv`

1. **Python Version:** The Agent Development Kit (**ADK**) requires **Python 3.10 or later**. We strongly recommend **Python 3.12** (`python3.12`) because the managed Vertex AI **Agent Runtime** container environment runs Python 3.12—using Python 3.12 locally prevents `cloudpickle` bytecode version-skew errors when deploying agents.
2. **Package Manager:** Install `uv` ([https://docs.astral.sh/uv/](https://docs.astral.sh/uv/)):
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```
3. **Clone the Starter & Pre-Cache Dependencies:** Clone this repository and run `make setup` (or run the commands below) so all Python 3.12 wheels are cached on your laptop before you join the event Wi-Fi:
   ```bash
   uv venv --python 3.12 .venv
   source .venv/bin/activate  # On Windows WSL2 / Linux / macOS
   uv pip install --python .venv/bin/python -r pyproject.toml
   ```

### Step 2.4 — Install Git & Verify Your GitHub Account

1. Install `git` ([https://git-scm.com/downloads](https://git-scm.com/downloads)).
2. Make sure you have an active **GitHub** account ([https://github.com](https://github.com)) and can clone and push to private repositories from your terminal (via SSH key or GitHub CLI / Personal Access Token).
3. Record your GitHub username—you will share it with your Table's **Repo Captain** on Day 1.

### Step 2.5 — Model Configuration Rule (Gemini 3.8 Flash via Environment Variables)

- Every Table's solution must use a Google **Gemini** model (**Gemini 3.8 Flash**, model ID `gemini-3.8-flash` on `location="global"`, is the default model for text, reasoning, and agent orchestration; **Gemma** open-weights models are optional for a Bonus; Anthropic Claude is not allowed).
- **Never hardcode model IDs or regions in Python code.** Always read the model ID and location from environment variables (for example `GEMINI_MODEL` and `GOOGLE_CLOUD_LOCATION`):
  ```python
  import os

  MODEL_ID = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")
  LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "global")
  ```

### Step 2.6 — Quick Local Self-Test (Everyone)

Activate your virtual environment and run this one-liner in your terminal. Confirm all four commands print valid version numbers without errors and the offline Starter test suite passes:

```bash
gcloud --version && .venv/bin/python --version && git --version && .venv/bin/adk --version && make test
```

## 3. Choose Your Google Cloud Path (Path 1 vs. Path 2)

At the hackathon, each **Table** will choose one environment where its **Scored Deployment** lives for the **Pitch**—either a **Google-provided Sandbox Project** (Path 1) or an **Own-Org Participant**'s corporate Google Cloud project (Path 2). Read the path that applies to you below.

### Path 1 — "I'll use a Google-provided Sandbox Project"

Choose **Path 1** if your company does not use Google Cloud yet, or if your corporate organisation has strict policies and you prefer a zero-setup sandbox.

- **Nothing to create before the event:** You do not need to create a Google Cloud project or provide a credit card.
- **Credentials handed out at check-in:** At registration on Day 1, you will receive temporary sandbox account credentials and a pre-billed **Google-provided Sandbox Project** (in team mode, all 5 **Participants** at your **Table** can share one **Sandbox Project** with Vertex AI, **Agent Runtime**, Cloud Run, Artifact Registry, Cloud Storage, and BigQuery ready to use).
- **Ephemeral lifecycle (3–4 days only):** Sandbox Projects live **only during the event** and are **permanently deleted afterwards**. Make sure all your code is pushed to your Table's GitHub repository before leaving on Day 2.
- **Service-account JSON keys are blocked:** Organization policies on the sandbox environment block creating or downloading service-account JSON key files (`iam.disableServiceAccountKeyCreation`). On Day 1, once you receive your sandbox credentials, you will authenticate your terminal and Python SDKs using Application Default Credentials (ADC):
  ```bash
  gcloud auth login
  gcloud auth application-default login
  gcloud config set project YOUR_SANDBOX_PROJECT_ID
  gcloud auth application-default set-quota-project YOUR_SANDBOX_PROJECT_ID
  ```

### Path 2 — "I'll use my company's Google Cloud" (Own-Org Participant)

Choose **Path 2** if you are an **Own-Org Participant** planning to build or host your Table's **Scored Deployment** inside your own company's Google Cloud organisation. **Complete all sub-steps below before travelling to London** so corporate IAM or Organization Policies do not slow your Table down.

#### 1. Create or Select a Dedicated Project with Active Billing

- Create a dedicated, non-production Google Cloud project (or select an existing sandbox project in your company org) at [https://console.cloud.google.com/projectcreate](https://console.cloud.google.com/projectcreate).
- Verify that an active **Cloud Billing account** is linked to the project.
- Note your alphanumeric **Project ID** (e.g. `my-startup-ai-hack`), not just the numeric project number.

#### 2. Authenticate `gcloud` and Application Default Credentials (ADC)

Run the following commands in your terminal and log in with your corporate Google Cloud account:

```bash
export PROJECT_ID="YOUR_PROJECT_ID"
gcloud auth login
gcloud auth application-default login
gcloud config set project "$PROJECT_ID"
gcloud auth application-default set-quota-project "$PROJECT_ID"
```

#### 3. Enable Required Google Cloud APIs

Enable the exact APIs required for Vertex AI, **Agent Runtime** deployment & container staging, Cloud Run (for MCP **Mock Action API** servers), Cloud Storage, BigQuery (**Seed Pack** data), and OpenTelemetry tracing:

```bash
gcloud services enable \
  aiplatform.googleapis.com \
  cloudresourcemanager.googleapis.com \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  storage.googleapis.com \
  bigquery.googleapis.com \
  telemetry.googleapis.com \
  cloudtrace.googleapis.com \
  logging.googleapis.com \
  --project="$PROJECT_ID"
```

*(Optional Bonus APIs: If your Table plans to explore the **Gemini Enterprise App** or **Agent Registry / Agent Gateway** bonuses, also enable `discoveryengine.googleapis.com`, `agentregistry.googleapis.com`, `networkservices.googleapis.com`, and `networksecurity.googleapis.com`.)*

#### 4. Provision the Vertex AI Service Agents & Verify Your User IAM Roles

First, trigger creation of the Google-managed Vertex AI and **Agent Runtime** service agents (`service-PROJECT_NUMBER@gcp-sa-aiplatform.iam.gserviceaccount.com` and `service-PROJECT_NUMBER@gcp-sa-aiplatform-re.iam.gserviceaccount.com`):

```bash
gcloud beta services identity create \
  --service=aiplatform.googleapis.com \
  --project="$PROJECT_ID"
```

Second, verify your own user account's IAM roles on `YOUR_PROJECT_ID`. Having **Project Owner** (`roles/owner`) or **Project Editor** (`roles/editor`) on a dedicated hackathon project is simplest; otherwise, ask your cloud administrator to grant your user principal these specific predefined roles (see [Vertex AI Agent Engine Setup docs](https://cloud.google.com/vertex-ai/generative-ai/docs/agent-engine/set-up)):

| **IAM Role ID** | **Role Name** | **Why It Is Needed** |
| --- | --- | --- |
| `roles/serviceusage.serviceUsageAdmin` | Service Usage Admin | Enable APIs (`serviceusage.services.enable`) and attribute quota (`serviceusage.services.use`). |
| `roles/aiplatform.user` | Vertex AI User | Deploy and query **Agent Runtime** (`reasoningEngines`) and invoke Gemini models. |
| `roles/storage.admin` | Storage Admin | Create and write to the Cloud Storage staging bucket required by **Agent Runtime** and load **Seed Pack** files. |
| `roles/bigquery.admin` | BigQuery Admin | Create datasets/tables and load synthetic **Seed Pack** data in BigQuery. |
| `roles/run.admin` | Cloud Run Admin | Deploy MCP **Mock Action API** servers or **A2A** services to Cloud Run. |
| `roles/iam.serviceAccountUser` | Service Account User | Attach the runtime service account when deploying to **Agent Runtime** or Cloud Run. |
| `roles/artifactregistry.writer` | Artifact Registry Writer | Push container images built during **Agent Runtime** or Cloud Run deployments. |
| `roles/cloudbuild.builds.editor` | Cloud Build Editor | Trigger Cloud Build container builds when staging agents or Cloud Run services. |

Also ensure the **Agent Runtime** default service agent (`service-PROJECT_NUMBER@gcp-sa-aiplatform-re.iam.gserviceaccount.com`) has `roles/artifactregistry.reader` if your organisation restricts default service agent grants.

#### 5. Check Organization Policies with Your Cloud Admin

Corporate Google Cloud organisations frequently enforce Organization Policies that can block hackathon deployments if not checked ahead of time. Ask your cloud admin to confirm the following on `YOUR_PROJECT_ID`:

- **VPC Service Controls (VPC-SC):** Confirm your laptop can call `aiplatform.googleapis.com`, `storage.googleapis.com`, `bigquery.googleapis.com`, and `telemetry.googleapis.com` without VPC-SC perimeter denials from outside your corporate VPN.
- **Resource Location Restrictions (`constraints/gcp.resourceLocations`):** Confirm that European regions (`europe-west1`, `europe-west2`, `europe-southwest1`) and/or `us-central1` and the `global` endpoint are allowed.
- **Service Account Key Creation (`constraints/iam.disableServiceAccountKeyCreation`):** Do **not** rely on JSON keys—our **Starter** uses `gcloud auth application-default login` (ADC), which works even when JSON keys are blocked.
- **Domain Restricted Sharing (`constraints/iam.allowedPolicyMemberDomains`) & Cloud Run Ingress (`constraints/run.allowedIngress`):** If you want your 4 Table teammates (from other companies) to access your project or call your Cloud Run / A2A endpoints directly, check whether external IAM principals or unauthenticated Cloud Run invocations are permitted—or plan to drive deployments from your laptop as an **Own-Org Participant**.

#### 6. Region Recommendation

- **Gemini Model Endpoint Location:** Use `GOOGLE_CLOUD_LOCATION="global"` for **Gemini 3.8 Flash** (`gemini-3.8-flash`).
- **Agent Runtime & Data Region:** The Starter defaults to `AGENT_RUNTIME_LOCATION="europe-west1"` and `BQ_LOCATION="EU"` (`europe-west2`, `europe-southwest1`, and `us-central1` are also supported for **Agent Runtime**). Create your Cloud Storage staging bucket (`gs://${PROJECT_ID}-hackathon-staging`) in the same region.

#### 7. Quick Gemini 3.8 Flash Access Check (Path 2 Verification)

Run this smoke test in your activated `.venv` to confirm your project, billing, ADC credentials, and **Gemini 3.8 Flash** access work end-to-end (note that the model ID is read from `GEMINI_MODEL`, never hardcoded):

```bash
export GOOGLE_GENAI_USE_VERTEXAI="True"
export GOOGLE_CLOUD_PROJECT="YOUR_PROJECT_ID"
export GOOGLE_CLOUD_LOCATION="global"
export GEMINI_MODEL="gemini-3.8-flash"
.venv/bin/python -c '
import os
from google import genai
client = genai.Client(
    vertexai=True,
    project=os.environ["GOOGLE_CLOUD_PROJECT"],
    location=os.environ["GOOGLE_CLOUD_LOCATION"],
)
response = client.models.generate_content(
    model=os.environ["GEMINI_MODEL"],
    contents="Reply with exactly: GEMINI_READY",
)
print("Success:", response.text.strip())
'
```

#### 8. Cost & Post-Event Cleanup Note

- **Keep it small:** Hackathon workloads (**Gemini 3.8 Flash** requests, compact synthetic **Seed Pack** tables in BigQuery, and one **Agent Runtime** deployment) cost only a few dollars over the two days. Avoid provisioning large GPU/TPU clusters unless specifically testing a small **Gemma** endpoint.
- **Clean up afterwards:** After Day 2 concludes, delete your **Agent Runtime** instance (`make delete`), any Cloud Run services, and your staging bucket (or delete the dedicated hackathon project) so no resources remain billed.

## 4. Prepare with Your Table & Tribe

1. **Read Your Table's Collaborative Challenge:** Browse [`challenges/README.md`](../challenges/README.md) (and the event deck shared by the organisers) to locate your assigned **Table** (1 to 10), your **Tribe** (pair of Tables sharing an industry theme), and your Table's **Challenge Card** with your persona, scenario, minimum playable scope, **Mock Action API** details, and the prompt-injection category you will face during the **VAR / Red Team Minute**.
2. **Appoint a "Repo Captain":** Because **Antigravity** does not support simultaneous multi-user editing on the same files, each Table must appoint one **Repo Captain**. On Day 1 (or ahead of time in your Tribe channel), the **Repo Captain** will create a **private GitHub repository** from this **Starter** repository and invite the other 4 **Participants** at the Table as collaborators.
3. **Join Your Tribe's Communication Channel & Pre-Event Call:**
    - Join your **Tribe**'s communication space (links shared by the organisers) led by your Google Tribe specialist mentor to say hello to your Table and coordinate whether your **Scored Deployment** will use a **Google-provided Sandbox Project** (Path 1) or an **Own-Org** project (Path 2).
    - Join the **Pre-Event Briefing Call** on **Thursday 22 October** (time and meeting link shared by the organisers), where the organisers will walk through event logistics and answer any setup questions.
    - *(Optional)* Drop into **Pre-Work Office Hours** on **Monday 26 October** (time and meeting link shared by the organisers) if you need live troubleshooting help.

## 5. Summary Checklist & Who to Contact

### Everyone (Mandatory Before Arrival)

- [ ] **Antigravity installed** from [https://antigravity.google/download](https://antigravity.google/download) and signed in with a **personal Google account** (`@gmail.com`).
- [ ] **Google Cloud CLI (`gcloud`) installed** (`gcloud --version` prints cleanly).
- [ ] **Python 3.12 + `uv` installed**, with repository dependencies installed via `make setup`.
- [ ] **Git installed** and **GitHub account** ready to push/pull private repos.
- [ ] **Self-test passed:** `gcloud --version && .venv/bin/python --version && git --version && .venv/bin/adk --version && make test` succeeds.

### Path 1 (Google-Provided Sandbox Project)

- [ ] Ready to pick up your Google-provided sandbox credentials at Day 1 check-in and authenticate via `gcloud auth login` + `gcloud auth application-default login` (no service-account JSON keys).

### Path 2 (Own-Org Participant — Using Your Company's Google Cloud)

- [ ] Dedicated Google Cloud project created/selected with active billing.
- [ ] Required APIs enabled (`aiplatform`, `cloudresourcemanager`, `run`, `artifactregistry`, `cloudbuild`, `storage`, `bigquery`, `telemetry`, `cloudtrace`, `logging`).
- [ ] User IAM roles verified (`roles/aiplatform.user`, `roles/storage.admin`, `roles/bigquery.admin`, `roles/run.admin`, `roles/iam.serviceAccountUser`, `roles/artifactregistry.writer`, `roles/cloudbuild.builds.editor`) and Vertex AI service identity created.
- [ ] Organization policies checked with your cloud admin (VPC-SC, resource locations, Cloud Run ingress).
- [ ] **Gemini 3.8 Flash** smoke test (`GEMINI_MODEL="gemini-3.8-flash"` on `GOOGLE_CLOUD_LOCATION="global"`) returned `GEMINI_READY`.

### Your Table

- [ ] Read your Table's **Challenge Card** in [`challenges/`](../challenges/README.md).
- [ ] Joined your **Tribe**'s communication channel (shared by the organisers) and agreed on a **Repo Captain**.

### Questions or Setup Blockers?

If you hit any issues with this checklist or your organisation's Google Cloud policies, reach out to the event team using the contact details shared by the organisers.
