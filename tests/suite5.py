"""Part five: real world scale, and the grid must never move when it scales.

The scale check is the one David has been bitten by before, so it is tested from
both ends: the card's translate must not change at all across a wide range of
sizes, and the rendered grid's centre must not move either. A translate that
holds while the render drifts would still be a bug.
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
    horizon, so the centre of mass rises even though the card has not moved.
    What must hold is containment, a smaller grid sitting inside the footprint
    of a larger one.
    """
    x0 = y0 = 10 ** 9
    x1 = y1 = -10 ** 9
    n = 0
    for i, row in enumerate(rows):
        y = len(rows) - 1 - i
        for x, px in enumerate(row):
            if px[0] > 140 and 60 < px[1] < 200 and px[2] < 90:
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
card = s.node("floorgrid")

# ---------------------------------------------------- 25. scale must not move it
print("\n=== 25. changing grid size must not move the grid ===")
s["unit"].setValue(0)
s["camera_height"].setValue(5.5)
s["cellsize"].setValue(2.0)
s["griddistance"].setValue(20.0)
places = []
for sz in (8.0, 20.0, 40.0, 90.0, 160.0, 240.0):
    s["gridsize"].setValue(sz)
    places.append([round(v, 6) for v in card["translate"].value()])
check("card translate is identical at every size",
      all(p == places[0] for p in places), str(places[0]))
rot = []
for sz in (8.0, 240.0):
    s["gridsize"].setValue(sz)
    rot.append([round(v, 6) for v in card["rotate"].value()])
check("card rotation is identical at every size", rot[0] == rot[1], str(rot[0]))

# the render has to agree, not just the knob
icam0 = s.node("cam")
projected = []
for sz in (8.0, 30.0, 120.0, 240.0):
    s["gridsize"].setValue(sz)
    t = card["translate"].value()
    projected.append([round(v, 3) for v in project_point(icam0, t)])
check("the card centre projects to the same pixel at every size",
      all(p == projected[0] for p in projected), str(projected[0]))

s["gridsize"].setValue(30.0)
b1 = grid_bbox(render(s, "sz30"))
s["gridsize"].setValue(120.0)
b2 = grid_bbox(render(s, "sz120"))
check("grid is actually drawn at both sizes", b1[4] > 200 and b2[4] > 200,
      "%d and %d px" % (b1[4], b2[4]))
check("bigger grid really is bigger", b2[4] > b1[4] * 1.3,
      "%d -> %d px" % (b1[4], b2[4]))
check("the smaller grid sits inside the larger one",
      b1[0] is not None and b2[0] is not None
      and b2[0] <= b1[0] + 2 and b2[1] <= b1[1] + 2
      and b2[2] >= b1[2] - 2 and b2[3] >= b1[3] - 2,
      "small %s  large %s" % (str(b1[:4]), str(b2[:4])))

# ---------------------------------------------------- 26. real world scale
print("\n=== 26. camera height sets the scale ===")
icam = s.node("cam")
s["camera_height"].setValue(5.5)
check("camera sits at the height you set", abs(icam["translate"].value()[1] - 5.5) < 1e-6,
      "%.3f" % icam["translate"].value()[1])
s["camera_height"].setValue(12.0)
check("camera follows the height knob", abs(icam["translate"].value()[1] - 12.0) < 1e-6,
      "%.3f" % icam["translate"].value()[1])
check("floor stays on the ground plane", abs(card["translate"].value()[1]) < 1e-6,
      "card y %.4f" % card["translate"].value()[1])
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
s["gridsize"].setValue(40.0)
s["griddistance"].setValue(20.0)
s["gridoffset"].setValue([3.0, 0.0, -4.0])
ft = [s[k].value() for k in ("camera_height", "cellsize", "gridsize", "griddistance")]
shape_ft = [round(v / s["cellsize"].value(), 6) for v in
            (s["camera_height"].value(), s["gridsize"].value(), s["griddistance"].value())]

s["unit"].setValue(1)                       # to metres
dhPersp.convert_units(s)
m = [s[k].value() for k in ("camera_height", "cellsize", "gridsize", "griddistance")]
check("feet to metres converts every length",
      all(abs(a * 0.3048 - b) < 1e-6 for a, b in zip(ft, m)),
      "height %.4f ft -> %.4f m" % (ft[0], m[0]))
check("the grid offset converts too",
      abs(s["gridoffset"].value()[0] - 3.0 * 0.3048) < 1e-6,
      "%.4f" % s["gridoffset"].value()[0])
shape_m = [round(v / s["cellsize"].value(), 6) for v in
           (s["camera_height"].value(), s["gridsize"].value(), s["griddistance"].value())]
check("the setup is physically unchanged by the switch",
      all(abs(a - b) < 1e-4 for a, b in zip(shape_ft, shape_m)),
      "cells: %s vs %s" % (shape_ft, shape_m))

s["unit"].setValue(2)                       # to centimetres
dhPersp.convert_units(s)
check("metres to centimetres is a factor of a hundred",
      abs(s["camera_height"].value() - m[0] * 100.0) < 1e-4,
      "%.3f cm" % s["camera_height"].value())
s["unit"].setValue(0)                       # back to feet
dhPersp.convert_units(s)
check("a full round trip returns the original numbers",
      all(abs(s[k].value() - v) < 1e-4 for k, v in
          zip(("camera_height", "cellsize", "gridsize", "griddistance"), ft)),
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
