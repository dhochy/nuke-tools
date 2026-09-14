"""Part three: the parts neither earlier suite touches.

Where something is drawn, this renders it to disk and counts pixels rather than
trusting a knob value, and every render check carries a control that must change.
"""
import os
import re
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
    print("  %-4s %-52s %s" % ("PASS" if ok else "FAIL", name, detail))


class _IC(object):
    def name(self):
        return "inputChange"


IC = _IC()

W, H = 1920, 1080
nuke.addFormat("%d %d 0 0 %d %d 1 testHD" % (W, H, W, H))
nuke.root()["format"].setValue("testHD")
plate = nuke.nodes.Constant(format="testHD")


def render(node, tag):
    """Render one frame and return rows -> pixel data, as 8 bit RGB."""
    path = os.path.join(TMP, "r_%s.png" % tag).replace("\\", "/")
    w = nuke.nodes.Write(file=path, file_type="png", datatype="8 bit")
    w.setInput(0, node)
    nuke.execute(w, 1, 1)
    nuke.delete(w)
    return read_png(path)


def read_png(path):
    """Minimal PNG reader, returns (width, height, rows of (r,g,b) tuples)."""
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
    return w, h, rows


def count(rows, pred):
    return sum(1 for row in rows for px in row if pred(px))


def make_cam(focal, rx, ry, height=14.0):
    c = nuke.nodes.Camera2() if "Camera2" in dir(nuke.nodes) else nuke.nodes.Camera()
    c["focal"].setValue(focal)
    c["rotate"].setValue([rx, ry, 0.0])
    c["translate"].setValue([0.0, height, 0.0])
    return c


def project(cam, p):
    r = nuke.nodes.Reconcile3D()
    r.setInput(0, plate)
    r.setInput(1, cam)
    a = nuke.nodes.Axis()
    a["translate"].setValue([float(v) for v in p])
    r.setInput(2, a)
    nuke.execute(r, 1, 1)
    o = r["output"].value()
    nuke.delete(a)
    nuke.delete(r)
    return [float(o[0]), float(o[1])]


def rig():
    a = nuke.createNode("dhPerspGuide", inpanel=False); a.setInput(0, plate)
    b = nuke.createNode("dhPerspGuide", inpanel=False); b.setInput(0, a)
    s = nuke.createNode("dhPerspSolve", inpanel=False); s.setInput(0, b)
    for n in nuke.allNodes():
        n.setSelected(False)
    a.setSelected(True); b.setSelected(True)
    dhPersp.link_guides(s)
    for n in nuke.allNodes():
        n.setSelected(False)
    return a, b, s


def lay_on_floor(a, b, cam):
    """Guide A marks lines running along world X, guide B along world Z."""
    a["p1a"].setValue(project(cam, [-30.0, 0.0, -40.0]))
    a["p1b"].setValue(project(cam, [40.0, 0.0, -40.0]))
    a["p2a"].setValue(project(cam, [-30.0, 0.0, -90.0]))
    a["p2b"].setValue(project(cam, [40.0, 0.0, -90.0]))
    b["p1a"].setValue(project(cam, [-20.0, 0.0, -30.0]))
    b["p1b"].setValue(project(cam, [-20.0, 0.0, -110.0]))
    b["p2a"].setValue(project(cam, [30.0, 0.0, -30.0]))
    b["p2b"].setValue(project(cam, [30.0, 0.0, -110.0]))


# ------------------------------------------------- 14. plates end to end
print("\n=== 14. ground truth plates, guides laid on real floor lines ===")
CASES = [("24mm_wide", 24.0, -9.0, 32.0),
         ("35mm_normal", 35.0, -6.0, 38.0),
         ("85mm_long", 85.0, -2.5, 41.0)]
worst_f = worst_rx = worst_ry = 0.0
modes_used = []
for name, focal, rx, ry in CASES:
    cam = make_cam(focal, rx, ry)
    a, b, s = rig()
    lay_on_floor(a, b, cam)
    # the two axis modes are the documented ambiguity: one of them is the truth
    best = None
    for m in (1, 2):
        s["axis_from"].setValue(m)
        e = abs(s["cam_ry"].value() - ry)
        if best is None or e < best[0]:
            best = (e, m, s["cam_focal"].value(), s["cam_rx"].value(), s["cam_ry"].value())
    worst_ry = max(worst_ry, best[0])
    worst_f = max(worst_f, abs(best[2] - focal))
    worst_rx = max(worst_rx, abs(best[3] - rx))
    modes_used.append(best[1])
    print("       %-12s f %6.2f (%.1f)  rx %6.2f (%.1f)  ry %6.2f (%.1f)  mode %d"
          % (name, best[2], focal, best[3], rx, best[4], ry, best[1]))
    nuke.delete(cam)
