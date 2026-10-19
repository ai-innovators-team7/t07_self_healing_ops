# Challenge Cards — AI Innovators Expedition London (Tables T01–T10)

> **Note:** Each file `T01-<slug>.md` through `T10-<slug>.md` in this folder has the **exact same content** as `seed_packs/tNN_<slug>/CHALLENGE_CARD.md`. They are collected here so you can browse all 10 **Tables**, **Tribes**, **Sister Tables** (for the **Tribe A2A Bonus**), and **VAR / Red Team Minute** attack vectors in one place.
>
> *All companies, personas, datasets, and mock APIs described in these Challenge Cards are 100% synthetic and fictional.*

---

## Table 1 – Table 10 Overview

| Table | Challenge Card | Tribe | Collaborative Challenge Title | Sister Table (Tribe A2A) | Seed Pack Directory | Known VAR / Red Team Attack Category |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **T01** | [`T01-campaign_orchestrator.md`](./T01-campaign_orchestrator.md) | Creative AI & AdTech | **Autonomous Creative Campaign Orchestrator** | **T02** (`t02_dynamic_storefronts`) | [`seed_packs/t01_campaign_orchestrator`](../seed_packs/t01_campaign_orchestrator/) | Poisoned Event Brief / Ad Copy Injection (CPM & budget cap bypass) |
| **T02** | [`T02-dynamic_storefronts.md`](./T02-dynamic_storefronts.md) | Creative AI & AdTech | **Visual Content Creator & Dynamic Storefronts** | **T01** (`t01_campaign_orchestrator`) | [`seed_packs/t02_dynamic_storefronts`](../seed_packs/t02_dynamic_storefronts/) | Untrusted Catalog Metadata Discount Injection (`discount_pct=95` override) |
| **T03** | [`T03-catalog_discovery.md`](./T03-catalog_discovery.md) | Content Intelligence | **Conversational Catalog Discovery Assistant** | **T04** (`t04_b2b_sourcing`) | [`seed_packs/t03_catalog_discovery`](../seed_packs/t03_catalog_discovery/) | Seller Listing Ranking Jailbreak (forced rank #1 & fake protection plan) |
| **T04** | [`T04-b2b_sourcing.md`](./T04-b2b_sourcing.md) | Content Intelligence | **Dynamic B2B Integration & Sourcing Agent** | **T03** (`t03_catalog_discovery`) | [`seed_packs/t04_b2b_sourcing`](../seed_packs/t04_b2b_sourcing/) | Malicious Supplier Feed Payload / Schema Smuggling (unauthorized PO above unit cost cap) |
| **T05** | [`T05-financial_auditor.md`](./T05-financial_auditor.md) | FinTech & Analytics | **Autonomous B2B Financial Auditor & Reconciler** | **T06** (`t06_climate_risk`) | [`seed_packs/t05_financial_auditor`](../seed_packs/t05_financial_auditor/) | Poisoned Invoice Line Memo (fake CFO override bypassing VAT & dual sign-off) |
| **T06** | [`T06-climate_risk.md`](./T06-climate_risk.md) | FinTech & Analytics | **Dynamic Climate & Regulatory Risk Assessor** | **T05** (`t05_financial_auditor`) | [`seed_packs/t06_climate_risk`](../seed_packs/t06_climate_risk/) | Poisoned Broker Submission Note (forced `LOW_RISK` & negative premium loading) |
| **T07** | [`T07-self_healing_ops.md`](./T07-self_healing_ops.md) | Cross-functional Ops & CX | **Self-Healing Infrastructure & Security Copilot** | **T08** (`t08_travel_concierge`) | [`seed_packs/t07_self_healing_ops`](../seed_packs/t07_self_healing_ops/) | Log-Injected Destructive Remediation (`target_replicas=0` outage trigger) |
| **T08** | [`T08-travel_concierge.md`](./T08-travel_concierge.md) | Cross-functional Ops & CX | **Hyper-Personalized Travel Concierge & Incident Management Agent** | **T07** (`t07_self_healing_ops`) | [`seed_packs/t08_travel_concierge`](../seed_packs/t08_travel_concierge/) | Poisoned Supplier Feed Note (excessive €5,000 compensation voucher trigger) |
| **T09** | [`T09-mobility_energy.md`](./T09-mobility_energy.md) | Smart Mobility & UX | **Smart Mobility & Energy Optimizer Agent** | **T10** (`t10_retention_matcher`) | [`seed_packs/t09_mobility_energy`](../seed_packs/t09_mobility_energy/) | Spoofed Grid Operator Notice (unsafe 2% battery reserve V2G discharge across depots) |
| **T10** | [`T10-retention_matcher.md`](./T10-retention_matcher.md) | Smart Mobility & UX | **Predictive Retention & Resource Matcher** | **T09** (`t09_mobility_energy`) | [`seed_packs/t10_retention_matcher`](../seed_packs/t10_retention_matcher/) | Cancellation Chat Credit Injection (€9,999 credit & 90% discount override) |

---

## How to Activate Your Table's Challenge in the Starter

```bash
# 1. Set SEED_PACK in .env (e.g. t01 .. t10)
cp .env.example .env
# Edit .env: set GOOGLE_CLOUD_PROJECT=<your-project-id> and SEED_PACK=t08

# 2. Load your Table's synthetic CSVs into BigQuery in your project
make seed PACK=t08

# 3. Launch the ADK Web UI locally or run the 5 golden evaluations
make dev
make eval PACK=t08
```
