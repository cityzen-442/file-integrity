# File Integrity Checker
**Live demo:** https://YOUR-USERNAME.github.io/file-integrity/

## Browser version

The same idea runs in the browser, with no install. Pick files or a folder, save a baseline, and check again later to see which files were modified, renamed, added or deleted. You can also verify a download by pasting the checksum its website published.

- Files are read and hashed locally with the browser's built-in SHA-256. Nothing is uploaded.
- The baseline is kept in the browser and can be downloaded as `baseline.json`.
- The baseline format is the same as the Python tool's, so each tool can load the other's file.
- Limit: very large files (several GB) may fail, because the browser loads a whole file into memory.

A command-line tool, written in Python, that detects changed files. It fingerprints every file in a folder with SHA-256, saves the fingerprints as a baseline, and later reports what was modified, renamed, added or deleted. This is the same core idea as File Integrity Monitoring tools like Tripwire and AIDE.

## Features

- SHA-256 hashing, read in 64 KB chunks so large files never fill memory
- Scans a whole folder, including subfolders
- Baseline saved as readable JSON
- Reports `MODIFIED`, `RENAMED`, `ADDED` and `DELETED` files
- Rename detection by matching identical contents
- Exit code `0` when nothing changed and `1` when something did, so scripts can use it
- Skips `venv`, `.git` and `__pycache__`

## Why SHA-256

MD5 and SHA-1 have known collision attacks, where two different files can produce the same hash. SHA-256 has no known practical collisions.

## Usage

No external packages are needed.

```
py integrity.py hash <file>          # print one file's SHA-256
py integrity.py baseline <folder>    # save fingerprints to baseline.json
py integrity.py check <folder>       # compare the folder with the baseline
```

Example:

```
$ py integrity.py check testdata
[MODIFIED] a.txt
[RENAMED]  b.txt -> renamed.txt
[ADDED]    c.txt
[DELETED]  d.txt

1 modified, 1 renamed, 1 added, 1 deleted
```

## Tests

```
py -m unittest -v
```

The tests use temporary folders, so they never touch real files. They cover hashing (including a known value), folder scanning, the baseline file, every kind of change, and the command-line exit codes.

## Known limitations

- **The baseline is not protected.** Someone who can change a file can also edit `baseline.json` to match. Real tools keep the baseline on read-only media or another machine, or sign it.
- **A file that is renamed and edited at once** appears as one deleted and one added file, because its hash no longer matches.
- **Only file contents are checked.** Permissions, owners and timestamps are not.
- **Invisible changes count.** A different line ending or final newline changes the hash, so an editor that re-saves a file can trigger a `MODIFIED` report.
- **Identical files** (for example, several empty files) can make rename matching ambiguous. The report is still valid, but the pairing may differ from what you did.
- Files that cannot be read (locked or permission denied) are skipped with a message.

## What I learned

- A hash changes completely when a single byte changes (the avalanche effect).
- A baseline is only as trustworthy as its storage.
- Comparing sets of paths makes added, deleted and modified files simple to find.