"""Helpers for the dhPerspGuide / dhPerspSolve tools.

Perspective toolkit by David Hochstadter.

The camera solve originates in Den Gheiko's dg_PerspLines, with three corrections:
the ViV2 typo (it used V1[1] for its second coordinate), the Python 2 print
statements, and the division by 1/K that failed on a level horizon.

Lives in ~/.nuke/python, which init.py puts on the plugin path, so these names
resolve in both GUI and -t sessions.
"""
import math
import re
import nuke
from math import sqrt, atan, hypot, pi as PI

# Nodes currently being updated by our own knobChanged handler. Dragging the
# vanishing point rewrites the points, which fires knobChanged again, which would
# rewrite the handle, which fires again. This breaks that loop.
_BUSY = set()


class _Busy(object):
    def __init__(self, node):
        self.key = node.fullName()

    def __enter__(self):
        _BUSY.add(self.key)
        return self

    def __exit__(self, *a):
        _BUSY.discard(self.key)
        return False


class _UndoGroup(object):
    """One undo step for an operation that touches several knobs.

    Without this, adding a line records the point, the on-flag and each
    visibility change separately, so one Ctrl+Z peels off part of the operation
    and leaves a point sitting somewhere new.
    """

    def __init__(self, name):
        self.name = name

    def __enter__(self):
        try:
            nuke.Undo.begin(self.name)
        except Exception:
            pass
        return self

    def __exit__(self, *a):
        try:
            nuke.Undo.end()
        except Exception:
            pass
        return False


class _NoUndo(object):
    """Keep derived state out of the undo stack.

    Knob visibility is rebuilt from the use_add* values on load, so it should
    never be an undo step of its own.
    """

    def __enter__(self):
        try:
            nuke.Undo.disable()
        except Exception:
            pass
        return self

    def __exit__(self, *a):
        try:
            nuke.Undo.enable()
        except Exception:
            pass
        return False

CLASS = "dhPerspGuide"


SIGNATURE = ("vp", "p1a", "p1b", "p2a", "p2b")

# Additional-line slots. The Expression that draws the lines has to reference a
# fixed set of knobs, so the slots always exist; unused ones are hidden, which
# also removes their handle from the viewer.
MAX_LINES = 12


def _slot_knobs(node, i):
    return node.knobs().get("add%d" % i), node.knobs().get("del%d" % i)


def _refresh_panel(node):
    """No-op.

    This used to hide and re-show the properties panel to force a rebuild, which
    was needed while the slot knobs carried +INVISIBLE in the gizmo file and never
    got a widget built. They are created visible now and hidden at load instead,
    so setVisible updates live and the forced rebuild only closed the panel under
    the user mid-click.
    """
    return


def sync_lines(node, refresh=False):
    """Show only the slots that are switched on.

    Knob visibility is not stored per instance, so this runs from the node's
    onCreate to rebuild it from the use_add* values when a script is reopened.
    """
    with _NoUndo():
        for i in range(1, MAX_LINES + 1):
            use = node.knobs().get("use_add%d" % i)
            if use is None:
                continue
            on = bool(use.value())
            for k in _slot_knobs(node, i):
                if k is not None:
                    k.setVisible(on)
            # the on/off flag is never shown; the delete button stands in for it
            use.setVisible(False)
    if refresh:
        _refresh_panel(node)


def node_format(node):
    """Working width/height for a node.

    node.width() already resolves to the connected input's format, and falls back
    to the project format when nothing is connected, so this covers all three
    cases: attached image, selected Read (which auto-connects), or project setting.
    """
    w = float(node.width() or 0)
    h = float(node.height() or 0)
    if w < 1 or h < 1:
        r = nuke.root()
        w, h = float(r.width()), float(r.height())
    return w, h


def _canonical(w, h):
    """Where a fresh fit puts the four base points for a given format.

    Both A points are the outer bottom corners and both B points are inner. The
    original had line 2 reversed, A inner and B at the corner, which made the two
    lines pivot about anchors at very different distances when the vanishing point
    is dragged. The lines themselves are unchanged, only which end is the anchor.
    """
    return {"p1a": (0.0, 0.0),                  # left corner  -> anchor
            "p1b": (w / 3.0, h / 3.0),          # inner
            "p2a": (w, 0.0),                    # right corner -> anchor
            "p2b": (2.0 * w / 3.0, h / 3.0)}    # inner


def _extra_canonical(w, h, slot):
    """Where the slot-th added line's point goes.

    Starts in the middle, between the two base lines, then fans alternately left
    and right. At this height the base lines sit at roughly 15% and 85% across,
    so the middle is where a new guide is actually useful.
    """
    step = 0.09
    if slot == 0:
        frac = 0.5
    else:
        k = (slot + 1) // 2
        sign = 1 if slot % 2 else -1
        frac = 0.5 + sign * k * step
    frac = min(max(frac, 0.06), 0.94)
    return (w * frac, h * 0.15)


def is_pristine(node, tol=0.5):
    """True only if every point still sits exactly where the last fit put it.

    This is the guard that lets a format change re-fit automatically without ever
    disturbing points the user has placed. If anything has been nudged, even one
    extra line, the answer is False and nothing is touched.
    """
    fw = node.knobs().get("_fitw")
    fh = node.knobs().get("_fith")
    if fw is None or fh is None:
        return False
    w, h = fw.value(), fh.value()
    if w < 1 or h < 1:
        return False
    for name, (cx, cy) in _canonical(w, h).items():
        v = node[name].value()
        if abs(v[0] - cx) > tol or abs(v[1] - cy) > tol:
            return False
    for slot, i in enumerate(active_lines(node)):
        cx, cy = _extra_canonical(w, h, slot)
        v = node["add%d" % i].value()
        if abs(v[0] - cx) > tol or abs(v[1] - cy) > tol:
            return False
    return True


def fit_to_format(node=None, quiet=True):
    """Place the guide points against the actual format instead of 2048x1556.

    Proportions match the original tool: line 1 from the bottom-left corner to a
    third in, line 2 mirrored to the bottom-right corner.
    """
    node = node or nuke.thisNode()
    w, h = node_format(node)
    with _UndoGroup("%s: fit to format" % CLASS):
        for name, (cx, cy) in _canonical(w, h).items():
            node[name].setValue([cx, cy])
        for slot, i in enumerate(active_lines(node)):
            node["add%d" % i].setValue(list(_extra_canonical(w, h, slot)))
        if "_fitted" in node.knobs():
            node["_fitted"].setValue(True)
        # remember what we fitted to, so a later format change can tell whether
        # the points are still untouched
        if "_fitw" in node.knobs():
            node["_fitw"].setValue(w)
            node["_fith"].setValue(h)
    if not quiet:
        say(node, "Guide points fitted to %dx%d." % (int(w), int(h)))
    return w, h