check("focal recovered from plate guides", worst_f < 0.05, "worst %.4f mm" % worst_f)
check("pitch recovered from plate guides", worst_rx < 0.05, "worst %.4f deg" % worst_rx)
check("yaw recovered from plate guides", worst_ry < 0.05, "worst %.4f deg" % worst_ry)
check("the correct axis mode is the same one every time",
      len(set(modes_used)) == 1, "modes %s" % modes_used)

# ------------------------------------------------- 15. horizon, measured in the render
print("\n=== 15. horizon line, measured in the render ===")
cam = make_cam(35.0, -6.0, 38.0)
a, b, s = rig()
lay_on_floor(a, b, cam)
s["axis_from"].setValue(modes_used[0])
s["show_floor"].setValue(False)
s["show_horizon"].setValue(True)
truth = project(cam, [1.0e9, 0.0, -1.0e9])[1]
_, hh, rows = render(s, "horizon")


def cyan_rows(rows, w):
    """Row indices, bottom-up in Nuke terms, holding cyan horizon pixels."""
    out = []
    for i, row in enumerate(rows):
        for px in row:
            if px[1] > 160 and px[2] > 160 and px[0] < 120:
                out.append(len(rows) - 1 - i)
                break
    return out


hits = cyan_rows(rows, W)
mid = (min(hits) + max(hits)) / 2.0 if hits else -1
check("horizon is actually drawn", bool(hits), "%d rows" % len(hits))
check("horizon sits at the true eye level", hits and abs(mid - truth) < 2.5,
      "drawn %.1f  truth %.1f" % (mid, truth))
check("horizon is level with no roll", hits and (max(hits) - min(hits)) <= 4,
      "spans %d rows" % ((max(hits) - min(hits)) if hits else -1))
# control: switching it off must remove it
s["show_horizon"].setValue(False)
_, _, off = render(s, "horizon_off")
check("horizon toggle really removes it", not cyan_rows(off, W),
      "%d rows when off" % len(cyan_rows(off, W)))
s["show_horizon"].setValue(True)
# control: moving the guides must move it
before = mid
a["p1a"].setValue([100.0, 100.0])
a["p1b"].setValue([1800.0, 500.0])
_, _, moved = render(s, "horizon_moved")
hm = cyan_rows(moved, W)
check("horizon follows the guides live",
      hm and abs(((min(hm) + max(hm)) / 2.0) - before) > 5,
      "%.1f -> %.1f" % (before, (min(hm) + max(hm)) / 2.0 if hm else -1))
nuke.delete(cam)

# ------------------------------------------------- 16. guide lines are drawn
print("\n=== 16. guide lines are drawn, and color is per node ===")
g = nuke.createNode("dhPerspGuide", inpanel=False)
g.setInput(0, plate)
for n in nuke.allNodes():
    n.setSelected(False)
dhPersp.fit_to_format(g)
g["linecolor"].setValue([1.0, 0.0, 0.0, 1.0])
_, _, red = render(g, "guide_red")
nred = count(red, lambda p: p[0] > 150 and p[1] < 90 and p[2] < 90)
check("guide draws its lines", nred > 500, "%d red pixels" % nred)
g["linecolor"].setValue([0.0, 1.0, 0.0, 1.0])
_, _, grn = render(g, "guide_green")
ngrn = count(grn, lambda p: p[1] > 150 and p[0] < 90 and p[2] < 90)
check("color knob changes what is drawn",
      ngrn > 500 and count(grn, lambda p: p[0] > 150 and p[1] < 90 and p[2] < 90) < 50,
      "%d green pixels" % ngrn)
g["linecolor"].setValue([1.0, 0.0, 0.0, 1.0])
thin = count(render(g, "guide_thin")[2], lambda p: p[0] > 150 and p[1] < 90 and p[2] < 90)
g["linewidth"].setValue(8.0)
thick = count(render(g, "guide_thick")[2], lambda p: p[0] > 150 and p[1] < 90 and p[2] < 90)
check("line width really thickens the lines", thick > thin * 1.5,
      "%d -> %d pixels" % (thin, thick))
