# Future Roadmap - Soterix QA Automation

## Overview

This document outlines the full scope of QA automation planned for Soterix Systems, extending beyond the current web application testing to cover all platforms and integration points.

---

## Integration Priorities

### 1. QA Touch (Test Management)
**Status:** Waiting for yearly license purchase

**Planned Integration:**
- Test case management and organization
- Test execution tracking
- Requirements traceability
- Defect linking
- Reporting dashboards

**Action Items:**
- [ ] Purchase yearly license
- [ ] Set up project structure matching our test modules
- [ ] Import existing test cases from spreadsheet (519 total)
- [ ] Configure Playwright test result upload
- [ ] Create test execution workflows

### 2. Jira (Issue Tracking)
**Status:** New company-managed instance in test phase

**Planned Integration:**
- Bug tracking linked to test failures
- User story to test case mapping
- Sprint/release test coverage reports
- Automated defect creation from failed tests

**Action Items:**
- [ ] Complete Jira instance setup and testing
- [ ] Define project structure and workflows
- [ ] Configure Playwright-Jira integration
- [ ] Set up automated bug creation on test failure
- [ ] Create dashboards for QA metrics

### 3. CI/CD Pipeline (Future)
**Status:** Planned for when pipeline engineers available

**Target Timeline:** 2-3 months

**Planned Setup:**
- Automated test runs on code push
- Nightly regression runs
- Environment-specific test gates
- Test result reporting to QA Touch/Jira

---

## Testing Scope by Platform

### Web Application Testing (Current Focus)

#### Main SOTERIX Platform
**Status:** In Progress (12% complete)

| Area | Description | Status |
|------|-------------|--------|
| API Testing | REST API smoke and regression | ✅ 16 tests |
| UI - Login | Authentication flows | ✅ 10 tests |
| UI - Views | Video wall, camera playback | 🔄 Next |
| UI - Events | Event management | Planned |
| UI - Search | AI-powered search | Planned |
| UI - Media | Clip management | Planned |
| UI - Admin | User/site management | Planned |
| Video/Streaming | Live video playback testing | Planned |
| AI Model Testing | Analytics accuracy validation | Planned |

#### Partner Admin Tool
**Status:** Not Started

**Access:** ✅ Credentials available for each environment

**Purpose:** Used by System Integrators to manage their customer sites

**Scope:**
- [ ] Partner login and authentication
- [ ] Customer/site management
- [ ] Site provisioning
- [ ] Billing and licensing
- [ ] White-label configuration

---

### Hardware Testing

#### Edge Box Testing (Ubuntu OS)
**Status:** Not Started

**Access:** 
- ✅ WireGuard VPN configured for remote access
- ✅ TeamViewer available for remote desktop

**Scope:**
- [ ] Docker container health checks
- [ ] System performance monitoring
- [ ] RAID configuration validation
- [ ] GPU utilization (A-100, A-1000, A-4000)
- [ ] Network connectivity and bandwidth
- [ ] Firmware compatibility

**Camera Brands to Test:**
- Hanwha
- i-Pro
- Avigilon
- Vivotek
- Axis
- VCA

**Protocols:**
- ONVIF compliance
- Camera discovery
- Stream quality validation

#### Hardware Components
- [ ] Temperature/environmental monitoring
- [ ] Power management
- [ ] Storage health (RAID status)
- [ ] Network interface testing

---

### Cloud Infrastructure Testing

#### Linode
**Status:** Access to request

**Scope:**
- [ ] Instance health monitoring
- [ ] Performance benchmarking
- [ ] Failover testing
- [ ] Scaling validation

#### MongoDB
**Status:** Access to request

**Scope:**
- [ ] Database performance monitoring
- [ ] Query performance testing
- [ ] Replication validation
- [ ] Backup/restore testing

**Current Access:**
- ✅ Grafana dashboards (view-only)

**Access to Request:**
- [ ] Read-only MongoDB access for test data validation
- [ ] Prometheus direct access for custom metric queries
- [ ] Linode console access for instance monitoring during load tests

---

### Mobile Application Testing

#### Current State
- **iOS App:** Fully native, tested manually via TestFlight ✅
- **Android App:** Fully native, tested manually via APK/Play Store internal testing
- **No mobile web version exists**

#### iOS App
**Status:** Manual testing only (automation requires Mac)

**Current Testing:**
- ✅ TestFlight access configured on iOS devices
- Manual testing of each beta build

**For Automation (Future):**
- ⚠️ **Mac computer required** (Apple restriction - no workaround)
- See: [Mac Justification Document](MAC_JUSTIFICATION_FOR_IOS_TESTING.md)
- Tools needed: Xcode, Appium, iOS Simulator or real device

**Test Scope:**
- [ ] Login and authentication
- [ ] Live view functionality
- [ ] Push notifications
- [ ] Offline mode handling
- [ ] Device compatibility matrix

#### Android App
**Status:** Manual testing only

**Current Testing:**
- APK files or Play Store internal testing track

