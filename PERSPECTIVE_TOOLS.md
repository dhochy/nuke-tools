# Perspective tools

`dhPerspGuide` and `dhPerspSolve`. Place perspective guide lines on a plate, get the
vanishing points, and solve a camera and ground plane from them.

Both are Groups, so their definitions travel inside the `.nk` and render on a farm
blade that does not have them installed.

## What they do

**dhPerspGuide** — two pairs of points define two lines; where those lines meet is the
vanishing point, reported on a read-only `vp` knob. Up to 12 extra guide lines can be
added, each running from the vanishing point through a point you place. Add and delete
buttons create and remove them; unused ones stay hidden so the viewer is not cluttered.

**dhPerspSolve** — takes two `dhPerspGuide` vanishing points and gives you three things:
the horizon line through them, a 3D wireframe floor rendered through a solved camera,
and the camera itself. If the floor grid lies flat on the floor in the plate, the solve
is right. **export camera** drops a copy into the node graph, expression-linked so it
keeps following the guides, with a **bake values** button to freeze it.

If you know the real focal length, tick **I know the focal length** on the Camera Solve
tab and enter it with the film back. The vanishing points then only set orientation,
which is both more accurate and the way out when the geometry cannot produce a focal.

## Install on a workstation

Clone or copy this repo, then add to `~/.nuke/init.py`:

```python
nuke.pluginAddPath('/path/to/nuke-tools/gizmos/3D')
nuke.pluginAddPath('/path/to/nuke-tools/icons')
nuke.pluginAddPath('/path/to/nuke-tools/python')
```

`init.py`, not `menu.py`. Nuke runs `init.py` in both GUI and `nuke -t` sessions but only
runs `menu.py` in the GUI, so paths added there are missing from terminal and farm renders.

Then in `~/.nuke/menu.py`:

```python
m = nuke.menu("Nodes").addMenu("DH_Tools")
t = m.addMenu("3D")
t.addCommand("dhPerspGuide", "nuke.createNode('dhPerspGuide')", icon="dhPerspGuide.png")
t.addCommand("dhPerspSolve", "nuke.createNode('dhPerspSolve')", icon="dhPerspSolve.png")

nuke.menu('Nuke').addCommand('Tools/Perspective/Horizon from 2 dhPerspGuide',
                             'import dhPersp; dhPersp.horizon()')
nuke.menu('Nuke').addCommand('Tools/Perspective/3D Floor from 2 dhPerspGuide',
                             'import dhPersp; dhPersp.floor_3d()')
nuke.menu('Nuke').addCommand('Tools/Perspective/Align Camera from 2 dhPerspGuide',
                             'import dhPersp; dhPersp.align_camera()', 'Shift+V')
```

`python/dhPersp.py` must be importable, which the `pluginAddPath` above handles. Without
it the gizmos still load and draw, but the add/delete buttons and the camera tools do not
work.

## Notes

Filenames are case sensitive on Linux and Nuke registers a gizmo by its filename, so
`dhPerspGuide.gizmo` must keep exactly that spelling to match `createNode('dhPerspGuide')`.

The lines are drawn analytically by an Expression node rather than as RotoPaint strokes.
Expressions stored inside RotoPaint control points no longer drive the raster in Nuke 15.2,
16.0 or 17.0, which is what broke the tool this replaces.

## The maths, and how it is verified

The camera solve is the standard two vanishing point calibration from Caprile and Torre
(1990), also Hartley and Zisserman chapter 8. For two vanishing points from perpendicular
world directions, square pixels, and the principal point assumed at the image center:

    (v1 - p) . (v2 - p) + f^2 = 0

The gizmo computes it in an equivalent geometric form: drop a perpendicular from the image
center O onto the horizon line to get the foot Vi, then

    f = sqrt( ViV1 * ViV2 - OVi^2 )

These are the same equation. Splitting each vector at the foot gives
(v1-O).(v2-O) = (v1-Vi).(v2-Vi) + |OVi|^2, and the two horizon segments point opposite
ways, so the first term is -ViV1*ViV2.

Pitch comes from the height of that foot above the center, and yaw from the signed offset
of the other vanishing point along the horizon, measured against sqrt(f^2 + OVi^2) rather
than f, because under pitch the relevant distance is to the horizon, not to the center.

### Test suites

`tests/` holds four suites, run with `nuke -t tests/suite.py` and so on. They cover 73
checks: solve accuracy against ground truth cameras, the published formula reimplemented
independently, degenerate inputs, format fitting, added lines, vanishing point dragging,
linking, export and bake, save and reload, and the drawn output measured by rendering to
disk and counting pixels rather than by reading knobs back.

