"""Generate artifacts/datagen_task_bank — 10 seeds × 13 forge categories.

Excludes already-completed Chakra/harness runs. Archive prompts that were never
implemented are reused; remaining slots are new seeds with dimension hints.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "datagen_task_bank"

# Themes already built in this workspace — do not re-queue.
SKIP_THEMES = {
    "whiteboard",
    "tidewatch",
    "tower defense",
    "palletlens",
    "image classification api",  # PalletLens seed
    "snake",
    "viper trace",
    "smart home",
    "social media platform",
    "gaming platform",
    "blogging platform",
    "django blog",
    "ecom_test",
    "flask todo",
    "taskflow",
    "reviewhub",
    "full-stack web application",  # polluted harness client/server demo
}

# 10 tasks per category: (title, seed, dim_hints, source)
# dimension hints are targets for later forge/LLM expansion — not final scores.
TASKS: dict[str, list[dict]] = {
    "collaborative_realtime": [
        {
            "title": "Slack-style team chat",
            "seed": "Build a Slack-style team chat application with channels, private messaging, notifications, and file sharing.",
            "source": "archive:bonus",
            "dimensions_hint": {
                "complexity": "hard",
                "value": "hard",
                "language_runtime": "typescript",
                "artifact_type": "web_fullstack",
                "task_family": "coding_implement",
                "business_domain": "productivity_collab",
                "modality": "text_code",
                "verification_mode": "smoke_run",
                "agent_topology": "subagent_spawns",
            },
        },
        {
            "title": "Multiplayer kanban board live sync",
            "seed": "Create a multiplayer kanban board where cards and columns sync in real time across users with presence indicators, conflict-safe moves, and room-based boards.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "hard",
                "value": "hard",
                "language_runtime": "typescript",
                "artifact_type": "web_fullstack",
                "task_family": "coding_implement",
                "business_domain": "productivity_collab",
            },
        },
        {
            "title": "Pair programming shared editor",
            "seed": "Build a pair-programming web app with a shared code editor, cursors for each user, chat sidebar, and session links. Use WebSockets for sync.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "hard",
                "value": "medium",
                "language_runtime": "javascript",
                "artifact_type": "web_fullstack",
                "task_family": "coding_implement",
                "business_domain": "education",
            },
        },
        {
            "title": "Live auction room",
            "seed": "Create a real-time auction room platform: users join rooms, place bids, see live bid feed and countdown timers, and get notified when outbid.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "medium",
                "value": "hard",
                "language_runtime": "python",
                "artifact_type": "web_fullstack",
                "task_family": "coding_implement",
                "business_domain": "ecommerce",
            },
        },
        {
            "title": "Classroom quiz live leaderboard",
            "seed": "Build a live classroom quiz app where a teacher pushes questions and students answer in real time with a running leaderboard.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "medium",
                "value": "medium",
                "language_runtime": "typescript",
                "artifact_type": "web_fullstack",
                "task_family": "coding_implement",
                "business_domain": "education",
            },
        },
        {
            "title": "Collaborative markdown notes",
            "seed": "Create a collaborative markdown notes app with rooms, live caret presence, version history snapshots, and export to Markdown/HTML.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "medium",
                "value": "medium",
                "language_runtime": "typescript",
                "artifact_type": "web_fullstack",
                "task_family": "coding_implement",
                "business_domain": "productivity_collab",
            },
        },
        {
            "title": "Ops war-room incident chat",
            "seed": "Build an incident war-room chat with channels per incident, @mentions, severity tags, and a timeline of status updates synced live.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "medium",
                "value": "hard",
                "language_runtime": "go",
                "artifact_type": "backend_api",
                "task_family": "coding_implement",
                "business_domain": "devops_platform",
            },
        },
        {
            "title": "Shared music listening room",
            "seed": "Create a synchronized listening room: queue tracks, play/pause sync across clients, chat, and host controls.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "medium",
                "value": "medium",
                "language_runtime": "javascript",
                "artifact_type": "web_fullstack",
                "task_family": "coding_implement",
                "business_domain": "media_cms",
            },
        },
        {
            "title": "Live CSV co-editing sheet",
            "seed": "Build a lightweight collaborative spreadsheet for CSV data with cell editing, live sync, and conflict highlighting (not Excel-plugin).",
            "source": "original",
            "dimensions_hint": {
                "complexity": "hard",
                "value": "hard",
                "language_runtime": "typescript",
                "artifact_type": "web_fullstack",
                "task_family": "coding_implement",
                "business_domain": "data_analytics",
                "modality": "tabular_excel",
            },
        },
        {
            "title": "Remote design critique board",
            "seed": "Create a real-time design critique board: upload images, pin comments with coordinates, resolve threads, and show live viewers.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "low",
                "value": "medium",
                "language_runtime": "python",
                "artifact_type": "web_fullstack",
                "task_family": "coding_implement",
                "business_domain": "media_cms",
            },
        },
    ],
    "storage_files": [
        {
            "title": "Mini cloud storage platform",
            "seed": "Create a cloud storage web application using React, Node.js, Express, and MongoDB. Users should be able to register, log in, upload files, organize them into folders, rename, move, delete, search, and download files. Implement JWT-based authentication, file size validation, storage usage statistics, and a clean dashboard.",
            "source": "archive:2",
            "dimensions_hint": {
                "complexity": "hard",
                "value": "hard",
                "language_runtime": "javascript",
                "artifact_type": "web_fullstack",
                "task_family": "coding_implement",
                "business_domain": "general_utilities",
            },
        },
        {
            "title": "File sharing platform",
            "seed": "Create a File Sharing Platform in Python: users upload files, get shareable links with optional expiry and password, track download counts, and manage their uploads via a simple web UI.",
            "source": "archive:python_7",
            "dimensions_hint": {
                "complexity": "medium",
                "value": "medium",
                "language_runtime": "python",
                "artifact_type": "web_fullstack",
                "task_family": "coding_implement",
                "business_domain": "general_utilities",
            },
        },
        {
            "title": "Team document vault with preview",
            "seed": "Build a team document vault with folder ACLs, text/PDF preview, upload quotas per team, and audit logs of downloads.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "hard",
                "value": "hard",
                "language_runtime": "typescript",
                "artifact_type": "web_fullstack",
                "task_family": "coding_implement",
                "business_domain": "productivity_collab",
            },
        },
        {
            "title": "Media library with tags",
            "seed": "Create a media library service for images and videos: upload, tag, search, thumbnail generation stubs, and collections.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "medium",
                "value": "medium",
                "language_runtime": "python",
                "artifact_type": "backend_api",
                "task_family": "coding_implement",
                "business_domain": "media_cms",
            },
        },
        {
            "title": "S3-like local object store CLI",
            "seed": "Implement a local S3-like object store CLI and HTTP API: buckets, put/get/list/delete objects, and simple versioning.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "medium",
                "value": "hard",
                "language_runtime": "go",
                "artifact_type": "cli_tool",
                "task_family": "coding_implement",
                "business_domain": "devops_platform",
            },
        },
        {
            "title": "Encrypted file dropbox",
            "seed": "Build an encrypted file drop service: client-side or server-side encryption, one-time download links, and expiry.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "medium",
                "value": "hard",
                "language_runtime": "rust",
                "artifact_type": "backend_api",
                "task_family": "coding_implement",
                "business_domain": "security_privacy",
            },
        },
        {
            "title": "Lab dataset repository",
            "seed": "Create a research dataset repository: upload zipped datasets, metadata forms, license tags, and download permissions by role.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "medium",
                "value": "medium",
                "language_runtime": "python",
                "artifact_type": "web_fullstack",
                "task_family": "coding_implement",
                "business_domain": "data_analytics",
            },
        },
        {
            "title": "Receipt image archive",
            "seed": "Build a receipt/image archive with folders by month, OCR-ready file naming, search by filename/tags, and bulk export.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "low",
                "value": "medium",
                "language_runtime": "typescript",
                "artifact_type": "web_fullstack",
                "task_family": "coding_implement",
                "business_domain": "finance_fintech",
            },
        },
        {
            "title": "CAD drawing document locker",
            "seed": "Create a document locker for engineering drawings: check-in/check-out, revision numbers, and lock ownership.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "hard",
                "value": "medium",
                "language_runtime": "java",
                "artifact_type": "web_fullstack",
                "task_family": "coding_implement",
                "business_domain": "logistics_ops",
            },
        },
        {
            "title": "Excel workbook drop zone",
            "seed": "Build a small service that accepts Excel/CSV uploads, validates sheets, stores them, and lists workbook metadata (sheet names, row counts) without requiring MS Office installed.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "low",
                "value": "medium",
                "language_runtime": "excel_office",
                "artifact_type": "spreadsheet_workbook",
                "task_family": "spreadsheet_excel",
                "business_domain": "data_analytics",
                "modality": "tabular_excel",
            },
        },
    ],
    "iot_automation": [
        {
            "title": "Greenhouse sensor automation console",
            "seed": "Build a greenhouse IoT automation console: simulate temperature/humidity/soil sensors, set thresholds, trigger watering/fan actuators, show history charts, and schedule rules.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "medium",
                "value": "hard",
                "language_runtime": "python",
                "artifact_type": "web_fullstack",
                "task_family": "coding_implement",
                "business_domain": "iot_automation",
            },
        },
        {
            "title": "Factory machine status board",
            "seed": "Create a factory machine status board with simulated PLC devices, downtime reasons, OEE-style metrics, and operator acknowledgements.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "hard",
                "value": "hard",
                "language_runtime": "typescript",
                "artifact_type": "web_fullstack",
                "task_family": "coding_implement",
                "business_domain": "iot_automation",
            },
        },
        {
            "title": "Fleet GPS tracker simulator",
            "seed": "Build a vehicle fleet tracker simulator: devices publish GPS points, map/list views, geofence alerts, and trip history.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "medium",
                "value": "medium",
                "language_runtime": "javascript",
                "artifact_type": "web_fullstack",
                "task_family": "coding_implement",
                "business_domain": "logistics_ops",
            },
        },
        {
            "title": "Aquarium controller dashboard",
            "seed": "Create an aquarium controller dashboard: light schedules, temperature alerts, dosing reminders, and device online/offline state.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "low",
                "value": "medium",
                "language_runtime": "python",
                "artifact_type": "web_fullstack",
                "task_family": "coding_implement",
                "business_domain": "iot_automation",
            },
        },
        {
            "title": "Building HVAC zone manager",
            "seed": "Build an HVAC zone manager: multiple zones with setpoints, schedules, occupancy modes, and energy usage history stubs.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "medium",
                "value": "medium",
                "language_runtime": "csharp",
                "artifact_type": "web_fullstack",
                "task_family": "coding_implement",
                "business_domain": "iot_automation",
            },
        },
        {
            "title": "MQTT device playground",
            "seed": "Create an MQTT device playground UI + broker stub: subscribe/publish topics, device registry, and rule: if topic X then command Y.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "medium",
                "value": "hard",
                "language_runtime": "go",
                "artifact_type": "backend_api",
                "task_family": "coding_implement",
                "business_domain": "iot_automation",
            },
        },
        {
            "title": "Smart irrigation planner",
            "seed": "Build a smart irrigation planner: zones, soil moisture simulation, weather stub, watering schedules, and manual override.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "medium",
                "value": "medium",
                "language_runtime": "python",
                "artifact_type": "web_fullstack",
                "task_family": "coding_implement",
                "business_domain": "iot_automation",
            },
        },
        {
            "title": "Lab instrument rack monitor",
            "seed": "Create a lab instrument rack monitor: power draw simulation, over-temp alarms, maintenance tickets, and CSV export of readings.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "low",
                "value": "medium",
                "language_runtime": "typescript",
                "artifact_type": "web_fullstack",
                "task_family": "coding_implement",
                "business_domain": "healthcare",
            },
        },
        {
            "title": "Home energy meter dashboard",
            "seed": "Build a home energy meter dashboard with simulated circuits, daily kWh charts, peak alerts, and appliance grouping.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "medium",
                "value": "medium",
                "language_runtime": "javascript",
                "artifact_type": "web_fullstack",
                "task_family": "data_visualization",
                "business_domain": "iot_automation",
            },
        },
        {
            "title": "Parking lot occupancy sensors",
            "seed": "Create a parking lot occupancy system: bay sensors, live map, free-bay counts, and reservation windows.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "low",
                "value": "low",
                "language_runtime": "python",
                "artifact_type": "web_fullstack",
                "task_family": "coding_implement",
                "business_domain": "logistics_ops",
            },
        },
    ],
    "ai_ml": [
        {
            "title": "AI Resume Analyzer",
            "seed": "Create a resume analysis web application using React, FastAPI, and a pre-trained NLP model from Hugging Face Transformers. Users should be able to upload PDF or DOCX resumes, extract structured information, identify skills, estimate experience level, and compare the resume against a provided job description. Display skill gaps, matching percentage, keyword analysis, and recommendations through an intuitive dashboard.",
            "source": "archive:4",
            "dimensions_hint": {
                "complexity": "hard",
                "value": "hard",
                "language_runtime": "python",
                "artifact_type": "web_fullstack",
                "task_family": "ml_inference_eval",
                "business_domain": "data_analytics",
            },
        },
        {
            "title": "ML experiment tracking (MLflow-like)",
            "seed": "Build a machine learning experiment tracking platform similar to MLflow with experiment comparison, metric visualization, artifact storage, and REST APIs.",
            "source": "archive:bonus",
            "dimensions_hint": {
                "complexity": "hard",
                "value": "hard",
                "language_runtime": "python",
                "artifact_type": "web_fullstack",
                "task_family": "ml_inference_eval",
                "business_domain": "data_analytics",
            },
        },
        {
            "title": "Automated resume screening system",
            "seed": "Create an Automated Resume Screening System in Python that scores resumes against a job description using keyword/skill heuristics or a small local model, with a review queue UI.",
            "source": "archive:python_15",
            "dimensions_hint": {
                "complexity": "medium",
                "value": "medium",
                "language_runtime": "python",
                "artifact_type": "web_fullstack",
                "task_family": "ml_inference_eval",
                "business_domain": "data_analytics",
            },
        },
        {
            "title": "AI document assistant",
            "seed": "Build an AI Document Assistant: upload text/PDF, chunk and index locally, answer questions with citations from retrieved chunks (stub LLM OK if labeled).",
            "source": "archive:python_13",
            "dimensions_hint": {
                "complexity": "hard",
                "value": "hard",
                "language_runtime": "python",
                "artifact_type": "web_fullstack",
                "task_family": "ml_inference_eval",
                "business_domain": "productivity_collab",
            },
        },
        {
            "title": "Sentiment triage inbox",
            "seed": "Create a support inbox that classifies message sentiment/urgency with a small local model or lexicon baseline and routes tickets to queues.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "medium",
                "value": "medium",
                "language_runtime": "python",
                "artifact_type": "backend_api",
                "task_family": "ml_inference_eval",
                "business_domain": "social_comms",
            },
        },
        {
            "title": "Tabular churn predictor demo",
            "seed": "Build a churn prediction demo: upload CSV, train a simple sklearn model, show feature importances, and predict on new rows.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "medium",
                "value": "medium",
                "language_runtime": "python",
                "artifact_type": "notebook_analysis",
                "task_family": "data_wrangling",
                "business_domain": "finance_fintech",
                "modality": "tabular_excel",
            },
        },
        {
            "title": "Embedding search for FAQs",
            "seed": "Create an FAQ semantic search API using local embeddings (or TF-IDF fallback), with admin CRUD for FAQ entries and ranked answers.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "medium",
                "value": "hard",
                "language_runtime": "python",
                "artifact_type": "backend_api",
                "task_family": "ml_inference_eval",
                "business_domain": "general_utilities",
            },
        },
        {
            "title": "OCR receipt field extractor",
            "seed": "Build a receipt field extractor: accept images, stub OCR to text if needed, parse merchant/date/total with rules, and return structured JSON + UI review.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "medium",
                "value": "medium",
                "language_runtime": "python",
                "artifact_type": "web_fullstack",
                "task_family": "ml_inference_eval",
                "business_domain": "finance_fintech",
                "modality": "image_vision",
            },
        },
        {
            "title": "Toxicity filter microservice",
            "seed": "Implement a toxicity/profanity filter microservice with batch and streaming endpoints, allowlists, and unit tests on fixtures.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "low",
                "value": "medium",
                "language_runtime": "go",
                "artifact_type": "backend_api",
                "task_family": "ml_inference_eval",
                "business_domain": "security_privacy",
            },
        },
        {
            "title": "Time-series anomaly flagger",
            "seed": "Create a time-series anomaly flagger: ingest metric CSV, detect spikes with z-score/IQR, plot anomalies, and export flagged windows.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "low",
                "value": "medium",
                "language_runtime": "python",
                "artifact_type": "cli_tool",
                "task_family": "data_visualization",
                "business_domain": "devops_platform",
            },
        },
    ],
    "cms_content": [
        {
            "title": "Digital library management system",
            "seed": "Create a complete library management system using Django. The application should support librarian and student accounts, book catalog management, borrowing and returning books, overdue tracking, reservation queues, notifications, search with multiple filters, and borrowing history. Include authentication, role-based permissions, SQLite database support, and automated unit tests covering the core workflows.",
            "source": "archive:5",
            "dimensions_hint": {
                "complexity": "hard",
                "value": "hard",
                "language_runtime": "python",
                "artifact_type": "web_fullstack",
                "task_family": "coding_implement",
                "business_domain": "education",
            },
        },
        {
            "title": "Notes and knowledge base",
            "seed": "Create a Notes & Knowledge Base app in Python with nested pages, tags, full-text search, and markdown rendering.",
            "source": "archive:python_8",
            "dimensions_hint": {
                "complexity": "medium",
                "value": "medium",
                "language_runtime": "python",
                "artifact_type": "web_fullstack",
                "task_family": "coding_implement",
                "business_domain": "productivity_collab",
            },
        },
        {
            "title": "University course registration portal",
            "seed": "Build a University Course Registration Portal: course catalog, student enrollment, waitlists, conflicts detection, and admin overrides.",
            "source": "archive:python_11",
            "dimensions_hint": {
                "complexity": "hard",
                "value": "medium",
                "language_runtime": "python",
                "artifact_type": "web_fullstack",
                "task_family": "coding_implement",
                "business_domain": "education",
            },
        },
        {
            "title": "Magazine CMS with issues",
            "seed": "Create a magazine CMS: issues, articles, authors, draft/publish workflow, and public reading site.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "medium",
                "value": "medium",
                "language_runtime": "typescript",
                "artifact_type": "web_fullstack",
                "task_family": "coding_implement",
                "business_domain": "media_cms",
            },
        },
        {
            "title": "Podcast episode CMS",
            "seed": "Build a podcast CMS for episodes, show notes, RSS feed generation, and guest profiles.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "medium",
                "value": "medium",
                "language_runtime": "javascript",
                "artifact_type": "web_fullstack",
                "task_family": "coding_implement",
                "business_domain": "media_cms",
            },
        },
        {
            "title": "Internal wiki with approvals",
            "seed": "Create an internal company wiki with page hierarchy, edit approvals, and change history diffs.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "medium",
                "value": "hard",
                "language_runtime": "java",
                "artifact_type": "web_fullstack",
                "task_family": "coding_implement",
                "business_domain": "productivity_collab",
            },
        },
        {
            "title": "Event listing & RSVP site",
            "seed": "Build an event listing CMS with RSVPs, capacity limits, calendar view, and organizer dashboards.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "low",
                "value": "medium",
                "language_runtime": "typescript",
                "artifact_type": "web_fullstack",
                "task_family": "coding_implement",
                "business_domain": "media_cms",
            },
        },
        {
            "title": "Recipe publisher",
            "seed": "Create a recipe publisher CMS: ingredients, steps, tags, nutrition fields, and public browse/search.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "low",
                "value": "low",
                "language_runtime": "python",
                "artifact_type": "web_fullstack",
                "task_family": "coding_implement",
                "business_domain": "media_cms",
            },
        },
        {
            "title": "Newsroom editorial desk",
            "seed": "Build a newsroom desk: story assignments, statuses (pitch→edit→publish), embargo times, and role-based access.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "hard",
                "value": "hard",
                "language_runtime": "csharp",
                "artifact_type": "web_fullstack",
                "task_family": "coding_implement",
                "business_domain": "media_cms",
            },
        },
        {
            "title": "Documentation portal versioned",
            "seed": "Create a versioned docs portal (v1/v2), markdown pages, sidebar nav, and search across versions.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "medium",
                "value": "medium",
                "language_runtime": "go",
                "artifact_type": "web_fullstack",
                "task_family": "documentation",
                "business_domain": "devops_platform",
            },
        },
    ],
    "security_privacy": [
        {
            "title": "Secure password manager",
            "seed": "Create a desktop password manager using Python and PySide6 (Qt). Users should be able to create encrypted password vaults protected by a master password. Implement AES encryption, password generation, categories, search, clipboard copying with automatic clearing, password strength indicators, and secure import/export functionality. Include proper exception handling and unit tests for the encryption logic.",
            "source": "archive:6",
            "dimensions_hint": {
                "complexity": "hard",
                "value": "hard",
                "language_runtime": "python",
                "artifact_type": "desktop_app",
                "task_family": "coding_implement",
                "business_domain": "security_privacy",
            },
        },
        {
            "title": "Secrets vault API",
            "seed": "Build a secrets vault HTTP API: store sealed secrets, role-based read, audit log, and rotation metadata (no plaintext at rest).",
            "source": "original",
            "dimensions_hint": {
                "complexity": "hard",
                "value": "hard",
                "language_runtime": "go",
                "artifact_type": "backend_api",
                "task_family": "security_audit",
                "business_domain": "security_privacy",
            },
        },
        {
            "title": "2FA login playground",
            "seed": "Create an auth playground with password login, TOTP 2FA enrollment, backup codes, and session management.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "medium",
                "value": "hard",
                "language_runtime": "typescript",
                "artifact_type": "web_fullstack",
                "task_family": "coding_implement",
                "business_domain": "security_privacy",
            },
        },
        {
            "title": "PII redaction CLI",
            "seed": "Implement a PII redaction CLI that scans text/CSV for emails/phones/SSNs and writes redacted copies with a report.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "low",
                "value": "medium",
                "language_runtime": "python",
                "artifact_type": "cli_tool",
                "task_family": "security_audit",
                "business_domain": "legal_compliance",
            },
        },
        {
            "title": "Permission policy tester",
            "seed": "Build a RBAC/ABAC policy tester: define roles/permissions, evaluate access queries, and show allow/deny with reasons.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "medium",
                "value": "medium",
                "language_runtime": "java",
                "artifact_type": "cli_tool",
                "task_family": "security_audit",
                "business_domain": "security_privacy",
            },
        },
        {
            "title": "JWT key rotation lab",
            "seed": "Create a JWT auth service demo with key rotation, JWKS endpoint, and middleware verification tests.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "medium",
                "value": "hard",
                "language_runtime": "rust",
                "artifact_type": "backend_api",
                "task_family": "coding_implement",
                "business_domain": "security_privacy",
            },
        },
        {
            "title": "Secure file shredder utility",
            "seed": "Build a secure delete utility that overwrites files before unlink and logs operations (cross-platform best-effort).",
            "source": "original",
            "dimensions_hint": {
                "complexity": "low",
                "value": "low",
                "language_runtime": "cpp",
                "artifact_type": "cli_tool",
                "task_family": "coding_implement",
                "business_domain": "security_privacy",
            },
        },
        {
            "title": "Consent and cookie preference center",
            "seed": "Create a consent preference center UI + API: categories of tracking, versioned policies, and user consent records.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "low",
                "value": "medium",
                "language_runtime": "javascript",
                "artifact_type": "web_fullstack",
                "task_family": "coding_implement",
                "business_domain": "legal_compliance",
            },
        },
        {
            "title": "API abuse rate-limit gateway",
            "seed": "Build a rate-limit gateway middleware/service with token buckets per API key, 429 responses, and metrics.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "medium",
                "value": "medium",
                "language_runtime": "go",
                "artifact_type": "backend_api",
                "task_family": "coding_implement",
                "business_domain": "devops_platform",
            },
        },
        {
            "title": "Certificate expiry monitor",
            "seed": "Create a TLS certificate expiry monitor: check hosts, store notAfter dates, alert when within N days, simple dashboard.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "low",
                "value": "medium",
                "language_runtime": "python",
                "artifact_type": "web_fullstack",
                "task_family": "coding_implement",
                "business_domain": "security_privacy",
            },
        },
    ],
    "ecommerce": [
        {
            "title": "E-commerce inventory and orders",
            "seed": "Create a full-stack inventory management system using React, Node.js, Express, PostgreSQL, and Prisma. Administrators should be able to manage products, categories, suppliers, inventory levels, purchase orders, and customer orders. Include dashboards with analytics, low-stock alerts, pagination, filtering, authentication, and REST APIs with proper validation. Write automated backend tests for critical endpoints.",
            "source": "archive:7",
            "dimensions_hint": {
                "complexity": "hard",
                "value": "hard",
                "language_runtime": "typescript",
                "artifact_type": "web_fullstack",
                "task_family": "coding_implement",
                "business_domain": "ecommerce",
            },
        },
        {
            "title": "Restaurant ordering system",
            "seed": "Create a Restaurant Ordering System in Python: menu, cart, order statuses, kitchen view, and basic payments stub.",
            "source": "archive:python_5",
            "dimensions_hint": {
                "complexity": "medium",
                "value": "medium",
                "language_runtime": "python",
                "artifact_type": "web_fullstack",
                "task_family": "coding_implement",
                "business_domain": "ecommerce",
            },
        },
        {
            "title": "Inventory management system",
            "seed": "Create an Inventory Management System in Python for SKUs, stock adjustments, suppliers, and low-stock reports.",
            "source": "archive:python_10",
            "dimensions_hint": {
                "complexity": "medium",
                "value": "medium",
                "language_runtime": "python",
                "artifact_type": "web_fullstack",
                "task_family": "coding_implement",
                "business_domain": "ecommerce",
            },
        },
        {
            "title": "Bike shop merchant catalog",
            "seed": "Build a bike shop merchant catalog with variants (size/color), inventory counts, and checkout cart (no payment processor required).",
            "source": "original",
            "dimensions_hint": {
                "complexity": "medium",
                "value": "medium",
                "language_runtime": "javascript",
                "artifact_type": "web_fullstack",
                "task_family": "coding_implement",
                "business_domain": "ecommerce",
            },
        },
        {
            "title": "Subscription box admin",
            "seed": "Create a subscription-box admin: plans, subscriber list, skip/pause months, and fulfillment export CSV.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "medium",
                "value": "hard",
                "language_runtime": "typescript",
                "artifact_type": "web_fullstack",
                "task_family": "coding_implement",
                "business_domain": "ecommerce",
            },
        },
        {
            "title": "Marketplace listings for crafts",
            "seed": "Build a craft marketplace: seller listings, buyer search/filters, orders, and simple ratings.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "hard",
                "value": "hard",
                "language_runtime": "python",
                "artifact_type": "web_fullstack",
                "task_family": "coding_implement",
                "business_domain": "ecommerce",
            },
        },
        {
            "title": "Coupon and promo engine",
            "seed": "Implement a coupon engine API: percent/fixed discounts, min cart, expiry, stacking rules, and unit tests.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "medium",
                "value": "hard",
                "language_runtime": "java",
                "artifact_type": "backend_api",
                "task_family": "coding_implement",
                "business_domain": "ecommerce",
            },
        },
        {
            "title": "Returns and RMA portal",
            "seed": "Create a returns/RMA portal: request return, reasons, approval workflow, and refund status tracking.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "medium",
                "value": "medium",
                "language_runtime": "csharp",
                "artifact_type": "web_fullstack",
                "task_family": "coding_implement",
                "business_domain": "ecommerce",
            },
        },
        {
            "title": "Wholesale price list Excel sync",
            "seed": "Build a wholesale price-list tool that imports/exports Excel price sheets and applies tier pricing to an in-app catalog.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "low",
                "value": "medium",
                "language_runtime": "excel_office",
                "artifact_type": "spreadsheet_workbook",
                "task_family": "spreadsheet_excel",
                "business_domain": "ecommerce",
                "modality": "tabular_excel",
            },
        },
        {
            "title": "POS lite for cafe",
            "seed": "Create a cafe POS lite: product buttons, ticket, tax, cash/card stub tender, and daily sales report.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "low",
                "value": "medium",
                "language_runtime": "typescript",
                "artifact_type": "web_fullstack",
                "task_family": "coding_implement",
                "business_domain": "ecommerce",
            },
        },
    ],
    "monitoring_ops": [
        {
            "title": "Network monitoring dashboard",
            "seed": "Create a network monitoring application using Python and FastAPI. The backend should periodically ping configurable hosts, measure response times, detect outages, and expose REST APIs for historical metrics. Build a React dashboard that visualizes uptime percentages, latency graphs, downtime history, and device health using interactive charts. Support configurable monitoring intervals and persistent storage using SQLite.",
            "source": "archive:8",
            "dimensions_hint": {
                "complexity": "hard",
                "value": "hard",
                "language_runtime": "python",
                "artifact_type": "web_fullstack",
                "task_family": "coding_implement",
                "business_domain": "devops_platform",
            },
        },
        {
            "title": "Service health board",
            "seed": "Build a service health board aggregating synthetic checks, dependency status, and a public status page with incident history.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "medium",
                "value": "hard",
                "language_runtime": "typescript",
                "artifact_type": "web_fullstack",
                "task_family": "coding_implement",
                "business_domain": "devops_platform",
            },
        },
        {
            "title": "Log error rate monitor",
            "seed": "Create a log tail monitor that counts error patterns, charts rates, and fires threshold alerts.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "medium",
                "value": "medium",
                "language_runtime": "go",
                "artifact_type": "cli_tool",
                "task_family": "coding_implement",
                "business_domain": "devops_platform",
                "modality": "logs_telemetry",
            },
        },
        {
            "title": "Cron job watchdog",
            "seed": "Build a cron/job watchdog: expected run windows, last-success heartbeats, and missed-run alerts.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "low",
                "value": "medium",
                "language_runtime": "python",
                "artifact_type": "backend_api",
                "task_family": "coding_implement",
                "business_domain": "devops_platform",
            },
        },
        {
            "title": "Disk and memory host agent",
            "seed": "Implement a local host agent that samples CPU/mem/disk and pushes metrics to a small collector UI.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "medium",
                "value": "medium",
                "language_runtime": "rust",
                "artifact_type": "cli_tool",
                "task_family": "coding_implement",
                "business_domain": "devops_platform",
            },
        },
        {
            "title": "SSL/HTTP probe farm",
            "seed": "Create an HTTP probe farm: configured URLs, expected status codes, latency SLOs, and failure screenshots stubs.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "medium",
                "value": "medium",
                "language_runtime": "javascript",
                "artifact_type": "web_fullstack",
                "task_family": "coding_implement",
                "business_domain": "devops_platform",
            },
        },
        {
            "title": "On-call rotation calendar",
            "seed": "Build an on-call rotation calendar with schedules, overrides, and alert routing contact list (no real PagerDuty).",
            "source": "original",
            "dimensions_hint": {
                "complexity": "low",
                "value": "medium",
                "language_runtime": "typescript",
                "artifact_type": "web_fullstack",
                "task_family": "coding_implement",
                "business_domain": "devops_platform",
            },
        },
        {
            "title": "Queue depth observatory",
            "seed": "Create a queue-depth observatory for fake workers: publish lag metrics, backlog charts, and saturation warnings.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "medium",
                "value": "hard",
                "language_runtime": "java",
                "artifact_type": "web_fullstack",
                "task_family": "data_visualization",
                "business_domain": "devops_platform",
            },
        },
        {
            "title": "Uptime Excel weekly report",
            "seed": "Build a tool that reads uptime check CSVs and produces a weekly Excel report with SLO burn and incident list.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "low",
                "value": "low",
                "language_runtime": "excel_office",
                "artifact_type": "spreadsheet_workbook",
                "task_family": "spreadsheet_excel",
                "business_domain": "devops_platform",
                "modality": "tabular_excel",
            },
        },
        {
            "title": "Synthetic transaction checker",
            "seed": "Implement a synthetic login→search→checkout transaction checker with step timings and pass/fail reports.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "hard",
                "value": "hard",
                "language_runtime": "python",
                "artifact_type": "cli_tool",
                "task_family": "testing_qa",
                "business_domain": "ecommerce",
            },
        },
    ],
    "games": [
        {
            "title": "Breakout clone with levels",
            "seed": "Create a Breakout/Arkanoid clone in Python + Pygame with multiple levels, power-ups, lives, high scores, and pause.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "medium",
                "value": "medium",
                "language_runtime": "python",
                "artifact_type": "game_prototype",
                "task_family": "coding_implement",
                "business_domain": "gaming",
            },
        },
        {
            "title": "Turn-based tactics grid",
            "seed": "Build a small turn-based tactics game on a grid: two units sides, move/attack, cover tiles, and win/lose conditions.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "hard",
                "value": "hard",
                "language_runtime": "typescript",
                "artifact_type": "game_prototype",
                "task_family": "coding_implement",
                "business_domain": "gaming",
            },
        },
        {
            "title": "Endless runner",
            "seed": "Create an endless runner with procedural obstacles, score distance, difficulty ramp, and restart flow (canvas or Pygame).",
            "source": "original",
            "dimensions_hint": {
                "complexity": "medium",
                "value": "medium",
                "language_runtime": "javascript",
                "artifact_type": "game_prototype",
                "task_family": "coding_implement",
                "business_domain": "gaming",
            },
        },
        {
            "title": "Minesweeper with solver hint",
            "seed": "Build Minesweeper with difficulty presets and a hint mode that highlights a safe deduction when possible.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "medium",
                "value": "medium",
                "language_runtime": "python",
                "artifact_type": "game_prototype",
                "task_family": "coding_implement",
                "business_domain": "gaming",
            },
        },
        {
            "title": "Card battler prototype",
            "seed": "Create a simple collectible card battler: deck, draw, mana, and a basic AI opponent turn.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "hard",
                "value": "hard",
                "language_runtime": "csharp",
                "artifact_type": "game_prototype",
                "task_family": "coding_implement",
                "business_domain": "gaming",
            },
        },
        {
            "title": "Physics sandbox balls",
            "seed": "Build a 2D physics sandbox with spawnable balls, gravity toggle, and collision counters (box2d or simple physics).",
            "source": "original",
            "dimensions_hint": {
                "complexity": "low",
                "value": "low",
                "language_runtime": "cpp",
                "artifact_type": "game_prototype",
                "task_family": "coding_implement",
                "business_domain": "gaming",
            },
        },
        {
            "title": "Typing race multiplayer local",
            "seed": "Create a local multiplayer typing race: shared prompt, per-player progress bars, WPM, and winner screen.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "low",
                "value": "medium",
                "language_runtime": "javascript",
                "artifact_type": "game_prototype",
                "task_family": "coding_implement",
                "business_domain": "education",
            },
        },
        {
            "title": "Roguelike ASCII dungeon",
            "seed": "Implement a small ASCII roguelike: procedural rooms, fog of war, enemies, inventory of 3 items, and save.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "hard",
                "value": "medium",
                "language_runtime": "rust",
                "artifact_type": "game_prototype",
                "task_family": "coding_implement",
                "business_domain": "gaming",
            },
        },
        {
            "title": "Puzzle match-3 lite",
            "seed": "Build a match-3 puzzle lite with board swap, cascades, score targets, and limited moves.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "medium",
                "value": "medium",
                "language_runtime": "typescript",
                "artifact_type": "game_prototype",
                "task_family": "coding_implement",
                "business_domain": "gaming",
            },
        },
        {
            "title": "Simulated stock trading game",
            "seed": "Create a stock trading simulation game: fake price series, buy/sell portfolio, leaderboard of profit.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "medium",
                "value": "hard",
                "language_runtime": "python",
                "artifact_type": "game_prototype",
                "task_family": "coding_implement",
                "business_domain": "finance_fintech",
            },
        },
    ],
    "distributed_systems": [
        {
            "title": "Distributed task queue (Go)",
            "seed": "Create a distributed task queue framework using Go. Implement a central scheduler, multiple worker nodes, task prioritization, retries with exponential backoff, worker heartbeats, failure detection, persistent job storage using SQLite, and a REST API for submitting and monitoring jobs. Include structured logging, graceful shutdown, concurrency using goroutines, and automated integration tests demonstrating multiple workers processing jobs simultaneously.",
            "source": "archive:10",
            "dimensions_hint": {
                "complexity": "hard",
                "value": "hard",
                "language_runtime": "go",
                "artifact_type": "backend_api",
                "task_family": "coding_implement",
                "business_domain": "devops_platform",
            },
        },
        {
            "title": "Priority job scheduler",
            "seed": "Build a priority job scheduler with delayed jobs, dead-letter queue, and an admin UI for retry/cancel.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "hard",
                "value": "hard",
                "language_runtime": "python",
                "artifact_type": "web_fullstack",
                "task_family": "coding_implement",
                "business_domain": "devops_platform",
            },
        },
        {
            "title": "Leader election toy cluster",
            "seed": "Implement a toy leader-election cluster (raft-lite or bully): nodes, heartbeat, failover demo CLI.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "hard",
                "value": "hard",
                "language_runtime": "rust",
                "artifact_type": "cli_tool",
                "task_family": "coding_implement",
                "business_domain": "devops_platform",
            },
        },
        {
            "title": "Pub/sub message broker lite",
            "seed": "Create an in-process pub/sub broker with topics, durable subscribers stub, and backpressure stats.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "medium",
                "value": "hard",
                "language_runtime": "java",
                "artifact_type": "library_sdk",
                "task_family": "coding_implement",
                "business_domain": "devops_platform",
            },
        },
        {
            "title": "MapReduce wordcount lab",
            "seed": "Build a mini MapReduce wordcount: split files, map workers, shuffle, reduce, and merge output.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "medium",
                "value": "medium",
                "language_runtime": "python",
                "artifact_type": "cli_tool",
                "task_family": "data_wrangling",
                "business_domain": "data_analytics",
            },
        },
        {
            "title": "Distributed lock service",
            "seed": "Implement a distributed lock service API with TTL, fencing tokens, and contention tests.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "hard",
                "value": "hard",
                "language_runtime": "go",
                "artifact_type": "backend_api",
                "task_family": "coding_implement",
                "business_domain": "devops_platform",
            },
        },
        {
            "title": "Sharded key-value store",
            "seed": "Create a sharded key-value store demo with consistent hashing, get/put, and rebalance command.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "hard",
                "value": "medium",
                "language_runtime": "csharp",
                "artifact_type": "backend_api",
                "task_family": "coding_implement",
                "business_domain": "devops_platform",
            },
        },
        {
            "title": "Workflow saga orchestrator",
            "seed": "Build a saga/workflow orchestrator for multi-step jobs with compensations on failure.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "hard",
                "value": "hard",
                "language_runtime": "typescript",
                "artifact_type": "backend_api",
                "task_family": "coding_implement",
                "business_domain": "finance_fintech",
            },
        },
        {
            "title": "Batch fan-out email workers",
            "seed": "Create a fan-out email sending simulator: enqueue campaigns, workers send stubs, track delivery states.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "medium",
                "value": "medium",
                "language_runtime": "javascript",
                "artifact_type": "backend_api",
                "task_family": "coding_implement",
                "business_domain": "media_cms",
            },
        },
        {
            "title": "Clock skew demo + NTP stub",
            "seed": "Build a multi-node clock skew demo showing logical clocks/vector clocks for event ordering.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "low",
                "value": "medium",
                "language_runtime": "python",
                "artifact_type": "cli_tool",
                "task_family": "analysis_reason",
                "business_domain": "devops_platform",
            },
        },
    ],
    "devops_infra": [
        {
            "title": "Docker container management dashboard",
            "seed": "Build a Docker container management dashboard that interacts with the Docker Engine API to start, stop, inspect, and monitor containers.",
            "source": "archive:bonus",
            "dimensions_hint": {
                "complexity": "hard",
                "value": "hard",
                "language_runtime": "typescript",
                "artifact_type": "web_fullstack",
                "task_family": "devops_ops",
                "business_domain": "devops_platform",
            },
        },
        {
            "title": "Kubernetes cluster visualization",
            "seed": "Build a Kubernetes cluster visualization dashboard that displays nodes, pods, deployments, services, logs, and resource utilization using the Kubernetes API.",
            "source": "archive:bonus",
            "dimensions_hint": {
                "complexity": "hard",
                "value": "hard",
                "language_runtime": "typescript",
                "artifact_type": "web_fullstack",
                "task_family": "devops_ops",
                "business_domain": "devops_platform",
            },
        },
        {
            "title": "GitHub-like code repository platform",
            "seed": "Build a GitHub-like code repository platform with repository browsing, issues, pull requests, authentication, and Markdown rendering.",
            "source": "archive:bonus",
            "dimensions_hint": {
                "complexity": "hard",
                "value": "hard",
                "language_runtime": "javascript",
                "artifact_type": "web_fullstack",
                "task_family": "coding_implement",
                "business_domain": "devops_platform",
            },
        },
        {
            "title": "CI pipeline status board",
            "seed": "Create a CI pipeline status board that ingests fake job events, shows stages, flaky detection, and retry buttons.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "medium",
                "value": "medium",
                "language_runtime": "go",
                "artifact_type": "web_fullstack",
                "task_family": "devops_ops",
                "business_domain": "devops_platform",
            },
        },
        {
            "title": "Terraform state explorer",
            "seed": "Build a Terraform state explorer: load state JSON, list resources, show attributes, and diff two state files.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "medium",
                "value": "hard",
                "language_runtime": "python",
                "artifact_type": "cli_tool",
                "task_family": "devops_ops",
                "business_domain": "devops_platform",
            },
        },
        {
            "title": "Local registry + image GC",
            "seed": "Create a local container image registry stub with tag list, delete, and garbage-collection policy demo.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "medium",
                "value": "medium",
                "language_runtime": "rust",
                "artifact_type": "backend_api",
                "task_family": "devops_ops",
                "business_domain": "devops_platform",
            },
        },
        {
            "title": "Env var & secrets sync tool",
            "seed": "Build an env sync tool: compare .env across environments, redact secrets in diffs, and apply patches.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "low",
                "value": "medium",
                "language_runtime": "python",
                "artifact_type": "cli_tool",
                "task_family": "devops_ops",
                "business_domain": "security_privacy",
            },
        },
        {
            "title": "Nginx config generator UI",
            "seed": "Create an Nginx config generator UI for reverse proxy upstreams, TLS toggles, and downloadable conf.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "low",
                "value": "low",
                "language_runtime": "javascript",
                "artifact_type": "web_fullstack",
                "task_family": "coding_implement",
                "business_domain": "devops_platform",
            },
        },
        {
            "title": "Backup job orchestrator",
            "seed": "Build a backup job orchestrator: schedules, destinations, retention, and restore dry-run reports.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "medium",
                "value": "hard",
                "language_runtime": "java",
                "artifact_type": "backend_api",
                "task_family": "devops_ops",
                "business_domain": "devops_platform",
            },
        },
        {
            "title": "Feature flag admin console",
            "seed": "Create a feature-flag admin console with percentage rollouts, targeting rules, and audit history.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "medium",
                "value": "hard",
                "language_runtime": "typescript",
                "artifact_type": "web_fullstack",
                "task_family": "coding_implement",
                "business_domain": "devops_platform",
            },
        },
    ],
    "finance_productivity": [
        {
            "title": "Personal finance tracker PRD",
            "seed": "Build a production-quality Personal Finance Tracker application from scratch. The application should allow users to manage their personal finances, track spending habits, and visualize their financial health through an intuitive interface. Support registration/auth, isolated user data, income/expense CRUD, categories, budgets, monthly/yearly summaries, dashboard charts, search/filter, and tests plus README.",
            "source": "archive:finance_prd",
            "dimensions_hint": {
                "complexity": "hard",
                "value": "hard",
                "language_runtime": "python",
                "artifact_type": "web_fullstack",
                "task_family": "coding_implement",
                "business_domain": "finance_fintech",
            },
        },
        {
            "title": "Personal finance manager",
            "seed": "Create a Personal Finance Manager in Python with accounts, transactions, budgets, and reports runnable locally.",
            "source": "archive:python_1",
            "dimensions_hint": {
                "complexity": "medium",
                "value": "medium",
                "language_runtime": "python",
                "artifact_type": "web_fullstack",
                "task_family": "coding_implement",
                "business_domain": "finance_fintech",
            },
        },
        {
            "title": "Expense splitter",
            "seed": "Create an Expense Splitter app: groups, shared expenses, balances, and settle-up suggestions.",
            "source": "archive:python_12",
            "dimensions_hint": {
                "complexity": "medium",
                "value": "medium",
                "language_runtime": "python",
                "artifact_type": "web_fullstack",
                "task_family": "coding_implement",
                "business_domain": "finance_fintech",
            },
        },
        {
            "title": "Employee leave management",
            "seed": "Create an Employee Leave Management System: leave types, balances, approvals, and calendar conflicts.",
            "source": "archive:python_4",
            "dimensions_hint": {
                "complexity": "medium",
                "value": "medium",
                "language_runtime": "python",
                "artifact_type": "web_fullstack",
                "task_family": "coding_implement",
                "business_domain": "productivity_collab",
            },
        },
        {
            "title": "Task and project management tool",
            "seed": "Create a Task & Project Management Tool with projects, tasks, assignees, due dates, and status workflow.",
            "source": "archive:python_9",
            "dimensions_hint": {
                "complexity": "medium",
                "value": "medium",
                "language_runtime": "python",
                "artifact_type": "web_fullstack",
                "task_family": "coding_implement",
                "business_domain": "productivity_collab",
            },
        },
        {
            "title": "Invoice generator",
            "seed": "Build an invoice generator: clients, line items, tax, PDF/HTML export, and payment status tracking.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "medium",
                "value": "hard",
                "language_runtime": "typescript",
                "artifact_type": "web_fullstack",
                "task_family": "coding_implement",
                "business_domain": "finance_fintech",
            },
        },
        {
            "title": "Habit streak tracker API",
            "seed": "Create a habit streak tracker API + minimal UI: daily check-ins, streaks, and weekly heatmap.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "low",
                "value": "low",
                "language_runtime": "javascript",
                "artifact_type": "web_fullstack",
                "task_family": "coding_implement",
                "business_domain": "productivity_collab",
            },
        },
        {
            "title": "Meeting notes action extractor",
            "seed": "Build a meeting-notes tool that stores notes and extracts action items with owners/due dates (rules or light NLP).",
            "source": "original",
            "dimensions_hint": {
                "complexity": "medium",
                "value": "medium",
                "language_runtime": "python",
                "artifact_type": "web_fullstack",
                "task_family": "analysis_reason",
                "business_domain": "productivity_collab",
            },
        },
        {
            "title": "Budget workbook assistant",
            "seed": "Create a budget workbook assistant that generates and updates an Excel monthly budget with categories and variance formulas.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "low",
                "value": "medium",
                "language_runtime": "excel_office",
                "artifact_type": "spreadsheet_workbook",
                "task_family": "spreadsheet_excel",
                "business_domain": "finance_fintech",
                "modality": "tabular_excel",
            },
        },
        {
            "title": "OKR tracker",
            "seed": "Build an OKR tracker: objectives, key results with progress %, check-ins, and team rollup view.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "medium",
                "value": "hard",
                "language_runtime": "csharp",
                "artifact_type": "web_fullstack",
                "task_family": "coding_implement",
                "business_domain": "productivity_collab",
            },
        },
    ],
    "generic_fullstack": [
        {
            "title": "Hospital appointment management",
            "seed": "Create a Hospital Appointment Management system: doctors, patients, slots, bookings, cancellations, and reminders stub.",
            "source": "archive:python_3",
            "dimensions_hint": {
                "complexity": "medium",
                "value": "hard",
                "language_runtime": "python",
                "artifact_type": "web_fullstack",
                "task_family": "coding_implement",
                "business_domain": "healthcare",
            },
        },
        {
            "title": "URL shortener service",
            "seed": "Create a URL Shortener Service with custom aliases, click analytics, and expiry.",
            "source": "archive:python_6",
            "dimensions_hint": {
                "complexity": "low",
                "value": "medium",
                "language_runtime": "python",
                "artifact_type": "web_fullstack",
                "task_family": "coding_implement",
                "business_domain": "general_utilities",
            },
        },
        {
            "title": "Local code search engine",
            "seed": "Create a Local Code Search Engine that indexes a repo directory and supports fast text/symbol search with a UI.",
            "source": "archive:python_14",
            "dimensions_hint": {
                "complexity": "hard",
                "value": "hard",
                "language_runtime": "python",
                "artifact_type": "web_fullstack",
                "task_family": "coding_implement",
                "business_domain": "devops_platform",
            },
        },
        {
            "title": "Community forum",
            "seed": "Build a community forum with threads, replies, votes, moderation flags, and user profiles.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "medium",
                "value": "medium",
                "language_runtime": "typescript",
                "artifact_type": "web_fullstack",
                "task_family": "coding_implement",
                "business_domain": "social_comms",
            },
        },
        {
            "title": "Job board",
            "seed": "Create a job board: employer posts, seeker applications, filters, and saved jobs.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "medium",
                "value": "medium",
                "language_runtime": "javascript",
                "artifact_type": "web_fullstack",
                "task_family": "coding_implement",
                "business_domain": "general_utilities",
            },
        },
        {
            "title": "Helpdesk ticket system",
            "seed": "Build a helpdesk ticket system with priorities, SLA timers, agent assignment, and canned responses.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "hard",
                "value": "hard",
                "language_runtime": "java",
                "artifact_type": "web_fullstack",
                "task_family": "coding_implement",
                "business_domain": "productivity_collab",
            },
        },
        {
            "title": "Bookmark manager",
            "seed": "Create a bookmark manager with folders, tags, full-text search, and import/export HTML.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "low",
                "value": "low",
                "language_runtime": "go",
                "artifact_type": "web_fullstack",
                "task_family": "coding_implement",
                "business_domain": "productivity_collab",
            },
        },
        {
            "title": "Survey builder",
            "seed": "Build a survey builder: form fields, publish link, responses table, and basic charts.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "medium",
                "value": "medium",
                "language_runtime": "typescript",
                "artifact_type": "web_fullstack",
                "task_family": "coding_implement",
                "business_domain": "data_analytics",
            },
        },
        {
            "title": "Classroom attendance app",
            "seed": "Create a classroom attendance app: roster, date sessions, present/absent, and export CSV.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "low",
                "value": "medium",
                "language_runtime": "csharp",
                "artifact_type": "web_fullstack",
                "task_family": "coding_implement",
                "business_domain": "education",
            },
        },
        {
            "title": "Personal CRM lite",
            "seed": "Build a personal CRM lite: contacts, companies, interaction notes, and follow-up reminders.",
            "source": "original",
            "dimensions_hint": {
                "complexity": "medium",
                "value": "hard",
                "language_runtime": "python",
                "artifact_type": "web_fullstack",
                "task_family": "coding_implement",
                "business_domain": "finance_fintech",
            },
        },
    ],
}


def slugify(title: str) -> str:
    s = "".join(c.lower() if c.isalnum() else "-" for c in title)
    while "--" in s:
        s = s.replace("--", "-")
    return s.strip("-")[:60]


def main() -> None:
    if OUT.exists():
        # wipe previous generated bank
        for p in OUT.rglob("*"):
            if p.is_file():
                p.unlink()
        for p in sorted(OUT.rglob("*"), reverse=True):
            if p.is_dir():
                p.rmdir()
    OUT.mkdir(parents=True, exist_ok=True)

    manifest = []
    skipped = []
    for cat, items in TASKS.items():
        assert len(items) == 10, f"{cat} has {len(items)} != 10"
        cat_dir = OUT / "by_category" / cat
        cat_dir.mkdir(parents=True, exist_ok=True)
        for i, item in enumerate(items, 1):
            blob = f"{item['title']}\n{item['seed']}".lower()
            if any(skip in blob for skip in SKIP_THEMES):
                skipped.append((cat, item["title"]))
                raise SystemExit(
                    f"Refusing to include completed theme: {cat}/{item['title']}"
                )
            tid = f"{cat}_{i:02d}_{slugify(item['title'])}"
            workdir = f"task_{cat}_{i:02d}"
            record = {
                "id": tid,
                "category": cat,
                "index": i,
                "title": item["title"],
                "seed": item["seed"],
                "source": item["source"],
                "dimensions_hint": {
                    "agent_topology": "subagent_spawns",
                    "verification_mode": "runtime_pass",
                    "session_shape": "multi_turn_repair",
                    "repo_state": "empty_scratch",
                    "tool_profile": "edit_heavy",
                    "user_persona": "solo_dev",
                    **item["dimensions_hint"],
                },
                "workdir": workdir,
                "pipeline_cmd": (
                    f'python main.py {json.dumps(item["seed"])} '
                    f"--forge-prompt --forge-category {cat} --workdir {workdir}"
                ),
            }
            path = cat_dir / f"{i:02d}_{slugify(item['title'])}.json"
            path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            (cat_dir / f"{i:02d}_{slugify(item['title'])}.md").write_text(
                f"# {item['title']}\n\n"
                f"- category: `{cat}`\n"
                f"- source: `{item['source']}`\n"
                f"- dimensions_hint: `{json.dumps(record['dimensions_hint'], ensure_ascii=False)}`\n\n"
                f"## Seed\n\n{item['seed']}\n\n"
                f"## Run (single category pipeline)\n\n"
                f"```bash\n{record['pipeline_cmd']}\n```\n",
                encoding="utf-8",
            )
            manifest.append(record)

    (OUT / "manifest.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in manifest) + "\n",
        encoding="utf-8",
    )
    (OUT / "manifest.json").write_text(
        json.dumps(
            {
                "n_categories": len(TASKS),
                "n_tasks": len(manifest),
                "excluded_completed_themes": sorted(SKIP_THEMES),
                "tasks": manifest,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    # one seed list per category for batching a single pipeline category
    for cat in TASKS:
        seeds = [m for m in manifest if m["category"] == cat]
        (OUT / "by_category" / cat / "SEEDS.txt").write_text(
            "\n\n-----\n\n".join(f"{s['index']}. {s['title']}\n{s['seed']}" for s in seeds),
            encoding="utf-8",
        )

    readme = f"""# Datagen task bank (13 × 10)

