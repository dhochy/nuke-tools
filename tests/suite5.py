"""Part five: real world scale, and the grid must never move when it scales.

The scale check is the one David has been bitten by before, so it is tested from
both ends, and from the ends that matter: the drawn footprint of the floor, and
the positions of the lines themselves. Checking a transform was what let the
earlier version pass every time while David watched the grid move, because what
moved was the card's edges and nothing was looking at those.
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
    print("  %-4s %-54s %s" % ("PASS" if ok else "FAIL", name, detail))


class _IC(object):
    def name(self):
        return "unit"


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
    path = os.path.join(TMP, "s5_%s.png" % tag).replace("\\", "/")
    w = nuke.nodes.Write(file=path, file_type="png", datatype="8 bit")
    w.setInput(0, node)
    nuke.execute(w, 1, 1)
    nuke.delete(w)
    return read_png(path)


def grid_bbox(rows):
    """Bounding box of the grid pixels, bottom-up y like Nuke.

    The centroid of the drawn pixels is NOT invariant under a pure scale: a
    bigger ground plane reaches further away, and distance compresses toward the
    horizon, so the center of mass rises even though the card has not moved.
    What must hold is containment, a smaller grid sitting inside the footprint
    of a larger one.
    """
    x0 = y0 = 10 ** 9
    x1 = y1 = -10 ** 9
    n = 0
    for i, row in enumerate(rows):
        y = len(rows) - 1 - i
        for x, px in enumerate(row):
            # orange, whether it is a line or ground covered by lines:
            # a window fitted to antialiased lines cannot see solid fill
            if px[0] > 140 and px[1] > 60 and px[1] < px[0] \
                    and px[2] < px[1] - 40:
                x0 = min(x0, x); x1 = max(x1, x)
                y0 = min(y0, y); y1 = max(y1, y)
                n += 1
    return (x0, y0, x1, y1, n) if n else (None, None, None, None, 0)


def project_point(cam, p):
    r = nuke.nodes.Reconcile3D()
    r.setInput(0, plate)
    r.setInput(1, cam)
    a = nuke.nodes.Axis()
    a["translate"].setValue([float(v) for v in p])
    r.setInput(2, a)
    nuke.execute(r, 1, 1)
    o = r["output"].value()
    nuke.delete(a); nuke.delete(r)
    return [float(o[0]), float(o[1])]


s = nuke.createNode("dhPerspSolve", inpanel=False)
s.setInput(0, plate)
for n in nuke.allNodes():
    n.setSelected(False)
s["vp1"].setValue([-2570.0, 640.0])
s["vp2"].setValue([1900.0, 640.0])
s["show_floor"].setValue(True)
s["show_horizon"].setValue(False)

# ---------------------------------------------------- 25. the grid cannot move
print("\n=== 25. the grid has no edges and no size, so nothing moves it ===")
s["unit"].setValue(0)
s["camera_height"].setValue(5.5)
s["cellsize"].setValue(2.0)
hz = 0.5 * (s["vp1"].value()[1] + s["vp2"].value()[1])

# The old measurement asked where the card's center was, and it always answered
# the same thing while David watched the grid move. What moved was the card's
# edges. So the measurement is the drawn footprint now, not a transform.
foot = {}
for cell in (1.0, 2.0, 6.0, 20.0):
    s["cellsize"].setValue(cell)
    foot[cell] = grid_bbox(render(s, "cell%g" % cell))
for cell, b in sorted(foot.items()):
    check("cell %g: the floor is drawn" % cell, b[4] > 200, "%d px" % b[4])
    check("cell %g: it runs off both sides of frame" % cell,
          b[0] is not None and b[0] <= 2 and b[2] >= W - 3,
          "x from %s to %s" % (b[0], b[2]))
    check("cell %g: it starts at the bottom of frame, there is no near edge" % cell,
          b[1] is not None and b[1] <= 2, "lowest row %s" % b[1])
    check("cell %g: and stops just under the horizon, there is no far edge" % cell,
          b[3] is not None and b[3] < hz and hz - b[3] < H / 12.0,
          "highest row %s, horizon %.0f" % (b[3], hz))

# The other thing "it moves" can mean is that the lines themselves shift. Double
# the cell size and every line of the coarse grid should land on a line the fine
# grid already had, because both are measured from the same place on the ground.
def lit_columns(rows, y):
    row = rows[len(rows) - 1 - y]
    return set(x for x, px in enumerate(row)
               if px[0] > 140 and 60 < px[1] < 200 and px[2] < 90)


s["gridoffset"].setValue([0.0, 0.0, 0.0])
s["cellsize"].setValue(1.0)
fine = lit_columns(render(s, "fine"), 30)
s["cellsize"].setValue(2.0)
coarse = lit_columns(render(s, "coarse"), 30)
near = set()
for x in fine:
    near.update((x - 2, x - 1, x, x + 1, x + 2))
stray = sorted(coarse - near)
check("doubling the cell size leaves every remaining line where it was",
      len(stray) <= 2, "%d of %d coarse pixels are not on a fine line %s"
      % (len(stray), len(coarse), stray[:6]))

# and the things that are only about how it is drawn move nothing at all
s["cellsize"].setValue(2.0)
base = grid_bbox(render(s, "base"))
s["gridwidth"].setValue(4.0)
wide = grid_bbox(render(s, "wide"))
# Thicker lines need more room between them before they can be drawn without
# turning into moire, so a wide line runs out further from the horizon. That is
# the fade doing its job, not the floor moving: the sides and the bottom are
# where they were, and those are the edges a card used to have.
check("line width leaves the sides and the bottom exactly where they were",
      wide[0] == base[0] and wide[1] == base[1] and wide[2] == base[2],
      "%s vs %s" % (str(base[:4]), str(wide[:4])))
check("it only changes how far up the lines stay readable",
      wide[3] <= base[3], "runs out at row %s, against %s" % (wide[3], base[3]))
s["gridwidth"].setValue(1.0)

# ---------------------------------------------------- 26. real world scale
print("\n=== 26. camera height sets the scale ===")
icam = s.node("cam")
s["camera_height"].setValue(5.5)
check("camera sits at the height you set", abs(icam["translate"].value()[1] - 5.5) < 1e-6,
      "%.3f" % icam["translate"].value()[1])
s["camera_height"].setValue(12.0)
check("camera follows the height knob", abs(icam["translate"].value()[1] - 12.0) < 1e-6,
      "%.3f" % icam["translate"].value()[1])
# The floor is the plane the camera rays are intersected with, so raising the
# camera cannot lift it off the ground: what changes is how far away everything
# is. A ground point read back at twice the height is twice as far.
was = nuke.sample(s.node("groundxz"), "red", 300.5, 120.5)
s["camera_height"].setValue(24.0)
now = nuke.sample(s.node("groundxz"), "red", 300.5, 120.5)
check("doubling the height doubles the distance, it does not lift the floor",
      abs(now - 2.0 * was) < max(0.01 * abs(was), 1e-4),
      "%.4f -> %.4f" % (was, now))
s["camera_height"].setValue(12.0)
before = (round(s["cam_focal"].value(), 6), round(s["cam_rx"].value(), 6),
          round(s["cam_ry"].value(), 6))
s["camera_height"].setValue(3.0)
after = (round(s["cam_focal"].value(), 6), round(s["cam_rx"].value(), 6),
         round(s["cam_ry"].value(), 6))
check("height does not disturb the solved lens or angles", before == after, str(after))
s["camera_height"].setValue(5.5)

# ---------------------------------------------------- 27. unit conversion
print("\n=== 27. switching units must not move anything ===")
s["unit"].setValue(0)
s["_unit_was"].setValue(0)
s["camera_height"].setValue(5.5)
s["cellsize"].setValue(2.0)
s["gridoffset"].setValue([3.0, 0.0, -4.0])
ft = [s[k].value() for k in ("camera_height", "cellsize")]
shape_ft = [round(v / s["cellsize"].value(), 6) for v in
            (s["camera_height"].value(), s["gridoffset"].value()[0])]

s["unit"].setValue(1)                       # to meters
dhPersp.convert_units(s)
m = [s[k].value() for k in ("camera_height", "cellsize")]
check("feet to meters converts every length",
      all(abs(a * 0.3048 - b) < 1e-6 for a, b in zip(ft, m)),
      "height %.4f ft -> %.4f m" % (ft[0], m[0]))
check("the grid offset converts too",
      abs(s["gridoffset"].value()[0] - 3.0 * 0.3048) < 1e-6,
      "%.4f" % s["gridoffset"].value()[0])
shape_m = [round(v / s["cellsize"].value(), 6) for v in
           (s["camera_height"].value(), s["gridoffset"].value()[0])]
check("the setup is physically unchanged by the switch",
      all(abs(a - b) < 1e-4 for a, b in zip(shape_ft, shape_m)),
      "cells: %s vs %s" % (shape_ft, shape_m))

s["unit"].setValue(2)                       # to centimeters
dhPersp.convert_units(s)
check("meters to centimeters is a factor of a hundred",
      abs(s["camera_height"].value() - m[0] * 100.0) < 1e-4,
      "%.3f cm" % s["camera_height"].value())
s["unit"].setValue(0)                       # back to feet
dhPersp.convert_units(s)
check("a full round trip returns the original numbers",
      all(abs(s[k].value() - v) < 1e-4 for k, v in
          zip(("camera_height", "cellsize"), ft)),
      "height back to %.4f ft" % s["camera_height"].value())

note = s["scale_note"].value()
check("the readout says what a cell is worth", "ft" in note and "m" in note, note[:58])

# ---------------------------------------------------- 28. export in real units
print("\n=== 28. exported camera carries the scale ===")
s["camera_height"].setValue(5.5)
cam = dhPersp.export_camera(s)
check("exported camera is in the main graph", "." not in cam.fullName(), cam.fullName())
check("exported camera sits at the real height",
      abs(cam["translate"].value()[1] - 5.5) < 1e-6,
      "y = %.4f" % cam["translate"].value()[1])
s["camera_height"].setValue(9.25)
check("exported camera follows the height live",
      abs(cam["translate"].value()[1] - 9.25) < 1e-6,
      "y = %.4f" % cam["translate"].value()[1])
check("exported camera states its unit",
      "units" in cam.knobs() and cam["units"].value() == "feet",
      cam["units"].value() if "units" in cam.knobs() else "no units knob")
dhPersp.bake_camera(cam)
s["camera_height"].setValue(2.0)
check("baking freezes the height too",
      abs(cam["translate"].value()[1] - 9.25) < 1e-6,
      "y = %.4f" % cam["translate"].value()[1])

print("\n" + "=" * 80)
npass = sum(1 for _, ok, _ in RESULTS if ok)
print("part 5: %d of %d passed" % (npass, len(RESULTS)))
for n, ok, d in RESULTS:
    if not ok:
        print("   FAILED: %s   %s" % (n, d))
