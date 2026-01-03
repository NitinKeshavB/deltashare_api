# Claude Code Documentation

This folder contains comprehensive documentation for the Delta Share API project.

## 📚 Documentation Index

### Core Documentation
- **[CLAUDE.md](./CLAUDE.md)** - Main project overview and development guide
  - Project structure
  - Development commands
  - Architecture patterns
  - Databricks SDK usage

### Deployment & Configuration
- **[AZURE_WEBAPP_CONFIG.md](./AZURE_WEBAPP_CONFIG.md)** - Azure Web App environment variable configuration
  - Required environment variables
  - Configuration methods (Portal, CLI, Bicep)
  - Security best practices
  - Troubleshooting guide

- **[DEPLOYMENT_CHECKLIST.md](./DEPLOYMENT_CHECKLIST.md)** - Step-by-step deployment checklist
  - Pre-deployment preparation
  - Configuration verification
  - Post-deployment testing
  - Common issues and solutions

### Token Management
- **[TOKEN_CACHING_GUIDE.md](./TOKEN_CACHING_GUIDE.md)** - Databricks token caching implementation
  - How token caching works
  - Performance impact (75% faster)
  - Local vs production behavior
  - Troubleshooting

### Testing
- **[TESTING_QUICK_REFERENCE.md](./TESTING_QUICK_REFERENCE.md)** - Quick testing reference
  - Test commands
  - Test structure
  - Common patterns

- **[TEST_SUITE_SUMMARY.md](./TEST_SUITE_SUMMARY.md)** - Comprehensive test suite overview
  - Test organization
  - Coverage details
  - Test fixtures

- **[FIXTURE_ORGANIZATION.md](./FIXTURE_ORGANIZATION.md)** - Test fixture documentation
  - Fixture structure
  - Mock setup
  - Usage examples

### CI/CD
- **[CI_FIX_GUIDE.md](./CI_FIX_GUIDE.md)** - GitHub Actions CI troubleshooting
  - Common CI failures
  - Dependency fixes
  - Workflow examples

### Logging
- **[README_LOGGING.md](./README_LOGGING.md)** - Logging system documentation
  - Azure Blob Storage logging
  - PostgreSQL logging
  - Log configuration

## 🚀 Quick Start

1. **Local Development**
   - Read [CLAUDE.md](./CLAUDE.md) for project overview
   - Run `make install` to set up
   - Run `make test` to verify setup

2. **Azure Deployment**
   - Follow [DEPLOYMENT_CHECKLIST.md](./DEPLOYMENT_CHECKLIST.md)
   - Configure variables per [AZURE_WEBAPP_CONFIG.md](./AZURE_WEBAPP_CONFIG.md)
   - Verify token caching per [TOKEN_CACHING_GUIDE.md](./TOKEN_CACHING_GUIDE.md)

3. **CI/CD Setup**
   - Fix issues using [CI_FIX_GUIDE.md](./CI_FIX_GUIDE.md)
   - Run tests: `bash run.sh test:ci`

## 📋 Key Features Documented

✅ **Environment Configuration** - Complete guide for local and Azure Web App
✅ **Token Caching** - Automatic token management and caching
✅ **Testing Framework** - Comprehensive test suite with 74 tests
✅ **Logging System** - Multi-destination logging (Azure Blob, PostgreSQL)
✅ **CI/CD Integration** - GitHub Actions workflow setup

## 🔧 Maintenance

These documentation files are maintained alongside the codebase and should be updated when:
- New features are added
- Configuration requirements change
- Deployment process is modified
- Testing patterns evolve

## 📝 Recent Updates

- **2026-01-04**: Added token caching implementation and CI fixes
- **2026-01-03**: Initial deployment and configuration guides
- **2026-01-02**: Test suite and logging documentation

---

For questions or issues, refer to the specific documentation file above or check the main [CLAUDE.md](./CLAUDE.md) for project context.