def on_create(node=None):
    """Node creation and script load.

    Fits to whatever format is visible now, but does NOT set _fitted: at creation
    time the node is not connected yet, so width() can only report the project
    format. The real fit happens on the first inputChange.
    """
    node = node or nuke.thisNode()
    fitted = node.knobs().get("_fitted")
    if fitted is not None and not fitted.value():
        fit_to_format(node)
        # Created with a Read selected? Nuke connects during creation, so the
        # format we just read is the real one and there may be no inputChange
        # coming. Only stay provisional when nothing is attached yet.
        if node.input(0) is None:
            fitted.setValue(False)
        with _Busy(node):
            sync_vp_handle(node)
    sync_lines(node)


ANCHORED = (("p1a", "p1b"), ("p2a", "p2b"))
VP_LIMIT = 1e7          # beyond this the vanishing point is effectively at infinity

# Bumped whenever the internals of either gizmo change. A Group carries its own
# copy of those internals, so a node created before a fix keeps the old ones.
BUILD = 15

NL = chr(10)
WARN_BLANK = (
    "<br><b>Warning: %s is still at the default cross. Nothing has been placed "
    "on it, so its vanishing point sits on the center of frame and the solved "
    "focal length is meaningless. Draw its two lines along real receding "
    "edges.</b>")

# Working units. A photograph carries no scale of its own, so one measured
# length has to supply it, and camera height is the one a compositor knows.
# Every other length on the node is then in the same unit.
UNITS = (("feet", 0.3048), ("meters", 1.0), ("centimeters", 0.01))
SCALED = ("camera_height", "cellsize")


def unit_index(node):
    """Index of the working unit.

    An Enumeration_Knob's value() is the label text, not the index, so reading
    it with int() silently falls back to zero and the conversion quietly does
    nothing. getValue() is the one that returns the number.
    """
    k = node.knobs().get("unit")
    if k is None:
        return 0
    try:
        return int(round(k.getValue()))
    except Exception:
        pass
    try:
        return [u[0] for u in UNITS].index(str(k.value()))
    except Exception:
        return 0


def unit_name(node):
    return UNITS[max(0, min(unit_index(node), len(UNITS) - 1))][0]


def unit_metres(node):
    return UNITS[max(0, min(unit_index(node), len(UNITS) - 1))][1]


def convert_units(node):
    """Renumber every length when the working unit changes.

    Switching feet to meters must leave the setup physically where it was, so
    the values are converted rather than reinterpreted. Without this the grid
    would jump by a factor of three the moment someone touched the dropdown.
    """
    if "unit" not in node.knobs():
        return
    now = unit_index(node)
    was = int(node["_unit_was"].value()) if "_unit_was" in node.knobs() else now
    if was == now:
        return
    was = max(0, min(was, len(UNITS) - 1))
    factor = UNITS[was][1] / UNITS[now][1]
    with _NoUndo():
        for nm in SCALED:
            k = node.knobs().get(nm)
            if k is not None and not k.hasExpression():
                k.setValue(k.value() * factor)
        g = node.knobs().get("gridoffset")
        if g is not None:
            g.setValue([v * factor for v in g.value()])
        node["_unit_was"].setValue(now)
    set_scale_note(node)


def set_scale_note(node):
    """Say what one cell is worth, in every unit, so nothing is ambiguous."""
    k = node.knobs().get("scale_note")
    if k is None:
        return
    try:
        cell = float(node["cellsize"].value())
        height = float(node["camera_height"].value())
    except Exception:
        return
    m = unit_metres(node)
    cell_m, height_m = cell * m, height * m
    k.setValue(
        "1 cell = %.4g %s   (%.4g m / %.4g ft).   Camera %.4g %s above the "
        "ground   (%.4g m / %.4g ft)."
        % (cell, unit_name(node), cell_m, cell_m / 0.3048,
           height, unit_name(node), height_m, height_m / 0.3048))


def sync_vp_handle(node):
    """Mirror the computed vp onto the draggable handle."""
    if "vp_drag" not in node.knobs():
        return
    v = node["vp"].value()
    if abs(v[0]) > VP_LIMIT or abs(v[1]) > VP_LIMIT:
        return          # parallel lines: nothing finite to point at, leave the handle
    node["vp_drag"].setValue([float(v[0]), float(v[1])])


def drag_vp(node):
    """Swing each line about its anchor so both pass through the dragged point.

    The anchors p1a and p2a hold still because those are the ones you place on a
    real feature in the plate. Each far point keeps its distance from its anchor,
    so the handles stay where you can grab them.
    """
    v = node["vp_drag"].value()
    grp = _UndoGroup("%s: drag vanishing point" % CLASS)
    grp.__enter__()
    for anchor, far in ANCHORED:
        A = node[anchor].value()
        B = node[far].value()
        dx, dy = v[0] - A[0], v[1] - A[1]
        d = hypot(dx, dy)
        if d < 1e-6:
            continue                     # handle sitting on the anchor, nothing to aim at
        L = hypot(B[0] - A[0], B[1] - A[1]) or d
        node[far].setValue([A[0] + dx / d * L, A[1] + dy / d * L])
    grp.__exit__()


def on_knob_changed(node=None, knob=None):
    """Input connection, and the draggable vanishing point."""
    node = node or nuke.thisNode()
    knob = knob or nuke.thisKnob()
    if knob is None or node.fullName() in _BUSY:
        return
    name = knob.name()

    if name == "role":
        apply_role_color(node)
        return
    if name == "use_vertical":
        set_axis_note(node)
        set_verdict(node)
        return
    if name == "unit":
        convert_units(node)
        return
    if name in ("cellsize", "camera_height"):
        set_scale_note(node)
    if name in ("vp1", "vp2", "vp3", "use_known_focal",
                "known_focal", "filmback", "axis_from"):
        set_verdict(node)

    if name == "inputChange":
        if node.input(0) is None:
            return
        fitted = node.knobs().get("_fitted")
        if fitted is None:
            return

        if "vp1" in node.knobs():                       # dhPerspSolve
            if not fitted.value() and not node["vp1"].hasExpression(0):
                fit_solve_to_format(node)
            # stacking guides into the chain should just work
            with _Busy(node):
                auto_link(node)
            return

        if not fitted.value():                          # first connection
            fit_to_format(node)
            with _Busy(node):
                sync_vp_handle(node)
            return

        # already fitted: re-fit only if the plate changed AND nothing was moved
        w, h = node_format(node)
        fw = node.knobs().get("_fitw")
        if fw is None:
            return
        if abs(w - fw.value()) < 0.5 and abs(h - node["_fith"].value()) < 0.5:
            return                                      # same format, nothing to do
        if not is_pristine(node):
            return                                      # user has placed points, leave them
        fit_to_format(node)
        with _Busy(node):
            sync_vp_handle(node)
        return

    if name == "vp_drag":
        with _Busy(node):
            drag_vp(node)
        return

    if name in ("p1a", "p1b", "p2a", "p2b"):
        with _Busy(node):
            sync_vp_handle(node)


