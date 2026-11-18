import hashlib
import json
import sys
from pathlib import Path

# Read files in 64 KB pieces so huge files never fill the computer's memory
CHUNK_SIZE = 65536
BASELINE_FILE = "baseline.json"

# Folders we never scan
SKIP_DIRS = {"venv", ".git", "__pycache__"}


def hash_file(path):
    """Return the SHA-256 fingerprint of a file as a hex string."""
    sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                break
            sha256.update(chunk)
    return sha256.hexdigest()


def scan_folder(folder):
    """Hash every file under a folder. Returns {relative_path: hash}."""
    root = Path(folder)
    hashes = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if not path.is_file():
            continue
        if SKIP_DIRS & set(relative.parts) or path.name == BASELINE_FILE:
            continue
        try:
            hashes[relative.as_posix()] = hash_file(path)
        except (PermissionError, OSError) as error:
            print(f"Skipped {relative}: {error}")
    return hashes


def save_baseline(hashes, baseline_file=BASELINE_FILE):
    """Write the hashes to a JSON file."""
    with open(baseline_file, "w", encoding="utf-8") as f:
        json.dump(hashes, f, indent=2, sort_keys=True)


def load_baseline(baseline_file=BASELINE_FILE):
    """Read the saved hashes. Returns None if there is no usable baseline."""
    try:
        with open(baseline_file, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except json.JSONDecodeError:
        return None


def compare(baseline, current):
    """Compare two {path: hash} dictionaries.

    Returns (added, modified, deleted) as sorted lists of file paths.
    """
    added = sorted(current.keys() - baseline.keys())
    deleted = sorted(baseline.keys() - current.keys())
    modified = sorted(
        path for path in baseline.keys() & current.keys()
        if baseline[path] != current[path]
    )
    return added, modified, deleted


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "hash":
        try:
            print(f"{hash_file(sys.argv[2])}  {sys.argv[2]}")
        except FileNotFoundError:
            print(f"File not found: {sys.argv[2]}")

    elif len(sys.argv) == 3 and sys.argv[1] == "baseline":
        folder = sys.argv[2]
        if not Path(folder).is_dir():
            print(f"Folder not found: {folder}")
            return
        hashes = scan_folder(folder)
        save_baseline(hashes)
        print(f"Saved baseline of {len(hashes)} files to {BASELINE_FILE}")

    elif len(sys.argv) == 3 and sys.argv[1] == "check":
        folder = sys.argv[2]
        if not Path(folder).is_dir():
            print(f"Folder not found: {folder}")
            return
        baseline = load_baseline()
        if baseline is None:
            print(f"No usable {BASELINE_FILE}. Run: py integrity.py baseline {folder}")
            return

        added, modified, deleted = compare(baseline, scan_folder(folder))

        for path in modified:
            print(f"[MODIFIED] {path}")
        for path in added:
            print(f"[ADDED]    {path}")
        for path in deleted:
            print(f"[DELETED]  {path}")

        if not (added or modified or deleted):
            print("OK: no changes since the baseline.")
        else:
            print(f"\n{len(modified)} modified, {len(added)} added, {len(deleted)} deleted")
            sys.exit(1)

    else:
        print("Usage:")
        print("  py integrity.py hash <file>")
        print("  py integrity.py baseline <folder>")
        print("  py integrity.py check <folder>")


if __name__ == "__main__":
    main()