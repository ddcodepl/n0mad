# N0MAD Claude Code Instructions

## N0MAD Project Overview

**N0MAD: Notion Orchestrated Management & Autonomous Developer**

N0MAD is an AI-powered autonomous developer that integrates with Notion to provide intelligent task management, automated development workflows, and seamless AI collaboration. This is a production-ready Python package installable via `pip install n0mad`.

## Basic Instructions

* Code should work with Python 3.8+
* Always use uv as package manager when available
* Prepare tests for each functionality that you are building
* Verify if tests are passing
* Use self explanatory names for files, methods, variables, classes and etc
* Use @python-pro agent when creating code
* Code should follow DRY and KISS principles
* Maintain production-ready security and error handling
* Tasks are stored in root directory: `./tasks/` (not in src)

## N0MAD Architecture

* **Package Name**: `n0mad` (installable via pip)
* **Main Command**: `n0mad` (also supports `nomad` for backwards compatibility)
* **Source Structure**: All source code in `src/` directory
* **Task Storage**: Tasks stored in `./tasks/` directory at project root
* **Version**: 0.0.1

## Task Master AI Instructions
**Import Task Master's development workflow commands and guidelines, treat as if import is in the main CLAUDE.md file.**
@./.taskmaster/CLAUDE.md
