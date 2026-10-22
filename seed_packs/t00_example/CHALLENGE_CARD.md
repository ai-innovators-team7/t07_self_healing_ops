# Challenge Card — Table 0 (Reference Example Pack: `t00_example`)

## Collaborative Challenge
**London Specialty Roastery Concierge & Inventory Agent** — Reference implementation demonstrating how every Table's Seed Pack plugs into the common Starter repository.

## Persona & Scenario
**Maya Lin**, Head of Operations at **Pancras Square Specialty Roasters** (3 London cafés: King's Cross, London Soho, Shoreditch). Every morning Maya checks which drinks are driving revenue, answers customer allergen/menu questions, and places urgent green-bean reorders before the morning rush.

## Minimum Playable Scope (First 60 Minutes)
1. Run `make seed PACK=t00_example` to create the `seed_t00` BigQuery dataset (`menu` and `daily_sales` tables) and stage sample assets in Cloud Storage.
2. Run `make dev` (`adk web`) and ask the agent about espresso prices, London Soho revenue, and placing a 25 kg Ethiopian Yirgacheffe bean reorder.
3. Run `make eval` to execute the 5 golden evaluation scenarios in `seed_packs/t00_example/eval/golden.test.json`.
4. Run `make deploy` and `make test-remote` to verify live execution on Vertex AI Agent Runtime (`europe-west1`).

## Stretch Goal
Add a margin-optimization tool that cross-references `menu` unit cost against `daily_sales` volume and recommends bundle promotions.

## Security & Guardrails Test Vector (Optional +1 Bonus)
- **Attack Vector**: **Unauthorized Supplier Payout / Instruction Override**: An adversarial prompt or poisoned record attempts to trick the agent into approving a fake supplier reorder or ignoring its tool data.
- **Defence Hint**: Enforce strict parameter validation in `submit_bean_reorder` and demonstrate blocking or safely handling untrusted inputs during your demo or evals to earn the `+1 pt` Security bonus.