g["linewidth"].setValue(2.0)
# an added line must appear in the render
base = count(render(g, "guide_base")[2], lambda p: p[0] > 150 and p[1] < 90 and p[2] < 90)
dhPersp.add_line(g)
more = count(render(g, "guide_added")[2], lambda p: p[0] > 150 and p[1] < 90 and p[2] < 90)
check("an added line is drawn too", more > base + 200, "%d -> %d pixels" % (base, more))
dhPersp.clear_lines(g)
cleared = count(render(g, "guide_cleared")[2], lambda p: p[0] > 150 and p[1] < 90 and p[2] < 90)
check("clearing removes it again", abs(cleared - base) < 200, "%d vs %d" % (cleared, base))
# two guides hold independent colors
g2 = nuke.createNode("dhPerspGuide", inpanel=False); g2.setInput(0, plate)
for n in nuke.allNodes():
    n.setSelected(False)
g2["linecolor"].setValue([0.0, 0.0, 1.0, 1.0])
check("each guide keeps its own color",
      list(g["linecolor"].value())[:3] != list(g2["linecolor"].value())[:3],
      "%s vs %s" % (list(g["linecolor"].value())[:3], list(g2["linecolor"].value())[:3]))

# ------------------------------------------------- 17. link, unlink, relink
print("\n=== 17. link, unlink, relink ===")
a, b, s = rig()
check("link sets expressions on both vanishing points",
      s["vp1"].hasExpression(0) and s["vp2"].hasExpression(0), s["linked_to"].value()[:40])
dhPersp.unlink_guides(s)
check("unlink clears the expressions",
      not s["vp1"].hasExpression(0) and not s["vp2"].hasExpression(0), "")
frozen = [round(v, 3) for v in s["vp1"].value()]
a["p1b"].setValue([700.0, 400.0])
b["p1b"].setValue([650.0, 380.0])
check("unlinked solve stops following the guides",
      [round(v, 3) for v in s["vp1"].value()] == frozen, str(frozen))
for n in nuke.allNodes():
    n.setSelected(False)
a.setSelected(True); b.setSelected(True)
dhPersp.link_guides(s)
check("relink restores live following", s["vp1"].hasExpression(0), "")
for n in nuke.allNodes():
    n.setSelected(False)

# ------------------------------------------------- 18. axis swap
print("\n=== 18. swap which vanishing point is which ground axis ===")
cam = make_cam(35.0, -6.0, 38.0)
a2, b2, s2 = rig()
lay_on_floor(a2, b2, cam)
seen = []
for m in (0, 1, 2):
    s2["axis_from"].setValue(m)
    seen.append(round(s2["cam_ry"].value(), 3))
check("the axis modes give distinct solutions", len(set(seen)) >= 2, str(seen))
check("no axis mode produces NaN", all(v == v for v in seen), str(seen))
check("the two explicit modes are complementary",
      abs(abs(seen[1] - seen[2]) - 90.0) < 0.1, "%.2f and %.2f" % (seen[1], seen[2]))
s2["axis_from"].setValue(1)
f_before = round(s2["cam_focal"].value(), 4)
s2["axis_from"].setValue(0)
s2["axis_from"].setValue(1)
check("axis mode round trip is stable", round(s2["cam_focal"].value(), 4) == f_before,
      "%.4f mm" % f_before)
nuke.delete(cam)

# ------------------------------------------------- 19. floor render
print("\n=== 19. 3D floor, measured in the render ===")
s2["axis_from"].setValue(modes_used[0])
s2["show_horizon"].setValue(True)
s2["show_floor"].setValue(True)
s2["cellsize"].setValue(4.0)
_, _, fr = render(s2, "floor_on")


def grid_rows(rows):
    out = []
    for i, row in enumerate(rows):
        for px in row:
            if px[0] > 140 and 60 < px[1] < 200 and px[2] < 90:
                out.append(len(rows) - 1 - i)
                break
    return out


gr = grid_rows(fr)
hz = cyan_rows(fr, W)
check("floor is actually drawn", bool(gr), "%d rows" % len(gr))
check("no floor pixel sits above the horizon",
      gr and hz and max(gr) <= max(hz) + 1,
      "floor top %d  horizon %d" % (max(gr) if gr else -1, max(hz) if hz else -1))
s2["show_floor"].setValue(False)
_, _, fo = render(s2, "floor_off")
check("floor toggle really removes it", not grid_rows(fo),
      "%d rows when off" % len(grid_rows(fo)))
s2["show_floor"].setValue(True)
s2["cellsize"].setValue(16.0)
_, _, big = render(s2, "floor_big")
gb = grid_rows(big)
check("a much coarser floor still stays below the horizon",
      gb and hz and max(gb) <= max(hz) + 1,
      "floor top %d  horizon %d" % (max(gb) if gb else -1, max(hz) if hz else -1))
