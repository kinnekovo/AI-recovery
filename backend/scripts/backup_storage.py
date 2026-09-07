import argparse
import json
import tarfile
from datetime import datetime, timezone
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Back up speech rehab storage files into a tar.gz archive.")
    parser.add_argument("--source", default="../storage", help="Storage root to back up.")
    parser.add_argument("--output", default="../backups", help="Directory where backup archives are written.")
    args = parser.parse_args()

    source = Path(args.source).resolve()
    output = Path(args.output).resolve()
    if not source.exists() or not source.is_dir():
        raise SystemExit(f"storage source does not exist or is not a directory: {source}")

    output.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive_path = output / f"speech_rehab_storage_{timestamp}.tar.gz"
    manifest_path = output / f"speech_rehab_storage_{timestamp}.manifest.json"
    files = [path for path in source.rglob("*") if path.is_file()]
    total_bytes = sum(path.stat().st_size for path in files)

    with tarfile.open(archive_path, "w:gz") as archive:
        archive.add(source, arcname=source.name)

    manifest = {
        "created_at": timestamp,
        "source": str(source),
        "archive": str(archive_path),
        "file_count": len(files),
        "total_bytes": total_bytes,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
