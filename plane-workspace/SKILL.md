---
name: plane-workspace
description: Manage projects and work items in a self-hosted Plane workspace through the REST API. Use when Codex needs to inspect, search, create, triage, assign, label, comment on, claim, update, complete, block, or summarize Plane work; manage project states, members, cycles, modules, and labels; convert plans into Plane issues; or let a coding agent select and update its next issue.
---

# Plane Workspace

Use the bundled CLI for deterministic API access. Do not reconstruct curl commands when the CLI supports the operation.

## Configuration

Require the API key through `PLANE_API_KEY`. Never print it, pass it as a command-line argument, place it in this skill, or commit it to a repository.

The CLI defaults to the owner's self-hosted instance:

- Base URL: `https://plane.tdagroup.co`
- Workspace: `dev`

Override these with `PLANE_BASE_URL` and `PLANE_WORKSPACE_SLUG` when needed.

```bash
export PLANE_API_KEY='...'
python3 ~/.codex/skills/plane-workspace/scripts/plane.py me
```

## Choose a workflow

### Inspect or report

1. Resolve the project with `projects list`.
2. Read states, members, labels, cycles, or modules only when relevant.
3. List work items with `issues list` or find agent-ready work with `issues next`.
4. Summarize the returned JSON in the terminology used by the user.

```bash
python3 ~/.codex/skills/plane-workspace/scripts/plane.py projects list
python3 ~/.codex/skills/plane-workspace/scripts/plane.py issues list --project LUNAR
python3 ~/.codex/skills/plane-workspace/scripts/plane.py issues next --project LUNAR --label agent-ready
```

### Manage work as a manager

Use `issues create`, `issues update`, and `issues comment`. Resolve human-readable names to IDs through the CLI rather than guessing IDs.

```bash
python3 ~/.codex/skills/plane-workspace/scripts/plane.py issues create \
  --project LUNAR --title 'Fix save-state restore' --priority high \
  --state unstarted --label bug

python3 ~/.codex/skills/plane-workspace/scripts/plane.py issues update LUNAR-42 \
  --state started --assignee bang
```

For a bulk change, first inspect the candidates and state the proposed mutations. Apply the batch only after the user approves it. The CLI intentionally does not support deletion.

### Work an issue as an agent

1. Select work with `issues next`; respect project, cycle, label, priority, and assignment constraints from the request.
2. Read the chosen work item and its comments before claiming it.
3. Claim with `issues claim`. This re-fetches the work item, checks its current assignees and state group, assigns the configured member, moves it to a started state, and comments with the agent identity.
4. Perform the repository work and verify it.
5. Complete with `issues complete`, including a concrete summary and test evidence.
6. If blocked, use `issues block` with the blocker and needed next action. Do not mark incomplete work as completed.

```bash
python3 ~/.codex/skills/plane-workspace/scripts/plane.py issues claim LUNAR-42 \
  --assignee bang --agent codex/rebit-worker

python3 ~/.codex/skills/plane-workspace/scripts/plane.py issues complete LUNAR-42 \
  --summary 'Fixed SRAM restoration and added regression coverage.' \
  --tests 'php artisan test tests/Feature/SavesTest.php' \
  --commit abc1234
```

Issue claiming is best-effort because Plane does not expose a compare-and-swap operation. Treat a conflicting assignment or a completed/cancelled state as a hard stop unless the user explicitly authorizes `--force`.

## Mutation rules

- Perform a single create, update, claim, comment, block, or completion when the user's request clearly authorizes it.
- Use `--dry-run` to preview uncertain writes.
- Re-read an issue immediately before claiming it.
- Discover state semantics from Plane's `group` field; do not hardcode names such as Todo, In Progress, or Done.
- Do not silently replace assignees or labels. Prefer `--add-assignee`, `--remove-assignee`, `--add-label`, and `--remove-label` unless replacement is intentional.
- Never create duplicate work items merely because a request was retried. Search for an existing matching item first.
- Report partial success if a primary mutation succeeds but a follow-up comment, cycle, or module association fails.

## References

- Read [references/conventions.md](references/conventions.md) for manager/worker coordination and recommended labels.
- Read [references/api.md](references/api.md) when extending or diagnosing the API integration.
- Run `python3 scripts/plane.py --help` and subcommand help for the complete command surface.
