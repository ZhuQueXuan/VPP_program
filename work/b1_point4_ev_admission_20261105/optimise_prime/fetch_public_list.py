"""List the published UKPN release using its public read-only catalogue link."""
import html
import hashlib
import json
import os
import re
import sys
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


CATALOGUE = "https://opennetzero.org/uk-power-networks/project-optimise-prime-commercial-electric-vehicles-trial"
BLOB = "https://ukpnoppublicdata001.blob.core.windows.net/optimiseprime"
OUT = Path(__file__).resolve().parent


def read_bytes(url, cap, byte_range=None):
    headers = {"User-Agent": "Research data admission audit/1.0"}
    if byte_range:
        headers["Range"] = byte_range
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=12) as response:
        if byte_range and response.status != 206:
            raise ValueError("Server did not honour the partial read request")
        data = response.read(cap + 1)
        if len(data) > cap:
            raise ValueError("Response exceeds the audit byte cap")
        return data


def public_signature():
    published = os.environ.get("OP_PUBLISHED_READ_LIST_QUERY")
    if published:
        return published
    page = html.unescape(read_bytes(CATALOGUE, 3_000_000).decode("utf-8"))
    match = re.search(r"sv=[^&\s\"<]+&ss=b&srt=sco&sp=rl&se=[^&\s\"<]+&st=[^&\s\"<]+&spr=https&sig=[^&\s\"<]+", page)
    if match is None:
        raise ValueError("Read/list URL not present in the publisher's syndicated metadata")
    return match.group()


def listing(prefix, signature, count=100):
    query = urllib.parse.urlencode({
        "restype": "container", "comp": "list", "delimiter": "/",
        "maxresults": count, "prefix": prefix,
    })
    blob_list = read_bytes(BLOB + "?" + query + "&" + signature, 250_000)
    root = ET.fromstring(blob_list)
    return {
        "names": [node.text for node in root.findall(".//Name")],
        "files": [
            {"path": node.findtext("Name"), "bytes": int(node.findtext("Properties/Content-Length"))}
            for node in root.findall(".//Blob")
        ],
        "listing_sha256": hashlib.sha256(blob_list).hexdigest(),
        "has_more": bool(root.findtext(".//NextMarker")),
    }


def save_sample(name, cap, source, signature, byte_range=None):
    url = BLOB + "/" + urllib.parse.quote(source["path"])
    data = read_bytes(url + "?" + signature, cap, byte_range)
    (OUT / name).write_bytes(data)
    return {"url_without_public_signature": url, "file": name,
            "stored_bytes": len(data), "source_bytes": source["bytes"],
            "sha256": hashlib.sha256(data).hexdigest(), "range": byte_range}


def fetch_meter_windows(signature):
    directory = json.loads((OUT / "release_directory.json").read_text(encoding="utf-8"))
    meter = next(item for item in directory["listings"]["27"]["files"] if item["path"].endswith("/depot_load.csv"))
    width = 65_536
    # Fixed positions in file order, selected without inspecting metered values.
    offsets = [meter["bytes"] * percent // 100 for percent in (10, 25, 40, 55, 70, 85)]
    inputs = [
        (f"table_27_{offset}.csv.part", width, meter, signature, f"bytes={offset}-{offset + width - 1}")
        for offset in offsets
    ]
    with ThreadPoolExecutor(max_workers=6) as pool:
        samples = list(pool.map(lambda args: save_sample(*args), inputs))
    (OUT / "meter_window_bytes.json").write_text(json.dumps(samples, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(samples, indent=2))


def fetch_trace(signature):
    directory = json.loads((OUT / "release_directory.json").read_text(encoding="utf-8"))
    inputs = []
    for number, month in (("25", "202108"), ("25", "202109"), ("26", "202109"),
                          ("25", "202111"), ("26", "202111")):
        source = next(item for item in directory["listings"][number]["files"]
                      if item["path"].endswith(f"_{month}.csv"))
        inputs.append((f"table_{number}_{month}.csv", 1_500_000, source, signature))
    with ThreadPoolExecutor(max_workers=5) as pool:
        samples = list(pool.map(lambda args: save_sample(*args), inputs))
    (OUT / "trace_bytes.json").write_text(json.dumps(samples, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(samples, indent=2))


def main():
    signature = public_signature()
    if sys.argv[1:] == ["--meter-windows"]:
        fetch_meter_windows(signature)
        return
    if sys.argv[1:] == ["--trace"]:
        fetch_trace(signature)
        return
    listings = {"": listing("", signature), "WS2/": listing("WS2/", signature)}
    identifiers = ("10", "25", "26", "27", "30", "31")
    directories = {
        number: next(name for name in listings["WS2/"]["names"] if name.startswith(f"WS2/Table {number} "))
        for number in identifiers
    }
    with ThreadPoolExecutor(max_workers=6) as pool:
        detailed = dict(zip(identifiers, pool.map(lambda p: listing(p, signature), directories.values())))
    listings.update(detailed)
    # Keep the public token out of files and reports.
    (OUT / "release_directory.json").write_text(
        json.dumps({"endpoint": BLOB, "delimiter": "/", "listings": listings}, indent=2) + "\n",
        encoding="utf-8",
    )
    inputs = [
        (f"table_{number}.csv", 2_000_000,
         next(item for item in detailed[number]["files"] if item["path"].endswith(".csv")), signature, None)
        for number in ("30", "31")
    ]
    meter = next(item for item in detailed["27"]["files"] if item["path"].endswith("/depot_load.csv"))
    inputs.append(("table_27_head.csv.part", 262_144, meter, signature,
                   "bytes=0-262143"))
    with ThreadPoolExecutor(max_workers=3) as pool:
        samples = list(pool.map(lambda args: save_sample(*args), inputs))
    (OUT / "source_bytes.json").write_text(json.dumps(samples, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(samples, indent=2))


if __name__ == "__main__":
    main()
