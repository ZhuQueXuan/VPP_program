"""Read the official LCL ZIP index and bounded anonymous samples via HTTP Range."""
import hashlib
import io
import json
import struct
import sys
import urllib.request
import zipfile
from pathlib import Path

URL = "https://data.london.gov.uk/download/2y5k8/c869f8ac-33d3-4cf9-bf28-d89c61bbc7a2/EV%20Load%20Profiles.zip"
LENGTH = 121006788
ETAG = '"66f6c8c234730c875c7b33c7dc4db2db"'
LIMIT = 3_000_000
HERE = Path(__file__).resolve().parent


class Remote(io.RawIOBase):
    def __init__(self):
        self.pos = 0
        self.trace = []

    def seekable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, off, whence=0):
        self.pos = (0, self.pos, LENGTH)[whence] + off
        if self.pos < 0:
            raise ValueError("negative seek")
        return self.pos

    def read(self, n=-1):
        end = min(LENGTH, self.pos + n) if n >= 0 else LENGTH
        if end <= self.pos:
            return b""
        if sum(x["bytes"] for x in self.trace) + end - self.pos > LIMIT:
            raise RuntimeError("stop: byte budget")
        expected = f"bytes {self.pos}-{end-1}/{LENGTH}"
        req = urllib.request.Request(URL, headers={
            "Range": f"bytes={self.pos}-{end-1}", "User-Agent": "curl",
            "Accept-Encoding": "identity"
        })
        with urllib.request.urlopen(req, timeout=18) as res:
            if (res.status != 206 or res.headers.get("Content-Range") != expected
                    or res.headers.get("ETag") != ETAG):
                raise RuntimeError(f"stop: archive version or range mismatch ({res.status})")
            b = res.read(end - self.pos + 1)
        if len(b) != end - self.pos:
            raise RuntimeError("stop: truncated range")
        self.trace.append({"range": expected, "bytes": len(b),
                           "sha256": hashlib.sha256(b).hexdigest()})
        self.pos = end
        return b


class Slice(io.RawIOBase):
    def __init__(self, remote, member):
        self.remote = remote
        self.pos = 0
        self.size = member.file_size
        if member.compress_type != zipfile.ZIP_STORED:
            raise ValueError("cannot seek nested compressed archive")
        remote.seek(member.header_offset)
        local = remote.read(30)
        if local[:4] != b"PK\x03\x04":
            raise ValueError("invalid member header")
        name_bytes, extra_bytes = struct.unpack_from("<HH", local, 26)
        self.start = member.header_offset + 30 + name_bytes + extra_bytes

    def tell(self):
        return self.pos

    def seekable(self):
        return True

    def seek(self, off, whence=0):
        self.pos = (0, self.pos, self.size)[whence] + off
        if self.pos < 0:
            raise ValueError("negative seek")
        return self.pos

    def read(self, n=-1):
        n = self.size - self.pos if n < 0 else min(n, self.size - self.pos)
        if n <= 0:
            return b""
        self.remote.seek(self.start + self.pos)
        b = self.remote.read(n)
        self.pos += len(b)
        return b


def directory(z):
    return [{"member": x.filename, "bytes": x.file_size, "compressed": x.compress_size,
             "crc32": f"{x.CRC:08x}"} for x in z.infolist()]


def save_sample(z, x, dest):
    if x.file_size > 12_000_000:
        raise RuntimeError("stop: member too large")
    data = z.read(x)  # verifies member CRC
    saved = b"".join(data.splitlines(keepends=True)[:61]) if x.filename.lower().endswith(".csv") else data
    (HERE / dest).write_bytes(saved)
    return {"member": x.filename, "path": dest, "member_bytes": len(data),
            "member_sha256": hashlib.sha256(data).hexdigest(), "saved_bytes": len(saved),
            "saved_sha256": hashlib.sha256(saved).hexdigest()}


def main():
    stream = Remote()
    out = {"url": URL, "length": LENGTH, "etag": ETAG,
           "network_byte_limit": LIMIT, "ranges": stream.trace, "samples": []}
    metadata_only = sys.argv[1:] == ["--dictionary"]
    nested = sys.argv[1:] == ["--nested"] or metadata_only
    target = ("lcl_members.json" if not sys.argv[1:] else
              "lcl_dictionary_access.json" if metadata_only else "lcl_sample_access.json")
    try:
        with zipfile.ZipFile(stream) as z:
            out["directory"] = directory(z)
            if nested:
                out["nested_directory"] = {}
                if not metadata_only:
                    cover = next(x for x in z.infolist() if x.filename.endswith(".docx"))
                    out["samples"].append(save_sample(z, cover, "lcl_cover_note.docx"))
                for name in sorted(x.filename for x in z.infolist() if x.filename.endswith(".zip")):
                    if metadata_only and "Public" in name:
                        continue
                    with zipfile.ZipFile(Slice(stream, z.getinfo(name))) as sub:
                        out["nested_directory"][name] = directory(sub)
                        if metadata_only:
                            for x in sub.infolist():
                                base = Path(x.filename).name.lower()
                                if base == "read me.txt" or base == "token vs recruit id..xlsx":
                                    label = "commercial" if "Commercial" in name else "residential"
                                    dest = f"lcl_sample_{label}_{'readme.txt' if base.endswith('.txt') else 'crosswalk.xlsx'}"
                                    out["samples"].append(dict(save_sample(sub, x, dest), nested_archive=name))
                            continue
                        if "Residential" not in name:
                            continue
                        # Choose by filename, not outcome, and bound full decompression.
                        picks = sorted(x.filename for x in sub.infolist()
                                       if x.filename.lower().endswith(".csv")
                                       and 1000 < x.file_size < 8_000_000
                                       and x.compress_size < 750_000
                                       and "survey" not in x.filename.lower())[:2]
                        for i, member in enumerate(picks, 1):
                            s = save_sample(sub, sub.getinfo(member), f"lcl_residential_sample_{i}.csv")
                            out["samples"].append(dict(s, nested_archive=name))
            else:
                for i, name in enumerate(sys.argv[1:], 1):
                    dest = f"lcl_sample_{i}{Path(name).suffix.lower()}"
                    out["samples"].append(save_sample(z, z.getinfo(name), dest))
    except Exception as exc:
        out["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        (HERE / target).write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n",
                                   encoding="utf-8")


if __name__ == "__main__":
    main()
