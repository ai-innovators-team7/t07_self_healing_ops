# Pre-Work - AI Innovators Expedition London (29-30 Oct 2026)

You'll spend two days building an AI agent with your Table. To spend that time building, not installing, please tick this list before Wednesday 28 October. It takes about 30 minutes.

## Checklist

- [ ] Install the Antigravity 2.0 app (https://antigravity.google/download) - not the Antigravity IDE. Don't sign in yet: on Day 1 you'll use a Business account we give you.
- [ ] Install the [Google Cloud CLI](https://cloud.google.com/sdk/docs/install)
- [ ] Install Python 3.12 and [uv](https://docs.astral.sh/uv/)
- [ ] Install Git and have a GitHub account ready
- [ ] Join your Tribe chat (link from the organisers) and say hello to your Table
- [ ] Read the 10 challenges below and start chatting about ideas
- [ ] Bring your laptop, charger and travel documents.

> **Using your company's Google Cloud? (optional)**
> Prepare a project with billing enabled. Ask your admin to enable Vertex AI, Cloud Run, Cloud Build, Artifact Registry, Cloud Storage and BigQuery, and to give you the Vertex AI User role (plus the roles needed to deploy). Check that company policies don't block them.
>
> **No company Google Cloud? No problem** - we'll give your Table a Google sandbox project on the day.

Please don't create cloud resources or start building before the event - everything is provided on Day 1 (full challenge cards, sample data and a starter kit). Step-by-step guide: https://medium.com/google-cloud/unlock-antigravity-2-0-logins-plans-cost-and-quota-9165725685be

## The 10 challenges

| Table | Tribe | Challenge title | One-line summary |
| :--- | :--- | :--- | :--- |
| **T1** | Creative AI & AdTech | **Autonomous Creative Campaign Orchestrator** | Spots underperforming event ads, drafts localized variants, and rebalances CPM bids from live ROAS telemetry. |
| **T2** | Creative AI & AdTech | **Visual Content Creator & Dynamic Storefronts** | Combines product catalogs and segment conversion data to publish personalized storefront layouts, visual renders, and promo banners. |
| **T3** | Content Intelligence | **Conversational Catalog Discovery Assistant** | Guides buyers through secondhand marketplace listings, matches protection plans, and flags suspicious seller listings. |
| **T4** | Content Intelligence | **Dynamic B2B Integration & Sourcing Agent** | Normalizes messy supplier feeds, checks vendor reliability, and issues purchase orders for open wholesale RFQs. |
| **T5** | FinTech & Analytics | **Autonomous B2B Financial Auditor & Reconciler** | Reconciles general ledger entries against supplier invoices, flags VAT or duplicate anomalies, and enforces treasury approval policies. |
| **T6** | FinTech & Analytics | **Dynamic Climate & Regulatory Risk Assessor** | Prices commercial property renewals from climate hazard projections and loss claims, triggers inspections, and raises accumulation alerts. |
| **T7** | Cross-functional Ops & CX | **Self-Healing Infrastructure & Security Copilot** | Correlates live service incidents with recent releases and SLO runbooks to execute safe rollbacks and bounded scaling. |
| **T8** | Cross-functional Ops & CX | **Hyper-Personalized Travel Concierge & Incident Management Agent** | Finds disrupted travellers, rebooks flights or rail, secures late check-in hotels, and issues policy-capped EU261 vouchers. |
| **T9** | Smart Mobility & UX | **Smart Mobility & Energy Optimizer Agent** | Optimizes depot EV charging against hourly grid tariffs, carbon intensity, transformer headroom, and safe V2G discharge reserves. |
| **T10** | Smart Mobility & UX | **Predictive Retention & Resource Matcher** | Predicts subscriber churn and matches at-risk accounts to capped retention offers or Customer Success rescue calls. |

Questions? Ask in your Tribe chat.

## Technical details (optional)

If you use your own Google Cloud project (`YOUR_PROJECT_ID`), authenticate and enable the APIs with:

```bash
gcloud auth login && gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID
gcloud auth application-default set-quota-project YOUR_PROJECT_ID
gcloud services enable aiplatform.googleapis.com run.googleapis.com cloudbuild.googleapis.com \
  artifactregistry.googleapis.com storage.googleapis.com bigquery.googleapis.com \
  cloudresourcemanager.googleapis.com
```

- **IAM roles (if not Project Owner/Editor):** `roles/aiplatform.user`, `roles/storage.admin`, `roles/bigquery.admin`, `roles/run.admin`, `roles/artifactregistry.writer`, `roles/cloudbuild.builds.editor`, `roles/iam.serviceAccountUser`, `roles/serviceusage.serviceUsageAdmin`.
- **Regions & models:** `GOOGLE_CLOUD_LOCATION=global` for `GEMINI_MODEL=gemini-3.8-flash`; `europe-west1` for Agent Runtime and Cloud Storage; `EU` for BigQuery.
