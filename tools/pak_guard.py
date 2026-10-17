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
# SBTextTableAsset .uexp: the first property tag Size (int32 @16) always equals len(uexp) - 49.
# If it lags behind a grown string, the loader stops short and reports "Serial size mismatch".
TEXT_TAG_SIZE_POS = 16
TEXT_TAG_GAP = 49
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


def is_text_table(path):
    return os.sep + "Text" + os.sep in os.path.normpath(path)


def text_tag_size(uexp):
    if len(uexp) < TEXT_TAG_SIZE_POS + 4:
        return None, None
    have = struct.unpack_from("<i", uexp, TEXT_TAG_SIZE_POS)[0]
    return have, len(uexp) - TEXT_TAG_GAP


NATIVE_STRUCTS = {
    "Vector", "Rotator", "Guid", "LinearColor", "Color", "Vector2D", "IntPoint", "DateTime",
    "Timespan", "SoftObjectPath", "GameplayTagContainer", "Quat",
}


def name_map(uasset):
    r = Reader(uasset)
    r.skip(4 + 4 + 4 + 4 + 4)
    r.skip(r.i32() * 20)  # custom versions
    r.skip(4)  # total header
    r.fstring()  # folder name
    r.skip(4)  # flags
    count, offset = r.i32(), r.i32()
    r.p = offset
    names = []
    for _ in range(count):
        n = r.i32()
        if n >= 0:
            names.append(uasset[r.p:r.p + max(n - 1, 0)].decode("latin-1"))
            r.p += n
        else:
            names.append(uasset[r.p:r.p - n * 2 - 2].decode("utf-16le"))
            r.p += -n * 2
        r.skip(4)  # hashes
    return names


class TagWalker:
    """Walk cooked tagged properties and insist that every Size matches the bytes it covers.

    Growing a string inside a text table must update the Size of the StrProperty, of the
    TextTable array inner tag and of the TextTable property itself; a stale one makes the
    loader read garbage ("破損データを検出しました" / Serial size mismatch)."""

    def __init__(self, uexp, names):
        self.d = uexp
        self.names = names

    def fname(self, p):
        i, num = struct.unpack_from("<ii", self.d, p)
        if not 0 <= i < len(self.names):
            raise ValueError("bad FName index %d @%d" % (i, p))
        return self.names[i] + ("_%d" % (num - 1) if num else ""), p + 8

    def tag_header(self, p):
        name, p = self.fname(p)
        if name == "None":
            return None, p
        typ, p = self.fname(p)
        size_pos = p
        size = struct.unpack_from("<i", self.d, p)[0]
        p += 8
        inner = None
        if typ == "StructProperty":
            inner, p = self.fname(p)
            p += 16
        elif typ == "BoolProperty":
            p += 1
        elif typ in ("ByteProperty", "EnumProperty", "ArrayProperty", "SetProperty"):
            inner, p = self.fname(p)
        elif typ == "MapProperty":
            inner, p = self.fname(p)
            _, p = self.fname(p)
        p += 1 + (16 if self.d[p] else 0)
        return (name, typ, inner, size_pos, size), p

    def tags(self, p, end=None):
        while True:
            tag, p = self.tag_header(p)
            if tag is None:
                if end is not None and p != end:
                    raise ValueError("struct ends at %d, Size says %d" % (p, end))
                return p
            name, typ, inner, size_pos, size = tag
            start = p
            stop = start + size
            if stop > len(self.d):
                raise ValueError("%s Size@%d runs past end" % (name, size_pos))
            if typ == "StrProperty":
                n = struct.unpack_from("<i", self.d, start)[0]
                need = 4 + (n if n >= 0 else -n * 2)
                if need != size:
                    raise ValueError("StrProperty %s Size@%d is %d, string needs %d" % (name, size_pos, size, need))
            elif typ == "StructProperty" and inner not in NATIVE_STRUCTS:
                self.tags(start, stop)
            elif typ == "ArrayProperty" and inner == "StructProperty":
                count = struct.unpack_from("<i", self.d, start)[0]
                itag, q = self.tag_header(start + 4)
                if itag is None:
                    raise ValueError("%s array missing inner tag" % name)
                istop = q + itag[4]
                for _ in range(count):
                    q = self.tags(q)
                if q != istop or istop != stop:
                    raise ValueError("%s array elements end at %d, inner Size@%d says %d, outer Size@%d says %d"
                                     % (name, q, itag[3], istop, size_pos, stop))
            p = stop


def text_layout_error(uasset, uexp):
    try:
        end = TagWalker(uexp, name_map(uasset)).tags(0)
    except (ValueError, struct.error, IndexError) as e:
        return str(e)
    if end + 8 != len(uexp):
        return "properties end at %d, uexp is %d" % (end, len(uexp))
    return None


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
        uexp = open(ux, "rb").read()
        try:
            expected, actual, info = inspect(open(ua, "rb").read(), uexp)
        except ValueError as e:
            bad.append("%s: %s" % (rel, e))
            continue
        have, want = text_tag_size(uexp) if is_text_table(ux) else (None, None)
        if have is not None and have != want:
            bad.append("%s: text tag Size %d, payload needs %d" % (rel, have, want))
        if have is not None:
            err = text_layout_error(open(ua, "rb").read(), uexp)
            if err:
                bad.append("%s: %s" % (rel, err))
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
        have, want = text_tag_size(uexp) if is_text_table(ux) else (None, None)
        if have is not None and have != want:
            patched = bytearray(uexp)
            struct.pack_into("<i", patched, TEXT_TAG_SIZE_POS, want)
            uexp = bytes(patched)
            open(ux, "wb").write(uexp)
            fixed.append("%s: text tag Size %d -> %d" % (os.path.relpath(ux, root), have, want))
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
