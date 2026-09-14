"""Part twelve: three guides, the thinning switch, and what camera height touches.

Three guides refused to link because all three said "ground", which is what the
role knob says until someone changes it. A guide drawn along upright edges is not
hard to tell apart from one drawn along a receding ground direction, so it is
worked out rather than asked for.

The thinning of far lines is a switch now, off by default, so the grid arrives at
the horizon.

And the question that matters before an export: does changing the camera height
disturb the solve. It must not. Scale is unobservable in a single photograph, so
height can only be a multiplier on distance; if it moved the focal length or the
angles, one of the two would be wrong.
"""
import math
import nuke

nuke.pluginAddPath(r"C:\Users\dhoch\.nuke\Gizmos\DH_Tools\3D")
import dhPersp

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))
    print("  %-4s %-62s %s" % ("PASS" if ok else "FAIL", name, detail))


IC = type("IC", (), {"name": staticmethod(lambda: "inputChange")})()
W, H = 1920, 1080
nuke.addFormat("%d %d 0 0 %d %d 1 testHD" % (W, H, W, H))
nuke.root()["format"].setValue("testHD")
plate = nuke.nodes.Constant(format="testHD", color=0.2)


def guide(after, pts):
    for n in nuke.allNodes():
        n.setSelected(False)
    g = nuke.createNode("dhPerspGuide", inpanel=False)
    g.setInput(0, after)
    dhPersp.on_knob_changed(g, IC)
    for k, v in zip(("p1a", "p1b", "p2a", "p2b"), pts):
        g[k].setValue([float(v[0]), float(v[1])])
    return g


# two ground directions, opposite sides of frame, and the uprights
g1 = guide(plate, [(1500, 900), (300, 780), (1500, 200), (300, 360)])
g2 = guide(g1, [(200, 100), (1700, 300), (200, 800), (1700, 700)])
g3 = guide(g2, [(500, 60), (512, 1020), (1400, 60), (1381, 1020)])

# ------------------------------------------------------ 43. telling them apart
print("\n=== 43. a third guide is recognized without being told ===")
check("the upright guide reads as vertical", dhPersp.looks_vertical(g3),
      "vp at %.0f, %.0f" % tuple(g3["vp"].value()))
check("the first ground guide does not", not dhPersp.looks_vertical(g1),
      "vp at %.0f, %.0f" % tuple(g1["vp"].value()))
check("the second ground guide does not", not dhPersp.looks_vertical(g2),
      "vp at %.0f, %.0f" % tuple(g2["vp"].value()))
check("all three still say 'ground' on the knob, because nobody touched it",
      all(g["role"].value() == "ground" for g in (g1, g2, g3)), "")

ground, vertical = dhPersp.split_guides([g1, g2, g3])
check("split_guides returns two ground and one vertical",
      len(ground) == 2 and len(vertical) == 1,
      "%d ground, %d vertical" % (len(ground), len(vertical)))
check("and it is the upright one", vertical and vertical[0] is g3,
      vertical[0].name() if vertical else "none")
check("the knob is set to match, so the panel is not lying",
      g3["role"].value() == "vertical", g3["role"].value())
check("the level guides are left alone",
      all(g["role"].value() == "ground" for g in (g1, g2)), "")

# a genuinely ambiguous set must still refuse rather than guess
g4 = guide(g3, [(1500, 880), (300, 760), (1500, 220), (300, 380)])
amb_ground, amb_vert = dhPersp.split_guides([g1, g2, g4])
check("three guides that all mark ground directions are not guessed at",
      len(amb_ground) == 3 and not amb_vert,
      "%d ground, %d vertical" % (len(amb_ground), len(amb_vert)))
nuke.delete(g4)

# ----------------------------------------------------------- 44. it links up
print("\n=== 44. and the solve links to all three ===")
for n in nuke.allNodes():
    n.setSelected(False)
s = nuke.createNode("dhPerspSolve", inpanel=False)
s.setInput(0, g3)
for n in nuke.allNodes():
    n.setSelected(False)
dhPersp.on_knob_changed(s, IC)
check("connecting the chain linked it on its own, three guides and all",
      s["vp1"].hasExpression(0) and s["vp2"].hasExpression(0)
      and s["vp3"].hasExpression(0), "")
check("and switched the vertical on", bool(s["use_vertical"].value()), "")
check("the vertical vanishing point is usable", s["_v3ok"].value() > 0.5, "")
moved = math.hypot(s["_px"].value() - W / 2.0, s["_py"].value() - H / 2.0)
check("the lens axis is solved off center but still on the frame",
      moved > 1.0 and moved < 0.5 * s["_diag"].value(),
      "%.0f px off center, frame diagonal %.0f" % (moved, s["_diag"].value()))
check("the solve stands up", s["_solveok"].value() > 0.5,
      "%.2f mm" % s["cam_focal"].value())

# pressing the button with three guides must not refuse either
dhPersp.unlink_guides(s)
check("unlinking really unlinks", not s["vp1"].hasExpression(0), "")
for n in nuke.allNodes():
    n.setSelected(False)
dhPersp.link_guides(s)
check("pressing 'solve from guides' with three of them links rather than refuses",
      s["vp1"].hasExpression(0) and s["vp3"].hasExpression(0), "")

# ----------------------------------------------- 45. an off frame lens axis
print("\n=== 45. a vertical guide that throws the lens axis off frame is refused ===")
s["vp3"].clearAnimated(0)
s["vp3"].clearAnimated(1)
s["vp3"].setValue([-40000.0, 9000.0])
check("the vertical vanishing point is inside the distance limits",
      s["_v3d"].value() > 0.75 * s["_diag"].value()
      and s["_v3d"].value() < 25 * s["_diag"].value(),
      "%.0f px out, limits %.0f to %.0f"
      % (s["_v3d"].value(), 0.75 * s["_diag"].value(), 25 * s["_diag"].value()))
