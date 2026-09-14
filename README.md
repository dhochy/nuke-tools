# nuke-tools

Personal Nuke gizmos, scripts, plugins, and remote workstation tools.

## Perspective tools

Solve a camera from a single photograph by tracing lines along edges that are
parallel in the real world.

Two nodes, under **Nodes > DH_Tools > 3D**:

- **dhPerspGuide** marks one direction in the scene.
- **dhPerspSolve** turns two or three guides into a camera.

Both carry their own instructions: the `?` button says what the node is, and the
**How to use** tab has the steps. This is the same thing in one place.

### Solving a camera

1. Put a **dhPerspGuide** under your plate. Drag its two lines onto two edges
   that are parallel in real life but converge on screen. Two curbs, the top and
   bottom of the same wall, two window sills on the same facade.
2. Set **these lines are**:
   - **ground** for a direction running away from you into the picture
   - **across** for one running left to right in front of you
   - **vertical** for upright edges
3. Add a second guide for the other level direction, at right angles to the
   first. One ground and one across.
4. Optionally add a third along the uprights. It lets the solve find the real
   lens axis instead of assuming the center of frame, which is what makes a
   cropped or shifted plate solve correctly. Leave it on **ground** if you like;
   with three guides connected the upright one is recognized from its own lines.
5. Drop a **dhPerspSolve** under the last guide. It links itself.
6. Read the verdict on the **Camera Solve** tab. It says whether these guides
   describe a camera that can exist, and what is wrong if they do not.
7. Set the **camera height** on the **Scale** tab. That is the one measurement
   that gives a photograph real scale.
8. Press **export camera**.

### Things worth knowing

**More lines make a better guide.** `add line` gives you another line with its
own point A and point B, and every line on the node feeds the vanishing point,
not just the first two. Two lines still give exactly their intersection, so
nothing about an existing guide changes; four or six give a point that no single
mis-traced edge can drag around. That matters most on a wall square to the
camera, where the lines barely converge and a pixel of placement moves the
vanishing point by thousands.

**The lines do not have to be on the ground.** Every level edge running the same
way shares a vanishing point whatever height it is at, so a roofline works as
well as a curb and is usually easier to trace. Longer lines are better than
shorter ones: a short line placed a pixel out swings its vanishing point a long
way.

**The floor is the check.** The grid is drawn from the solve, so if it lies flat
on the ground in the plate and runs along the same directions, the camera is
right. It reaches the horizon and fills in solid where the lines get finer than a
pixel; `thin out lines too fine to draw` stops that at the cost of the grid
ending short of the horizon.

**Camera height changes nothing in the solve.** Focal length, tilt, pan, roll and
lens axis are identical at any height, because scale is unobservable in a single
image. Height only decides how big the world is. Set `cell size` to something you
can measure in the plate and adjust the height until the cells match.

**Name both level guides before exporting to Maya or Blender.** Ground and across
are what pin the world X and Z axes. Left unnamed, which way round the scene
arrives is a guess.

**Animation works.** Key the guide points and the camera follows, frame by frame,
and so does the floor. Pin the axis first: on automatic the choice is made again
every frame and can flip ninety degrees mid shot. `bake values` keeps the whole
move.

**A near one point shot cannot be solved from guides alone.** Looking straight
down a street, one of the two directions barely converges and its vanishing point
is unreliable. Tick **I know the focal length** and let the guides set the
orientation only.

### Nodes made by an older build

They bring themselves up to date when the script is opened. There is no menu
command and nothing to remember. It only happens in the GUI: a render runs the
internals the script was saved with.

### More

[PERSPECTIVE_TOOLS.md](PERSPECTIVE_TOOLS.md) is the long version: the geometry,
what each decision was measured against, and the traps found along the way.

Tests live in `tests/`. Run one with
`"C:/Program Files/Nuke17.0v1/Nuke17.0.exe" -t tests/suite.py`.
`tools/sync.py` keeps this repo and the `.nuke` install in step.
