# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2025-01-26

### Added
- Two-phase collection process for Rio Hondo College
  - Phase 1: POST to p_search endpoint to select term
  - Phase 2: POST to p_listthislist with full parameter set
- Automated collection schedule (3x daily at offset minutes: 6:26 AM, 2:26 PM, 10:26 PM UTC)
- Git scraping style commit messages with timestamps
- Support for URL-encoded wildcards in search parameters

### Changed
- Updated Rio Hondo collector to match exact browser API workflow from HAR file analysis
- Simplified GitHub Actions workflow following git scraping best practices
- Removed test step from collection workflow (tests run in CI/PR instead)
- Parameter structure now uses list of tuples to maintain order and allow duplicates

### Fixed
- Parameter encoding issues (proper handling of % wildcards)
- Missing required parameters (aa, ee, duplicate sel_camp)
- Collection now successfully retrieves 1634 courses from 102 departments

### Removed
- Anthropic API key from workflow (not needed for web scraping approach)
- Unused API configuration from config.yml

## [0.1.0] - 2025-01-25

### Added
- Initial project structure with multi-college collector architecture
- Rio Hondo College collector with BeautifulSoup HTML parser
- CLI tool for data analysis and validation
- GitHub Actions workflow for automated collection
- Comprehensive test suite
- Documentation and README

[Unreleased]: https://github.com/jmcpheron/ccc-schedule-collector/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/jmcpheron/ccc-schedule-collector/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/jmcpheron/ccc-schedule-collector/releases/tag/v0.1.0