def active_lines(node):
    return [i for i in range(1, MAX_LINES + 1)
            if node.knobs().get("use_add%d" % i) and node["use_add%d" % i].value()]


def add_line(node=None):
    """Switch on the next free slot, place its point, and reveal it."""
    node = node or nuke.thisNode()
    used = active_lines(node)
    free = [i for i in range(1, MAX_LINES + 1) if i not in used]
    if not free:
        say(node, "All %d additional lines are in use. "
                     "Delete one first, or use a second PerspLines node."
                     % MAX_LINES)
        return
    i = free[0]
    w, h = node_format(node)
    with _UndoGroup("%s: add line" % CLASS):
        # same placement the fit uses, so adding a line keeps the node pristine
        node["add%d" % i].setValue(list(_extra_canonical(w, h, len(used))))
        node["use_add%d" % i].setValue(True)
    sync_lines(node, refresh=True)
    return i


def del_line(i, node=None):
    """Switch off one slot and hide it again."""
    node = node or nuke.thisNode()
    with _UndoGroup("%s: delete line" % CLASS):
        node["use_add%d" % i].setValue(False)
    sync_lines(node, refresh=True)


def clear_lines(node=None):
    node = node or nuke.thisNode()
    with _UndoGroup("%s: clear lines" % CLASS):
        for i in range(1, MAX_LINES + 1):
            node["use_add%d" % i].setValue(False)
    sync_lines(node, refresh=True)


def is_persplines(node):
    """A Group's Class() is 'Group', not 'PerspLines', so identify by its knobs.

    Checking Class() is what broke the original tool's addOnCreate hook; do not
    reintroduce it here.
    """
    try:
        k = node.knobs()
    except Exception:
        return False
    return all(name in k for name in SIGNATURE)


def _selected_persplines(n=2):
    """Return exactly n selected PerspLines nodes, or None after warning."""
    nodes = list(nuke.selectedNodes())
    if len(nodes) != n:
        nuke.tprint("dhPersp: select exactly %d %s nodes; %d selected."
                     % (n, CLASS, len(nodes)))
        return None
    bad = [x.name() for x in nodes if not is_persplines(x)]
    if bad:
        nuke.tprint("dhPersp: these are not %s nodes: %s"
                    % (CLASS, ", ".join(bad)))
        return None
    return nodes


def horizon():
    """Create a dhPerspSolve linked to the vanishing points of two dhPerspGuides."""
    nodes = _selected_persplines(2)
    if not nodes:
        return
    a, b = nodes
    nodes[0].selectOnly()
    h = nuke.createNode("dhPerspSolve")
    h["vp1"].setExpression(a.name() + ".vp.x", 0)
    h["vp1"].setExpression(a.name() + ".vp.y", 1)
    h["vp2"].setExpression(b.name() + ".vp.x", 0)
    h["vp2"].setExpression(b.name() + ".vp.y", 1)
    # linked now, so never auto-fit these on top of the link
    if "_fitted" in h.knobs():
        h["_fitted"].setValue(True)
    set_link_label(h)
    return h


def set_link_label(node):
    """Say which guide drives which vanishing point.

    nuke.selectedNodes() does not return click order, so which guide lands on vp1
    is effectively arbitrary. Showing it removes the 'I moved one and nothing
    happened' confusion.
    """
    k = node.knobs().get("linked_to")
    if k is None:
        return
    parts = []
    for name in ("vp1", "vp2"):
        kn = node[name]
        if kn.hasExpression(0):
            src = kn.animation(0).expression().split(".")[0]
            parts.append("%s &larr; %s" % (name, src))
        else:
            parts.append("%s: set by hand" % name)
    label = "   ".join(parts)
    if not any("&larr;" in p for p in parts):
        label += "      (select two %s nodes and press 'link to selected guides')" % CLASS
    # An untouched guide's two lines cross at the exact center of frame, which
    # is the principal point, so its vanishing point lands there and the focal
    # length collapses to nothing. Reporting that as a lens would be a lie.
    blank = pristine_guides(node)
    if blank:
        label += (WARN_BLANK % ", ".join(blank))
    k.setValue(label)
    set_verdict(node)


def align_camera():
    """Estimate focal length and orientation from two PerspLines vanishing points."""
    nodes = _selected_persplines(2)
    if not nodes:
        return
    return _build_camera(nodes)


def _build_camera(nodes):
    V1 = nodes[0]["vp"].value()
    V2 = nodes[1]["vp"].value()

    Oi = [nodes[0].width() / 2.0, nodes[0].height() / 2.0]

    # Vi is the foot of the perpendicular from the principal point onto the
    # horizon. The original solved this via 1/K, which divides by zero on a LEVEL
    # horizon -- the ordinary case of an untilted camera. Projecting onto the
    # V1->V2 direction is the same point and has no singularity.
    dx = V2[0] - V1[0]
    dy = V2[1] - V1[1]
    dd = dx * dx + dy * dy
    if dd < 1e-9:
        nuke.tprint("dhPersp: the two vanishing points are on top of each other. "
                     "Adjust one of the PerspLines pairs and try again.")
        return
    t = ((Oi[0] - V1[0]) * dx + (Oi[1] - V1[1]) * dy) / dd
    Vi = [V1[0] + t * dx, V1[1] + t * dy]

    K = dy / dx if abs(dx) > 1e-9 else None   # slope, only used for roll

    ViV1 = sqrt(pow(Vi[0] - V1[0], 2) + pow(Vi[1] - V1[1], 2))
    ViV2 = sqrt(pow(Vi[0] - V2[0], 2) + pow(Vi[1] - V2[1], 2))

    OcVi = sqrt(ViV1 * ViV2)
    OiVi = sqrt(pow(Oi[0] - Vi[0], 2) + pow(Oi[1] - Vi[1], 2))

    inner = pow(OcVi, 2) - pow(OiVi, 2)
    if inner <= 0:
        nuke.tprint("dhPersp: cannot solve a focal length from these points. "
                     "They are too close together or too near the frame center.")
        return
    f = sqrt(inner)

    f_scale = sqrt(pow(Oi[0] * 2, 2) + pow(Oi[1] * 2, 2)) / f

    cam = nuke.createNode("Camera", inpanel=False)
    cam["tile_color"].setValue(884320767)
    cam["focal"].setValue(
        sqrt(pow(cam["haperture"].value(), 2) + pow(cam["vaperture"].value(), 2)) / f_scale)

    Rx = atan((Oi[1] - Vi[1]) / f) * 180 / PI
    Ry = atan(min(ViV1, ViV2) / f) * 180 / PI
    Ry2 = atan(max(ViV1, ViV2) / f) * 180 / PI
    Rz = 0.0 if K is None else -atan(K) * 180 / PI   # roll; 0 on a level horizon

    cam["rotate"].setValue([Rx, Ry, Rz])
    cam["translate"].setValue([0, 1, 0])

    cam.addKnob(nuke.Tab_Knob("alternate"))
    k = nuke.Double_Knob("Ry", "Ry")
    k.setValue(Ry2)
    cam.addKnob(k)
    sw = nuke.PyScript_Knob("swap", "swap")
    sw.setCommand("import dhPersp\ndhPersp.swap(nuke.thisNode())")
    cam.addKnob(sw)
    return cam


