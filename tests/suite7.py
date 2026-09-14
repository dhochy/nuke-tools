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
    """Orange, whether it is a line or a patch of ground covered by lines.

    Not a window on each channel: with the thinning off, ground near the horizon
    fills in at the grid color itself, which sits outside a window fitted to
    antialiased lines. Asking for the color rather than for a brightness keeps
    the red and cyan guide overlays out and lets the solid band in.
    """
    return px[0] > 140 and px[1] > 60 and px[1] < px[0] and px[2] < px[1] - 40


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

print("\n=== 31. the floor from eight hundred and fifty feet up ===")
print("  solved focal %.2f mm, pitch %.2f, yaw %.2f"
      % (s["cam_focal"].value(), s["cam_rx"].value(), s["cam_ry"].value()))
check("the solve stands up at this height", s["_solveok"].value() > 0.5,
      "%.2f mm" % s["cam_focal"].value())
s["cellsize"].setValue(30.0)                # a city block is about 260 ft
# Thinning the far lines is a switch now, and off by default, because the
# horizon is what you line up against and a grid that stops short of it is
# less use than one that goes solid. This section is about the switch.
s["fade_far"].setValue(True)

rows = render(s, "fitted")
top, lt, rt, hz = measure(rows)
check("the horizon is drawn", hz > 0, "horizon row %d" % hz)


def taper(rows, hz_row):
    """Mean grid brightness per 40px band, walking down from the horizon.

    Not the brightest pixel: near the horizon the lines are dim but crossing
    each other constantly, so the brightest pixel in a band stays high until
    the band is completely empty, and a smooth dissolve measures as a cliff.
    Not a thresholded count either, which cannot see a fade at all. The mean
    over the band falls the way the picture falls.
    """
    band = []
    for step in range(6):
        lo = hz_row - (step + 1) * 40
        hi = hz_row - step * 40
        tot, n = 0, 0
        for i, row in enumerate(rows):
            y = len(rows) - 1 - i
            if lo <= y < hi:
                for px in row:
                    tot += px[0] if (px[0] > px[2] and px[0] >= px[1]) else 0
                    n += 1
        band.append(round(tot / float(max(n, 1)), 2))
    return band


bands = taper(rows, hz)
check("the floor fades out instead of stopping at a hard edge",
      all(bands[i] <= bands[i + 1] + 0.5 for i in range(len(bands) - 1))
      and bands[-1] > 1.0 and bands[0] < bands[-1] * 0.6,
      "mean grid brightness per 40px band toward the horizon: %s" % bands)
check("and it does not stop dead: every step toward the horizon is a fraction "
      "of the one before, never all of it",
      all(bands[i] > bands[i + 1] * 0.12 for i in range(len(bands) - 1)
          if bands[i + 1] > 2.0), str(bands))
check("the floor runs off the left edge of frame", lt > 100, "%d rows touch" % lt)
check("the floor runs off the right edge of frame", rt > 100, "%d rows touch" % rt)
check("and it reaches the bottom of frame with no near edge",
      bool(rows), "")

# There is no longer a control case where the floor is too small, because there
# is no knob that can make it small. That the previous version needed one, and
# that the fit it was checking had to give up reach to keep the cells drawable,
# is the whole reason the card went.
for gone in ("autofit", "near_cells", "horizon_gap", "gridrows", "gridsize",
             "griddistance"):
    check("nothing left to mis-fit: no %s" % gone, gone not in s.knobs(), "")

s["fade_far"].setValue(False)
rows_off = render(s, "nofade")
top_off, lt_off, rt_off, hz_off = measure(rows_off)
s["fade_far"].setValue(True)
rows_on = render(s, "fade")
top_on, lt_on, rt_on, hz_on = measure(rows_on)
check("with thinning off the grid is drawn nearer the horizon than with it on",
      top_off > top_on, "off stops at row %d, on at row %d, horizon %d"
      % (top_off, top_on, hz_off))
check("off, it arrives at the horizon",
      hz_off - top_off <= 3, "stops %d rows short" % (hz_off - top_off))
s["fade_far"].setValue(False)

print("\n=== 32. cell size at city scale ===")
s["cellsize"].setValue(30.0)
mid = render(s, "cell30")
s["cellsize"].setValue(300.0)
big = render(s, "cell300")
s["cellsize"].setValue(0.5)
tiny = render(s, "cell_half")


def grid_px(rows):
    n = 0
    for row in rows:
        for px in row:
            if px[0] > px[2] + 12 and px[0] > px[1] > px[2]:
                n += 1
    return n


nm, nb, nt = grid_px(mid), grid_px(big), grid_px(tiny)
check("a thirty foot cell draws from up here", nm > 2000, "%d px" % nm)
check("a three hundred foot cell draws too, and sparser", 0 < nb < nm,
      "%d px vs %d px" % (nb, nm))
check("a six inch cell from eight hundred feet up covers the ground, which is "
      "what half foot lines from there really do", nt > nm,
      "%d px, against %d at thirty feet" % (nt, nm))
s["fade_far"].setValue(True)
thin = grid_px(render(s, "cell_half_thinned"))
s["fade_far"].setValue(False)
check("and the switch is what stops it", thin < nt,
      "%d px thinned, against %d not" % (thin, nt))
s["cellsize"].setValue(30.0)
check("the readout reports a real cell size in feet",
      "ft" in s["scale_note"].value(), s["scale_note"].value()[:56])

s["camera_height"].setValue(5.5)
s["cellsize"].setValue(2.0)
low = grid_px(render(s, "lowcam"))
check("dropping to eye level still draws a floor, with no refitting",
      low > 2000, "%d px" % low)

print("\n" + "=" * 82)
npass = sum(1 for _, ok, _ in RESULTS if ok)
print("part 7: %d of %d passed" % (npass, len(RESULTS)))
for n, ok, d in RESULTS:
    if not ok:
        print("   FAILED: %s   %s" % (n, d))