off = math.hypot(s["_ox"].value() - W / 2.0, s["_oy"].value() - H / 2.0)
if off > 0.5 * s["_diag"].value():
    check("but the lens axis it produces is off the frame, so it is not used",
          s["_v3ok"].value() < 0.5, "%.0f px off center" % off)
    check("and the lens axis falls back to the center of frame",
          abs(s["_px"].value() - W / 2.0) < 0.5, "%.1f" % s["_px"].value())
else:
    check("this fixture no longer throws the axis off frame, so it proves nothing",
          False, "%.0f px off center" % off)
dhPersp.link_guides(s)

# ------------------------------------------------------- 46. thinning switch
print("\n=== 46. far lines are drawn unless you ask for them to thin out ===")
s["camera_height"].setValue(5.5)
s["cellsize"].setValue(2.0)
mask = s.node("gridmask")
hy = 0.5 * (s["vp1"].value()[1] + s["vp2"].value()[1])
check("the switch exists and is off", "fade_far" in s.knobs()
      and not s["fade_far"].value(), "")


def lit(y, step=2):
    n = 0
    x = 0
    while x < W:
        if nuke.sample(mask, "red", x + 0.5, y + 0.5) > 0.02:
            n += 1
        x += step
    return n


def reach():
    for y in range(int(hy) - 1, 4, -1):
        if lit(y) > 0:
            return y
    return None


off_reach = reach()
s["fade_far"].setValue(True)
on_reach = reach()
s["fade_far"].setValue(False)
check("off, the grid is drawn all the way to the horizon",
      off_reach is not None and hy - off_reach < 3.0,
      "last row %s, horizon %.1f" % (off_reach, hy))
check("on, it stops short, which is what the switch is for",
      on_reach is not None and off_reach - on_reach > 8,
      "off reaches %s, on reaches %s" % (off_reach, on_reach))
check("off, the near ground is not harmed either",
      lit(20) > 0, "%d lit on row 20" % lit(20))

# where the lines are closer than a pixel the answer is solid, not noise: that
# is both the right picture and the way round losing the fraction of a very
# large ground coordinate
near_hz = [lit(int(hy) - d) for d in (2, 6, 14)]
check("just under the horizon it fills in rather than going to noise",
      all(v > W / 4 for v in near_hz), "lit pixels 2, 6 and 14 rows under: %s"
      % near_hz)

# --------------------------------------- 47. camera height and the solve
print("\n=== 47. camera height changes the scale and nothing else ===")
s["fade_far"].setValue(False)


def solved():
    return tuple(round(s[k].value(), 9) for k in
                 ("cam_focal", "cam_rx", "cam_ry", "cam_rz", "_px", "_py", "_f"))


s["camera_height"].setValue(5.5)
base = solved()
readings = []
for h in (0.5, 3.0, 5.5, 12.0, 120.0, 850.0):
    s["camera_height"].setValue(h)
    readings.append(solved())
check("the focal length is identical at every height",
      len(set(r[0] for r in readings)) == 1, "%.6f mm" % readings[0][0])
check("pitch, yaw and roll are identical at every height",
      len(set(r[1:4] for r in readings)) == 1,
      "%.4f, %.4f, %.4f" % readings[0][1:4])
check("the lens axis is identical at every height",
      len(set(r[4:6] for r in readings)) == 1,
      "%.2f, %.2f" % readings[0][4:6])

# what it does change is distance, exactly in proportion
s["camera_height"].setValue(5.5)
ground = s.node("groundxz")
probe = [(300, 120), (960, 200), (1600, 80)]
was = [nuke.sample(ground, "red", x + 0.5, y + 0.5) for x, y in probe]
s["camera_height"].setValue(55.0)
now = [nuke.sample(ground, "red", x + 0.5, y + 0.5) for x, y in probe]
check("ten times the height is ten times the distance to everything",
      all(abs(n - 10.0 * w) < max(0.001 * abs(w), 1e-4) for w, n in zip(was, now)),
      "%s -> %s" % ([round(v, 2) for v in was], [round(v, 2) for v in now]))
s["camera_height"].setValue(5.5)

# and the exported camera has to agree
cam = dhPersp.export_camera(s)
check("a camera exports", cam is not None, cam.name() if cam else "none")
if cam is not None:
    before = (round(cam["focal"].value(), 9), round(cam["rotate"].value()[0], 9),
              round(cam["rotate"].value()[1], 9), round(cam["rotate"].value()[2], 9))
    s["camera_height"].setValue(22.0)
    after = (round(cam["focal"].value(), 9), round(cam["rotate"].value()[0], 9),
             round(cam["rotate"].value()[1], 9), round(cam["rotate"].value()[2], 9))
    check("changing the height after export leaves its focal and angles alone",
          before == after, "%.4f mm, %.3f %.3f %.3f" % after)
    check("and moves only its height",
          abs(cam["translate"].value()[1] - 22.0) < 1e-6,
          "translate y %.4f" % cam["translate"].value()[1])
    s["camera_height"].setValue(5.5)

print("\n" + "=" * 88)
npass = sum(1 for _, ok, _ in RESULTS if ok)
print("part 12: %d of %d passed" % (npass, len(RESULTS)))
for n, ok, d in RESULTS:
    if not ok:
        print("   FAILED: %s   %s" % (n, d))