def swap(node):
    """Swap the solved Ry for the alternate solution."""
    R = node["rotate"].value()
    P = R[1]
    node["rotate"].setValue([R[0], node["Ry"].value(), R[2]])
    node["Ry"].setValue(P)


def export_camera(node=None):
    """Copy the solved camera out of a PerspHorizon into the node graph.

    Exported expression-linked, so it keeps following the PerspLines while you
    adjust them. The exported camera carries its own 'bake' button to freeze the
    values when the solve is settled or the camera is going somewhere else.
    """
    node = node or nuke.thisNode()
    src = node.node("cam")
    if src is None:
        say(node, "<b>No solved camera inside this node.</b> Reopening "
            "the script rebuilds an out of date one.")
        return

    blank = pristine_guides(node)
    if blank:
        msg = ("%s has not been placed. Its two lines are still at the "
               "default cross, which meets at the exact center of frame. A "
               "vanishing point there makes the focal length collapse to "
               "zero, so this camera would be meaningless."
               % ", ".join(blank))
        say(node, msg + " Draw both of its lines along real receding "
            "edges first.")
        return
    solved = node["cam_focal"].value()
    doubt = ""
    if solved < 4.0 or solved > 400.0:
        doubt = ("<b>The solve gives %.4g mm, which is not a believable "
                 "lens.</b> Usually the two guides are not following two "
                 "directions at right angles to each other, or one of them has "
                 "barely been moved. The Camera Solve tab says which. "
                 % solved)

    # A button on a Group fires with that Group as the current context, so a plain
    # nuke.nodes.Camera() would be created INSIDE the gizmo. Force root.
    root = nuke.root()
    root.begin()
    try:
        cam = nuke.nodes.Camera2() if "Camera2" in dir(nuke.nodes) else nuke.nodes.Camera()
        cam.setName("dhPerspCamera")
        cam.setXYpos(node.xpos() + 160, node.ypos())
        cam["tile_color"].setValue(884320767)
    finally:
        root.end()

    if "." in cam.fullName():
        say(node, "<b>Could not place the camera in the main node graph.</b> "
            "It ended up at " + cam.fullName())

    n = node.name()
    cam["focal"].setExpression("%s.cam_focal" % n)
    for i, axis in enumerate(("cam_rx", "cam_ry", "cam_rz")):
        cam["rotate"].setExpression("%s.%s" % (n, axis), i)
    # Height is what carries the real world scale, so the exported camera
    # follows it rather than sitting at an arbitrary one unit.
    cam["translate"].setValue([0.0, 1.0, 0.0])
    if "camera_height" in node.knobs():
        cam["translate"].setExpression("%s.camera_height" % n, 1)

    cam.addKnob(nuke.Tab_Knob("persp", "PerspLines"))
    info = nuke.Text_Knob("src", "solved by", n)
    cam.addKnob(info)
    if "unit" in node.knobs():
        u = nuke.Text_Knob("units", "units", unit_name(node))
        u.setTooltip("Translate values on this camera are in this unit. "
                     "Set the same linear unit in Maya or Blender before "
                     "importing.")
        cam.addKnob(u)
    bake = nuke.PyScript_Knob("bake", "bake values")
    bake.setCommand("import dhPersp\ndhPersp.bake_camera(nuke.thisNode())")
    bake.setTooltip("Freeze the current solve and drop the links to " + n)
    cam.addKnob(bake)
    cam.addKnob(nuke.Text_Knob("status", "", ""))

    say(node, doubt + "Exported %s. It stays linked to this node, so it follows "
        "the guides as you adjust them, including frame by frame if they are "
        "animated. Press 'bake values' on its PerspLines tab to freeze it."
        % cam.name())
    if doubt:
        say(cam, doubt + "Exported from %s anyway." % n)
    return cam


def animated_guides(node):
    """Guides feeding this solve that have keys on their points.

    An expression link is not animation: every vanishing point on a solve is
    expression linked whether or not anything moves, so asking the solve is no
    use. The guide points are the knobs a person actually keys, and a curve with
    one key on it is not a move either.
    """
    out = []
    for g in upstream_guides(node):
        for nm in ("p1a", "p1b", "p2a", "p2b"):
            k = g.knobs().get(nm)
            if k is None:
                continue
            hit = False
            for i in (0, 1):
                try:
                    if k.isAnimated(i) and len(k.animation(i).keys()) > 1:
                        hit = True
                except Exception:
                    pass
            if hit:
                out.append(g)
                break
    return out


def _range():
    r = nuke.root()
    try:
        return int(r["first_frame"].value()), int(r["last_frame"].value())
    except Exception:
        return 1, 1


BAKE_KNOBS = ("focal", "rotate", "translate", "haperture", "vaperture")


def _sample(cam, first, last):
    """Every baked knob's value at every frame, read before anything is cleared.

    getValueAt is the one that answers for a frame other than the current one.
    A plain value() reads whatever context the knob happens to be in, which in a
    terminal session is the first frame no matter what frame you asked for, and
    that is how a whole move gets baked as its first pose.
    """
    out = {}
    for name in BAKE_KNOBS:
        k = cam.knobs().get(name)
        if k is None:
            continue
        try:
            n = k.arraySize() if hasattr(k, "arraySize") else 1
        except Exception:
            n = 1
        n = max(int(n), 1)
        rows = []
        for f in range(first, last + 1):
            vals = []
            for i in range(n):
                try:
                    vals.append(float(k.getValueAt(f, i)) if n > 1
                                else float(k.getValueAt(f)))
                except Exception:
                    vals.append(None)
            rows.append(vals)
        out[name] = rows
    return out


def _moves(rows, tol=1e-7):
    first = rows[0]
    for r in rows[1:]:
        for a, b in zip(first, r):
            if a is None or b is None:
                continue
            if abs(a - b) > tol:
                return True
    return False


