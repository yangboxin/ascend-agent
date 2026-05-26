# Roadmap: Ascend Diagnostic Agent

**Created:** 2025-05-20

---

## Milestones

- ✅ **v1.0 MVP** — Phases 1-5 (shipped 2026-05-25)
- 🚧 **v1.1 Multi-Provider & Multi-Repo** — Phases 6-9 (in progress)

## Phases

<details>
<summary>✅ v1.0 MVP (Phases 1-5) — SHIPPED 2026-05-25</summary>

- [x] Phase 1: Architecture Foundation (5/5 plans) — completed 2026-05-21
- [x] Phase 2: Diagnosis Engine (3/3 plans) — completed 2026-05-21
- [x] Phase 3: Fix Generation (3/3 plans) — completed 2026-05-21
- [x] Phase 4: Reproduction Capability (5/5 plans) — completed 2026-05-25
- [x] Phase 5: Verification &闭环 (3/3 plans) — completed 2026-05-25

**Full details:** `.planning/milestones/v1.0-ROADMAP.md`

</details>

---

## Summary

| Phase | Milestone | Plans | Status | Completed |
|-------|-----------|-------|--------|-----------|
| 1. Architecture Foundation | v1.0 | 5/5 | Complete | 2026-05-21 |
| 2. Diagnosis Engine | v1.0 | 3/3 | Complete | 2026-05-21 |
| 3. Fix Generation | v1.0 | 3/3 | Complete | 2026-05-21 |
| 4. Reproduction Capability | v1.0 | 5/5 | Complete | 2026-05-25 |
| 5. Verification &闭环 | v1.0 | 3/3 | Complete | 2026-05-25 |

---
### 🚧 v1.1 Multi-Provider & Multi-Repo (In Progress)

- [x] Phase 6: Provider Routing Foundation (4 requirements) — PROV-01..04
  Plans:
  - [x] 06-01-PLAN.md — Core infra: ProviderConfig, create_router, ModelRouter update, Settings fields, root --provider flag, router tests (completed 2026-05-26)
  - [x] 06-02-PLAN.md — CLI wiring: create_router() in all 4 CLI commands, per-command --provider overrides, CLI integration tests
- [ ] Phase 7: Chinese Model Integration (4 requirements) — CHN-01..04
- [ ] Phase 8: Multi-Repo Support (4 requirements) — REPO-01..04
- [ ] Phase 9: Provider & Multi-Repo Testing (4 requirements) — TEST-01..04

## Summary

| Phase | Milestone | Plans | Status | Completed |
|-------|-----------|-------|--------|-----------|
| 1. Architecture Foundation | v1.0 | 5/5 | Complete | 2026-05-21 |
| 2. Diagnosis Engine | v1.0 | 3/3 | Complete | 2026-05-21 |
| 3. Fix Generation | v1.0 | 3/3 | Complete | 2026-05-21 |
| 4. Reproduction Capability | v1.0 | 5/5 | Complete | 2026-05-25 |
| 5. Verification &闭环 | v1.0 | 3/3 | Complete | 2026-05-25 |
| 6. Provider Routing Foundation | v1.1 | 2/2 | Complete   | 2026-05-26 |
| 7. Chinese Model Integration | v1.1 | 0/0 | Not started | - |
| 8. Multi-Repo Support | v1.1 | 0/0 | Not started | - |
| 9. Provider & Multi-Repo Testing | v1.1 | 0/0 | Not started | - |

**Total: 9 phases (5 complete, 4 planned) | 16 requirements**

---

*Roadmap created: 2025-05-20 | Last updated: 2026-05-26 after Plan 06-01*
