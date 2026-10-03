# Notionary Context Documentation Hub

Welcome to the centralized context directory for **Notionary** (ProjectOS / KBC-NOTION-02 Reference System).
All foundational requirements, architectural specifications, design sitemaps, evaluation benchmarks, and presenter scripts are organized here in both structured markdown and source PDF formats.

---

## Document Index & Summary

| File | Type | Description |
| :--- | :---: | :--- |
| **[`PRD.md`](./PRD.md)** | Requirements | **Product Requirements Document (PRD v1.0)** — Covers the complete 44 sections including domain model, 3-tier confidence gateway, bidirectional Notion sync rules, contradiction radar, and evaluation criteria. |
| **[`TRD.md`](./TRD.md)** | Technical Spec | **Technical Architecture & Build Specification (TRD v1.0)** — 88-page comprehensive engineering specification covering data contracts, SQLite schemas, BFS graph traversal algorithms, hybrid search, and latency SLAs. |
| **[`SITEMAP.md`](./SITEMAP.md)** | UI / Stitch | **Screen & Component Sitemap** — Defines the 11 application screens, visual tokens, layout grids, components, and API endpoint bindings for Stitch and frontend engineering. |
| **[`IMPLEMENTATION_PLAN.md`](./IMPLEMENTATION_PLAN.md)** | Roadmap | **Phase 0–9 Prototype Implementation Plan** — Engineering roadmap from initial foundations through demo hardening, acceptance tests, and delivery milestones. |
| **[`ARCHITECTURE.md`](./ARCHITECTURE.md)** | System Design | **High-Level System Architecture** — Subsystem breakdown: FastAPI backend, Next.js frontend, SQLite WAL storage, Graph-RAG pipeline, bidirectional Notion sync engine, and resilience layer. |
| **[`EVAL_RESULTS.md`](./EVAL_RESULTS.md)** | Benchmarks | **Empirical Benchmark & Evaluation Results** — 20 canonical questions evaluation (100% Hit@5, 100% citation accuracy, 0% hallucination), extraction precision/recall, and latency performance vs TRD SLAs. |
| **[`DEMO_GUIDE.md`](./DEMO_GUIDE.md)** | Runbook | **Presenter Guide & Live Demo Script** — Scene-by-scene script covering the 8 demo scenes, speaker talk tracks, UI navigation instructions, and emergency fallback procedures. |

---

## Source PDFs

- **`Notionary_PRD.pdf`**: Original compiled PRD document.
- **`trd_notionary.pdf`**: Original 88-page Technical Architecture & Build Specification.
- **`Kaun_Banega_Codepati_2026.pdf`**: Official competition challenge statement and evaluation guidelines.

---

## How to Use This Directory

- **For Stitch / UI Generation**: Consult [`SITEMAP.md`](./SITEMAP.md) for the exact visual tokens, screen breakdown, component hierarchy, and API endpoint mapping.
- **For AI Reasoning / Context Injection**: Point prompts or LLM agents to [`PRD.md`](./PRD.md) and [`TRD.md`](./TRD.md) for domain model rules, entity relationships, and schemas.
- **For Presentation & Demos**: Follow [`DEMO_GUIDE.md`](./DEMO_GUIDE.md) alongside the live app at `http://localhost:3000`.
