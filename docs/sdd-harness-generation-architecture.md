# openHarness SDD + Harness Architecture

## Overview

openHarness now uses a single minimal workflow:

1. SDD side
   - `oph prd`, `oph spec`, and `oph gen` generate change-based requirement artifacts.
   - Each requirement lives under `input/changes/<change-id>/`.
2. Harness side
   - `oph start` executes only the active change.
   - Before execution, openHarness prepares `.openharness/runtime-input/` as a flat compatibility view for existing agents.

This keeps demand-side planning and implementation-side execution connected without generating OpenSpec proposal or design documents.

## Commands

```powershell
oph init --backend codex
oph gen "实现登录功能，状态保存在 localStorage"
oph change list
oph change use login
oph start --backend codex
```

Command behavior:

- `oph prd "<requirement>"`
  - Creates a new change PRD at `input/changes/<change-id>/prd.md`
  - Creates `input/prd/tech-stack.md` when missing
- `oph spec "<requirement>"`
  - Writes or updates `input/changes/<change-id>/techspec.md`
  - Defaults to the active change when one exists
- `oph gen "<requirement>"`
  - Generates `prd.md`, `techspec.md`, `meta.yaml`, and optional `missing-info.md`
  - Sets the generated change as active
- `oph change list`
  - Lists all changes under `input/changes/`
- `oph change use <change-id>`
  - Switches `.openharness/active_change`

## Directory Contract

Global files:

- `input/prd/tech-stack.md`
- `.openharness/active_change`
- `.openharness/runtime-input/`

Per-change files:

- `input/changes/<change-id>/prd.md`
- `input/changes/<change-id>/techspec.md`
- `input/changes/<change-id>/meta.yaml`
- `input/changes/<change-id>/missing-info.md` when the request is incomplete

Runtime compatibility view:

- `.openharness/runtime-input/input/prd/generated-prd.md`
- `.openharness/runtime-input/input/PRD/generated-prd.md`
- `.openharness/runtime-input/input/techspec/tech-spec-<change-id>.md`

The runtime-input mirror exists only so existing agents can keep reading flat input paths while the source of truth stays in `input/changes/`.

## Provider Model

The generation layer still supports three providers:

- `openspec`
  - Default provider name
  - Generates Harness SDD change docs, not OpenSpec proposal/design/tasks/spec files
- `codex`
  - Uses Codex CLI to draft change content, then normalizes it into the same change contract
- `template`
  - Local deterministic fallback without an external model

Resolution order:

1. `--provider`
2. `generator_provider` in `.openharness/config.yaml`
3. default `openspec`
