# Design

## Mode

Operate.

## Direction Contract

THESIS: The app is a calm rehabilitation cockpit for one daily loop, refusing a marketing homepage or decorative medical dashboard.

OWN-WORLD: Clean clinical workspace with warm human accents, soft green for recovery progress, blue for primary action, coral only for guidance and attention. Components are compact, legible, and task-first.

STORY: The patient signs in, sees the current companion, starts one training session, records speech, receives a score and one useful next step.

FIRST VIEWPORT: The first screen after login shows current companion, today’s training status, and a large start-training command before secondary history or setup actions.

FORM: Patient workflow app with restrained color strategy; structure follows the MVP documents rather than a generated visual seed.

## Tokens

- Background: `#f7faf8`
- Surface: `#ffffff`
- Text: `#20302a`
- Muted text: `#66756f`
- Primary: `#2563eb`
- Recovery: `#2f9e73`
- Attention: `#e86f51`
- Border: `#dce7e1`
- Radius: `8px`

## Components

Use simple app-shell navigation, clear form fields, status chips, upload panels, training task panels, recorder controls, and score summaries. Avoid nested cards and oversized hero layouts.

## Interaction

Primary workflows should need few decisions. File upload, recording, scoring, and report states must show explicit pending, success, and failure messaging.
