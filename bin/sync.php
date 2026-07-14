#!/usr/bin/env php
<?php

declare(strict_types=1);

function removeDirectory(string $directory): void
{
    if (!is_dir($directory)) {
        return;
    }

    $items = new RecursiveIteratorIterator(
        new RecursiveDirectoryIterator($directory, FilesystemIterator::SKIP_DOTS),
        RecursiveIteratorIterator::CHILD_FIRST,
    );

    foreach ($items as $item) {
        if ($item->isDir() && !$item->isLink()) {
            rmdir($item->getPathname());
        } else {
            unlink($item->getPathname());
        }
    }

    rmdir($directory);
}

function copyDirectory(string $source, string $target): void
{
    mkdir($target, 0777, true);

    $items = new RecursiveIteratorIterator(
        new RecursiveDirectoryIterator($source, FilesystemIterator::SKIP_DOTS),
        RecursiveIteratorIterator::SELF_FIRST,
    );

    foreach ($items as $item) {
        $name = $item->getFilename();

        if ($name === '.git' || str_ends_with($name, '.zip')) {
            continue;
        }

        $relativePath = $items->getSubPathName();
        $destination = $target . DIRECTORY_SEPARATOR . $relativePath;

        if ($item->isDir()) {
            if (!is_dir($destination)) {
                mkdir($destination, 0777, true);
            }

            continue;
        }

        $destinationDirectory = dirname($destination);
        if (!is_dir($destinationDirectory)) {
            mkdir($destinationDirectory, 0777, true);
        }

        if (!copy($item->getPathname(), $destination)) {
            throw new RuntimeException("Unable to copy {$item->getPathname()}");
        }
    }
}

$repoRoot = dirname(__DIR__);
$sourceRoot = getenv('SKILLS_SOURCE_ROOT') ?: dirname($repoRoot);
$manifestPath = $repoRoot . DIRECTORY_SEPARATOR . 'sources.json';
$sources = json_decode(
    file_get_contents($manifestPath),
    true,
    512,
    JSON_THROW_ON_ERROR,
);

if (!is_array($sources)) {
    throw new RuntimeException('sources.json must contain an array.');
}

foreach ($sources as $source) {
    $name = $source['name'] ?? null;
    $repository = $source['repository'] ?? null;
    $sourcePath = $source['path'] ?? null;

    if (!is_string($name) || !preg_match('/^[a-z0-9]+(?:-[a-z0-9]+)*$/', $name)) {
        throw new RuntimeException("Invalid skill name '{$name}'.");
    }

    if (!is_string($repository) || $repository === '' || !is_string($sourcePath) || $sourcePath === '') {
        throw new RuntimeException("Invalid source configuration for '{$name}'.");
    }

    $pathParts = preg_split('/[\\\\\/]+/', $sourcePath);
    if (preg_match('/^(?:[A-Za-z]:)?[\\\\\/]/', $sourcePath) || in_array('..', $pathParts, true)) {
        throw new RuntimeException("Invalid source path '{$sourcePath}'.");
    }

    $repositoryParts = preg_split('/[\\\\\/]+/', $repository);
    $repositoryDirectory = end($repositoryParts);
    $normalizedSourcePath = str_replace(['/', '\\'], DIRECTORY_SEPARATOR, $sourcePath);
    $sourceDirectory = $sourceRoot
        . DIRECTORY_SEPARATOR . $repositoryDirectory
        . DIRECTORY_SEPARATOR . $normalizedSourcePath;
    $targetDirectory = $repoRoot . DIRECTORY_SEPARATOR . $name;

    if (!is_file($sourceDirectory . DIRECTORY_SEPARATOR . 'SKILL.md')) {
        fwrite(STDERR, "Skipping {$name}: source checkout not found at {$sourceDirectory}" . PHP_EOL);
        continue;
    }

    removeDirectory($targetDirectory);
    copyDirectory($sourceDirectory, $targetDirectory);

    echo "Synced {$name} from {$repository}:{$sourcePath}" . PHP_EOL;
}
