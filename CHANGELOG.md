# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [4.1.0] - 2026-04-07

### Added
- Optional Codex CLI as a third execution backend alongside OpenCode and Claude Code
- Change-scoped SDD workflow (`input/changes/<id>/`) with `hc prd`, `hc spec`, `hc gen`, and `hc change`
- Local read-only monitor (`hc monitor`) with configurable host and port
- Generator provider selection (`openspec`, `codex`, `template`) and output language hints

### Changed
- Renamed package and runtime paths to **openHarness** / `openharness` / `.openharness/` (with legacy env aliases)
- Documentation refresh for SDD + Harness two-track model (README, architecture docs)
- Slimmed repository layout for CLI-focused users (removed bundled test suite and contributor-only tooling from the tree)

### Fixed
- Backend resolution order when both environment and project config specify a runner
- Monitor port parsing and invalid-argument handling on Windows

## [4.0.0] - 2026-03-19

### Added
- Multi-step Harness loop with Orchestrator, Coder, Tester, Fixer, and Reviewer agents
- Project-scoped state under `.openharness/` (reports, feature list, missing-info tracking)
- Git branch prompts during `hc init` for multi-repo workspaces

### Changed
- Hardened subprocess and path handling for AI CLI backends
- Clearer CLI help and version output

### Fixed
- Edge cases when `.openharness/config.yaml` is missing or partially written

## [3.0.0] - 2026-02-26

### Added
- Claude Code backend with agent markdown install under the Claude config layout
- OpenCode backend with merged `opencode.json` and packaged agent definitions
- Webhook hook points for loop milestones (optional `OPENHARNESS_WEBHOOK_URL`)

### Changed
- Refactored installer and initialization flow for repeatable `hc init`

### Fixed
- Unicode console output on Windows for status and error lines

## [2.0.0] - 2026-02-07

### Added
- First public **harnesscode**-era CLI (`hc`) with `init`, `start`, `status`, `restore`, `uninstall`
- PRD-driven feature list generation and orchestration stubs
- Sample `input/` layout for `tech-stack.md` and techspec snippets

### Changed
- Standardized on Python 3.8+ and PyYAML dependency

### Fixed
- None (initial numbered release line)

## [1.0.0] - 2026-01-14

### Added
- Proof-of-concept spec-to-task bridge and single-agent trial runs

---

## Versioning Notes

- **Major**: incompatible API or CLI contract changes
- **Minor**: backward-compatible features
- **Patch**: backward-compatible fixes

## How To Upgrade

```bash
pip install --upgrade openharness
```

Or from a clone:

```bash
git pull
pip install -e .
```

## Contributing

Use GitHub Issues and pull requests; install from source with `pip install -e .` (see README).