def bake_camera(cam=None):
    """Freeze a linked camera: keep the numbers, drop the expressions.

    A solve that moves is baked as a key per frame over the script range. A solve
    that does not is baked as plain values, as before.
    """
    cam = cam or nuke.thisNode()
    first, last = _range()
    data = _sample(cam, first, last)
    moving = [name for name, rows in data.items() if _moves(rows)]

    frozen = []
    for name, rows in data.items():
        k = cam.knobs()[name]
        n = len(rows[0])
        if name in moving:
            for i in range(n):
                try:
                    k.clearAnimated(i)
                except Exception:
                    pass
                try:
                    k.setAnimated(i)
                except Exception:
                    pass
            for f, vals in zip(range(first, last + 1), rows):
                for i, v in enumerate(vals):
                    if v is None:
                        continue
                    try:
                        k.setValueAt(v, f, i) if n > 1 else k.setValueAt(v, f)
                    except Exception:
                        pass
        else:
            vals = rows[0]
            for i in range(n):
                try:
                    k.clearAnimated(i)
                except Exception:
                    pass
                if vals[i] is None:
                    continue
                try:
                    k.setValue(vals[i], i) if n > 1 else k.setValue(vals[i])
                except Exception:
                    pass
        frozen.append(name)

    if moving:
        msg = ("Baked %s. %d frames, %d to %d, keyed on %s. This camera no "
               "longer follows the guides."
               % (", ".join(frozen), last - first + 1, first, last,
                  ", ".join(moving)))
    else:
        msg = ("Baked %s. Nothing was animated, so these are plain values. This "
               "camera no longer follows the guides." % ", ".join(frozen))
    say(cam, msg)
    return cam


def floor_3d(rows=20, size=40.0):
    """Build the real 3D floor: aligned camera + a wireframe ground plane.

    This is what the Nukepedia screenshots actually show. The blue grid there is
    geometry rendered through the solved camera, not lines drawn in 2D, and it is
    how you confirm the camera solve is correct: if the grid sits flat on the
    floor of the plate, the solve is good.

    Returns (camera, card, scanlinerender).
    """
    nodes = _selected_persplines(2)
    if not nodes:
        return

    plate = nodes[0].input(0)
    cam = _build_camera(nodes)
    if cam is None:
        return

    card = nuke.nodes.Card2() if "Card2" in dir(nuke.nodes) else nuke.nodes.Card()
    card.setName("dhPerspFloorGrid")
    for knob, value in (("rows", rows), ("columns", rows)):
        if knob in card.knobs():
            card[knob].setValue(value)
    # lie the card flat on the ground plane
    if "orientation" in card.knobs():
        try:
            card["orientation"].setValue("ZX")
        except Exception:
            card["rotate"].setValue([-90.0, 0.0, 0.0])
    else:
        card["rotate"].setValue([-90.0, 0.0, 0.0])
    if "uniform_scale" in card.knobs():
        card["uniform_scale"].setValue(size)
    else:
        card["scaling"].setValue([size, size, size])
    if "display" in card.knobs():
        card["display"].setValue("wireframe")
    if "render_mode" in card.knobs():
        card["render_mode"].setValue("wireframe")

    sr = nuke.nodes.ScanlineRender()
    sr.setName("dhPerspFloorRender")
    sr.setInput(1, card)     # obj
    sr.setInput(2, cam)      # cam
    if plate is not None:
        sr.setInput(0, plate)  # bg
    if "antialiasing" in sr.knobs():
        sr["antialiasing"].setValue("low")

    nuke.tprint("dhPersp: built a 3D floor grid through the solved camera. "
                "If it does not lie flat on the floor of the plate, press "
                "'swap' on the camera's alternate tab, or nudge the guide "
                "points.")
    return cam, card, sr

def fit_solve_to_format(node=None, quiet=True):
    """Place dhPerspSolve's default vanishing points against the actual format."""
    node = node or nuke.thisNode()
    w, h = node_format(node)
    node["vp1"].setValue([-0.30 * w, 0.58 * h])
    node["vp2"].setValue([1.30 * w, 0.58 * h])
    if "_fitted" in node.knobs():
        node["_fitted"].setValue(True)
    if not quiet:
        say(node, "Vanishing points fitted to %dx%d." % (int(w), int(h)))
    return w, h


def on_create_solve(node=None):
    """Creation and script load.

    Like the guide, this fits to whatever format is visible but leaves _fitted
    False: at creation the node is not connected yet, so width() can only report
    the project format. The real fit happens on the first inputChange.
    """
    set_scale_note(node)
    node = node or nuke.thisNode()
    fitted = node.knobs().get("_fitted")
    if fitted is not None and not fitted.value():
        if not node["vp1"].hasExpression(0):
            fit_solve_to_format(node)
            # created with a plate selected? then the format just read is real and
            # no inputChange is coming, so stop treating the fit as provisional
            if node.input(0) is None:
                fitted.setValue(False)
    auto_link(node)
    set_link_label(node)
    set_verdict(node)


def upstream_guides(node, limit=200):
    """Every dhPerspGuide feeding this node, nearest first.

    Walking the input chain means stacking Read > Guide > Guide > Solve just
    works, which is what people expect from a node graph.
    """
    found, seen, queue = [], set(), [node.input(0)]
    while queue and limit > 0:
        limit -= 1
        n = queue.pop(0)
        if n is None:
            continue
        key = n.fullName()
        if key in seen:
            continue
        seen.add(key)
        if is_persplines(n):
            found.append(n)
        for i in range(n.inputs()):
            queue.append(n.input(i))
    return found


def _apply_link(node, a, b, vert=None):
    node["vp1"].setExpression(a.name() + ".vp.x", 0)
    node["vp1"].setExpression(a.name() + ".vp.y", 1)
    node["vp2"].setExpression(b.name() + ".vp.x", 0)
    node["vp2"].setExpression(b.name() + ".vp.y", 1)
    if "vp3" in node.knobs():
        if vert is not None:
            node["vp3"].setExpression(vert.name() + ".vp.x", 0)
            node["vp3"].setExpression(vert.name() + ".vp.y", 1)
            node["use_vertical"].setValue(True)
        else:
            for i in (0, 1):
                if node["vp3"].hasExpression(i):
                    node["vp3"].clearAnimated(i)
            node["use_vertical"].setValue(False)
    if "_fitted" in node.knobs():
        node["_fitted"].setValue(True)
    pin_axis(node, a, b)
    set_link_label(node)
    set_axis_note(node)
    return node


def auto_link(node):
    """Link to the guides feeding this node, when they make a solvable set.

    Two marking the ground, and optionally one more on the uprights. A third
    guide nobody has told the tool about is worked out from its lines, so
    stacking a vertical guide into the chain just works.
    """
    if node["vp1"].hasExpression(0):
        return None                       # already linked, leave it alone
    ground, vertical = split_guides(upstream_guides(node))
    if len(ground) != 2:
        return None
    return _apply_link(node, ground[0], ground[1],
                       vertical[0] if vertical else None)


