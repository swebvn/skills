#!/usr/bin/env node

import {
  cpSync,
  existsSync,
  mkdirSync,
  readFileSync,
  rmSync,
} from 'node:fs';
import { dirname, isAbsolute, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const repoRoot = dirname(dirname(fileURLToPath(import.meta.url)));
const sourceRoot = process.env.SKILLS_SOURCE_ROOT || dirname(repoRoot);
const manifestPath = join(repoRoot, 'sources.json');
const sources = JSON.parse(readFileSync(manifestPath, 'utf8'));

if (!Array.isArray(sources)) {
  throw new Error('sources.json must contain an array.');
}

for (const source of sources) {
  const { name, repository, path: sourcePath } = source;

  if (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(name || '')) {
    throw new Error(`Invalid skill name '${name}'.`);
  }

  if (
    typeof repository !== 'string' ||
    repository.length === 0 ||
    typeof sourcePath !== 'string' ||
    sourcePath.length === 0
  ) {
    throw new Error(`Invalid source configuration for '${name}'.`);
  }

  if (
    isAbsolute(sourcePath) ||
    sourcePath.split(/[\\/]/).includes('..')
  ) {
    throw new Error(`Invalid source path '${sourcePath}'.`);
  }

  const repositoryDirectory = repository.split(/[\\/]/).at(-1);
  const sourceDirectory = join(sourceRoot, repositoryDirectory, sourcePath);
  const targetDirectory = join(repoRoot, 'skills', name);

  if (!existsSync(join(sourceDirectory, 'SKILL.md'))) {
    console.warn(
      `Skipping ${name}: source checkout not found at ${sourceDirectory}`,
    );
    continue;
  }

  rmSync(targetDirectory, { recursive: true, force: true });
  mkdirSync(dirname(targetDirectory), { recursive: true });
  cpSync(sourceDirectory, targetDirectory, {
    recursive: true,
    filter: (entry) => {
      const entryName = entry.split(/[\\/]/).at(-1);
      return entryName !== '.git' && !entryName.endsWith('.zip');
    },
  });

  console.log(`Synced ${name} from ${repository}:${sourcePath}`);
}