`tests/make_testplates.py` and `tests/corridor.py` render ground truth plates with known
focal length and orientation, for placing guides on by hand.

### When to enter a known focal length instead of solving one

Accuracy depends entirely on how far off frame the vanishing points sit. Measured cost of
a two pixel slip in guide placement, on a 1920x1080 plate at 35mm:

| camera yaw | vanishing point offset | focal error per 2px slip |
|---|---|---|
| 2 deg | 78,700 px | 68.6% |
| 5 deg | 31,400 px | 13.7% |
| 15 deg | 10,300 px | 1.6% |
| 30 deg | 4,800 px | 0.3% |
| 45 deg | 2,700 px | 0.1% |

A near one point shot, such as looking straight down a corridor or an alley, cannot be
solved reliably from guides alone. Use "I know the focal length" there and let the
vanishing points set orientation only.

## Real world scale, and getting the camera into Maya or Blender

A photograph carries no scale of its own. Vanishing points fix the camera's
orientation and focal length and nothing else, because a doll's house and a real
house photograph identically. Scale has to come from one measured length, and the
one a compositor actually knows is how high the camera was off the ground.

The Scale tab takes that height. Everything else on the node is then in the same
unit: cell size, and the grid offset that slides the floor along the ground.

| knob | meaning |
|---|---|
| working unit | feet, meters or centimeters |
| camera height | height above the ground plane, in that unit |

Feet is the default because US survey and location data is given that way.
Changing the dropdown converts the values you have already set rather than
reinterpreting them, so switching feet to meters leaves the setup physically
where it was. A full round trip returns the original numbers exactly.

Changing the height never disturbs the solved focal length or angles. That is
correct rather than a limitation: scale is unobservable in a single image, so
only the numbers change, not the picture.

`export camera` writes the height into the exported camera's translate, live
linked, and puts a `units` knob on it saying which unit the numbers are in. Set
the same linear unit at the other end before importing:

- Maya: Preferences, Settings, Linear
- Blender: Scene Properties, Units, Length

### The axis choice matters more for export than for the overlay

The two settings of `ground X axis runs toward` give complementary yaws that add
up to ninety degrees. In the viewer they look identical, because a square grid
turned ninety degrees about its own center is the same square grid. The choice
only becomes visible once the camera leaves Nuke and real geometry arrives on
it, where it decides which world direction is X and which is Z. Check it before
exporting, not after.

### The grid cannot move, because there is nothing left to move it with

There is no size knob and no distance knob. The floor is not an object that has
to be placed in front of the camera; it is the ground, worked out per pixel, and
the only things that change it are the solve and the camera height.

This replaced a real and stubborn bug. While the floor was a Card, the card's
`translate` genuinely did hold still across every size, and the grid still
appeared to move, because what moves when you scale a rectangle is its edges.
A test that measured the transform passed every time while the picture kept
moving. If you ever test this sort of thing yourself, measure the render.

## Every line feeds the vanishing point

A guide's two base lines and any line added with `add line` are fitted together.
The fit minimizes the perpendicular distance from the point to each line, with
each line normalized first so a long edge does not outvote a short one: line
length is how much of the edge was visible, not how much it deserves to be
trusted.

Two lines give exactly their intersection, to the last decimal, because a least
squares fit through two lines passes through both. So no existing guide moved.

A line whose two points sit on top of each other has no direction, weighs nothing
and draws nothing. That is what an unplaced slot looks like.

### `follows the vanishing point`, per line

The two behaviours are not one tool wearing different hats. They answer different
questions and both are worth having.

Ticked, the line runs out from the vanishing point through one point: a
prediction of where an edge should lie, for checking the fit against another
feature. It cannot vote, because it was drawn from the thing it would be voting
on, so it can neither help nor hurt.

Unticked, it is a line in its own right and a measurement: does this edge agree
with the others. Measured on traced lines, one thirty degrees off costs about
four degrees of camera roll among six good ones, and least squares squares the
residual so one bad line can outvote several good ones. That is the risk the
switch puts back under your control.

The default is ticked, and that is also why a guide from any earlier build is
safe to open. Rebuilding copies knob values by name; an older node has no switch
to copy, so the new one keeps the default and its added lines do exactly what
they always did. No conversion, and nothing to get wrong. A line you add arrives
ticked too, so adding one can never change the answer until you say it should.

### Lines that barely converge report a direction