def link_guides(node=None):
    """Link the vanishing points to two dhPerspGuide nodes.

    Uses the selection when two guides are selected, otherwise falls back to the
    guides feeding this node's input.
    """
    node = node or nuke.thisNode()
    guides = [n for n in nuke.selectedNodes() if is_persplines(n)]
    if len(guides) < 2:
        guides = upstream_guides(node)
    ground, vertical = split_guides(guides)
    if len(ground) == 2 and vertical:
        return _apply_link(node, ground[0], ground[1], vertical[0])
    if len(ground) == 2:
        return _apply_link(node, ground[0], ground[1])
    if len(ground) < 2:
        say(node,
            "<b>Found %d %s node%s marking a level direction, and a solve needs "
            "two.</b><br>Each guide marks one vanishing point. Two of them, one "
            "running away from the camera and one running across in front of it, "
            "give the focal length and the orientation. A third on the upright "
            "edges is optional.<br>Pipe another %s into this node's input chain, "
            "or select the ones you want and press this again."
            % (len(ground), CLASS, "" if len(ground) == 1 else "s", CLASS))
        return
    say(node,
        "<b>Found %d %s nodes and none of them is set to vertical.</b><br>"
        "A solve uses two level guides, one ground and one across. A third is "
        "for upright edges, and it is normally recognized from its own lines: "
        "this one was not, which usually means its lines are not steep enough to "
        "be uprights, or two guides are following the same direction.<br>"
        "Set the odd one's 'these lines are' to vertical, or select the two you "
        "want to solve from and press this again."
        % (len(ground), CLASS))
    return


def unlink_guides(node=None):
    """Drop the links and keep the current vanishing points as plain values."""
    node = node or nuke.thisNode()
    for name in ("vp1", "vp2"):
        k = node[name]
        v = list(k.value())
        for i in (0, 1):
            try:
                k.clearAnimated(i)
            except Exception:
                pass
            k.setValue(float(v[i]), i)
    set_link_label(node)
    return node


def node_build(node):
    k = node.knobs().get("_build")
    try:
        return int(k.value()) if k is not None else 0
    except Exception:
        return 0


def stale_nodes():
    """Every dhPersp node in the script that predates the current build."""
    out = []
    for n in nuke.allNodes(recurseGroups=True):
        try:
            nm = n.knobs().get("name")
        except Exception:
            continue
        if not (is_persplines(n) or is_solve(n)):
            continue
        if node_build(n) < BUILD:
            out.append(n)
    return out


# The two vanishing points are the whole reason the node exists, so they are the
# safest thing to recognize it by: every build has had them, and no other node
# here has both. Anything more specific risks naming a knob that a later build
# removes, which is exactly what went wrong last time.
SOLVE_SIGNATURE = ("vp1", "vp2")


def is_solve(node):
    """A solve node, identified the same way a guide is: by its knobs.

    It used to be identified by having a gridsize knob, which worked right up
    until the build that removed gridsize. A node that cannot be recognized
    cannot be brought up to date, so this has to name knobs that are the point
    of the node rather than knobs that happen to be on it.
    """
    try:
        k = node.knobs()
    except Exception:
        return False
    return all(name in k for name in SOLVE_SIGNATURE) and not is_persplines(node)


def _class_of(node):
    if is_persplines(node):
        return CLASS
    if is_solve(node):
        return "dhPerspSolve"
    return None


def _user_knobs(node):
    """Knob names the user can actually set, in panel order."""
    skip = ("_build", "name", "xpos", "ypos", "selected", "help", "onCreate",
            "knobChanged", "tile_color", "note_font", "label", "inputChange")
    out = []
    for k in node.knobs().values():
        nm = k.name()
        if nm in skip or nm.startswith("__"):
            continue
        if isinstance(k, (nuke.Tab_Knob, nuke.PyScript_Knob, nuke.Script_Knob)):
            continue
        if isinstance(k, nuke.Text_Knob) and not k.value():
            continue
        out.append(nm)
    return out


def update_nodes(nodes=None, quiet=False):
    """Rebuild stale dhPersp nodes in place, keeping everything you have set.

    These are Groups so the render farm can run them without the gizmo
    installed, and the price of that is that an existing node keeps the
    internals it was created with. This makes a fresh one, copies the user
    knobs across (expressions included, so a linked solve stays linked),
    reconnects it and puts it back where the old one was.
    """
    nodes = nodes if nodes is not None else stale_nodes()
    nodes = [n for n in nodes if _class_of(n)]
    if not nodes:
        if not quiet:
            nuke.tprint("dhPersp: every node is already at build %d." % BUILD)
        return []

    done, failed = [], []
    with _UndoGroup("Update dhPersp nodes"):
        for old in nodes:
            cls = _class_of(old)
            name = old.name()
            xp, yp = old.xpos(), old.ypos()
            ins = [(i, old.input(i)) for i in range(old.inputs())]
            outs = []
            for n in nuke.allNodes(recurseGroups=True):
                for i in range(n.inputs()):
                    if n.input(i) is old:
                        outs.append((n, i))

            # values first, so an expression can be restored over the top
            keep = {}
            for nm in _user_knobs(old):
                k = old[nm]
                try:
                    expr = [k.animation(i) and None for i in range(0)]
                except Exception:
                    expr = None
                entry = {"value": None, "exprs": {}, "enum": None}
                try:
                    entry["value"] = k.value()
                except Exception:
                    pass
                # A pulldown's value() is its label, and a label can be renamed
                # between builds. Setting one the new build does not have fails
                # quietly and leaves the knob at its default, so the index is
                # kept as well and used when the label has gone.
                if isinstance(k, nuke.Enumeration_Knob):
                    try:
                        entry["enum"] = (k.value(), int(round(k.getValue())))
                    except Exception:
                        entry["enum"] = None
                try:
                    for idx in range(k.arraySize() if hasattr(k, "arraySize") else 1):
                        if k.hasExpression(idx):
                            entry["exprs"][idx] = k.animation(idx).expression()
                except Exception:
                    pass
                keep[nm] = entry

            with _NoUndo():
                for n in nuke.allNodes():
                    n.setSelected(False)
            try:
                new = nuke.createNode(cls, inpanel=False)
            except Exception as e:
                failed.append("%s (%s)" % (name, e))
                continue

            for nm, entry in keep.items():
                k = new.knobs().get(nm)
                if k is None:
                    continue
                if entry.get("enum") is not None:
                    label, idx = entry["enum"]
                    try:
                        options = list(k.values())
                    except Exception:
                        options = []
                    try:
                        if label in options:
                            k.setValue(label)
                        elif options:
                            k.setValue(max(0, min(idx, len(options) - 1)))
                    except Exception:
                        pass
                elif entry["value"] is not None and not entry["exprs"]:
                    try:
                        k.setValue(entry["value"])
                    except Exception:
                        pass
                for idx, ex in entry["exprs"].items():
                    try:
                        k.setExpression(ex, idx)
                    except Exception:
                        pass

            nuke.delete(old)
            new.setName(name)
            new.setXYpos(xp, yp)
            for i, src in ins:
                if src is not None:
                    new.setInput(i, src)
            for n, i in outs:
                n.setInput(i, new)
            done.append(name)

    for n in nuke.allNodes():
        n.setSelected(False)
    if not quiet:
        msg = "updated %d node%s to build %d: %s" % (
            len(done), "" if len(done) == 1 else "s", BUILD, ", ".join(done))
        if failed:
            msg += ".  Could not update: " + ", ".join(failed)
        nuke.tprint("dhPersp: " + msg)
    return done


