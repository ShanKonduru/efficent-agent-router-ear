---
mode: ask
model: GPT-5
description: "Break a user story into engineering tasks, sub-tasks, acceptance criteria, and test cases for EAR."
---

You are planning work for Efficient Agent Router (EAR).

Input user story:
{{input:user_story}}

Context:
- Python 3.12+
- asyncio
- Typer CLI first
- MCP server after CLI validation
- Pydantic v2
- 100% coverage target for routing logic

Return:
1. Story objective in one sentence.
2. Task breakdown with sub-tasks.
3. Acceptance criteria in Given/When/Then form.
4. Test matrix (unit, integration, failure-path).
5. Risks and mitigations.
6. Effort estimate in story points (1, 2, 3, 5, 8).