Nearly parallel lines meet a very long way off, and out there the meeting point is
not a real quantity: it swings by a hundred thousand pixels when a line end moves
one, and it can land on the wrong side entirely. Their common direction is one of
the best determined things in the picture, because it is exactly what makes them
nearly parallel.

So the fit is rejected and replaced by that direction, placed very far along it,
when any of three things is true: the system is singular, the point lands beyond
a hundred frame diagonals, or the fit's angular error is over about half a degree.

The third is the one that matters and it took three attempts to find. The
determinant does not separate a good far fit from a failed near one: measured on a
facade, a fit that worked and a fit that put thirty degrees of roll on the camera
had determinants within 10% of each other. Nor does the raw residual, because a
point far away turns a hair of angular error into tens of pixels, so a good fit at
forty diagonals has a larger residual than a failed one sitting in the middle of
frame. The residual divided by how far away the fit landed is the angular error of
the fit, and that separated them by a factor of a hundred.

## Two guides, or three

Each guide marks one vanishing point. Two of them, following directions at right
angles to each other on the ground, give the focal length and the orientation. A
third along the upright edges is optional and solves the lens axis as well.

`these lines are` says which sort a guide is:

`grid offset` moves the floor. X and Z slide it along the ground in the two
directions the guides marked. Y raises and lowers the ground itself: the camera
stays at the height on the Scale tab and the ground sits at Y, so raising it
brings the floor nearer and spreads the cells down the frame, lowering it pushes
the ground away and bunches them toward the horizon. The horizon does not move
either way, because the horizon is where the ground goes at infinity.

| | |
|---|---|
| **ground** | runs away from you into the picture. Curbs, road markings, the seams in paving, the long side of a building going away. |
| **across** | runs left to right in front of you. The top of a wall facing the camera, a window sill or a roofline on it. |
| **vertical** | upright. Building corners, door frames, lamp posts. |

Despite the name, ground lines do not have to be on the ground, and across lines
do not have to be at eye level. Every level edge running the same way shares a
vanishing point whatever height it is at, so a roofline works as well as a curb
and is usually easier to trace than one with people standing on it. The two names
describe the direction, not the surface.

**Naming both level guides pins the world axes.** Ground becomes Z and across
becomes X, so an exported camera lands the right way round in Maya or Blender
instead of ninety degrees off, and `ground X axis runs toward` does not have to
guess. It is also the only way to stop an animated solve flipping, because
"auto" decides again on every frame. Two guides both left on ground still solve
exactly as before, and the panel says the axis is not pinned.

The vertical one you do not have to set. A guide drawn along uprights has two
steep lines and a vanishing point a long way off the frame, and a guide drawn
along a receding level direction cannot do both, because its lines run to a point
on the horizon. The odd one out of three is worked out from its own lines and the
knob is set to match.

Ground against across is never worked out from the picture, and that is
deliberate. The two are symmetric in the image and only the person who took the
photograph knows which way they were facing.

## The third guide: solving the lens axis instead of assuming it

Two vanishing points give two equations. That is enough for focal length and
orientation only if you already know where the lens axis sits on the frame, and
the tool assumed the center. That assumption is written into the expressions as
`width/2, height/2`, and it is false for any cropped, re-framed or shifted plate.
A cropped photograph then solves to the wrong focal length with nothing to
indicate trouble.

Set a third `dhPerspGuide` to **vertical** and place its two lines on upright
building edges. With three mutually perpendicular vanishing points the principal
point is the orthocenter of their triangle, so it is solved rather than assumed
(Caprile and Torre 1990; Hartley and Zisserman ch. 8). The focal length then
follows from the same formula already in use, with the solved point substituted
for the frame center.

Measured on a 35mm camera with the lens axis deliberately shifted, which is what
a crop is:

| lens axis shift | two guides | three guides | axis found |
|---|---|---|---|
| none | 35.00 mm | 35.00 mm | exactly center |
| 0.30 right | 34.13 mm | 35.00 mm | 672, 540 |
| 0.25 down | 34.20 mm | 35.00 mm | 960, 780 |
| 0.35, 0.20 | 34.39 mm | 35.00 mm | 624, 348 |
| half frame crop | 32.79 mm | 35.00 mm | 240, 108 |

The axis positions are exact, not approximate.

### It refuses a vertical guide it cannot trust

