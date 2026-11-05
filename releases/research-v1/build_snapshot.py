"""Prepare the research-v1 source selection and lossless experiment assets.

Never deletes files, rewrites research artifacts, or changes Git's index.
"""
from pathlib import Path
from collections import Counter
import argparse
import hashlib
import json
import re
import zipfile

ROOT = Path(__file__).resolve().parents[2]
LOCAL = ROOT / "work/research_v1_publication_20261105"
META = Path(__file__).resolve().parent
SOURCE = {".py", ".r", ".ps1", ".md", ".js", ".css", ".html", ".yaml", ".yml", ".toml", ".xml"}
ALLOWED = SOURCE | {".txt", ".json", ".csv", ".tsv", ".npy", ".npz", ".joblib", ".png", ".svg", ".log", ".bin", ".docx"}
BLOCK_PARTS = {"runtime", "__pycache__", ".venv", "venv", "env", "node_modules", "site-packages", "acn_raw", "original", "downloads", "python_packages", "python_caches", "mpl_cache"}
SUMMARY = re.compile(r"summary|receipt|verification|protocol|selection|decision|freeze|manifest|admission|review|counts|sources|catalog|completion|preflight|result|audit|plan", re.I)
SECRETS = [
    ("private_key", re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("github_token", re.compile(rb"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})\b")),
    ("aws_access_key", re.compile(rb"\bAKIA[A-Z0-9]{16}\b")),
    ("openai_key", re.compile(rb"\bsk-(?:proj-)?[A-Za-z0-9_-]{40,}\b")),
]


def dump(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def classify(row):
    p = Path(row["path"])
    parts = set(p.parts)
    ext = p.suffix.lower()
    if parts & BLOCK_PARTS:
        return "excluded", "Reinstallable runtime/cache or acquired original data."
    if ext not in ALLOWED:
        return "excluded", "External binaries, raw archives/spreadsheets, or paper/export formats."
    if p.name.startswith("~$"):
        return "excluded", "Office lock file."
    if "optimise_prime" in parts and (p.name.startswith("table_") or ext == ".part"):
        return "excluded", "Acquired Optimise Prime original table; keep access/provenance records."
    if p.name.startswith(("lcl_residential_sample_", "prepared_P_events", "P_household_registry", "independent_expected_roster", "independent_metadata_checks")):
        return "excluded", "Original or row-level real-meter dataset; use original source and preparation scripts."
    if "targeted_link" in parts and ext not in SOURCE:
        return "excluded", "Acquired real-meter sample."
    if p.parts[0].startswith("B1"):
        return "git", "Algorithm source, retained model parameters, or interface documentation."
    # Real datasets are not silently mirrored as research evidence assets.
    real_folder = any(k in p.parts[1] for k in ("real_training_data", "real_response_data", "iflex_real_training"))
    if real_folder and ext in {".csv", ".tsv", ".json", ".npy", ".npz"} and row["bytes"] > 200_000 and not SUMMARY.search(p.name):
        return "excluded", "Large real-data row derivative; retain model, preparation and aggregate evidence."
    if ext in SOURCE:
        return "git", "Research code, report, or demonstration."
    if ext in {".png", ".svg"}:
        return "git", "Research figure."
    if "_demo_" in p.parts[1] and row["bytes"] <= 8 * 1024**2:
        return "git", "Demonstration inputs/state needed by the published example."
    if ext == ".json" and SUMMARY.search(p.name) and row["bytes"] <= 1024**2:
        return "git", "Protocol, decision, audit or provenance evidence."
    if len(p.parts) == 3 and ext in {".json", ".csv", ".tsv", ".txt"} and row["bytes"] <= 256 * 1024:
        return "git", "Small top-level research result or table."
    if ("models" in parts or "frozen_models" in parts or "state_v2" in parts) and row["bytes"] <= 10 * 1024**2:
        return "git", "Retained trained model or model metadata."
    return "archive", "Lossless experiment evidence asset; not placed in Git history."


def digest_file(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def make_plan():
    rows = json.loads((LOCAL / "inventory.json").read_text(encoding="utf-8"))
    out = []
    for row in rows:
        tier, reason = classify(row)
        out.append({**row, "destination": tier, "reason": reason})
    findings = []
    for row in out:
        if row["destination"] == "excluded" or row["ext"] not in SOURCE | {".json", ".txt", ".csv", ".tsv", ".log"}:
            continue
        p = ROOT / row["path"]
        with p.open("rb") as f:
            tail = b""
            while chunk := f.read(1024 * 1024):
                buf = tail + chunk
                for name, rx in SECRETS:
                    if rx.search(buf):
                        findings.append({"path": row["path"], "kind": name})
                tail = buf[-256:]
    dump(LOCAL / "publication_plan.json", {"files": out, "credential_findings": findings})
    counts = Counter(r["destination"] for r in out)
    sizes = {k: sum(r["bytes"] for r in out if r["destination"] == k) for k in counts}
    print(json.dumps({"files": counts, "MiB": {k: round(v / 1024**2, 2) for k, v in sizes.items()}, "credential_findings": findings}, indent=2), flush=True)
    if findings:
        raise ValueError("Review credential findings before packing; no secret values are printed.")


def pack():
    plan = json.loads((LOCAL / "publication_plan.json").read_text(encoding="utf-8"))
    if plan["credential_findings"]:
        raise ValueError("Unreviewed credential findings.")
    assets = LOCAL / "assets"
    assets.mkdir(exist_ok=True)
    rows = plan["files"]
    manifest = []
    for row in rows:
        if row["destination"] == "git":
            manifest.append({**row, "sha256": digest_file(ROOT / row["path"])})
    batches = []
    batch, size = [], 0
    for row in sorted((r for r in rows if r["destination"] == "archive"), key=lambda r: r["path"]):
        if batch and size + row["bytes"] > 900 * 1024**2:
            batches.append(batch)
            batch, size = [], 0
        batch.append(row)
        size += row["bytes"]
    if batch:
        batches.append(batch)
    archive_records = []
    for number, batch in enumerate(batches, 1):
        name = f"research-v1-evidence-{number:02d}.zip"
        path = assets / name
        with zipfile.ZipFile(path, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=4, allowZip64=True) as z:
            for row in batch:
                source = ROOT / row["path"]
                h = hashlib.sha256()
                count = 0
                with source.open("rb") as src, z.open(row["path"], "w", force_zip64=True) as dst:
                    while chunk := src.read(1024 * 1024):
                        h.update(chunk)
                        count += len(chunk)
                        dst.write(chunk)
                if count != row["bytes"]:
                    raise ValueError("Source changed while archiving: " + row["path"])
                manifest.append({**row, "sha256": h.hexdigest(), "asset": name})
        # Validate every member's name/size and the largest member's lossless content.
        with zipfile.ZipFile(path) as z:
            if {i.filename: i.file_size for i in z.infolist()} != {r["path"]: r["bytes"] for r in batch}:
                raise ValueError("Archive inventory mismatch.")
            sample = max(batch, key=lambda r: r["bytes"])
            h = hashlib.sha256()
            with z.open(sample["path"]) as src:
                while chunk := src.read(1024 * 1024):
                    h.update(chunk)
            expected = next(m["sha256"] for m in manifest if m["path"] == sample["path"])
            if h.hexdigest() != expected:
                raise ValueError("Archive content verification failed.")
        record = {"asset": name, "bytes": path.stat().st_size, "files": len(batch), "uncompressed_bytes": sum(r["bytes"] for r in batch), "sha256": digest_file(path), "largest_member_rehashed": sample["path"]}
        archive_records.append(record)
        print(json.dumps({"completed": number, "of": len(batches), "asset": name, "MiB": round(record["bytes"] / 1024**2, 2)}, ensure_ascii=True), flush=True)
    excluded = [r for r in rows if r["destination"] == "excluded"]
    dump(META / "FILE_MANIFEST.json", {"title": "\u6b63\u5f0f\u7b2c\u4e00\u7248\u7814\u7a76\u5185\u5bb9", "date": "2026-11-05", "files": sorted(manifest, key=lambda r: r["path"]), "scope": "B1 algorithm and all existing b1_* research work; metadata added for publication is tracked separately."})
    dump(META / "ASSETS.json", archive_records)
    dump(META / "EXCLUDED_FILES.json", excluded)
    sums = "".join(f"{r['sha256']}  {r['asset']}\n" for r in archive_records)
    (META / "SHA256SUMS.txt").write_text(sums, encoding="utf-8")
    dump(LOCAL / "pack_validation.json", {"passed": True, "git_files": sum(r["destination"] == "git" for r in manifest), "archive_files": sum(r["destination"] == "archive" for r in manifest), "excluded_files": len(excluded), "source_bytes": sum(r["bytes"] for r in manifest), "assets": archive_records, "credential_scan": "passed", "archive_member_names_sizes_checked": True, "largest_member_of_each_archive_rehashed": True, "no_research_models_refitted": True})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["plan", "pack"])
    args = parser.parse_args()
    make_plan() if args.stage == "plan" else pack()