Generated seeds for forge categories. **Completed prior runs are excluded**
(whiteboard, smart home, Tidewatch/tower defense, PalletLens/image-class API,
Snake, social platform, gaming platform, Django blog, thin ecom_test, flask todos, etc.).

## Layout

- `by_category/<category>/*.json` — machine-readable task + dimension hints
- `by_category/<category>/*.md` — same with run command
- `by_category/<category>/SEEDS.txt` — all 10 seeds for that category
- `manifest.json` / `manifest.jsonl` — full index

## Counts

- categories: {len(TASKS)}
- tasks: {len(manifest)}

## Dimension hints

Each task has `dimensions_hint` (`complexity`/`value` low|medium|hard, language,
artifact, task_family, business_domain, …). These are **targets for diversity**;
forge/LLM expansion should deepen the PRD later.

## Run one category through Chakra (example)

```bash
# start Chakra gRPC first
python main.py "$(cat artifacts/datagen_task_bank/by_category/games/01_*.md | ...)" \\
  --forge-prompt --forge-category games --workdir task_games_01
```

Or use the `pipeline_cmd` field inside each JSON.

## Archive reuse

Seeds marked `archive:*` come from `docs/archive/project_prompts.md` items that
were never fully implemented in this workspace.
"""
    (OUT / "README.md").write_text(readme, encoding="utf-8")
    print(f"Wrote {len(manifest)} tasks → {OUT}")
    print("Categories:", ", ".join(TASKS))


if __name__ == "__main__":
    main()