On a near level camera the verticals are almost parallel, so their vanishing
point runs off toward infinity and the orthocenter becomes noise. Measured at
0.4 degrees of pitch, it sat 391,668 px from the center of a 1920x1080 frame.
The solve detects that, ignores the vertical guide, falls back to the centered
assumption and says so in the panel rather than reporting a confident wrong
answer. Three things have to hold before the third guide is used: its vanishing
point has to be off the frame, because an untouched guide's sits on the center of
it; it has to be inside a sane distance, because verticals that barely converge
put it out at infinity where the orthocenter means nothing; and the lens axis it
produces has to land on the frame. The last one is the one that catches the rest.
A lens axis solved to a point half a frame diagonal away from the center is not a
lens axis, and the focal length is computed from it, so letting it through is how
a plate comes back reading a couple of millimeters. A camera tilted up or down, which is most architectural photography,
gives verticals that genuinely converge and is the case where the third guide
earns its keep.

Two-guide setups behave exactly as before.

## Nothing pops up

Every message the tools produce goes on the node that produced it, on a status
line under the buttons, where it can be read twice. A dialog interrupts you to
say something in a place you cannot look at again, and all of these are answers
to "I pressed the button, what happened".

The one dialog that asked a question rather than telling you something, "the
solve gives 4mm, export anyway", is gone too. It was asking about something the
Camera Solve tab already says in more detail than a dialog has room for. The
export goes ahead and the exported camera carries the warning on itself.

The two menu commands have no node to write to, so they print to the script
editor. They are the only ones.

## Animating the guides

Key the guide points and the camera moves with them. Nothing has to be switched
on: every link in the chain is an expression, an expression is evaluated per
frame, and the solve is no exception. The floor grid follows too.

Two things are worth knowing before you do it.

**Pin the ground axis first.** `ground X axis runs toward` defaults to picking
whichever vanishing point needs the smaller turn. Per frame that is a reasonable
answer; across a shot it is not, because the two answers are ninety degrees apart
and nothing stops it changing its mind halfway through. Measured on a keyed setup
it goes from -44.4 to +44.6 degrees between two frames, an eighty nine degree snap
in the middle of the move. Set it to vanishing point 1 or 2 and the largest step
between frames drops to under a degree. The panel says so when it sees keys on
the guides.

**Baking follows the move.** `bake values` samples the script's frame range and
writes a key per frame when the solve moves, and plain numbers when it does not.
It used to freeze the current frame either way, which turned a shot into a single
pose without saying anything.

If you are reading animated values in a script of your own, use `getValueAt`.
`value()` answers for whatever context the knob is in, and in a terminal session
that stays on the first frame however you set `nuke.frame`, so a moving camera
measures as a still one.

## The floor is the ground, not a card standing on it

There is no geometry in the floor at all. Every pixel is turned into a camera
ray, intersected with the plane `y = 0`, and the result is that point's real
position on the ground in the working unit. The grid is drawn from those two
numbers.

That is worth the change because a card cannot do this job:

- **A card has edges.** Scaling it about its center holds the lines still and
  walks its near edge toward the camera and its far edge toward the horizon, so
  the visible floor moves on every size change. No pivot fixes that.
- **A card cannot reach the horizon.** The horizon is the image of ground at
  infinity, so a finite plane always stops short and shows a far corner.
- **A card cannot be fine and far at once.** Covering the bottom of frame to the
  horizon with even cells needs roughly `3 x (horizon height in px) / gap` of
  them, about 545 at a 4 px gap, against Nuke's cap of 400 rows. Everything that
  used to be on the floor tab, the fit, the textured mode, the horizon fade, was
  a way of living with that number.

None of those apply to a plane with no edges. The floor now fills the frame side
to side, starts at the bottom with no near edge, and converges into the horizon
by construction, because ground above the horizon does not exist and the ray test
drops it.

### The cells are square by construction

The two ground directions come from the two horizontal vanishing points, and they
are perpendicular only when the focal length is exactly the one that makes them
so. That used to be guaranteed, because the focal length was solved from that
pair. It is not any more: on a facade the focal comes from a vertical pair, so
nothing forces the ground square and the cells come out as diamonds.

One Gram-Schmidt step fixes it. Whichever direction is better conditioned, meaning
its vanishing point is nearer the lens axis, is kept, and the other is derived
perpendicular to it in the same plane. Where the pair really was perpendicular
this changes nothing at all, because the derived direction is the one that was
already there. Where it was not, the direction being replaced is the one that was
least trustworthy anyway. Measured: a case whose vanishing points disagreed by 31
degrees draws at 90.0000.

### Where the lines close up, coverage replaces nearest-line

The mask asks how far a pixel is from the nearest grid line. That is the right
question while the lines are further apart than a pixel. Closer than that several
land inside one pixel, counting only the nearest throws the rest away, and the
answer flips on and off with whichever line happened to fall nearest the sample.
That is moire.

