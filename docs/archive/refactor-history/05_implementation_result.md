# Product Reset v1 Implementation Result

> Date: 2026-09-20  
> Canonical inputs: `docs/product/Speech_Rehab_Product_Design_v1.md`, `docs/product/Speech_Rehab_UI_Interaction_Spec_v1.md`  
> Status: Product Reset v1 implementation complete; migration, seeded PostgreSQL acceptance, automated suites, production build, and authenticated browser checks are complete.

## 1. Product Reset summary

The repository now contains the Product v1 architecture without replacing its stable technical base. The primary product chain is implemented as Therapist → RehabilitationGoal → versioned TrainingPlan → TrainingSession → Exercise → ExerciseAttempt → Evidence → Metric → Comparability/Trend → Observation → Recommendation/AttentionItem → StageReview → TherapistDecision → new plan draft.

The implementation is additive. Auth, patient/therapist identities, authorization, FileAsset/storage, audio upload, ASR, acoustic analysis, pronunciation shadow evaluation, ScenarioDialogue, TTS, voice clone, avatar, EvaluationRun, clinical_stage, error handling, and legacy APIs remain in place.

## 2. Implemented architecture

- Product application/domain module: `backend/app/modules/product_v2/`.
- New API prefix: `/api/v2`; page-oriented aggregate DTOs, not table CRUD.
- Existing TrainingSession, SessionTask, Attempt adapted with additive lifecycle and snapshot fields.
- Existing scoring and ScenarioDialogue services remain the execution engines.
- Evidence/Metric are projected from existing durable outputs with provider and quality provenance.
- Comparability and Trend are deterministic. Mock/demo and ineligible records are excluded.
- Observation is derived only from at least three real, decision-eligible comparable measurements.
- Recommendation remains a candidate; only TherapistDecision can create a new plan draft, and a therapist must publish it separately.
- `clinical_stage` remains an internal canonical Assessment capability and is referenced by StageReview.

## 3. New domain objects

- RehabilitationGoal
- TrainingPlanVersion and TrainingPlanExerciseRule
- EvidenceRecord
- MetricRecord
- ObservationRecord
- RecommendationRecord
- Milestone
- AttentionItem
- StageReview
- TherapistDecision
- TrainingSessionSummary

SessionTask is the Exercise instance; Attempt is the ExerciseAttempt. Both retain immutable/session-specific state instead of redefining the stable storage chain.

## 4. New tables/models

| Table | Main responsibility |
|---|---|
| `rehabilitation_goals` | Therapist-controlled longitudinal goal; one active primary goal per patient |
| `training_plan_versions` | Immutable-after-publish formal plan versions |
| `training_plan_exercise_rules` | Ordered repeat/scenario plan composition |
| `clinical_evidence` | Traceable source references and provenance |
| `clinical_metrics` | Atomic measured/status-bearing facts |
| `clinical_observations` | Fact-supported system/human observations |
| `clinical_recommendations` | Observation-backed candidate actions |
| `patient_milestones` | Deduplicated patient-facing milestones |
| `attention_items` | Deterministic/explicit therapist work queue |
| `stage_reviews` | Review-time facts and reference snapshot |
| `therapist_decisions` | Auditable professional decisions |
| `training_session_summaries` | Stable, LLM-independent session summary |

## 5. Migration

- New revision: `0040_product_reset_v1`
- Down revision: `0039_controlled_governance`
- Strategy: additive-first; no DROP in upgrade.
- Adds PatientProfile timezone; TrainingSession formal-plan/lifecycle/status fields; SessionTask immutable snapshots; Attempt terminal/technical/measurement fields.
- Partial unique indexes protect active goal, active plan, formal daily session, and open AttentionItem dedup semantics.
- Offline PostgreSQL SQL generation succeeded and Alembic has one head.
- The configured PostgreSQL database was upgraded successfully and `python -m alembic current` reports `0040_product_reset_v1 (head)`.

## 6. New APIs

Patient:

- `GET /api/v2/patient/home`
- `GET /api/v2/patient/progress`
- `GET|PATCH /api/v2/patient/settings`
- `POST /api/v2/patient/training-sessions/start-or-resume`
- `GET /api/v2/patient/training-sessions/{id}`
- `POST .../{pause|resume|abort|complete}`
- `POST .../exercises/{task_id}/{hint|help|skip}`
- `GET .../summary`
- `POST /api/v2/patient/attempts`, audio upload, and analyze

Therapist:

- `GET /api/v2/therapist/workbench`
- `GET /api/v2/therapist/patients/{id}/workspace`
- `GET /api/v2/therapist/training-sessions/{id}`
- Goal create; plan list/draft/publish
- Attention acknowledge/resolve
- StageReview create/read; TherapistDecision create
- Formal Assessment create
- `GET /api/v2/provider-matrix`

## 7. New frontend routes

Patient primary: `/home`, `/training`, `/progress`, `/me`. Supporting routes: `/training/session/:sessionId`, summary.

Therapist primary: `/therapist`, `/therapist/patients`, `/therapist/plans`. Supporting routes: patient workspace, training detail, formal Assessment entry, StageReview.

`VITE_PRODUCT_V2_ENABLED=false` restores legacy implementations for shared entry routes. Frozen legacy deep links remain available.

## 8. Provider matrix

Runtime selection was checked without printing secrets.

| Capability | Configured | Real implementation | Runtime selected | V2 used | Mock | Verification result |
|---|---|---|---|---|---|---|
| ASR | `tencent` | yes | `TencentASRProvider` | repeat + scenario through existing services | test fallback exists | REAL AND ACTIVE |
| Acoustic | `local` | yes | `LocalAcousticAnalysisProvider` | repeat scoring | test mock exists | REAL AND ACTIVE |
| Pronunciation | `tencent_soe` | yes | `TencentSoeProvider` | existing shadow pipeline | disabled/mock test path | REAL AND ACTIVE |
| Generic LLM Feedback | `openai_compatible` requested | no real factory | `MockLLMFeedbackProvider` | no; v2 uses deterministic summary | yes | MOCK ONLY / NOT IMPLEMENTED |
| Scenario Semantics | `openai_compatible` | yes | OpenAI-compatible path; required config present | scenario service | deterministic fallback | REAL AND ACTIVE (selection/config verified; no paid live call performed) |
| TTS | `windows` | yes | `WindowsTTSProvider` | preserved legacy companion surfaces; v2 core uses browser speech synthesis | test mock exists | REAL AND ACTIVE |
| Voice Clone | `tencent` | yes | `TencentVCLProvider` | preserved, not required by v2 core | test mock exists | REAL AND ACTIVE |
| Avatar | `disabled` | yes, Aliyun | disabled | preserved, not required by v2 core | test mock exists | DISABLED / REAL IMPLEMENTATION NOT CONFIGURED |

No live paid provider request was made. Existing provider parsing/contract tests stayed green. Provenance and technical-invalid paths prevent fallback/mock output from becoming formal Metric data.

## 9. Legacy compatibility

- Old API routers remain registered.
- Old data models and migration history remain intact.
- Legacy TrainingPlan relation stays on TrainingSession.
- Legacy UI is frozen, not deleted; flag/deep links provide rollback.
- No historical data deletion or destructive migration exists.

## 10. Test results

Latest green results on 2026-09-20:

- Backend: `221 passed in 14.99s` (baseline 208; Product v2 contract/lifecycle coverage added).
- Frontend: `7 files / 13 tests passed` (baseline 6 files / 10 tests).
- Frontend typecheck + production build: passed, 2329 modules; existing large-chunk warning remains.
- Alembic heads: one source head, `0040_product_reset_v1`.
- Migration offline SQL: passed.
- Connected DB upgrade: passed; current revision is `0040_product_reset_v1 (head)`.
- Trial and Product v2 demo seed: passed; `source_status=mock`, `formal_trend_eligible=false`.

New backend tests cover plan versions/activation, repeat+scenario composition, idempotent formal session vs extra practice, pause/resume/terminal states/summary, therapist assignment authorization, AttentionItem dedup/resolution, StageReview → Decision → unpublished plan draft, formal Assessment boundary, WAB reliability exclusion, Metric comparability/trend, mock exclusion, schema and route registration. Existing provider, scenario, clinical-stage, authorization, retry and legacy tests remain green.

