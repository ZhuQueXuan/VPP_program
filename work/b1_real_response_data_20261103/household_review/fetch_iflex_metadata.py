"""Fetch small author-published design metadata only; no meter outcomes."""
from pathlib import Path
import urllib.request
import json
import hashlib
import csv
import io
import sys

HERE = Path(__file__).resolve().parent
SOURCES = {
    "iflex_zenodo_record.json": "https://zenodo.org/api/records/8248802",
    "iflex_price_signals.csv": "https://zenodo.org/records/8248802/files/price_signals.csv?download=1",
    "iflex_experiment_days.csv": "https://zenodo.org/records/8248802/files/experiment_days.csv?download=1",
}
receipt = {}
for name, url in SOURCES.items():
    path = HERE / name
    if path.exists():
        raise FileExistsError(path)
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 source metadata review"})
        with urllib.request.urlopen(request, timeout=25) as response:
            raw = response.read(1048577)
            if len(raw) > 1048576:
                raise ValueError("metadata source unexpectedly exceeds 1 MiB")
        with path.open("xb") as stream:
            stream.write(raw)
        info = dict(url=url, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(), status="downloaded")
        if name.endswith(".csv"):
            rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
            info.update(rows=len(rows), columns=list(rows[0]) if rows else [])
            if "price_signals" in name:
                info.update(price_signal_count=len({r["Price_signal"] for r in rows}),
                            unique_hourly_price_count=len({r["Experiment_price_NOK_kWh"] for r in rows}))
        else:
            record = json.loads(raw)
            info.update(license=record.get("metadata", {}).get("license"),
                        official_rdata=[dict(name=x.get("key"), bytes=x.get("size"), checksum=x.get("checksum"))
                                        for x in record.get("files", []) if "RData" in x.get("key", "")])
        receipt[name] = info
    except Exception as error:
        receipt[name] = dict(url=url, status="failed", error=repr(error))
target = HERE / (sys.argv[1] if len(sys.argv) > 1 else "metadata_fetch_receipt.json")
with target.open("x", encoding="utf-8") as stream:
    json.dump(receipt, stream, ensure_ascii=False, indent=2)
print(json.dumps(receipt, ensure_ascii=False))