Down there the answer is the fraction of the ground the lines cover, which is
line width over line spacing. It reaches solid smoothly as the spacing closes,
because the ground really is covered, and it cannot alias because it does not
depend on where the sample fell. The two are blended on the spacing: nearest-line
above four widths apart, coverage below two, a ramp between.

The ground coordinate is clamped before `floor()` as well. At the horizon it
grows without limit and `floor(inf) - inf` is a nan that would paint one bad
pixel.

### `thin out lines too fine to draw`, and why it is off

Off, which is the default, the grid is drawn at full strength all the way to the
horizon. Where the lines close up tighter than a pixel the ground fills in solid,
because that is what lines a fraction of a pixel apart actually do, and there is
a band of moire on the way in. The horizon is the thing you line up against, so a
grid that reaches it beats a tidier one that stops short.

On, each direction dims in proportion to how far apart its own lines are, so the
far half stays clean at the cost of the grid running out before the horizon. How
early depends on the cell size: fine cells run out sooner than coarse ones,
because they are the ones that close up first.

The dimming runs on the square root of the spacing. A family of ground lines
closes up as the square of the distance to the horizon, so a fade linear in
spacing happens over almost no screen distance and reads as a hard edge. On the
square root it is linear in distance from the horizon.

Two things follow. A thicker `line width` needs more room before lines can be
drawn cleanly, so with the switch on it runs out slightly further from the
horizon; the sides and the bottom do not move either way. And sub pixel spacing
is also where a ground coordinate runs out of fractional precision, so the solid
fill is doing double duty: it is the right picture and it is why there is no
noise up there.

## Updating nodes made by an older build

These are Groups so the render farm can run them without the gizmo installed.
The price is that a Group is copied into the script when it is created, so a node
already in a comp keeps the internals it was born with: editing the `.gizmo` on
disk fixes new nodes and does nothing for old ones.

That is not theoretical. The floor card's position used to be tied to its size
(`* parent.gridsize/2`), so growing the grid moved it. The expression was fixed,
and nodes created before the fix carried on moving.

It happens on its own. Each node carries a hidden build number, and opening a
script rebuilds any node that is behind, in place, keeping placed points, knob
values and expression links. It is quiet unless something was actually rebuilt,
and it leaves the script's modified flag where it found it, so a script that was
clean when you opened it stays clean.

Only in the GUI. A render runs the internals the script was saved with, which is
the entire reason these are declared `Group` rather than `Gizmo`.

The thing that has to keep working for this to keep working is recognition. A
node used to be identified as a solve by having a `gridsize` knob, which was fine
until the build that removed `gridsize`; after that a current node could not be
recognized, so a later build could never have updated one. They are identified by
their two vanishing points now, which is what the node is for and so is the last
thing that would ever be taken away.

## Guides that describe no camera are refused, not solved

Two vanishing points only describe a real camera when the lens axis falls between
them along the horizon. That is not a rule of thumb, it is what
`(V1-P).(V2-P) + f^2 = 0` says: with `s1` and `s2` the signed distances from the
lens axis along the horizon, `f^2 = -s1*s2 - oivi^2`, so the product has to be
negative and large enough to leave room for a focal length.

The focal length used to come from `sqrt(v1*v2 - oivi^2)` with `v1` and `v2` as
plain unsigned distances. Those agree exactly wherever a camera exists, and where
one does not the unsigned form still returns something: the suite has it
inventing a 56 mm lens for a pair that describes nothing at all, and near the
boundary it returns a few millimeters, which is how a 55 mm lens reads as 4 mm.

The Camera Solve tab now carries a verdict line. It says the guides do not
describe a camera, and the usual cause: one guide following the same ground
direction as the other, or one of its lines not on a receding edge. It also flags
a solve that works out but lands somewhere improbable, such as outside 8 to 200
mm or rolled more than a few degrees.

A near one point shot is the common honest case. There, tick **I know the focal
length** and let the guides set orientation only.

## An unplaced guide is refused, not solved

A fresh `dhPerspGuide` has its two lines crossing at the exact center of frame.
That is the principal point, so an untouched guide's vanishing point lands on it
and every term in the focal formula collapses. Feeding one to the solve used to
produce a confident looking small number, measured at 0.000 mm where the real
answer was 28.27 mm.

The panel now names any guide still sitting at its default cross, and the camera
export refuses rather than handing over a meaningless camera. Exporting a solve
outside 4 to 400 mm asks for confirmation first.