def pristine_guides(node):
    """Guides feeding this solve that are still at their default layout.

    An untouched guide's two lines cross at the exact center of frame, so its
    vanishing point sits on the principal point and the focal length collapses.
    """
    bad = []
    for g in upstream_guides(node):
        if is_pristine(g):
            bad.append(g.name())
    return bad


GROUND, ACROSS, VERTICAL = 0, 1, 2
ROLE_NAMES = ("ground", "across", "vertical")
ROLE_COLORS = ((1.0, 0.0, 0.0, 1.0),      # ground
               (0.0, 1.0, 0.0, 1.0),      # across
               (0.0, 0.3, 1.0, 1.0))      # vertical


def guide_role(node):
    """0 ground, 1 across, 2 vertical. Anything older reads as ground.

    Read by label rather than by index, because the index of "vertical" moved
    when "across" was added and a node rebuilt from an older build could
    otherwise come back meaning something else.
    """
    k = node.knobs().get("role")
    if k is None:
        return GROUND
    try:
        label = str(k.value())
        if label in ROLE_NAMES:
            return ROLE_NAMES.index(label)
    except Exception:
        pass
    try:
        return max(0, min(int(round(k.getValue())), VERTICAL))
    except Exception:
        return GROUND


def looks_vertical(node):
    """Whether a guide is drawn along upright edges rather than a level direction.

    Both its lines are steep on screen and its vanishing point is a long way off
    above or below frame. A receding ground direction cannot do both: its lines
    run toward a point on the horizon, which is somewhere near the middle of the
    frame vertically, so at least one of them is shallow.

    This is not a close call in a real photograph, so it is safe to decide it
    rather than ask. The role knob is set from it, so the answer stays visible
    and can be overridden.
    """
    try:
        pts = [node[k].value() for k in ("p1a", "p1b", "p2a", "p2b")]
    except Exception:
        return False
    steep = 0
    for a, b in ((pts[0], pts[1]), (pts[2], pts[3])):
        dx, dy = abs(b[0] - a[0]), abs(b[1] - a[1])
        if dx < 1e-6 and dy < 1e-6:
            return False                       # a line with no length says nothing
        if dy > 1.7 * dx:                      # steeper than about 60 degrees
            steep += 1
    if steep < 2:
        return False
    try:
        vp = node["vp"].value()
        h = float(node.height() or 1)
    except Exception:
        return False
    return abs(vp[1] - h / 2.0) > 1.5 * h      # and it converges well off frame


def split_guides(guides, decide=True):
    """Separate the level guides from the upright ones.

    Ground and across are both level directions and both feed the solve, so they
    come back together; which of the two a guide is only matters for pinning the
    world axes, and that is asked separately.

    The role knob is the authority. When nothing has been marked vertical and
    there are more guides than a solve can use, the extra one is worked out from
    its lines and the knob is set to match, because the alternative is refusing
    to do anything with a setup that is perfectly clear. Ground against across is
    never guessed at: the two are symmetric in the picture and only the person
    who took it knows which way they were facing.
    """
    level = [g for g in guides if guide_role(g) != VERTICAL]
    vertical = [g for g in guides if guide_role(g) == VERTICAL]
    if decide and not vertical and len(level) > 2:
        upright = [g for g in level if looks_vertical(g)]
        if len(upright) == len(level) - 2:
            for g in upright:
                try:
                    g["role"].setValue("vertical")
                except Exception:
                    pass
                apply_role_color(g)
            level = [g for g in level if g not in upright]
            vertical = upright
    return level, vertical


def pin_axis(node, a, b):
    """Point the world X axis along whichever guide is the across one.

    axis_from setting 1 runs X along the first vanishing point and setting 2
    along the second; that is measured, not assumed, because the expression
    behind it reads the other way round. Pinning it is what makes an exported
    camera land the right way round in Maya, and it is also the only way to stop
    an animated solve flipping ninety degrees mid shot, because "auto" chooses
    again every frame and an expression cannot remember what it chose last.

    Two guides that are both still on ground are left alone. They are symmetric
    and guessing between them would be inventing an answer.
    """
    k = node.knobs().get("axis_from")
    note = node.knobs().get("axis_state")
    if k is None:
        return None
    ra, rb = guide_role(a), guide_role(b)
    pinned = None
    if ra == ACROSS and rb == GROUND:
        pinned = 1
    elif rb == ACROSS and ra == GROUND:
        pinned = 2
    if pinned is not None:
        try:
            k.setValue(pinned)
        except Exception:
            pinned = None
    if note is not None:
        if pinned is not None:
            note.setValue(
                "Pinned from the guides: X runs along %s, the 'across' one, and "
                "Z runs along %s."
                % ((a if pinned == 1 else b).name(),
                   (b if pinned == 1 else a).name()))
        else:
            note.setValue(
                "<b>Not pinned.</b> Both guides are set to the same thing, so "
                "which way X and Z run is being guessed at. Set the one running "
                "left to right in front of the camera to 'across' and the one "
                "running away from you to 'ground'. It decides which way round "
                "the scene arrives in Maya, and on an animated solve the guess "
                "can flip ninety degrees mid shot.")
    return pinned


def set_axis_note(node):
    """Say whether the lens axis was solved or assumed, and why."""
    k = node.knobs().get("axis_note")
    if k is None:
        return
    if "use_vertical" not in node.knobs() or not node["use_vertical"].value():
        k.setValue("lens axis: center of frame (no vertical guide)")
        return
    ok = node["_v3ok"].value() > 0.5
    if ok:
        k.setValue("lens axis solved from the vertical guide: %.1f, %.1f  "
                   "(center of frame is %.1f, %.1f)"
                   % (node["_px"].value(), node["_py"].value(),
                      node.width() / 2.0, node.height() / 2.0))
    else:
        # Two different guides fail this and they need different advice: one
        # that was never drawn on has its vanishing point sitting on the center
        # of frame, and one drawn along genuinely parallel uprights has it off
        # at infinity. Both make the orthocenter meaningless.
        d = math.hypot(node["vp3"].value()[0] - node.width() / 2.0,
                       node["vp3"].value()[1] - node.height() / 2.0)
        if d < node["_diag"].value():
            k.setValue("<b>The vertical guide has not been placed. Its two "
                       "lines still cross at the center of frame, so there is "
                       "no vanishing point to solve from and the lens axis is "
                       "being assumed at the center. Draw its lines along two "
                       "upright edges in the plate.</b>")
        else:
            k.setValue("<b>The vertical guide is too close to parallel to be "
                       "used. Its vanishing point is off at infinity, where the "
                       "orthocenter is meaningless, so the lens axis is being "
                       "assumed at the center of frame. A camera tilted up or "
                       "down gives verticals that actually converge.</b>")


