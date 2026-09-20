# Product Reset v1 Design System

## Direction contract

**THESIS** — The product is a calm rehabilitation workspace organized around the next safe action and the evidence behind it. It refuses the monitoring-dashboard pattern and decorative metric walls.

**OWN WORLD** — Daylight clinic surfaces: soft mineral gray background, white work surfaces, deep ink, therapeutic teal for action, cobalt for navigational information, amber for attention, and restrained red only for destructive or unsafe states. Rounded geometry is compact rather than playful; dividers carry structure more often than cards.

**STORY** — Patients immediately understand what to practise, why, and for how long. Therapists see who needs attention, inspect evidence, and record a decision without mistaking system suggestions for clinical facts.

**FIRST VIEWPORT** — A quiet shell frames one dominant task. Patient home leads with today's plan and one large action; therapist workbench leads with an ordered attention queue. Secondary evidence stays below or behind deliberate disclosure.

**FORM** — Operate-mode healthcare workspace, extending the repository's warm teal visual language while replacing its old information architecture.

## Durable visual rules

- Use the system UI stack for legibility across Windows rehabilitation environments.
- Body text is at least 16px; patient primary copy is 18–20px. Patient controls are at least 48px high.
- Use one restrained page-scale palette. Status always includes text or an icon; color is never the only signal.
- Prefer sections, rows, and deliberate whitespace over nested cards. Cards are reserved for actionable units such as an AttentionItem or today's plan.
- Patients see plain language and stable button positions. Technical provenance is hidden from patient surfaces.
- Therapist pages distinguish Measurement, Observation, Recommendation, and Decision by headings and structure, not by a generic “AI analysis” container.
- Motion is limited to one gentle state transition and respects `prefers-reduced-motion`.
- Desktop therapist views may be dense; patient views remain spacious and mobile-first. Mobile patient navigation is fixed at the bottom.

