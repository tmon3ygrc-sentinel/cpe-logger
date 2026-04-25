# Changelog

All notable changes to this project will be documented in this file.

The format follows [Semantic Versioning](https://semver.org/).

---

## [1.0.0] - 2025-07-28
### Added
- **Executive Orders Schema (eoschema)** in JSON and YAML formats
- **Framework Schema (frameworkschema)** in JSON and YAML formats
- **Regulations Schema (regschema)** in JSON and YAML formats
- **Sample documents** for Executive Orders, Frameworks, and Regulations in both JSON and YAML
- **Validation scripts**:
  - `scripts/validate.py` (Python-based JSON/YAML validator)
  - `scripts/validate.sh` (AJV CLI-based quick validator)
- **README.md** with Quick Start guide
- **VERSION** file (1.0.0)
- **Documentation placeholders** (`docs/SchemaDocumentation.md` and `docs/Methodology.md`) for schema details and methodology

---

## Planned
- GitHub Actions workflow for automated schema validation on pull requests
- Expanded documentation for contributors (`CONTRIBUTING.md`)
- Detailed role-based CODEOWNERS file for repository governance
- Additional schema examples and extended test cases
