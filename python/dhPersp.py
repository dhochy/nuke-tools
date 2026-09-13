"""Helpers for the dhPerspGuide / dhPerspSolve tools.

Perspective toolkit by David Hochstadter.

The camera solve originates in Den Gheiko's dg_PerspLines, with three corrections:
the ViV2 typo (it used V1[1] for its second coordinate), the Python 2 print
statements, and the division by 1/K that failed on a level horizon.

Lives in ~/.nuke/python, which init.py puts on the plugin path, so these names
resolve in both GUI and -t sessions.
"""
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
        nuke.message("Guide points fitted to %dx%d." % (int(w), int(h)))
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
BUILD = 5

NL = chr(10)
WARN_BLANK = (
    "<br><b>Warning: %s is still at the default cross. Nothing has been placed "
    "on it, so its vanishing point sits on the centre of frame and the solved "
    "focal length is meaningless. Draw its two lines along real receding "
    "edges.</b>")

# Working units. A photograph carries no scale of its own, so one measured
# length has to supply it, and camera height is the one a compositor knows.
# Every other length on the node is then in the same unit.
UNITS = (("feet", 0.3048), ("metres", 1.0), ("centimetres", 0.01))
SCALED = ("camera_height", "gridsize", "griddistance", "cellsize")


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

    Switching feet to metres must leave the setup physically where it was, so
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

    if name == "use_vertical":
        set_axis_note(node)
        return
    if name == "unit":
        convert_units(node)
        return
    if name in ("cellsize", "camera_height"):
        set_scale_note(node)
    if name in ("autofit", "horizon_gap", "gridrows", "camera_height"):
        maybe_fit_floor(node)

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
        nuke.message("All %d additional lines are in use.\n\n"
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
        nuke.message("Select exactly %d %s nodes.\n\nSelected: %d"
                     % (n, CLASS, len(nodes)))
        return None
    bad = [x.name() for x in nodes if not is_persplines(x)]
    if bad:
        nuke.message("These are not %s nodes:\n\n  %s" % (CLASS, "\n  ".join(bad)))
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
    # An untouched guide's two lines cross at the exact centre of frame, which
    # is the principal point, so its vanishing point lands there and the focal
    # length collapses to nothing. Reporting that as a lens would be a lie.
    blank = pristine_guides(node)
    if blank:
        label += (WARN_BLANK % ", ".join(blank))
    k.setValue(label)


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
        nuke.message("The two vanishing points are on top of each other.\n"
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
        nuke.message("Cannot solve a focal length from these vanishing points.\n"
                     "They are too close together or too near the frame centre.")
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
        nuke.message("No solved camera inside this node.")
        return

    blank = pristine_guides(node)
    if blank:
        msg = ("%s has not been placed. Its two lines are still at the "
               "default cross, which meets at the exact centre of frame. A "
               "vanishing point there makes the focal length collapse to "
               "zero, so this camera would be meaningless."
               % ", ".join(blank))
        nuke.message(msg + NL + NL +
                     "Draw both of its lines along real receding edges first.")
        return
    solved = node["cam_focal"].value()
    if solved < 4.0 or solved > 400.0:
        why = ("That usually means the two guides are not marking two "
               "perpendicular sets of parallel edges, or one of them has "
               "barely been moved.")
        head = ("The solve gives %.2f mm, which is not a believable lens."
                % solved)
        if not nuke.ask(head + NL + NL + why + NL + NL + "Export anyway?"):
            return

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
        nuke.message("Could not place the camera in the main node graph.\n"
                     "It ended up at: " + cam.fullName())

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

    nuke.message("Exported %s.\n\nIt stays linked to %s, so it updates as you\n"
                 "adjust the PerspLines. Press 'bake values' on its PerspLines\n"
                 "tab to freeze it." % (cam.name(), n))
    return cam


def bake_camera(cam=None):
    """Freeze a linked camera: keep the current numbers, drop the expressions."""
    cam = cam or nuke.thisNode()
    frozen = []
    for name in ("focal", "rotate", "translate", "haperture", "vaperture"):
        k = cam.knobs().get(name)
        if k is None:
            continue
        val = k.value()
        if isinstance(val, (list, tuple)):
            for i, v in enumerate(val):
                try:
                    k.clearAnimated(i)
                except Exception:
                    pass
                k.setValue(float(v), i)
        else:
            try:
                k.clearAnimated()
            except Exception:
                pass
            k.setValue(float(val))
        frozen.append(name)
    nuke.message("Baked: %s\n\n%s no longer follows the PerspLines."
                 % (", ".join(frozen), cam.name()))
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

    nuke.message(
        "Built a 3D floor grid through the solved camera.\n\n"
        "If the grid does not lie flat on the floor of the plate, press "
        "'swap' on the camera's alternate tab, or nudge the PerspLines points.")
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
        nuke.message("Vanishing points fitted to %dx%d." % (int(w), int(h)))
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
    set_link_label(node)
    set_axis_note(node)
    maybe_fit_floor(node)
    return node


def auto_link(node):
    """Link to the guides feeding this node, if there are exactly two."""
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
    guides = ground
    if len(guides) != 2:
        nuke.message(
            "Need exactly two %s nodes, found %d.\n\n"
            "Each guide marks ONE vanishing point, and a camera solve needs two.\n\n"
            "Either pipe a second %s into this node's input chain, or select two "
            "of them in the node graph and press this again.\n\n"
            "Connecting a guide to this node's input only passes the picture "
            "through. The vanishing points are linked separately, which is what "
            "this button does."
            % (CLASS, len(guides), CLASS))
        return
    return _apply_link(node, guides[0], guides[1])


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
        if not (is_persplines(n) or "vp1" in n.knobs() and "gridsize" in n.knobs()):
            continue
        if node_build(n) < BUILD:
            out.append(n)
    return out


def _class_of(node):
    if is_persplines(node):
        return CLASS
    if "gridsize" in node.knobs() and "vp1" in node.knobs():
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
            nuke.message("Every dhPersp node is already at build %d." % BUILD)
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
                entry = {"value": None, "exprs": {}}
                try:
                    entry["value"] = k.value()
                except Exception:
                    pass
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
                try:
                    if entry["value"] is not None and not entry["exprs"]:
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
        msg = "Updated %d node%s to build %d:\n  %s" % (
            len(done), "" if len(done) == 1 else "s", BUILD, ", ".join(done))
        if failed:
            msg += "\n\nCould not update: " + ", ".join(failed)
        nuke.message(msg)
    return done


def pristine_guides(node):
    """Guides feeding this solve that are still at their default layout.

    An untouched guide's two lines cross at the exact centre of frame, so its
    vanishing point sits on the principal point and the focal length collapses.
    """
    bad = []
    for g in upstream_guides(node):
        if is_pristine(g):
            bad.append(g.name())
    return bad


def fit_floor(node=None, quiet=True):
    """Size and place the floor so it covers the frame and reaches the horizon.

    A ground plane has no edges in shot. A card does, so the card has to be big
    enough and far enough that its edges leave the frame and its far edge lands
    on the horizon.

    A ground point at horizontal distance d ahead of the camera projects about
    f_px * height / d pixels below the horizon, so the distance that stops a
    chosen few pixels short is f_px * height / gap. Spanning from behind the
    camera out to there, and the same again sideways, covers everything the
    frame can see.
    """
    node = node or nuke.thisNode()
    if "gridsize" not in node.knobs():
        return None
    try:
        f_px = float(node["_f"].value())
        height = float(node["camera_height"].value())
        gap = max(float(node["horizon_gap"].value()), 0.5)
        cells = max(int(round(node["gridrows"].value())), 4)
    except Exception:
        return None
    if f_px <= 1.0 or height <= 0.0:
        if not quiet:
            nuke.message("Nothing to fit yet: the solve has no usable focal "
                         "length or the camera height is zero.")
        return None

    # How many pixels of ground there are between the horizon and the bottom of
    # frame. That ratio, not the scene scale, decides everything: the nearest
    # visible ground is f*h/hz away and the farthest is f*h/gap, so covering both
    # with one uniform grid needs about 3*hz/gap cells. A Card caps at 400 rows,
    # so the gap has to be opened up until the cell count fits, otherwise the
    # cells grow larger than the whole near half of frame and nothing is drawn
    # there at all.
    try:
        hz = 0.5 * (node["vp1"].value()[1] + node["vp2"].value()[1])
    except Exception:
        hz = node.height() * 0.75
    hz = max(min(hz, node.height() * 4.0), 40.0)
    cap = min(cells, 400)

    # Cell size is set by the NEAR field, which is the half you judge alignment
    # against. Aim for `near_cells` cells across the width of frame at the bottom.
    # The ground there is f*h/hz away and the frame spans 2*d*(w/2)/f across it,
    # so the cell that gives n cells across is simply (w/n) * (h/hz).
    try:
        want = max(float(node["near_cells"].value()), 1.0)
    except Exception:
        want = 6.0
    cell = (node.width() / want) * (height / hz)

    # Then reach as far as the 400 row ceiling allows at that cell size.
    far = cap * cell / 3.0
    gap = max(gap, f_px * height / max(far, 1e-9))
    far = f_px * height / gap
    cells = int(max(8, min(cap, round(3.0 * far / cell))))
    # The card is axis aligned to world X and Z while the camera can be looking
    # any which way, so its silhouette is a diamond. Pushing it forward leaves
    # its near corner in shot, which is the pointed near edge and the visible
    # side edges. Centring it under the camera instead means every direction is
    # covered out to the inscribed radius, whatever the yaw.
    # Visible ground sits within about far*sqrt(2) of the point under the
    # camera, so a half side of 1.5*far clears it with room to spare.
    size = 3.0 * far
    dist = 0.0
    with _NoUndo():
        node["gridsize"].setValue(size)
        node["griddistance"].setValue(dist)
        node["cellsize"].setValue(size / float(cells))
    set_scale_note(node)
    if not quiet:
        nuke.message("Floor fitted: %.6g across, centred %.6g in front, "
                     "%d cells of %.6g %s each."
                     % (size, dist, cells, size / float(cells), unit_name(node)))
    return size


def maybe_fit_floor(node):
    """Fit only if the user has left it on automatic."""
    k = node.knobs().get("autofit")
    if k is not None and k.value():
        return fit_floor(node, quiet=True)
    return None


def guide_role(node):
    """0 for a ground guide, 1 for a vertical one. Older guides are ground."""
    k = node.knobs().get("role")
    if k is None:
        return 0
    try:
        return int(round(k.getValue()))
    except Exception:
        return 0


def split_guides(guides):
    """Separate the two ground guides from an optional vertical one."""
    ground = [g for g in guides if guide_role(g) == 0]
    vertical = [g for g in guides if guide_role(g) == 1]
    return ground, vertical


def set_axis_note(node):
    """Say whether the lens axis was solved or assumed, and why."""
    k = node.knobs().get("axis_note")
    if k is None:
        return
    if "use_vertical" not in node.knobs() or not node["use_vertical"].value():
        k.setValue("lens axis: centre of frame (no vertical guide)")
        return
    ok = node["_v3ok"].value() > 0.5
    if ok:
        k.setValue("lens axis solved from the vertical guide: %.1f, %.1f  "
                   "(centre of frame is %.1f, %.1f)"
                   % (node["_px"].value(), node["_py"].value(),
                      node.width() / 2.0, node.height() / 2.0))
    else:
        k.setValue("<b>The vertical guide is too close to parallel to be used. "
                   "Its vanishing point is off at infinity, where the orthocenter "
                   "is meaningless, so the lens axis is being assumed at the "
                   "centre of frame. A camera tilted up or down gives verticals "
                   "that actually converge.</b>")
