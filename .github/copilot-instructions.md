---
title: Agent Development Rules
---

Agent bootstrap instructions for repository contributors and AI agents.

**Source of Truth**: docs/PRD.md

All development decisions must reference the project specification in docs/PRD.md. The PRD defines architecture, component contracts, task DAG, API contracts, database models, operational constraints, acceptance criteria, and the definition of done.

**Mandatory Workflow**

1. Read `docs/PRD.md` and/or the `components` section relevant to the change.
2. Identify the relevant PRD section: `components`, `api_contracts`, `database_models`, `task_graph`, or `acceptance_contracts`.
3. Implement changes that conform strictly to those specifications. If code conflicts with the PRD, the PRD takes precedence—open an RFC if the codebase must diverge.
4. Add unit and integration tests to verify acceptance contracts before marking work complete.

**Architecture Constraints**

Required stack (do NOT replace):
- FastAPI (async endpoints only)
- PostgreSQL
- SQLModel
- Redis
- ARQ worker runtime
- Docker / docker-compose

Forbidden changes:
- Replacing PostgreSQL
- Adding synchronous HTTP endpoints
- Introducing new queueing systems (e.g., RabbitMQ) without prior approval

**Repository Layout (must be preserved)**

Keep the structure described in the PRD:

src/
  api/
  services/
  workers/
  models/
  db/
  observability/

tests/
  unit/
  integration/

load_tests/

migrations/

docs/

**Implementation Discipline**

- Keep API routes thin; move business logic to `services/`.
- Enforce transactional state updates in the database layer.
- Ensure idempotent task processing and strict state machine enforcement.
- No business logic inside route handlers.

**Testing Requirements**

- Unit tests: cover state transitions, retry logic, idempotency behavior.
- Integration tests: cover API + database and worker + database interactions.
- Minimum test coverage: 80% (as required by PRD).

**Operational Requirements**

- Structured JSON logging (consistent schema across services).
- Health endpoint: `/health` that checks DB and Redis connectivity.
- Metrics endpoint for request latency, worker duration, and task failures.

**Acceptance & Definition of Done**

Work is only marked complete when it meets the `definition_of_done` in docs/PRD.md and passes the relevant acceptance contracts (task submission, worker execution, retry logic, dead-letter behavior, health endpoint).

**When Uncertain**

1. Re-check `docs/PRD.md` for architectural intent.
2. Prefer asking for clarification or opening a short RFC rather than making unilateral infra changes.

**How to use this file**

- Use this as the agent bootstrap for automated agents and humans producing code or PRs.
- For larger or cross-cutting changes, create an `AGENTS.md` or `.github/RFC.md` referencing specific PRD sections and include migration steps.

----
Created by agent bootstrap script. Reference: docs/PRD.md