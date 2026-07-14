# SwebVN Skills

Shared Codex skills published from SwebVN project repositories.

## Source of truth

Project-owned skills are edited and regenerated in their source repositories. The copies under `skills/` in this repository are distribution mirrors and should not be edited directly.

## Synchronize

Check out the source repositories as siblings of this repository, then run:

```bash
./bin/sync
```

Set `SKILLS_SOURCE_ROOT` when the source repositories live elsewhere:

```bash
SKILLS_SOURCE_ROOT=/path/to/projects ./bin/sync
```

Register additional project-owned skills in `sources.json`. Each entry identifies the skill name, source repository, and path within that repository.

Missing source repositories are skipped with a warning. Their existing published copies under `skills/` are left unchanged.