## 11. Seed/demo instructions

After applying migration 0040:

```powershell
cd backend
python scripts/init_trial_data.py --patient-count 2 --family-count 0
python scripts/seed_product_v2_demo.py
```

Default local trial password is defined by `init_trial_data.py` and may be overridden with `--password`. Demo-derived records are visibly labeled `source_status=mock`/“演示数据”, `decision_eligible=false`, and are excluded from formal trends, clinical observations/recommendations, and decisions.

## 12. Manual verification

Start backend with `python -m uvicorn app.main:app --reload`; start frontend with `npm run dev`.

Patient path: login as `trial_patient_01` → Home → start/resume today → repeat recording/analyze/retry/hint → scenario multi-turn/hint → complete → summary → progress/milestone → settings. Reload during a session and confirm the same session/exercise resumes.

Therapist path: login as `trial_therapist_01` → Workbench → AttentionItem → Patient Workspace → training detail → Evidence/Metric/source/comparability → plan draft with repeat + scenario → publish → confirm only a newly created patient formal session binds the new version.

StageReview: Patient Workspace → create StageReview → inspect facts/trends/Assessment/Observation/Recommendation → record Decision → for plan-version decision, inspect the new draft and publish it separately.

Assessment: Patient Workspace → “录入正式评估” → fill instrument/version/mode and only actually administered CADL/WAB fields → leave missing items blank → save → verify clinical_stage is internal shadow and WAB reliability displays unsupported.

Authenticated browser acceptance was completed for the patient Home, today’s Training, Progress and Settings routes, and for the therapist Workbench, Patient directory/workspace, training detail, plan management, StageReview and formal Assessment entry surfaces. Destructive or clinically consequential form submissions were covered by service/API tests rather than performed as browser-side manual mutations.

## 13. Known limitations

- Generic LLM feedback provider is still mock-only by repository design. V2 completion and summaries do not depend on it.
- Live external provider calls were not executed to avoid irreversible/paid external operations; runtime selection and contract tests were verified.
- Frontend has no full Playwright E2E harness; route/API contracts, typecheck/build, responsive CSS, and authenticated manual browser acceptance were verified.
- Existing Vite large bundle warning is unrelated technical debt.

## 14. Unsupported / source-sensitive metrics

- WAB reliability: explicitly `unsupported`; never accepted into formal Assessment metrics.
- CADL and supported WAB subscales: only from a therapist-created formal Assessment; blank means `not_administered`.
- Error count, loudness, expression completeness/script accuracy, speech rate: may come from the current training provider pipeline, but only valid real-provider measurements are eligible for formal comparison.
- Acceptance and other Assessment-only values are never synthesized from TrainingSession.

## 15. Remaining technical debt

- Add Playwright/browser E2E after the connected database is migrated and seeded.
- Replace generic LLM mock factory only when a real, tested capability is intentionally implemented; do not conflate it with scenario semantics.
- Consider route-chunk/manual-chunk optimization after the product loop is accepted, not before.

## IMPLEMENTATION_PROGRESS

### completed

- Canonical product specs and changelog
- Product v2 models, schemas, services, routes and additive migration
- Patient and therapist product shells, repeat/scenario plan composition, formal Assessment entry
- Evidence/Metric/Comparability/Trend/Observation/Recommendation boundaries
- Attention, StageReview and TherapistDecision loop
- Legacy switch and compatibility
- Regression tests, build, provider runtime inventory and seed dry run

### in_progress

- None. Product Reset v1 is at the requested completion boundary.

### remaining

- No required Product Reset v1 implementation work remains. The items in “Known limitations” are explicit follow-up engineering work, not blockers to the v1 loop.

### last_green_test_result

- Backend: 221 passed
- Frontend: 7 files / 13 tests passed
- Frontend build/typecheck: passed

### current_migration_head

- Source head: `0040_product_reset_v1`
- Connected DB: `0040_product_reset_v1 (head)`

### next_exact_task

Product Reset v1 implementation is complete. The next task should be chosen from post-v1 follow-up work only after product acceptance.
