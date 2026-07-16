# Plane Management Conventions

## Recommended labels

Create these per project when agent-driven work is desired:

| Label | Meaning |
|---|---|
| `agent-ready` | Clear acceptance criteria and safe for an agent to start |
| `agent-working` | Currently owned by an agent |
| `agent-blocked` | Agent cannot proceed without a decision or external change |
| `needs-review` | Implementation is complete and awaits human review |

Labels are optional. Assignment plus Plane's state group remains the source of truth.

## Manager workflow

1. Write a clear title and outcome-oriented description.
2. Add acceptance criteria and relevant technical context.
3. Set priority and the appropriate unstarted state.
4. Add cycle/module membership when the work is scheduled.
5. Add `agent-ready` only after dependencies and required decisions are resolved.
6. Review blocked, overdue, and unassigned work regularly.

## Agent selection workflow

Choose candidates that:

- Belong to the requested project and cycle/module when specified.
- Have a state group of `backlog` or `unstarted`.
- Are unassigned unless the agent is explicitly continuing assigned work.
- Carry `agent-ready` when that convention is enabled.
- Do not have unresolved parent or dependency constraints described in the issue.

Order candidates by priority, target date, then sequence number. Read the full item and comments before claiming it.

## Claim record

A useful claim comment includes:

- Agent or task identity.
- Branch name when one exists.
- Start time only when it adds coordination value.
- A short statement of the intended outcome.

Claiming is best-effort: re-fetch before mutation and stop if another assignee appeared or the state moved to completed/cancelled.

## Completion record

The completion comment should include:

- What changed.
- Tests or verification performed.
- Commit or pull-request reference when available.
- Follow-up work that remains outside the issue scope.

Move to a completed state only after the requested work is actually finished. Use `needs-review` or the project's review state instead when human review remains a required workflow step.

## Blocker record

State the concrete blocker, evidence already gathered, and the smallest decision or external change needed to resume. Keep the issue in a started state unless the project's conventions define a dedicated blocked state.
