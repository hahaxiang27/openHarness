# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- Added the `CONTRIBUTING.md` contribution guide
- Added the base unit test framework
- Added the GitHub Actions CI/CD workflow
- Added development dependencies and tool configuration

### Changed
- Improved `pyproject.toml` configuration
- Added code quality tools (`ruff`, `mypy`, `bandit`)

### Fixed
- None

## [4.1.0] - 2026-03-28

### Added
- Git branch selection support
- Multi-repository Git support
- Branch scanning and interactive selection
- Support for creating and switching branches

### Changed
- Improved the Git repository scanning algorithm
- Improved the user interaction flow
- Strengthened error handling

### Fixed
- Fixed path resolution issues
- Fixed configuration file reading errors

## [4.0.0] - 2026-03-15

### Added
- Dual-backend support (OpenCode and Claude Code)
- Modular agent architecture
- State file management
- Auto-commit support

### Changed
- Refactored the overall architecture
- Improved performance
- Improved documentation

### Fixed
- Initial release, no fixes

## [3.0.0] - 2026-02-20

### Added
- Initial public release
- Basic development loop
- Simple agent collaboration

---

## Versioning Notes

- **Major**: incompatible API changes
- **Minor**: backward-compatible feature additions
- **Patch**: backward-compatible bug fixes

## How To Upgrade

```bash
# Upgrade to the latest version
pip install --upgrade openharness

# Or install from source
git pull
pip install -e .
```

## Contributing

See `CONTRIBUTING.md` for contribution guidelines.
