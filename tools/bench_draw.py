"""Time the drawing, and prove a change to it did not alter a single pixel.

The guide and the solve draw everything with per pixel Expression nodes, and
those expressions have grown large: the guide evaluates all fourteen possible
lines at every pixel, and works out each line's length, square root included,
inside that per pixel loop even though the length is the same everywhere.

Anything done about that has to be provably invisible. So this does two jobs
from one setup. Run it with `save` and it renders a set of configurations to
PNG and keeps them as the reference. Run it with `check` and it renders them
again and compares every pixel against those files, and reports the timings
either way.

    Nuke17.0.exe -t tools/bench_draw.py save
    ...make the change...
    Nuke17.0.exe -t tools/bench_draw.py check

The configurations are chosen to reach the parts that differ: nothing added, a
few added lines attached to the vanishing point, a few detached on two points,
and the full twelve, because an expression that is only exercised with its
slots empty proves nothing about the branch that draws them.
"""
import os
import struct
import sys
import time
import zlib
import nuke

nuke.pluginAddPath(r"C:\Users\dhoch\.nuke\Gizmos\DH_Tools\3D")
import dhPersp

MODE = (sys.argv[1] if len(sys.argv) > 1 else "check").lower()
REF = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "..", "tests", "fixtures", "bench")
REF = os.path.abspath(REF)
TMP = r"C:\temp\dgtest\bench"
for d in (REF, TMP):
    if not os.path.isdir(d):
        os.makedirs(d)

W, H = 1024, 683
nuke.addFormat("%d %d 0 0 %d %d 1 bench" % (W, H, W, H))
nuke.root()["format"].setValue("bench")
plate = nuke.nodes.Constant(format="bench", color=0.2)

g1 = nuke.createNode("dhPerspGuide", inpanel=False)
g1.setInput(0, plate)
g1["p1a"].setValue([60.0, 120.0]); g1["p1b"].setValue([900.0, 300.0])
g1["p2a"].setValue([60.0, 560.0]); g1["p2b"].setValue([900.0, 430.0])
g2 = nuke.createNode("dhPerspGuide", inpanel=False)
g2.setInput(0, g1)
g2["role"].setValue("across")
g2["p1a"].setValue([980.0, 140.0]); g2["p1b"].setValue([120.0, 330.0])
g2["p2a"].setValue([980.0, 540.0]); g2["p2b"].setValue([120.0, 450.0])
s = nuke.createNode("dhPerspSolve", inpanel=False)
s.setInput(0, g2)
for n in nuke.allNodes():
    n.setSelected(False)
dhPersp.on_knob_changed(
    s, type("IC", (), {"name": staticmethod(lambda: "inputChange")})())
s["camera_height"].setValue(5.5)
s["cellsize"].setValue(2.0)


def add_lines(g, count, pinned):
    """Turn on `count` added lines, attached to the vanishing point or not."""
    for i in range(1, 13):
        on = i <= count
        g["use_add%d" % i].setValue(on)
        if not on:
            continue
        g["pin%d" % i].setValue(pinned)
        g["add%d" % i].setValue([120.0 + i * 60.0, 180.0 + i * 25.0])
        if not pinned:
            g["add%db" % i].setValue([820.0 - i * 40.0, 520.0 - i * 18.0])


CASES = [
    # The control. A Constant does no work at all, so whatever this costs is
    # Nuke's execute plus PNG encoding, and every other row has to be read as
    # the number above this one. Without it the harness reports the write time
    # as if it were the expression time, which is a benchmark that lies.
    ("control_constant", plate, 0, True),
    ("guide_plain", g2, 0, True),
    ("guide_4_pinned", g2, 4, True),
    ("guide_4_loose", g2, 4, False),
    ("guide_12_pinned", g2, 12, True),
    ("guide_12_loose", g2, 12, False),
    ("solve_plain", s, 0, True),
    ("solve_12_pinned", s, 12, True),
]


