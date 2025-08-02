# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Multi-College Architecture**: Complete plugin-based system for supporting multiple colleges
  - Abstract `BaseCollector` class providing common functionality for all collectors
  - College-specific implementations in `collectors/<college_name>/` directories
  - Standardized configuration format with `config.json` per college
  - College-specific data storage in `/data/<college-id>/` directories
- **Citrus College Support**: Full implementation as second supported institution
  - Custom collector handling Citrus's two-phase search process
  - Parser adapted for Citrus's HTML structure with `deheader` class
  - Support for Citrus's term code format (202620 vs Rio Hondo's 202570)
  - Successfully collects 451 courses from 30 departments
  - Dedicated GitHub Actions workflow (`.github/workflows/collect-citrus.yml`)
- **Documentation**:
  - Comprehensive guide for adding new colleges (`docs/adding-new-colleges.md`)
  - Updated README with multi-college architecture details
  - College support status table
  - Workflow badges for each college
- **Storage Enhancements**:
  - `ScheduleStorage` class now supports college-specific subdirectories
  - Automatic directory creation for each college
  - Consistent file naming: `schedule_<term>_latest.json` per college

### Changed
- **Rio Hondo Workflow Updates**:
  - Updated to use new college-specific directory structure (`data/rio-hondo/`)
  - Added directory creation step to ensure proper structure
  - Modified validation, reporting, and commit steps for new paths
  - Commit messages now specify "Rio Hondo data" for clarity
- **Collector Registry**:
  - `collect.py` now uses lazy loading for college collectors to avoid circular imports
  - Added `--college` flag for selecting target college (defaults to rio-hondo)
  - Dynamic collector loading based on selection
- **Base Infrastructure**:
  - All collectors now extend `BaseCollector` for consistency
  - Standardized validation and output methods
  - College ID embedded in output data for identification

### Fixed
- Python indentation errors in GitHub Actions workflows
  - Fixed inline Python code in report generation steps
  - Corrected YAML string formatting for multi-line Python scripts
- Import handling for multi-college support with proper lazy loading

### Technical Details
- **Architecture Pattern**: Plugin-based system where each college is self-contained
- **Data Format**: Unchanged - maintains backward compatibility
- **Term Code Handling**: Each college can have its own term numbering system
- **Scalability**: Easy to add new colleges by following established patterns

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