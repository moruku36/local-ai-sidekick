# Architecture Decisions

This file records architecture decisions made by Lead AI.
Sidekick must respect these decisions and must NOT modify this file.

## ADR-001: Separation of Lead AI and Local Sidekick

- **Decision**: Use Lead AI for high-level architectural design and planning, and Local Sidekick for implementation, test execution, and repo-level exploration.
- **Reason**: Minimize expensive LLM token consumption while maintaining high architectural quality.
- **Date**: 2026-09-14
