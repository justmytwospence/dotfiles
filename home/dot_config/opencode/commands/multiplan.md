---
description: Plan with Claude Fable and GPT-6 Astra in parallel, then pick one plan or synthesize them
agent: plan
---
Plan the task below with two independent planners, then let me choose.

1. In a single message, launch the planner-claude and planner-gpt subagents in parallel with the task tool. Give both the identical brief: the task, the relevant context from this conversation (decisions, constraints, and answers I've already given), and a request for one complete, decision-ready plan. Never show either planner the other's plan.
2. Show both plans in full as "Plan A · planner-claude" and "Plan B · planner-gpt", then list briefly where they materially differ.
3. Ask me with the question tool: use Plan A, use Plan B, or synthesize. I may add guidance about what to take from each.
4. If I pick one, present it unchanged as the final plan. If I ask for a synthesis, check the disagreements against the code, merge following my guidance, and present the complete final plan.
5. Do not edit files. End by telling me the two ways to implement: press Tab for the build agent to keep this conversation, or run /implement-fresh to give only the plan to a fresh-context implementer.

Task: $ARGUMENTS
