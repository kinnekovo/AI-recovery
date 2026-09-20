# Product context

> Status: inferred from the repository's current V4.0 product brief and the four current V2/V3 architecture documents. This file records product intent; it does not introduce clinical rules.

## Product

言语康复智能体 is a web-based rehabilitation support product. It connects traceable speech and communication evidence with patient-safe longitudinal views and a professional review workspace. It supports rehabilitation workflows; it does not diagnose, prescribe, replace therapist judgment, or claim clinical efficacy.

## Users

- Patients: complete repeat and scenario training, review understandable feedback, and see a safe projection of their longitudinal Profile V2.
- Therapists and authorized professionals: review assigned patients, assessments, canonical Clinical Stage results, Profile V2 evidence, Policy V2 shadow decisions, calibration and validation evidence, controlled actions, and governance state.
- Family members: receive the existing limited support view. They do not access Policy, validation, controlled-action, or governance internals.

## Core jobs

1. Preserve a low-friction, accessible patient training loop on mobile and desktop.
2. Let therapists trace every professional conclusion back to real backend evidence and state.
3. Make shadow, review-required, stale, blocked, and suspended states explicit before any action.
4. Require deliberate confirmation for irreversible or high-risk workflow transitions.

## Product principles

- API-first: pages consume repository endpoints through typed domain clients; no final mock data.
- Evidence over decoration: empty and insufficient-evidence states remain honest and useful.
- Human control: Policy V2 remains shadow/advisory; controlled actions require backend authorization and explicit approval/apply steps.
- Patient-safe language: no internal reason codes, provider metadata, clinical interpretation, or invented aggregate score in patient views.
- Professional traceability: preserve versions, units, provenance, warnings, reason codes, and audit history in authorized views.
- Compatibility: retain existing patient training, legacy assessment, scoring, and phase4.3 routes while adding V4 navigation and adapters.

## Experience direction

- Warm, quiet healthcare interface with light surfaces, low-saturation blue/teal/green accents, clear typography, and restrained status color.
- Patient views use larger targets, simpler language, and low information density.
- Professional views use compact tables and structured detail panels without becoming a monitoring-wall dashboard.
- Status is always communicated with text and icon/shape, never color alone.

## Constraints and boundaries

- Frontend does not calculate canonical scores, comparability, Profile, Policy, validation eligibility, or governance status.
- Page load never triggers rebuild, calibration, policy generation, apply, rollback, freeze, or approval.
- Backend authorization is the source of truth; hidden or disabled controls are usability safeguards only.
- Existing backend endpoints do not currently expose list operations for every professional entity. The UI may use explicit entity IDs for those workflows and must not synthesize records.
- Current scope excludes autonomous training, automatic approval, diagnosis, prescription, reinforcement learning, efficacy claims, patient-facing Policy recommendations, and family approval.
