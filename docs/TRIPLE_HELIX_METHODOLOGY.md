# Triple-Helix Testing Methodology for NexaiQ VSAAS

## Overview

The Triple-Helix Testing Methodology is a QA approach for AI-powered Video Surveillance as a Service (VSAAS) platforms. It combines three testing strands that must work together.

## Current Status

| Strand | Progress | Tests |
|--------|----------|-------|
| Software (Web/API) | 🟢 Active | 26 tests passing |
| Hardware | 🟡 Planned | Documentation ready |
| AI/ML | 🟡 Planned | Requirements defined |

---

## The Three Testing Strands

### 1. Hardware Testing Strand

**Focus Areas:**
- Edge boxes (Ubuntu-based customer deployment units)
- Camera integration (Hanwha, i-Pro, Avigilon, Vivotek, Axis, VCA)
- ONVIF protocol compliance and discovery
- GPU performance validation (A-100, A-1000, A-4000)
- Network connectivity and bandwidth optimization
- ZFS RAID storage configuration

**Key Testing Activities:**
- Environmental stress testing (temperature, humidity, power)
- Network latency and throughput validation
- Camera feed stability and quality assessment
- Edge processing capability under load
- Firmware compatibility across camera brands
- RAID failover and recovery testing

**Access Methods:**
- WireGuard VPN for remote access
- TeamViewer for remote desktop
- SSH for command-line testing

**Reference Docs:** See `docs/reference/hardware/`

---

### 2. Software Testing Strand

**Focus Areas:**
- Web applications (SOTERIX platform, Partner Admin Tool)
- Mobile applications (iOS, Android)
- Backend services and APIs
- Cloud infrastructure (Linode, MongoDB)
- Integration with ONVIF protocols

**Key Testing Activities:**
- Functional and regression testing
- Performance testing under varying loads
- Security vulnerability assessment (SQL injection, XSS)
- API endpoint validation
- User interface responsiveness
- Cross-browser compatibility
- Session management and authentication

**Current Implementation:**
- Playwright + Python + pytest
- 16 API smoke tests
- 10 Login UI tests
- Page Object Model pattern
- Multi-environment support (QA, Staging, Prod)

**Reference Docs:** See `docs/SELENIUM_TO_PLAYWRIGHT_MIGRATION.md`

---

### 3. AI/ML Testing Strand

**Focus Areas:**
- Model accuracy and performance metrics
- Real-time inference capabilities
- Data quality and preprocessing validation
- Model drift detection
- Explainability and bias assessment

**Key Testing Activities:**
- Precision/recall validation on live camera feeds
- False positive/negative analysis
- Processing latency measurement
- Model performance under different lighting/environmental conditions
- Data annotation quality verification
- Edge case scenario testing

**Quality Gates:**
- Model accuracy meets baseline metrics
- Inference latency within acceptable limits
- No significant bias detected
- Data quality validation passes

---

## Cross-Strand Integration

The power of Triple-Helix comes from testing across strands:
Camera Feed (Hardware) -> AI Processing (AI) -> UI Display (Software)
↓                        ↓                      ↓
Network Stability      Model Accuracy         User Experience
GPU Utilization        Inference Speed        Response Time

### Integration Test Scenarios

| Scenario | Strands | Test |
|----------|---------|------|
| Live video streaming | HW + SW | Camera -> Edge box -> Web UI |
| AI analytics | HW + AI + SW | Camera -> GPU -> Model -> Alert |
| System under load | All | Multiple cameras + AI + Users |
| Failover | HW + SW | RAID failure -> Recovery -> UI status |

---

## Implementation Phases

### Phase 1: Foundation (COMPLETE) ✅
- [x] Playwright test framework setup
- [x] API smoke tests (16 tests)
- [x] Login UI tests (10 tests)
- [x] Multi-environment configuration
- [x] Session caching and auth handling