def render(node, path):
    w = nuke.nodes.Write(file=path.replace("\\", "/"), file_type="png",
                         datatype="8 bit")
    w.setInput(0, node)
    nuke.execute(w, 1, 1)
    nuke.delete(w)


def png_bytes(path):
    """Raw decoded rows, so two renders can be compared pixel by pixel."""
    raw = open(path, "rb").read()
    pos, idat, w_, h_, ch = 8, b"", 0, 0, 3
    while pos < len(raw):
        ln = struct.unpack(">I", raw[pos:pos + 4])[0]
        typ = raw[pos + 4:pos + 8]
        data = raw[pos + 8:pos + 8 + ln]
        if typ == b"IHDR":
            w_, h_, depth, ctype = struct.unpack(">IIBB", data[:10])
            ch = {0: 1, 2: 3, 4: 2, 6: 4}[ctype]
        elif typ == b"IDAT":
            idat += data
        elif typ == b"IEND":
            break
        pos += 12 + ln
    d = zlib.decompress(idat)
    stride = w_ * ch
    out, prev, i = [], bytearray(stride), 0
    for _ in range(h_):
        f = d[i]
        i += 1
        line = bytearray(d[i:i + stride])
        i += stride
        for x in range(stride):
            a = line[x - ch] if x >= ch else 0
            b = prev[x]
            c = prev[x - ch] if x >= ch else 0
            if f == 1:
                line[x] = (line[x] + a) & 255
            elif f == 2:
                line[x] = (line[x] + b) & 255
            elif f == 3:
                line[x] = (line[x] + (a + b) // 2) & 255
            elif f == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[x] = (line[x] + pr) & 255
        out.append(bytes(line))
        prev = line
    return w_, h_, ch, out


print("mode: %s" % MODE)
print("%-20s %10s   %s" % ("case", "render", "pixels"))
worst_name, worst_n, worst_amt = "", 0, 0
for name, node, count, pinned in CASES:
    add_lines(g2, count, pinned)
    out = os.path.join(TMP, name + ".png")
    # nudge so nothing is served from cache, then time a clean render
    g1["p1b"].setValue([900.0, 300.0])
    render(node, out)
    a = time.time()
    g1["p1b"].setValue([901.0, 301.0])
    render(node, out)
    g1["p1b"].setValue([900.0, 300.0])
    render(node, out)
    ms = 1000.0 * (time.time() - a) / 2.0

    ref = os.path.join(REF, name + ".png")
    verdict = ""
    if MODE == "save":
        open(ref, "wb").write(open(out, "rb").read())
        verdict = "saved as the reference"
    elif not os.path.exists(ref):
        verdict = "NO REFERENCE, run with save first"
    else:
        aw, ah, ach, arows = png_bytes(ref)
        bw, bh, bch, brows = png_bytes(out)
        if (aw, ah, ach) != (bw, bh, bch):
            verdict = "SIZE CHANGED %dx%dx%d vs %dx%dx%d" % (aw, ah, ach,
                                                             bw, bh, bch)
        else:
            n, amt = 0, 0
            for y in range(ah):
                ra, rb = arows[y], brows[y]
                if ra == rb:
                    continue
                for i in range(len(ra)):
                    if ra[i] != rb[i]:
                        n += 1
                        amt = max(amt, abs(ra[i] - rb[i]))
            verdict = ("identical" if n == 0
                       else "%d samples differ, worst by %d of 255" % (n, amt))
            if n > worst_n:
                worst_name, worst_n, worst_amt = name, n, amt
    print("%-20s %8.0f ms   %s" % (name, ms, verdict))

if MODE != "save":
    print("")
    if worst_n == 0:
        print("every case is pixel for pixel what it was.")
    else:
        print("NOT IDENTICAL. worst case %s, %d samples, up to %d of 255."
              % (worst_name, worst_n, worst_amt))
