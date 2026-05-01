---
name: ear-delivery-planning
description: "Use when planning EAR features, creating milestones, sizing stories, and defining acceptance criteria for router, CLI, and MCP phases."
---

# EAR Delivery Planning Skill

## Purpose
Create consistent execution plans for Efficient Agent Router workstreams.

## Inputs
- Feature or epic description
- Constraints (timeline, risk, quality gates)
- Team capacity assumptions

## Workflow
1. Clarify feature intent and user impact.
2. Split into user stories and acceptance criteria.
3. Decompose stories into implementable tasks and sub-tasks.
4. Estimate effort using Fibonacci points (1, 2, 3, 5, 8).
5. Define milestones with dependency order.
6. Attach validation plan (tests, coverage, security scans).

## Output Format
- Feature summary
- User stories
- Tasks and sub-tasks
- Estimates and sizing
- Risks and mitigations
- Milestone plan

## EAR Constraints
- CLI-first delivery before MCP transport.
- asyncio and Typer defaults.
- 100% coverage target for router decision logic.
- Security checks include prompt injection and PII safeguards.