### Phase 2: Software Expansion (IN PROGRESS)
- [ ] Views module migration (27 tests)
- [ ] Events module migration (26 tests)
- [ ] Search, Media, Insights modules
- [ ] Admin module tests

### Phase 3: Hardware Integration (PLANNED)
- [ ] Edge box health monitoring tests
- [ ] Camera connectivity validation
- [ ] RAID/storage testing
- [ ] GPU utilization monitoring

### Phase 4: AI Validation (PLANNED)
- [ ] Model accuracy benchmarks
- [ ] Inference performance tests
- [ ] Bias detection testing
- [ ] Drift monitoring

---

## Daily Testing Workflow

### Morning Health Check (30 minutes)
1. Run Playwright smoke suite
2. Check GPU performance metrics
3. Verify camera feed connectivity
4. Review overnight test results

### Feature Testing (4-6 hours)
1. New feature validation across relevant strands
2. Integration testing for recent changes
3. Performance impact assessment
4. Log results in QA Touch

### End-of-Day Regression (2 hours)
1. Run full regression suite
2. Cross-strand impact analysis
3. Document failures with traces/screenshots
4. Set priorities for next day

---

## Weekly Deep Testing

| Day | Focus | Activities |
|-----|-------|------------|
| Monday | Hardware | Stress testing, new camera integration |
| Wednesday | Software | Security scans, load testing, API validation |
| Friday | AI | Model accuracy, bias detection, performance |

---

## Quality Gates

### Release Readiness Checklist

**Hardware Strand:**
- [ ] All supported camera models tested
- [ ] Edge box performance meets baseline
- [ ] Network connectivity stable under stress
- [ ] GPU utilization within acceptable ranges
- [ ] RAID configuration validated

**Software Strand:**
- [ ] All critical user journeys pass Playwright tests
- [ ] API endpoints respond within SLA
- [ ] Security scans pass (no critical vulnerabilities)
- [ ] Cross-browser compatibility validated
- [ ] Mobile and web interfaces functional

**AI Strand:**
- [ ] Model accuracy meets baseline metrics
- [ ] Inference latency within limits
- [ ] No significant bias detected
- [ ] Data quality validation passes

**Integration:**
- [ ] End-to-end customer workflow completes
- [ ] System performs under simulated load
- [ ] Real-time AI processing maintains quality
- [ ] Monitoring and alerting functional

---

## Tools and Infrastructure

### Current Tools
| Purpose | Tool | Status |
|---------|------|--------|
| Web/API Automation | Playwright + pytest | ✅ Active |
| Test Management | QA Touch | ⏳ Pending license |
| Issue Tracking | Jira | ⏳ Setup in progress |
| Monitoring | Grafana + Prometheus | ✅ View access |
| CI/CD | Windows Task Scheduler | ✅ Temporary |

### Future Tools
| Purpose | Tool | Timeline |
|---------|------|----------|
| CI/CD Pipeline | GitHub Actions / Jenkins | Month 3-4 |
| Load Testing | k6 or Locust | Month 4-5 |
| Mobile Testing | Appium | Month 5-6 |
| Security Scanning | TBD | Month 4-5 |

---

## Success Metrics

### Short-Term (Months 1-3)
- 80% of critical workflows automated
- 90% of bugs caught before deployment
- 26 -> 100+ tests automated
- All Selenium tests migrated

### Long-Term (Months 4-12)
- Zero critical bugs in production
- 50% reduction in manual testing time
- Full cross-strand integration testing
- Support for 10x customer load

---

## Related Documents

- [Implementation Roadmap](IMPLEMENTATION_ROADMAP.md)
- [Selenium Migration Status](SELENIUM_TO_PLAYWRIGHT_MIGRATION.md)
- QA Roadmap: `dashboards/soterix-internal-dashboards/docs/QA_ROADMAP.md` (workspace-level)
- [Hardware Reference](reference/hardware/README.md)
- [Original Methodology](reference/archive/Optimized_Triple-Helix_Testing.txt)
