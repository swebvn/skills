# SwebVN Skills

Shared Codex skills published from SwebVN project repositories.

## Source of truth

Project-owned skills are edited and regenerated in their source repositories. The copies under `skills/` in this repository are distribution mirrors and should not be edited directly.

## Synchronize

Check out the source repositories as siblings of this repository, then run on Windows, macOS, or Linux:

```bash
npm run sync
```

The command uses only Node.js built-in modules, so no package installation is required. On macOS and Linux, `./bin/sync` remains available as a shortcut.

Set `SKILLS_SOURCE_ROOT` when the source repositories live elsewhere. In Bash:

```bash
SKILLS_SOURCE_ROOT=/path/to/projects ./bin/sync
```

In Windows PowerShell:

```powershell
$env:SKILLS_SOURCE_ROOT = "C:\path\to\projects"
npm run sync
```

Register additional project-owned skills in `sources.json`. Each entry identifies the skill name, source repository, and path within that repository.

Missing source repositories are skipped with a warning. Their existing published copies under `skills/` are left unchanged.
