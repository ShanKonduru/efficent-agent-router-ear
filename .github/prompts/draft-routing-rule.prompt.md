---
mode: ask
model: GPT-5
description: "Draft and validate a new EAR routing rule with rationale, pseudo-code, and test cases."
---

Design a routing rule for Efficient Agent Router.

Rule goal:
{{input:rule_goal}}

Constraints:
- Must improve quality/cost/latency tradeoff.
- Must not weaken safety or PII controls.
- Must be deterministic and testable.

Output:
1. Rule description.
2. Inputs and outputs.
3. Pseudo-code.
4. Priority order relative to existing rules.
5. Edge cases.
6. Unit tests needed to reach branch coverage.
7. Rollback strategy if rule degrades outcomes.
