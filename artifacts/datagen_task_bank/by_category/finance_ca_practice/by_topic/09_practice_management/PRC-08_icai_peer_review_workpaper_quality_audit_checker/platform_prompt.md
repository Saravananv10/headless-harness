# ICAIPeerReviewWorkpaperQuality — ICAI Peer Review Workpaper Quality Audit Checker

## Complexity & fidelity lock (datagen)
- Task ID: **PRC-08**
- Category: **practice_management**
- Complexity band: **hard**
- UI fidelity: HIGH — multi-view dashboard, clean tabular views, clickable action paths
- Anti-stub: FORBIDDEN as DONE: skeleton CRUD, unstyled link farms, claims of features without runnable paths
- **Never** stop for time/turns/“too big”; keep using tools until acceptance criteria pass, then print DONE.
- Match locked stack: language=`python`, ui=`static_html`, persistence=`csv_json`, testing=`smoke_only`, verification=`runtime_pass`.
- Working execution demo required. Direct code execution mandatory (`tool_uses >= 1`).

## 1. Product identity
Build **ICAIPeerReviewWorkpaperQuality** for category `finance_ca_practice`. Seed intent (honor this product, do not genericize away):

> Create a Python tool that audits completed audit files against ICAI Peer Review Board guidelines, verifying presence of mandatory working papers and sign-offs.

Artifact type: `data_pipeline`. Business Domain: `finance_ca_practice`. Delivery: `one_command_cli_or_script`.

## 2. Target users & jobs
- Primary user: Chartered Accountants, Audit Managers, Tax Advisors, and Finance Ops Teams.
- Job: Complete the core financial workflow end-to-end offline using local CSV/JSON datasets with zero cloud dependencies.

## 3. Core entities
1. **FinancialRegister**: Ingested accounting source data (Trial Balance, 26AS, Journal Entries, Bank Statements).
2. **ReconciliationItem**: Primary reconciliation line items matched between books and external statements.
3. **AuditException**: Flagged discrepancies, math errors, odd-hour transactions, or compliance delays.
4. **VerificationReport**: Consolidated summary report containing mathematical invariants and audit findings.

## 4. Major feature areas
- **Data Ingestion**: Robust parsing of source CSV/JSON files with schema validation and regex type checks.
- **Deterministic Calculation Engine**: Execution of accounting formulas (Double-Entry, Tax Slabs, Interest u/s 201(1A)).
- **Anomaly & Exception Flagger**: Deterministic scoring and tagging of high-risk items against ground-truth rules.
- **Report & Artifact Generator**: Output of structured CSV/Markdown/Excel summary reports to `output/`.

## 5. Domain workflows
1. **Ingest Phase**: Load input files from `data/` directory.
2. **Processing Phase**: Execute pandas/python data wrangling and verification algorithms.
3. **Audit & Calculation Phase**: Reconcile balances, compute tax/interest impact, and calculate precision/recall metrics.
4. **Export Phase**: Write clean, validated outputs to `output/` directory.

## 6. Data & persistence
File-based persistence using CSV and JSON files in `data/` and `output/`. State schema auto-created on startup.

## 7. Quality, security, reliability
- Offline-first execution.
- Mandatory zero-mental-math policy: All figures computed via Python code execution.
- Deterministic output generation with zero-tool rejection quality gate.

## 8. Acceptance criteria
- [ ] Program boots and runs via documented command
- [ ] Source data from `data/` parsed cleanly without runtime exceptions
- [ ] Mathematical invariants (Double-Entry balance, TDS rates, Tax slabs) verified
- [ ] Output artifacts written to `output/` directory
- [ ] Execution completes with exit code 0 (`RUNTIME_CHECK: PASS`)

---

## Category Template Guidelines
# Category template: Finance / CA Practice

Family shape for finance tools used by chartered accountancy firms and finance teams
that ingest trial balances, TDS certificates, journal entries, bank statements,
compliance calendars, and payment logs to perform audits, reconciliations, forensic
analytics, and compliance tracking.

## Product family intent

A CA firm or finance team uploads accounting data exports. The system reconciles
TDS entries, tests journal entries for anomalies, reconciles bank statements,
tracks compliance deadlines, and produces actionable outputs: reconciliation
reports, exception lists, audit plans, forensic findings, and advisory memos.

## Identity & positioning (invent uniquely)

- Product name and finance focus (TDS reconciler, audit planner, forensic analyzer)
- Operational tone (strict auditor, compliance advisor, analytical reviewer)
- Primary insight (TDS leakage, audit risk, bookkeeping accuracy, fraud detection)
- One twist (vendor-employee linkage detection, automated materiality setting, compliance countdown)

## Required capability areas

### Data Ingestion
- Parse CSV/Excel for trial balance, TDS certificates (26AS), TDS register
- Parse journal entries, bank statements, invoice/payment registers
- Load vendor and employee master data
- Validate schemas and data types

### TDS Reconciliation
- Match 26AS entries with books by deductor, section, quarter
- Identify amount mismatches and missing entries
- Cross-reference challan deposits
- Calculate interest liability for late deposits

### Audit & Analytics
- Trial balance variance analysis (current vs prior year)
- Materiality computation (planning and performance)
- Journal entry anomaly detection (round sums, odd hours, period-end clusters)
- User-specific pattern analysis

### Bank Reconciliation
- Match bank transactions against ledger entries
- Identify uncleared items beyond threshold
- Draft adjustment entries
- Generate MIS pack with commentary

### Compliance Tracking
- ROC/MCA filing calendar management
- Deadline monitoring and escalation
- Filing status reporting

### Forensic Analytics
- Duplicate invoice detection
- Vendor-employee linkage analysis (shared bank accounts)
- Round-sum and weekend-approval pattern detection
- Anomaly scoring and report drafting

## Data & persistence

Entities: Account, TDSEntry, JournalEntry, BankTransaction, Invoice, Payment,
Vendor, Employee, ComplianceFiling, Finding.
Local file-based storage (CSV/JSON). All input under configurable data directory.

## Quality & reliability

- TDS matching must be exact on key fields
- Anomaly detection rules must be deterministic and auditable
- Bank reconciliation must balance
- Reports must be internally consistent

## Acceptance criteria checklist (customize)

- [ ] Data files parsed correctly
- [ ] TDS reconciliation identifies mismatches
- [ ] Journal entry testing flags anomalies
- [ ] Bank reconciliation identifies uncleared items
- [ ] Reports generated in output directory
- [ ] README documents usage

## Variation axes

TDS vs audit focus · forensic depth · compliance framework scope ·
MIS format (markdown vs Excel) · single vs multi-entity · materiality algorithm ·
anomaly scoring method · report format

## Anti-clone rules

Specialize the finance domain, reconciliation logic, and output format.
Vary the primary use case emphasis, anomaly detection depth, and reporting style.