check("and still reaches the bottom of frame, because ground has no near edge",
      gb and min(gb) < 40, "floor bottom %d" % (min(gb) if gb else -1))
s2["cellsize"].setValue(4.0)

# The floor used to go through a ScanlineRender, which had to be told the plate
# format or it rendered at the project one. It is drawn in 2D now and inherits
# the format from the plate it is over, so the trap is gone rather than fixed.
nuke.addFormat("640 480 0 0 640 480 1 tinyproj")
nuke.root()["format"].setValue("tinyproj")
dhPersp.on_knob_changed(s2, IC)
fmt = s2.format()
check("the node still follows the plate, not the project format",
      fmt.width() == W and fmt.height() == H,
      "node %dx%d  plate %dx%d" % (fmt.width(), fmt.height(), W, H))
nuke.root()["format"].setValue("testHD")

# ------------------------------------------------- 20. files on disk
print("\n=== 20. gizmo files and wiring on disk ===")
bad = []
for fn in ("dhPerspGuide.gizmo", "dhPerspSolve.gizmo"):
    p = os.path.join(GIZDIR, fn)
    if not os.path.isfile(p):
        bad.append(fn + " missing")
        continue
    src = open(p).read()
    # line one is the version stamp, so look for the declaration anywhere
    if not re.search(r"^Group \{", src, re.M):
        bad.append("%s does not declare Group" % fn)
    if re.search(r"^Gizmo \{", src, re.M):
        bad.append("%s declares Gizmo, which the render farm rejects" % fn)
    want = os.path.splitext(fn)[0]
    if not re.search(r"^\s*name\s+%s\s*$" % want, src, re.M):
        bad.append("%s has no top level name %s" % (fn, want))
    if "persp_tools" in src:
        bad.append("%s still references the old module persp_tools" % fn)
check("both gizmos are Groups carrying their own name", not bad, str(bad))

menu = open(r"C:\Users\dhoch\.nuke\menu.py").read()
init = open(r"C:\Users\dhoch\.nuke\init.py").read()
stale = [w for w in ("persp_tools", "dg_PerspLines", "PerspLines_") if w in menu or w in init]
check("menu.py and init.py carry no stale references", not stale, str(stale))
check("menu.py registers both tools",
      "dhPerspGuide" in menu and "dhPerspSolve" in menu, "")
icons = [f for f in ("dhPerspGuide.png", "dhPerspSolve.png")
         if not os.path.isfile(os.path.join(r"C:\Users\dhoch\.nuke\Icons", f))]
check("both icons are present", not icons, str(icons))

# ------------------------------------------------- 21. order independence
print("\n=== 21. the answer must not depend on guide link order ===")
cam = make_cam(35.0, -6.0, 38.0)
a3, b3, s3 = rig()
lay_on_floor(a3, b3, cam)
s3["axis_from"].setValue(2)
truth_ry, truth_f = 38.0, 35.0
got_a = (s3["cam_ry"].value(), s3["cam_focal"].value(), s3["cam_rx"].value())
check("yaw sign is correct with the guides in this order",
      abs(got_a[0] - truth_ry) < 0.05, "ry %.2f  want %.2f" % (got_a[0], truth_ry))
# now hand the same two vanishing points over in the opposite order
v1, v2 = list(s3["vp1"].value()), list(s3["vp2"].value())
dhPersp.unlink_guides(s3)
s3["vp1"].setValue(v2)
s3["vp2"].setValue(v1)
s3["axis_from"].setValue(1)
got_b = (s3["cam_ry"].value(), s3["cam_focal"].value(), s3["cam_rx"].value())
check("swapping the two vanishing points gives the same camera",
      abs(got_b[0] - got_a[0]) < 0.05 and abs(got_b[1] - got_a[1]) < 0.05
      and abs(got_b[2] - got_a[2]) < 0.05,
      "ry %.2f/%.2f  f %.2f/%.2f" % (got_a[0], got_b[0], got_a[1], got_b[1]))
check("focal survives the swap", abs(got_b[1] - truth_f) < 0.05, "%.3f mm" % got_b[1])
nuke.delete(cam)

print("\n" + "=" * 80)
npass = sum(1 for _, ok, _ in RESULTS if ok)
print("part 3: %d of %d passed" % (npass, len(RESULTS)))
for n, ok, d in RESULTS:
    if not ok:
        print("   FAILED: %s   %s" % (n, d))
