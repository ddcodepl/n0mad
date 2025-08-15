# Package Management Guide

This comprehensive guide covers package management practices, procedures, and best practices for the Nomad project.

## Table of Contents
1. [Overview](#overview)
2. [Package Management Tools](#package-management-tools)
3. [Dependency Management](#dependency-management)
4. [Update Procedures](#update-procedures)
5. [Version Management](#version-management)
6. [Security Considerations](#security-considerations)
7. [Development Dependencies](#development-dependencies)
8. [Testing Procedures](#testing-procedures)
9. [Rollback Procedures](#rollback-procedures)
10. [Best Practices](#best-practices)

---

## Overview

Nomad uses multiple package management systems to handle different types of dependencies:

- **Python Packages**: Managed via pip, with uv for enhanced performance
- **Node.js Modules**: For JavaScript task processing components
- **System Dependencies**: Platform-specific package managers
- **Development Tools**: Additional tools for development and testing

### Current Package Management Stack

| Tool | Purpose | Configuration Files |
|------|---------|-------------------|
| **pip** | Python package installation | `requirements.txt`, `pyproject.toml` |
| **uv** | Fast Python package resolver | `uv.lock`, `pyproject.toml` |
| **npm** | Node.js package management | `package.json`, `package-lock.json` |
| **setuptools** | Python package building | `setup.py`, `pyproject.toml` |

---

## Package Management Tools

### Primary Tools

#### 1. uv (Recommended for Development)
**uv** is an extremely fast Python package installer and resolver.

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Basic operations
uv pip install package-name
uv pip list
uv pip freeze
uv sync  # Install from lockfile
```

**Advantages**:
- 10-100x faster than pip
- Better dependency resolution
- Lockfile support
- Drop-in pip replacement

#### 2. pip (Standard Python Package Manager)
Traditional Python package manager, widely supported.

```bash
# Basic operations
pip install package-name
pip list
pip freeze
pip install -r requirements.txt
```

#### 3. npm (Node.js Package Manager)
For JavaScript components and task processing modules.

```bash
# Basic operations
npm install
npm update
npm list
npm audit
```

### Configuration Files

#### Python Package Configuration

##### `pyproject.toml` (Primary Configuration)
```toml
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "nomad-notion-automation"
version = "0.2.0"
description = "Global Notion task refinement and automation tool with AI integration"
requires-python = ">=3.8.1"
dependencies = [
    "aiohttp>=3.9.0",
    "notion-client>=2.2.1",
    "openai>=1.35.0",
    "psutil>=7.0.0",
    "python-dotenv>=1.0.1",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-asyncio>=0.21.0",
    "pytest-cov>=4.0.0",
    "black>=23.0.0",
    "isort>=5.0.0",
    "flake8>=6.0.0",
    "mypy>=1.0.0",
]
```

##### `requirements.txt` (Legacy Support)
```txt
# Core Dependencies
psutil>=7.0.0
notion-client>=2.2.1
openai>=1.35.0
python-dotenv>=1.0.1
aiohttp>=3.9.0

# Development Dependencies
pytest>=7.0.0
setuptools>=65.0.0

# Optional/Recommended Dependencies
pydantic>=2.0.0
requests>=2.28.0

# Slack Integration
slack-sdk>=3.25.0
```

##### `uv.lock` (Dependency Lockfile)
Auto-generated file that locks exact versions and hashes for reproducible installs.

#### Node.js Configuration

##### `package.json`
```json
{
  "name": "nomad-task-processor",
  "version": "1.0.0",
  "description": "Automated task processing module for nomad project",
  "main": "process-tasks.js",
  "scripts": {
    "start": "node process-tasks.js",
    "test": "echo \"Error: no test specified\" && exit 1"
  },
  "dependencies": {
    "axios": "^1.4.0",
    "fs-extra": "^11.0.0",
    "dotenv": "^16.0.0"
  },
  "keywords": ["task-processing", "automation", "claude"],
  "author": "",
  "license": "ISC"
}
```

---

## Dependency Management

### Core Dependencies

#### Required Python Packages
| Package | Version | Purpose |
|---------|---------|---------|
| `aiohttp` | >=3.9.0 | Async HTTP client for API calls |
| `notion-client` | >=2.2.1 | Notion API integration |
| `openai` | >=1.35.0 | OpenAI API client |
| `psutil` | >=7.0.0 | System monitoring and performance |
| `python-dotenv` | >=1.0.1 | Environment variable management |

#### Optional Dependencies
| Package | Version | Purpose |
|---------|---------|---------|
| `pydantic` | >=2.0.0 | Data validation and settings |
| `requests` | >=2.28.0 | HTTP client (fallback) |
| `slack-sdk` | >=3.25.0 | Slack integration |

#### Development Dependencies
| Package | Version | Purpose |
|---------|---------|---------|
| `pytest` | >=7.0.0 | Testing framework |
| `pytest-asyncio` | >=0.21.0 | Async testing support |
| `pytest-cov` | >=4.0.0 | Coverage reporting |
| `black` | >=23.0.0 | Code formatting |
| `isort` | >=5.0.0 | Import sorting |
| `flake8` | >=6.0.0 | Linting |
| `mypy` | >=1.0.0 | Type checking |

### Adding New Dependencies

#### 1. Assess the Need
Before adding a new dependency:
- Is it absolutely necessary?
- Can existing functionality be used instead?
- What's the maintenance status?
- What are the security implications?
- How does it affect package size?

#### 2. Choose the Right Dependency
Evaluation criteria:
- **Maintenance**: Active development and updates
- **Security**: No known vulnerabilities
- **License**: Compatible with project license
- **Size**: Reasonable impact on package size
- **Quality**: Good documentation and test coverage

#### 3. Add to Configuration

##### For Core Dependencies:
```bash
# Add to pyproject.toml dependencies array
dependencies = [
    "new-package>=1.0.0",
]

# Or add to requirements.txt
echo "new-package>=1.0.0" >> requirements.txt
```

##### For Development Dependencies:
```bash
# Add to pyproject.toml optional dependencies
[project.optional-dependencies]
dev = [
    "new-dev-package>=1.0.0",
]
```

##### For Node.js Dependencies:
```bash
# Add production dependency
npm install --save package-name

# Add development dependency
npm install --save-dev package-name
```

#### 4. Update Lockfiles
```bash
# Update Python lockfile
uv pip compile pyproject.toml -o requirements.lock

# Update Node.js lockfile
npm install  # Updates package-lock.json automatically
```

#### 5. Test the Addition
```bash
# Create clean environment
python -m venv test-env
source test-env/bin/activate

# Install with new dependency
pip install -e .

# Run tests
pytest tests/
```

---

## Update Procedures

### Python Package Updates

#### 1. Check for Updates
```bash
# Check outdated packages
pip list --outdated

# Or with uv
uv pip list --outdated
```

#### 2. Update Strategies

##### Conservative Updates (Recommended)
Update one package at a time to isolate issues:

```bash
# Update specific package
uv pip install --upgrade package-name

# Test immediately
pytest tests/test_related_functionality.py
```

##### Bulk Updates (Use with Caution)
```bash
# Update all packages
uv pip install --upgrade -r requirements.txt

# Or update all outdated packages
pip list --outdated --format=freeze | grep -v '^\-e' | cut -d = -f 1 | xargs -n1 pip install -U
```

#### 3. Update Process Checklist

- [ ] **Backup Current Environment**
  ```bash
  pip freeze > current-requirements.txt
  cp uv.lock uv.lock.backup
  ```

- [ ] **Review Changelogs**
  - Check release notes for breaking changes
  - Review security updates
  - Identify deprecated features

- [ ] **Create Test Environment**
  ```bash
  python -m venv update-test-env
  source update-test-env/bin/activate
  ```

- [ ] **Perform Updates**
  ```bash
  uv pip install --upgrade package-name
  ```

- [ ] **Run Comprehensive Tests**
  ```bash
  pytest tests/ --cov
  python -m flake8 .
  python -m mypy .
  ```

- [ ] **Test in Staging Environment**
  ```bash
  nomad --health-check
  nomad --config-status
  ```

- [ ] **Update Lockfiles**
  ```bash
  uv pip freeze > requirements.lock
  uv lock
  ```

- [ ] **Update Documentation**
  - Update version numbers in docs
  - Note any breaking changes
  - Update installation instructions if needed

### Node.js Package Updates

#### 1. Check for Updates
```bash
npm outdated
```

#### 2. Update Process
```bash
# Update package.json ranges
npm update

# Update to latest versions (use carefully)
npx npm-check-updates -u
npm install
```

#### 3. Security Updates
```bash
# Check for security vulnerabilities
npm audit

# Fix automatically where possible
npm audit fix

# Fix high-severity issues
npm audit fix --force
```

---

## Version Management

### Semantic Versioning
Nomad follows semantic versioning (SemVer):
- **MAJOR**: Incompatible API changes
- **MINOR**: Backwards-compatible functionality additions
- **PATCH**: Backwards-compatible bug fixes

### Version Pinning Strategies

#### 1. Minimum Version Pinning (Recommended)
```txt
# Allow patch and minor updates
package-name>=1.2.0

# Allow only patch updates
package-name~=1.2.0

# Exact version (use sparingly)
package-name==1.2.0
```

#### 2. Range Specifications
```txt
# Compatible with 1.x.x, but not 2.x.x
package-name>=1.0.0,<2.0.0

# Compatible with specific minor versions
package-name>=1.2.0,<1.3.0
```

#### 3. Development vs Production
```toml
# Production: Conservative pinning
dependencies = [
    "aiohttp>=3.9.0,<4.0.0",
    "openai>=1.35.0,<2.0.0",
]

# Development: More flexible
[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "black>=23.0.0",
]
```

### Version Compatibility Matrix

#### Python Version Support
| Nomad Version | Python 3.8 | Python 3.9 | Python 3.10 | Python 3.11 | Python 3.12 |
|---------------|-------------|-------------|--------------|--------------|--------------|
| 0.1.x | ✅ | ✅ | ✅ | ❌ | ❌ |
| 0.2.x | ✅ | ✅ | ✅ | ✅ | ✅ |
| 0.3.x (planned) | ❌ | ✅ | ✅ | ✅ | ✅ |

#### Dependency Version Compatibility
| Package | Nomad 0.1.x | Nomad 0.2.x | Notes |
|---------|-------------|-------------|-------|
| `aiohttp` | >=3.8.0 | >=3.9.0 | Security updates required |
| `openai` | >=1.0.0 | >=1.35.0 | API changes in 1.35+ |
| `notion-client` | >=2.0.0 | >=2.2.1 | Bug fixes in 2.2.1 |

---

## Security Considerations

### Vulnerability Management

#### 1. Regular Security Scans
```bash
# Check for known vulnerabilities
pip-audit

# Check Node.js vulnerabilities
npm audit

# Use safety for Python
safety check

# Use snyk for comprehensive scanning
snyk test
```

#### 2. Automated Security Updates
Consider using tools like:
- **Dependabot**: Automated dependency updates
- **PyUp**: Python package security monitoring
- **Snyk**: Vulnerability scanning and fixes

#### 3. Security Update Process

##### Critical Security Updates (Immediate)
1. **Assess Impact**: Determine if vulnerability affects Nomad
2. **Test Update**: Quick testing in isolated environment
3. **Deploy Immediately**: Push to production ASAP
4. **Communicate**: Notify users of security update

##### Regular Security Updates (Weekly/Monthly)
1. **Review Vulnerabilities**: Check all dependencies
2. **Plan Updates**: Group related updates
3. **Test Thoroughly**: Full test suite
4. **Deploy with Monitoring**: Monitor for issues

#### 4. Security Best Practices

##### Package Source Verification
```bash
# Verify package integrity
pip install --require-hashes -r requirements.txt

# Use trusted hosts only
pip install --trusted-host pypi.org package-name
```

##### Lock File Management
```bash
# Generate locked requirements
pip-compile requirements.in

# Update locks regularly
pip-compile --upgrade requirements.in
```

##### Environment Isolation
```bash
# Use virtual environments always
python -m venv secure-env
source secure-env/bin/activate

# Use containers for production
docker build -t nomad:secure .
```

---

## Development Dependencies

### Categories of Development Dependencies

#### 1. Testing Framework
```toml
[project.optional-dependencies]
test = [
    "pytest>=7.0.0",
    "pytest-asyncio>=0.21.0",
    "pytest-cov>=4.0.0",
    "pytest-mock>=3.10.0",
    "httpx>=0.24.0",  # For testing HTTP clients
]
```

#### 2. Code Quality Tools
```toml
[project.optional-dependencies]
lint = [
    "black>=23.0.0",
    "isort>=5.0.0",
    "flake8>=6.0.0",
    "mypy>=1.0.0",
    "bandit>=1.7.0",  # Security linting
]
```

#### 3. Documentation Tools
```toml
[project.optional-dependencies]
docs = [
    "mkdocs>=1.4.0",
    "mkdocs-material>=9.0.0",
    "mkdocstrings>=0.20.0",
]
```

#### 4. Development Utilities
```toml
[project.optional-dependencies]
dev = [
    "pre-commit>=3.0.0",
    "tox>=4.0.0",
    "pip-tools>=6.0.0",
    "wheel>=0.40.0",
]
```

### Installing Development Dependencies

#### All Development Dependencies
```bash
# Install all dev dependencies
pip install -e ".[dev,test,lint,docs]"

# Or with uv
uv pip install -e ".[dev,test,lint,docs]"
```

#### Specific Categories
```bash
# Install only testing dependencies
pip install -e ".[test]"

# Install only linting tools
pip install -e ".[lint]"
```

---

## Testing Procedures

### Pre-Update Testing

#### 1. Baseline Tests
```bash
# Run full test suite
pytest tests/ --cov --cov-report=html

# Check code quality
black --check .
isort --check-only .
flake8 .
mypy .

# Security checks
bandit -r .
safety check
```

#### 2. Integration Tests
```bash
# Test API integrations
pytest tests/integration/ -v

# Test with real APIs (if configured)
pytest tests/integration/ --run-integration
```

#### 3. Performance Tests
```bash
# Run performance benchmarks
pytest tests/performance/ --benchmark-only
```

### Post-Update Testing

#### 1. Smoke Tests
```bash
# Quick functionality check
nomad --version
nomad --config-status
nomad --health-check
```

#### 2. Regression Tests
```bash
# Run regression test suite
pytest tests/regression/ -v

# Test backward compatibility
pytest tests/compatibility/ -v
```

#### 3. End-to-End Tests
```bash
# Full workflow tests
pytest tests/e2e/ -v --slow
```

### Automated Testing Pipeline

#### GitHub Actions Example
```yaml
name: Package Update Tests
on:
  pull_request:
    paths:
      - 'requirements.txt'
      - 'pyproject.toml'
      - 'package.json'

jobs:
  test-updates:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [3.8, 3.9, 3.10, 3.11, 3.12]

    steps:
    - uses: actions/checkout@v3
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}

    - name: Install dependencies
      run: |
        pip install uv
        uv pip install -e ".[dev,test]"

    - name: Run tests
      run: |
        pytest tests/ --cov
        black --check .
        mypy .

    - name: Security check
      run: |
        pip-audit
        bandit -r .
```

---

## Rollback Procedures

### When to Rollback

Rollback if you encounter:
- **Critical Functionality Loss**: Core features stop working
- **Security Issues**: New vulnerabilities introduced
- **Performance Degradation**: Significant performance impact
- **Compatibility Issues**: Breaks existing integrations
- **Test Failures**: New test failures that can't be quickly fixed

### Rollback Strategies

#### 1. Quick Rollback (Emergency)
```bash
# Restore from backup
pip install -r current-requirements.txt --force-reinstall

# Or use lockfile
uv pip sync requirements.lock.backup
```

#### 2. Selective Rollback
```bash
# Rollback specific package
pip install package-name==previous-version

# Update lockfile
uv pip freeze > requirements.lock
```

#### 3. Full Environment Rollback
```bash
# Remove current environment
deactivate
rm -rf venv/

# Recreate from backup
python -m venv venv
source venv/bin/activate
pip install -r backup-requirements.txt
```

### Rollback Checklist

- [ ] **Stop Production Services**: Prevent further issues
- [ ] **Identify Problem**: Understand what went wrong
- [ ] **Choose Rollback Strategy**: Quick vs. selective vs. full
- [ ] **Execute Rollback**: Follow chosen strategy
- [ ] **Verify Functionality**: Test that system works
- [ ] **Update Documentation**: Note what happened
- [ ] **Plan Fix**: Schedule proper fix for later

### Rollback Prevention

#### 1. Staged Deployments
```bash
# Test in development
pip install --upgrade package-name
# Run tests, verify functionality

# Deploy to staging
# Full integration testing

# Deploy to production
# Monitor closely
```

#### 2. Feature Flags
```python
# Use feature flags for new functionality
if config.get("enable_new_feature", False):
    # New code using updated package
    pass
else:
    # Fallback to old implementation
    pass
```

#### 3. Blue-Green Deployments
- Maintain two identical production environments
- Deploy updates to inactive environment
- Switch traffic after verification
- Keep old environment for quick rollback

---

## Best Practices

### General Principles

#### 1. Principle of Least Change
- Update one package at a time when possible
- Test each change independently
- Document all changes

#### 2. Defense in Depth
- Use multiple tools (pip-audit, safety, snyk)
- Test at multiple levels (unit, integration, e2e)
- Monitor in production

#### 3. Automation with Human Oversight
- Automate routine tasks
- Require human approval for critical updates
- Log all automated actions

### Package Selection Criteria

#### Must Have
- [ ] **Active Maintenance**: Recent commits and releases
- [ ] **Security Track Record**: No critical unpatched vulnerabilities
- [ ] **License Compatibility**: Compatible with project license
- [ ] **Stable API**: Minimal breaking changes

#### Should Have
- [ ] **Good Documentation**: Clear API docs and examples
- [ ] **Test Coverage**: High test coverage
- [ ] **Community Support**: Active community and contributors
- [ ] **Performance**: Reasonable performance characteristics

#### Nice to Have
- [ ] **Type Hints**: Python type annotations
- [ ] **Async Support**: Async/await compatibility where relevant
- [ ] **CLI Tools**: Command-line utilities
- [ ] **Plugin System**: Extensibility

### Update Scheduling

#### Critical Updates (Immediate)
- Security vulnerabilities
- Critical bug fixes
- Compatibility issues

#### Regular Updates (Monthly)
- Minor version updates
- Performance improvements
- New features

#### Major Updates (Quarterly)
- Major version updates
- Breaking changes
- Architecture changes

### Monitoring and Alerting

#### Package Vulnerability Monitoring
```bash
# Set up automated scans
pip-audit --format=json --output=vulnerabilities.json

# Monitor for new vulnerabilities
safety check --json
```

#### Dependency Freshness
```bash
# Check for outdated packages
pip list --outdated --format=json
```

#### Performance Monitoring
```bash
# Monitor application performance after updates
nomad --health-check
python -m cProfile -o profile.stats your_script.py
```

### Documentation Standards

#### Change Documentation
For each package update, document:
- **What Changed**: Package name and version change
- **Why Changed**: Reason for update (security, features, etc.)
- **Impact Assessment**: What functionality might be affected
- **Testing Done**: What tests were run
- **Rollback Plan**: How to rollback if needed

#### Example Change Log Entry
```markdown
## Package Update: openai 1.35.0 → 1.40.0

**Date**: 2024-01-15
**Type**: Minor version update
**Reason**: New features and bug fixes

### Changes
- Added support for new GPT-4 models
- Improved error handling for rate limits
- Fixed streaming response issues

### Testing
- [x] Unit tests pass
- [x] Integration tests with OpenAI API
- [x] Performance regression tests
- [x] Security scan (no new vulnerabilities)

### Rollback Plan
If issues arise, rollback with:
```bash
pip install openai==1.35.0
```

### Impact
- New GPT-4 models available for use
- Better error messages for users
- No breaking changes to existing functionality
```

---

## Troubleshooting Common Issues

### Dependency Conflicts

#### Problem: Version Conflicts
```
ERROR: pip's dependency resolver does not currently take into account all the packages that are installed.
```

**Solutions**:
1. **Use uv for better resolution**:
   ```bash
   uv pip install package-name
   ```

2. **Create clean environment**:
   ```bash
   python -m venv clean-env
   source clean-env/bin/activate
   pip install -r requirements.txt
   ```

3. **Pin conflicting versions**:
   ```txt
   package-a==1.0.0
   package-b>=2.0.0,<3.0.0
   ```

### Installation Failures

#### Problem: Package Won't Install
**Common causes and solutions**:

1. **Network Issues**:
   ```bash
   pip install --retries 10 --timeout 60 package-name
   ```

2. **Compilation Errors**:
   ```bash
   # Install pre-compiled wheels
   pip install --only-binary=all package-name

   # Install build dependencies
   pip install wheel setuptools
   ```

3. **Permission Issues**:
   ```bash
   pip install --user package-name
   ```

### Performance Issues

#### Problem: Slow Package Installation
**Solutions**:

1. **Use uv instead of pip**:
   ```bash
   uv pip install -r requirements.txt
   ```

2. **Use pip with cache**:
   ```bash
   pip install --cache-dir ~/.pip/cache -r requirements.txt
   ```

3. **Parallel downloads**:
   ```bash
   pip install --upgrade-strategy eager -r requirements.txt
   ```

---

This comprehensive package management guide provides the foundation for maintaining secure, up-to-date, and reliable dependencies in the Nomad project. Regular review and updates of this guide ensure it remains current with best practices and new tools.
