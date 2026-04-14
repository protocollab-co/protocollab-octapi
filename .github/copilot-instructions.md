---
name: Workspace Instructions
applyTo:
  - '**/*'
description: |
  Workspace-wide instructions for AI agents contributing to the protocollab-octapi project. Follow these principles for all code, documentation, and automation tasks.

principles:
  - Link, don't embed: Reference existing documentation in docs/ and README.md files instead of duplicating content.
  - Use Docker for all runtime and build/test operations unless explicitly noted otherwise.
  - Validate YAML and Lua using the provided pipelines and Docker sandbox.
  - Follow the error format: field, message, expected, got, hint, source.
  - Use Jinja2 templates for Lua code generation (see templates/octapi/).
  - Security: Always run untrusted code in the Docker sandbox with hardening flags (see README.md for details).
  - Document new endpoints, templates, or pipeline steps in docs/ and update the main README.md if user-facing.
  - For UI/UX changes, see docs/boost/ui.md for guidelines and examples.
  - For verification and test artifacts, see docs/verification/.
  - For planning and deliverables, see docs/planning/ and docs/deliverables/.
  - Use English for code and comments; Russian is allowed in documentation only.
  - If unsure, consult the relevant docs/ section before making changes.

anti-patterns:
  - Duplicating documentation from docs/ or README.md.
  - Running Lua or YAML validation outside the Docker sandbox.
  - Introducing new error formats or skipping error details.
  - Adding templates without Jinja2 or without tests.
  - Making UI/UX changes without updating docs/boost/ui.md.
  - Skipping verification steps for new features.

# See also:
# - docs/README.md for documentation structure
# - README.md for quick start and architecture
# - docs/ubuntu_runbook.md for environment setup
# - docs/verification/ for test/verification protocols
# - templates/octapi/ for Lua templates
# - tests/ for test coverage
