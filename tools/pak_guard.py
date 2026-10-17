# -*- coding: utf-8 -*-
"""Keep .uasset export headers in sync with .uexp payloads.

The game aborts with "Serial size mismatch: Got X, Expected Y" when a text edit
changes a .uexp's length but the .uasset still records the old SerialSize.

    python pak_guard.py check <dir|pak>   # exit 1 on any mismatch
    python pak_guard.py fix <dir>         # rewrite SerialSize/BulkDataStartOffset in place

Only UE4 cooked packages (legacy file version -7, unversioned or UE4 >= 511) are handled.
"""
import os
import struct
import subprocess
import sys
import tempfile

TAG = 0x9E2A83C1
EXPORT_ENTRY_SIZE = 104
PKG_FILTER_EDITOR_ONLY = 0x80000000
REPAK = os.path.expanduser(r"~/.cargo/bin/repak.exe")


class Reader:
    def __init__(self, data):
        self.d = data
        self.p = 0

    def i32(self):
        v = struct.unpack_from("<i", self.d, self.p)[0]
        self.p += 4
        return v

    def u32(self):
        v = struct.unpack_from("<I", self.d, self.p)[0]
        self.p += 4
        return v

    def i64(self):
        v = struct.unpack_from("<q", self.d, self.p)[0]
        self.p += 8
        return v

    def skip(self, n):
        self.p += n

    def fstring(self):
        n = self.i32()
        if n > 0:
            self.p += n
        elif n < 0:
            self.p += -n * 2

    def engine_version(self):
        self.skip(2 + 2 + 2 + 4)
        self.fstring()


def parse(uasset):
    r = Reader(uasset)
    if r.u32() != TAG:
        raise ValueError("bad tag")
    legacy = r.i32()
    if legacy != -7:
        raise ValueError("unsupported legacy version %d" % legacy)
    r.i32()  # LegacyUE3Version
    ver = r.i32()
    # Unversioned cooks write 0 and use the engine's latest (4.27) layout.
    if ver != 0 and ver < 511:
        raise ValueError("unsupported UE4 version %d" % ver)
    r.i32()  # licensee
    r.skip(r.i32() * 20)  # custom versions
    total_header = r.i32()
    r.fstring()  # folder name
    flags = r.u32()
    if not flags & PKG_FILTER_EDITOR_ONLY:
        raise ValueError("not a cooked package")
    r.skip(8)  # names
    r.skip(8)  # gatherable text
    export_count = r.i32()
    export_offset = r.i32()
    r.skip(8)  # imports
    r.skip(4)  # depends
    r.skip(8)  # soft package refs
    r.skip(4)  # searchable names
    r.skip(4)  # thumbnail table
    r.skip(16)  # guid
    r.skip(r.i32() * 8)  # generations
    r.engine_version()  # saved by
    r.engine_version()  # compatible with
    r.u32()  # compression flags
    if r.i32():
        raise ValueError("compressed chunks")
    r.u32()  # package source
    for _ in range(r.i32()):
        r.fstring()
    r.i32()  # asset registry data offset
    bulk_pos = r.p
    bulk = r.i64()
    exports = []
    for i in range(export_count):
        pos = export_offset + i * EXPORT_ENTRY_SIZE
        size, offset = struct.unpack_from("<qq", uasset, pos + 28)
        exports.append({"pos": pos + 28, "size": size, "offset": offset})
    return {"total_header": total_header, "bulk_pos": bulk_pos, "bulk": bulk, "exports": exports}


def inspect(uasset, uexp):
    """Return (expected_end, actual_end, info)."""
    info = parse(uasset)
    if info["total_header"] != len(uasset):
        raise ValueError("TotalHeaderSize %d != uasset %d" % (info["total_header"], len(uasset)))
    if len(uexp) < 4 or struct.unpack_from("<I", uexp, len(uexp) - 4)[0] != TAG:
        raise ValueError("uexp missing package tag")
    expected = max(e["offset"] + e["size"] for e in info["exports"])
    actual = len(uasset) + len(uexp) - 4
    return expected, actual, info


def pairs(root):
    for base, _, files in os.walk(root):
        for name in files:
            if name.endswith(".uasset"):
                ua = os.path.join(base, name)
                ux = ua[:-7] + ".uexp"
                if os.path.exists(ux):
                    yield ua, ux


def check_dir(root):
    bad = []
    n = 0
    for ua, ux in pairs(root):
        n += 1
        rel = os.path.relpath(ua, root)
        try:
            expected, actual, info = inspect(open(ua, "rb").read(), open(ux, "rb").read())
        except ValueError as e:
            bad.append("%s: %s" % (rel, e))
            continue
        if expected != actual:
            last = max(info["exports"], key=lambda e: e["offset"])
            bad.append("%s: Got %d, Expected %d" % (rel, last["size"] + actual - expected, last["size"]))
        elif info["bulk"] != actual:
            bad.append("%s: BulkDataStartOffset %d, end %d" % (rel, info["bulk"], actual))
    return n, bad


def fix_dir(root):
    fixed = []
    for ua, ux in pairs(root):
        uasset = bytearray(open(ua, "rb").read())
        uexp = open(ux, "rb").read()
        expected, actual, info = inspect(bytes(uasset), uexp)
        if expected == actual and info["bulk"] == actual:
            continue
        rel = os.path.relpath(ua, root)
        notes = []
        if expected != actual:
            if len(info["exports"]) != 1:
                raise SystemExit("%s: %d exports, cannot attribute size change" % (rel, len(info["exports"])))
            e = info["exports"][0]
            struct.pack_into("<q", uasset, e["pos"], e["size"] + actual - expected)
            notes.append("SerialSize %d -> %d" % (e["size"], e["size"] + actual - expected))
        # Cooked packages always place BulkDataStartOffset at the end of the export data.
        if info["bulk"] != actual:
            struct.pack_into("<q", uasset, info["bulk_pos"], actual)
            notes.append("BulkDataStartOffset %d -> %d" % (info["bulk"], actual))
        open(ua, "wb").write(bytes(uasset))
        fixed.append("%s: %s" % (rel, ", ".join(notes)))
    return fixed


def unpack(pak):
    tmp = tempfile.mkdtemp(prefix="pak_guard_")
    subprocess.run([REPAK, "unpack", "-o", tmp, pak], check=True, capture_output=True)
    return tmp


def main():
    if len(sys.argv) != 3 or sys.argv[1] not in ("check", "fix"):
        raise SystemExit(__doc__)
    mode, target = sys.argv[1], sys.argv[2]
    if mode == "fix":
        if not os.path.isdir(target):
            raise SystemExit("fix needs an unpacked directory")
        for line in fix_dir(target):
            print("fixed", line)
    root = unpack(target) if os.path.isfile(target) else target
    n, bad = check_dir(root)
    for line in bad:
        print("MISMATCH", line)
    print("checked %d assets, %d bad" % (n, len(bad)))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
