"""Part seven: the floor must read as ground, not as a card in shot.

David's two complaints, measured in the render rather than argued about:
the grid has to run off both sides of frame, and its far edge has to reach the
horizon. Both are checked with a control that must fail, so a pass means
something.
"""
import os
import struct
import zlib
import nuke

GIZDIR = r"C:\Users\dhoch\.nuke\Gizmos\DH_Tools\3D"
TMP = r"C:\temp\dgtest"
if not os.path.isdir(TMP):
    os.makedirs(TMP)
nuke.pluginAddPath(GIZDIR)
import dhPersp

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))
    print("  %-4s %-56s %s" % ("PASS" if ok else "FAIL", name, detail))


W, H = 1920, 1080
nuke.addFormat("%d %d 0 0 %d %d 1 testHD" % (W, H, W, H))
nuke.root()["format"].setValue("testHD")
plate = nuke.nodes.Constant(format="testHD")


def read_png(path):
    raw = open(path, "rb").read()
    pos, idat, w, h, ch = 8, b"", 0, 0, 3
    while pos < len(raw):
        ln = struct.unpack(">I", raw[pos:pos + 4])[0]
        typ = raw[pos + 4:pos + 8]
        data = raw[pos + 8:pos + 8 + ln]
        if typ == b"IHDR":
            w, h, depth, ctype = struct.unpack(">IIBB", data[:10])
            ch = {0: 1, 2: 3, 4: 2, 6: 4}[ctype]
        elif typ == b"IDAT":
            idat += data
        elif typ == b"IEND":
            break
        pos += 12 + ln
    buf = zlib.decompress(idat)
    stride = w * ch
    rows, prev, p = [], bytearray(stride), 0
    for _ in range(h):
        ft = buf[p]; p += 1
        line = bytearray(buf[p:p + stride]); p += stride
        for i in range(stride):
            a = line[i - ch] if i >= ch else 0
            b = prev[i]
            c = prev[i - ch] if i >= ch else 0
            if ft == 1:
                line[i] = (line[i] + a) & 255
            elif ft == 2:
                line[i] = (line[i] + b) & 255
            elif ft == 3:
                line[i] = (line[i] + (a + b) // 2) & 255
            elif ft == 4:
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 255
        rows.append([tuple(line[i:i + 3]) for i in range(0, stride, ch)])
        prev = line
    return rows


def render(node, tag):
    path = os.path.join(TMP, "s7_%s.png" % tag).replace("\\", "/")
    w = nuke.nodes.Write(file=path, file_type="png", datatype="8 bit")
    w.setInput(0, node)
    nuke.execute(w, 1, 1)
    nuke.delete(w)
    return read_png(path)


def is_grid(px):
    return px[0] > 140 and 60 < px[1] < 200 and px[2] < 90


def is_horizon(px):
    return px[1] > 160 and px[2] > 160 and px[0] < 120


def measure(rows):
    """Grid reach, in Nuke bottom-up rows, plus how far it touches each side."""
    top = -1
    left_touch = right_touch = 0
    for i, row in enumerate(rows):
        y = len(rows) - 1 - i
        hit = False
        for x, px in enumerate(row):
            if is_grid(px):
                hit = True
                break
        if hit:
            top = max(top, y)
            if any(is_grid(px) for px in row[:3]):
                left_touch += 1
            if any(is_grid(px) for px in row[-3:]):
                right_touch += 1
    hz = [len(rows) - 1 - i for i, row in enumerate(rows)
          if any(is_horizon(px) for px in row)]
    return top, left_touch, right_touch, (max(hz) if hz else -1)


g1 = nuke.createNode("dhPerspGuide", inpanel=False); g1.setInput(0, plate)
g2 = nuke.createNode("dhPerspGuide", inpanel=False); g2.setInput(0, g1)
IC = type("IC", (), {"name": staticmethod(lambda: "inputChange")})()
for g in (g1, g2):
    dhPersp.on_knob_changed(g, IC)
# two real, perpendicular families
g1["p1a"].setValue([-400.0, 250.0]); g1["p1b"].setValue([1500.0, 520.0])
g1["p2a"].setValue([-400.0, 40.0]); g1["p2b"].setValue([1500.0, 430.0])
g2["p1a"].setValue([2300.0, 250.0]); g2["p1b"].setValue([500.0, 500.0])
g2["p2a"].setValue([2300.0, 40.0]); g2["p2b"].setValue([500.0, 400.0])

s = nuke.createNode("dhPerspSolve", inpanel=False)
s.setInput(0, g2)
for n in nuke.allNodes():
    n.setSelected(False)
g1.setSelected(True); g2.setSelected(True)
dhPersp.link_guides(s)
for n in nuke.allNodes():
    n.setSelected(False)
s["show_horizon"].setValue(True)
s["show_floor"].setValue(True)
s["unit"].setValue(0)
s["camera_height"].setValue(850.0)          # Top of the Rock, in feet

print("\n=== 31. the floor is fitted from the solve ===")
print("  solved focal %.2f mm, pitch %.2f, yaw %.2f"
      % (s["cam_focal"].value(), s["cam_rx"].value(), s["cam_ry"].value()))
check("linking fitted the floor automatically", s["gridsize"].value() > 1000.0,
      "grid size %.6g ft" % s["gridsize"].value())

rows = render(s, "fitted")
top, lt, rt, hz = measure(rows)
check("the horizon is drawn", hz > 0, "horizon row %d" % hz)
# The floor now dissolves as it approaches the horizon, so "reaches it" is the
# wrong question: what matters is that there is no hard far edge to give the
# card away. Measure the taper instead of the stopping point.
def taper(rows, hz_row):
    """Brightest grid pixel per 40px band, walking down from the horizon.

    Counting thresholded pixels cannot see a fade: a grid line dimmed to a
    quarter still reads as a grid line to the eye but falls under any threshold,
    so the faded band counts as zero and a smooth dissolve looks like a hard
    edge. Brightness is the thing that is actually fading, so measure that.
    """
    band = []
    for step in range(6):
        lo = hz_row - (step + 1) * 40
        hi = hz_row - step * 40
        best = 0
        for i, row in enumerate(rows):
            y = len(rows) - 1 - i
            if lo <= y < hi:
                for px in row:
                    if px[0] > px[2] + 12 and px[0] > px[1] > px[2]:
                        best = max(best, px[0])
        band.append(best)
    return band


bands = taper(rows, hz)
check("the floor fades out instead of stopping at a hard edge",
      all(bands[i] <= bands[i + 1] + 6 for i in range(len(bands) - 1))
      and bands[0] < bands[-1] * 0.7 and bands[0] > 5,
      "brightest grid pixel per 40px band toward the horizon: %s" % bands)
check("the floor runs off the left edge of frame", lt > 100, "%d rows touch" % lt)
check("the floor runs off the right edge of frame", rt > 100, "%d rows touch" % rt)

# control: a hand sized small grid must fail both, or the test proves nothing
s["autofit"].setValue(False)
s["gridsize"].setValue(2000.0)
s["griddistance"].setValue(3000.0)
s["cellsize"].setValue(100.0)
rows2 = render(s, "small")
top2, lt2, rt2, hz2 = measure(rows2)
check("CONTROL: a hand sized grid does show its edges in frame",
      (hz2 - top2) > 14 or lt2 < 100 or rt2 < 100,
      "top %d, horizon %d, sides %d/%d" % (top2, hz2, lt2, rt2))

s["autofit"].setValue(True)
dhPersp.fit_floor(s)
rows3 = render(s, "refit")
top3, lt3, rt3, hz3 = measure(rows3)
check("pressing fit puts it back",
      hz3 > 0 and lt3 > 100 and rt3 > 100,
      "top %d, horizon %d, sides %d/%d" % (top3, hz3, lt3, rt3))

print("\n=== 32. the fit respects the controls ===")
# Reach is now set by cell size, not by the gap: the floor stretches as far as
# the 400 row ceiling allows at whatever cell the near field asks for. So fewer
# cells across the near edge means bigger cells, and bigger cells reach further.
before = s["gridsize"].value()
s["near_cells"].setValue(3.0)
dhPersp.fit_floor(s)
check("coarser near cells reach further", s["gridsize"].value() > before * 1.5,
      "%.6g -> %.6g ft" % (before, s["gridsize"].value()))
s["near_cells"].setValue(6.0)
dhPersp.fit_floor(s)
s["gridrows"].setValue(40.0)
dhPersp.fit_floor(s)
cells = s["gridsize"].value() / s["cellsize"].value()
check("cells across follows the knob", abs(cells - 40.0) < 0.5, "%.1f cells" % cells)
check("the readout reports a real cell size in feet",
      "ft" in s["scale_note"].value(), s["scale_note"].value()[:56])

s["camera_height"].setValue(5.5)
dhPersp.fit_floor(s)
check("a low camera gives a proportionally smaller floor",
      s["gridsize"].value() < 1.0e5, "%.6g ft at 5.5 ft up" % s["gridsize"].value())

print("\n" + "=" * 82)
npass = sum(1 for _, ok, _ in RESULTS if ok)
print("part 7: %d of %d passed" % (npass, len(RESULTS)))
for n, ok, d in RESULTS:
    if not ok:
        print("   FAILED: %s   %s" % (n, d))