**For Automation:**
- ✅ Can run on Windows/Linux (no special hardware needed)
- Tools: Appium + Android SDK + Emulator or real device

**Test Scope:**
- [ ] Login and authentication
- [ ] Live view functionality
- [ ] Push notifications
- [ ] Offline mode handling
- [ ] Device compatibility matrix

#### Mobile Automation Path Forward

| Phase | Timeline | Scope |
|-------|----------|-------|
| **Now** | Current | Continue manual testing via TestFlight (iOS) and APK (Android) |
| **Short-term** | Month 2-3 | Set up Android automation with Appium (no special hardware) |
| **Medium-term** | Month 4+ | Procure Mac, set up iOS automation with Appium |

**To Request from India Developer:**
- [ ] Documentation on which backend environment the app connects to
- [ ] Instructions for switching environments in the app (if possible)
- [ ] Release notes for each TestFlight/APK build

---

## Triple-Helix Testing Integration

All testing should align with the Triple-Helix methodology:

| Strand | Focus Areas | Tools |
|--------|-------------|-------|
| **Hardware** | Edge boxes, cameras, GPUs, network | SSH utilities, SNMP, custom scripts |
| **Software** | Web UI, APIs, mobile apps | Playwright, pytest, requests |
| **AI** | Model accuracy, inference speed, analytics | Custom validation scripts |

### Cross-Strand Test Scenarios
- Camera feed -> AI processing -> UI display
- Hardware stress -> Software stability
- AI model update -> End-to-end validation

---

## Recommended Additional Testing

### Performance Testing
- [ ] Load testing for concurrent users
- [ ] Stress testing for camera feeds
- [ ] API response time benchmarking
- [ ] Video streaming latency measurement

### Security Testing
- [ ] Authentication bypass attempts (covered partially)
- [ ] API authorization validation
- [ ] Input validation (SQL injection, XSS - covered)
- [ ] Session management testing

### Accessibility Testing
- [ ] WCAG compliance for web UI
- [ ] Screen reader compatibility
- [ ] Keyboard navigation

### Localization Testing
- [ ] Multi-language support (if applicable)
- [ ] Date/time format handling
- [ ] Currency display (if applicable)

---

## Tool Stack Summary

| Purpose | Current | Planned |
|---------|---------|---------|
| Test Automation (Web) | Playwright + pytest | Continue |
| API Testing | requests + pytest | Continue |
| Test Management | Spreadsheet | QA Touch |
| Issue Tracking | - | Jira (company-managed) |
| CI/CD | Windows Task Scheduler | GitHub Actions / Jenkins |
| Monitoring | Grafana (view) | + Prometheus direct access |
| Mobile Testing (Android) | Manual | Appium |
| Mobile Testing (iOS) | TestFlight (manual) | Appium (requires Mac) |
| Performance | - | k6 or Locust |

---

## Timeline Overview

### Month 1-2 (Current)
- Complete web UI migration (Views, Events)
- Set up QA Touch integration
- Configure Jira integration
- Reach 50% Selenium migration

### Month 3-4
- Complete Selenium migration
- Begin hardware testing framework
- Set up CI/CD pipeline
- Set up Android automation with Appium

### Month 5-6
- Cloud infrastructure testing
- Performance testing framework
- Full cross-strand integration
- Partner Admin Tool testing
- Procure Mac for iOS automation

### Month 7+
- iOS automation setup
- New feature coverage
- Advanced AI model testing
- Continuous improvement

---

## Resolved Questions

| Question | Answer |
|----------|--------|
| Pre-Prod URL | In planning, not yet available |
| Hardware Lab Access | ✅ WireGuard VPN + TeamViewer configured |
| Partner Tool Access | ✅ Credentials available for each environment |
| Mobile Apps | Fully native (iOS & Android), no mobile web version |
| iOS Testing | TestFlight available, Mac needed for automation |
| Cloud Access | Grafana dashboards available (view-only) |

## Outstanding Questions

| Question | Action Needed |
|----------|---------------|
| MongoDB access | Request read-only access for test data validation |
| Prometheus access | Request direct access for custom metric queries |
| Linode access | Request console access for instance monitoring |
| Mobile backend | Ask India developer which environment app connects to |
| Environment switching | Ask if app can switch between QA/Stage/Prod |

---

## Related Documents
- [Implementation Roadmap](IMPLEMENTATION_ROADMAP.md)
- [Selenium Migration](SELENIUM_TO_PLAYWRIGHT_MIGRATION.md)
- [ReCAPTCHA Bypass Plan](RECAPTCHA_BYPASS_PLAN.md)
- [Mac Justification for iOS Testing](MAC_JUSTIFICATION_FOR_IOS_TESTING.md)
- [Credentials Setup](CREDENTIALS_SETUP.md)
- [Triple-Helix Methodology](../Optimized_Triple-Helix_Testing_Methodology_for_AI_VSAAS_QA.md) (See <attachments> above for file contents. You may not need to search or read the file again.)