def set_verdict(node=None):
    """Say out loud whether the two guides describe a camera that can exist.

    A lens axis has to fall between the two vanishing points along the horizon.
    That is not a rule of thumb, it is what (V1-P).(V2-P) + f^2 = 0 means: the
    product of the two signed distances has to be negative and big enough to
    leave room for the focal length. Guides that do not satisfy it have no
    camera at all, and the arithmetic that used to run anyway returned a few
    millimeters, which reads like a fisheye rather than like an error.
    """
    node = node or nuke.thisNode()
    k = node.knobs().get("verdict")
    if k is None:
        return None
    try:
        ok = node["_solveok"].value() > 0.5
        fsq = float(node["_fsq"].value())
        focal = float(node["cam_focal"].value())
        roll = float(node["cam_rz"].value())
    except Exception:
        return None
    pair = 0
    try:
        pair = int(round(node["_pair"].value()))
    except Exception:
        pass
    from_pair = ""
    if pair == 13:
        from_pair = (" Solved from the ground guide against the vertical one: "
                     "the two level vanishing points are too nearly parallel to "
                     "use against each other.")
    elif pair == 23:
        from_pair = (" Solved from the across guide against the vertical one: "
                     "the two level vanishing points are too nearly parallel to "
                     "use against each other.")

    try:
        ill = node["_ill"].value() > 0.5
    except Exception:
        ill = False
    if ill:
        from_pair += (
            "<br><b>Treat this number with suspicion.</b> One of the two "
            "directions it was solved from barely converges, so its vanishing "
            "point is a very long way off and the focal length depends mostly "
            "on which pixel you put the line ends on. It can be tens of "
            "millimeters out while still looking like a lens. A guide along the "
            "upright edges fixes it, because vertical against a receding "
            "direction is well conditioned on exactly these shots. Otherwise "
            "tick 'I know the focal length'.")

    if node.knobs().get("use_known_focal") is not None and \
            node["use_known_focal"].value():
        k.setValue("Focal length is being taken as given, %.4g mm. The guides "
                   "are only setting the orientation." % focal)
        return True
    if not ok:
        k.setValue(
            "<b>These two guides do not describe a camera.</b> For a real lens "
            "the two vanishing points have to sit on opposite sides of the lens "
            "axis along the horizon, and these do not%s. Usually one guide is "
            "following the same direction on the ground as the other, or one of "
            "its lines is not on a receding edge. On a shot square to a wall "
            "there may be no answer from two guides at all, because the wall's "
            "own horizontals barely converge: add a third guide along the "
            "upright edges, or tick 'I know the focal length'. The focal length "
            "below is a floor value, not a solve."
            % ("" if fsq < 0 else " by enough to leave room for a focal length"))
        return False
    warn = []
    if focal < 8.0 or focal > 200.0:
        warn.append("%.4g mm is outside the range most lenses live in" % focal)
    if abs(roll) > 5.0:
        warn.append("the camera is rolled %.1f degrees, which is rare unless "
                    "the shot really is tilted" % roll)
    if warn:
        k.setValue("<b>Solved, but check it: %s.</b>%s"
                   % (", and ".join(warn), from_pair))
        return True
    moving = animated_guides(node)
    if moving and int(round(node["axis_from"].getValue())) == 0:
        k.setValue(
            "Solved: %.4g mm, roll %.2f degrees.<br><b>The guides are animated "
            "and the ground axis is on automatic.</b> Automatic picks whichever "
            "vanishing point needs the smaller turn, and it picks again every "
            "frame. The two answers are ninety degrees apart, so the frame where "
            "they swap puts a ninety degree snap in the middle of the move. Set "
            "'ground X axis runs toward' to vanishing point 1 or 2 before "
            "exporting."
            % (focal, roll))
        return True
    if moving:
        k.setValue("Solved: %.4g mm, roll %.2f degrees, animated from %d guide%s. "
                   "The camera follows them frame by frame.%s"
                   % (focal, roll, len(moving), "" if len(moving) == 1 else "s",
                      from_pair))
        return True
    k.setValue("Solved: %.4g mm, roll %.2f degrees. That is a believable "
               "camera.%s" % (focal, roll, from_pair))
    return True


def update_on_load():
    """Bring any out of date dhPersp node in the opened script up to build.

    Registered on script load in the GUI, so this is the only thing that ever
    needs to happen and nobody has to know it did. Quiet unless something was
    actually rebuilt, and it leaves the script's modified flag where it found
    it: redoing this next time costs nothing, so there is no reason to make
    someone save a change they did not ask for.
    """
    try:
        stale = stale_nodes()
        if not stale:
            return []
        root = nuke.root()
        was_modified = root.modified()
        done = update_nodes(stale, quiet=True)
        if done and not was_modified:
            root.setModified(False)
        if done:
            nuke.tprint("dhPersp: brought %d node%s up to build %d (%s)"
                        % (len(done), "" if len(done) == 1 else "s", BUILD,
                           ", ".join(done)))
        return done
    except Exception as e:
        nuke.tprint("dhPersp: could not update nodes on load: %s" % e)
        return []


def say(node, text):
    """Put a message where the person who pressed the button will see it.

    On the node's own status line, which stays there to be read again, and in
    the script editor for anything watching. A dialog would interrupt to say the
    same thing somewhere it cannot be looked at twice.
    """
    if node is not None:
        k = node.knobs().get("status")
        if k is not None:
            try:
                k.setValue(text)
            except Exception:
                pass
    plain = re.sub("<[^>]+>", "", text.replace("<br>", "  "))
    try:
        nuke.tprint("dhPersp: " + plain)
    except Exception:
        pass
    return text


def apply_role_color(node=None):
    """Color a guide by what it is: red ground, green across, blue vertical.

    The point is the viewer, not the panel. Three guides on a plate look the same
    until they are colored, and a color chosen by hand means whatever you last
    remembered it to mean; tied to the role it means one thing, so a guide set to
    the wrong sort shows up without opening it.
    """
    node = node or nuke.thisNode()
    k = node.knobs().get("linecolor")
    if k is None:
        return None
    rgba = ROLE_COLORS[max(0, min(guide_role(node), len(ROLE_COLORS) - 1))]
    try:
        k.setValue(list(rgba))
    except Exception:
        return None
    return rgba
