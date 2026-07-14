# SwebVN Skills

Shared Codex skills published from SwebVN project repositories.

## Source of truth

Project-owned skills are edited and regenerated in their source repositories. Each top-level skill directory in this repository is a distribution mirror and should not be edited directly.

## Synchronize

Check out the source repositories as siblings of this repository, then run on Windows, macOS, or Linux:

```bash
composer sync
```

The command uses only PHP built-in functions. It does not require `composer install`, a `vendor/` directory, or external packages. You can also run it directly:

```bash
php bin/sync.php
```

On macOS and Linux, `./bin/sync` remains available as a shortcut.

Set `SKILLS_SOURCE_ROOT` when the source repositories live elsewhere. In Bash:

```bash
SKILLS_SOURCE_ROOT=/path/to/projects ./bin/sync
```

In Windows PowerShell:

```powershell
$env:SKILLS_SOURCE_ROOT = "C:\path\to\projects"
composer sync
```

Register additional project-owned skills in `sources.json`. Each entry identifies the skill name, source repository, and path within that repository.

Missing source repositories are skipped with a warning. Their existing published copies are left unchanged.
