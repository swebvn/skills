# SwebVN Skills

Shared Codex skills published from SwebVN project repositories.

## Source of truth

Project-owned skills are edited and regenerated in their source repositories. Each top-level skill directory in this repository is a distribution mirror and should not be edited directly.

Source repositories contain only their skill directories and skill-owned resources. Registry, synchronization, and publishing files belong only in this central repository.

## Development and synchronization

### Requirements

- PHP 8.0 or newer
- Composer is optional and only provides the `composer sync` shortcut

The sync script uses PHP built-in functions. It does not require `composer install`, a `vendor/` directory, or external packages.

### Workspace layout

Check out this repository and any source projects under the same parent directory:

```text
swebvn/
├── skills/
├── lucommerce/
└── another-project/
```

Only projects available on the developer's machine are synchronized. Missing source repositories are skipped with a warning, and their existing published skills are left unchanged.

### Run synchronization

From this repository, run either command on Windows, macOS, or Linux:

```bash
composer sync
```

```bash
php bin/sync.php
```

If the source repositories are not siblings of this repository, set `SKILLS_SOURCE_ROOT` to their common parent directory.

Bash:

```bash
SKILLS_SOURCE_ROOT=/path/to/swebvn php bin/sync.php
```

Windows PowerShell:

```powershell
$env:SKILLS_SOURCE_ROOT = "C:\path\to\swebvn"
php bin\sync.php
```

The command copies each available source skill into a top-level directory in this repository. Files removed from a source skill are also removed from its published copy.

### Add another skill

1. Create and maintain the skill in its source project:

   ```text
   project-name/
   └── skills/
       └── example-skill/
           ├── SKILL.md
           ├── agents/
           └── references/
   ```

2. Register it in `sources.json`:

   ```json
   {
     "name": "example-skill",
     "repository": "swebvn/project-name",
     "path": "skills/example-skill"
   }
   ```

3. Run `composer sync` and review the generated changes.
4. Commit the source skill in its project repository, then commit the synchronized copy in this repository.

Do not edit a published top-level skill directly. The next synchronization replaces it with the source project's version.
