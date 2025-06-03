from ursina import *
from tkinter import simpledialog
import importlib
import sys

app = Ursina()

# ─── Globals ──────────────────────────────────────────────
deleting      = False
selecting     = None
snap_enabled  = False
snap_size     = 1.0
rotation_snap = 15.0
objects       = []

delete_button = None
snap_button   = None

# ─── DebugBehaviour (with Highlight + Snap-on-Release) ─────
class DebugBehaviour():
    def __init__(self) -> None:
        self.entity: Entity
        self._orig_color = None

    def update(self):
        # Ensure clicking calls toggle()
        self.entity.on_click = self.toggle

        # Only allow transformations if this instance is selected
        if selecting != self:
            return

        # — Scale vs. Move (continuous) —
        if held_keys["shift"]:
            # Continuous scaling while Shift + arrows/page keys held
            self.entity.scale_z += (held_keys['up arrow'] - held_keys['down arrow']) \
                                  * (time.dt * (1 if held_keys['control'] else 5) if not held_keys['alt'] else 0)
            self.entity.scale_y += (held_keys['page up'] - held_keys['page down']) \
                                  * (time.dt * (1 if held_keys['control'] else 5) if not held_keys['alt'] else 0)
            self.entity.scale_x += (held_keys['right arrow'] - held_keys['left arrow']) \
                                  * (time.dt * (1 if held_keys['control'] else 5) if not held_keys['alt'] else 0)
        else:
            # Continuous movement while arrows/page keys held
            self.entity.z += (held_keys['up arrow'] - held_keys['down arrow']) \
                            * (time.dt * (1 if held_keys['control'] else 5) if not held_keys['alt'] else 0)
            self.entity.y += (held_keys['page up'] - held_keys['page down']) \
                            * (time.dt * (1 if held_keys['control'] else 5) if not held_keys['alt'] else 0)
            self.entity.x += (held_keys['right arrow'] - held_keys['left arrow']) \
                            * (time.dt * (1 if held_keys['control'] else 5) if not held_keys['alt'] else 0)

        # — Continuous Rotation (X/Z, C/V, B/N) —
        self.entity.rotation_y += (held_keys['x'] - held_keys['z']) \
                                 * time.dt * (10 if held_keys['control'] else 20)
        self.entity.rotation_x += (held_keys['c'] - held_keys['v']) \
                                 * time.dt * (10 if held_keys['control'] else 20)
        self.entity.rotation_z += (held_keys['b'] - held_keys['n']) \
                                 * time.dt * (10 if held_keys['control'] else 20)

        # ▶ Removed per-frame snapping from here.
        # ▶ Snapping now occurs on key-release in input().

    def input(self, key):
        # Only respond if this instance is selected
        if selecting != self:
            return

        # Press F to print debug info
        if key == 'f':
            print(f"'{self.entity.name}' pos : {self.entity.position}")
            print(f"'{self.entity.name}' rot : {self.entity.rotation}")

        # — Alt + arrows/page keys: discrete ±1 steps, then integer‐snap immediately —
        if held_keys["shift"]:
            if held_keys['alt']:
                # Discrete scaling steps
                self.entity.scale_z += (int(key == 'up arrow') - int(key == 'down arrow'))
                self.entity.scale_y += (int(key == 'page up') - int(key == 'page down'))
                self.entity.scale_x += (int(key == 'right arrow') - int(key == 'left arrow'))
                if key not in ('alt',):
                    # Snap scale to nearest integer
                    self.entity.scale_x = int(self.entity.scale_x)
                    self.entity.scale_y = int(self.entity.scale_y)
                    self.entity.scale_z = int(self.entity.scale_z)
        else:
            if held_keys['alt']:
                # Discrete movement steps
                self.entity.z += (int(key == 'up arrow') - int(key == 'down arrow'))
                self.entity.y += (int(key == 'page up') - int(key == 'page down'))
                self.entity.x += (int(key == 'right arrow') - int(key == 'left arrow'))
                if key not in ('alt',):
                    # Snap position to nearest integer
                    self.entity.x = int(self.entity.x)
                    self.entity.y = int(self.entity.y)
                    self.entity.z = int(self.entity.z)

        # — Snap-on-release if snap_enabled is True —
        if snap_enabled:
            # Snap position when any arrow or page key is released
            if key in (
                'up arrow up', 'down arrow up',
                'left arrow up', 'right arrow up',
                'page up up', 'page down up'
            ):
                px = round(self.entity.x / snap_size) * snap_size
                py = round(self.entity.y / snap_size) * snap_size
                pz = round(self.entity.z / snap_size) * snap_size
                self.entity.position = Vec3(px, py, pz)

            # Snap rotation when any rotation key is released
            if key in ('x up', 'z up', 'c up', 'v up', 'b up', 'n up'):
                ry = round(self.entity.rotation_y / rotation_snap) * rotation_snap
                rx = round(self.entity.rotation_x / rotation_snap) * rotation_snap
                rz = round(self.entity.rotation_z / rotation_snap) * rotation_snap
                self.entity.rotation = Vec3(rx, ry, rz)

    def toggle(self):
        global selecting, deleting

        # If delete mode is active, destroy entity immediately
        if deleting:
            if self.entity in objects:
                objects.remove(self.entity)
            destroy(self.entity)
            del self
            return

        # Deselect if clicking the already-selected entity
        if selecting == self:
            if self._orig_color is not None:
                self.entity.color = self._orig_color
            selecting = None
            return

        # If some other entity was selected, restore its color first
        if selecting is not None:
            if selecting._orig_color is not None:
                selecting.entity.color = selecting._orig_color
            selecting = None

        # Now select this entity: store original color and apply highlight
        selecting = self
        if self._orig_color is None:
            self._orig_color = self.entity.color
        self.entity.color = color.azure

# ─── Global Input (Escape to Unselect) ─────────────────────
def input(key):
    global selecting
    if key == 'escape' and selecting is not None:
        # Restore original color on Escape
        if selecting._orig_color is not None:
            selecting.entity.color = selecting._orig_color
        selecting = None

# ─── “Add New Object” ──────────────────────────────────────
def addnew():
    name     = simpledialog.askstring("Add new Object", "Enter Object's name")
    model    = simpledialog.askstring("Add new Object", "Enter Object's Model name")
    texture  = simpledialog.askstring("Add new Object", "Enter Object's Texture name")
    collider = simpledialog.askstring("Add new Object", "Enter Object's Collider type")
    try:
        e = Entity(
            name     = name if name not in (None, "") else None,
            model    = model if model not in (None, "") else "cube",
            texture  = texture if texture not in (None, "") else "grass",
            collider = collider if collider not in (None, "") else None
        )
        e.add_script(DebugBehaviour())
        if e.model is None:
            e.model = 'cube'
        objects.append(e)
    except:
        pass

# ─── “Toggle Delete Mode” ──────────────────────────────────
def toggleDelete():
    global deleting
    deleting = not deleting

    if deleting:
        delete_button.text = 'Delete: ON'
        delete_button.color = color.red
        delete_button.text_color = color.white
    else:
        delete_button.text = 'Delete: OFF'
        delete_button.color = color.white
        delete_button.text_color = color.black

# ─── “Toggle Snap Mode” ────────────────────────────────────
def toggleSnap():
    global snap_enabled
    snap_enabled = not snap_enabled

    if snap_enabled:
        snap_button.text = 'Snap: ON'
        snap_button.color = color.azure
        snap_button.text_color = color.white
    else:
        snap_button.text = 'Snap: OFF'
        snap_button.color = color.white
        snap_button.text_color = color.black

# ─── “Save” (restores color before writing) ────────────────
def save():
    global selecting
    # If an entity is still selected, restore its color first
    if selecting is not None:
        if selecting._orig_color is not None:
            selecting.entity.color = selecting._orig_color
        selecting = None

    # Serialize each entity in 'objects' using repr()
    code = "from ursina import *\n\n"
    for i in objects:
        code += repr(i) + "\n"
    with open('scene.py', 'w') as file:
        file.write(code)

# ─── “Load” (clears scene and reloads scene.py) ─────────────
def load():
    scene.clear()
    camera.overlay.color = color.clear
    if 'scene' in sys.modules:
        importlib.reload(sys.modules['scene'])
    else:
        importlib.import_module('scene')

    for e in scene.entities:
        if not e.eternal:
            objects.append(e)
            e.add_script(DebugBehaviour())

# ─── UI SETUP ──────────────────────────────────────────────

# Background panel for buttons
Entity(
    model      = Quad(.1, aspect = .7),
    color      = color.black33,
    parent     = camera.ui,
    scale      = (.7, 1),
    x          = -0.6479,
    eternal    = True
)

# “Add new Object” button
Button(
    'Add new Object',
    position   = Vec3(-0.6127, 0.3932, -0.895),
    color      = color.white,
    highlight_color = color.light_gray,    # ← this line
    on_click   = addnew,
    scale      = (.5, .1),
    text_color = color.black,
    eternal    = True
)

# “Toggle Delete Mode” button
delete_button = Button(
    'Delete: OFF',
    position   = Vec3(-0.6127, 0.1932, -0.895),
    color      = color.white,
    highlight_color = color.light_gray,    # ← this line
    on_click   = toggleDelete,
    scale      = (.5, .1),
    text_color = color.black,
    eternal    = True
)

# “Snap-to-Grid” button
snap_button = Button(
    'Snap: OFF',
    position   = Vec3(-0.6127, 0.05, -0.895),
    color      = color.white,
    highlight_color = color.light_gray,    # ← this line
    on_click   = toggleSnap,
    scale      = (.5, .1),
    text_color = color.black,
    eternal    = True
)

# “Save” button
Button(
    'Save',
    position   = Vec3(-0.6127, -0.1932, -0.895),
    color      = color.white,
    on_click   = save,
    highlight_color = color.light_gray,    # ← this line
    scale      = (.5, .1),
    text_color = color.black,
    eternal    = True
)

# “Load” button
Button(
    'Load',
    position   = Vec3(-0.6127, -0.3032, -0.895),
    color      = color.white,
    highlight_color = color.light_gray,    # ← this line
    on_click   = load,
    scale      = (.5, .1),
    text_color = color.black,
    eternal    = True
)

# Ground grid (eternal)
Entity(
    model      = Grid(512, 512),
    rotation_x = 90,
    scale      = 512,
    color      = color.white33,
    x          = .5,
    z          = .5,
    y          = -.5,
    eternal    = True
)

# Sky and EditorCamera (both eternal)
Sky(eternal=True)
EditorCamera(eternal=True)

app.run()



"""
Below are several ideas—ranging from small usability tweaks to larger feature additions—that can make your in‐scene editor even more powerful, intuitive, and robust. You can pick and choose whichever feel most useful for your workflow.

---

## 1. On‐Screen Numeric Input & Sliders (Instead of Tkinter Pop‐ups)

### Why

Having to type every model/texture/collider name into separate Tkinter dialogs can be interruptive. An in‐Ursina UI panel with text fields and sliders lets you stay in one window.

### How

1. **Create a collapsible UI panel** (e.g. a `Panel` or a `Window`‐like `Entity` parented to `camera.ui`) that appears when you click “Add new Object.”

2. Inside that panel, place `InputField` objects for:

   * Object Name
   * Model Name (drop‐down or free‐form)
   * Texture Name (drop‐down or free‐form)
   * Collider Type (drop‐down of `None`, `box`, `sphere`, `mesh`)

   Example:

   ```python
   panel = Entity(parent=camera.ui, model='quad', color=color.rgba(30,30,30,200),
                  scale=(.6, .7), x=0.2, y=0.2, visible=False)  # hidden by default

   name_input = InputField(parent=panel, hint='Object Name', x=-.2, y=0.25, scale=(.4,.07))
   model_input = InputField(parent=panel, hint='Model (e.g. cube)', x=-.2, y=0.1, scale=(.4,.07))
   texture_input = InputField(parent=panel, hint='Texture (e.g. grass)', x=-.2, y=-.05, scale=(.4,.07))
   collider_input = InputField(parent=panel, hint='Collider (box/sphere/…)', x=-.2, y=-.2, scale=(.4,.07))

   Button('Create', parent=panel, x=0.25, y=-.35, scale=(.3,.1),
          on_click=lambda: finalize_new_object())
   Button('Cancel', parent=panel, x=-0.25, y=-.35, scale=(.3,.1),
          on_click=lambda: setattr(panel, 'visible', False))
   ```

3. When the user clicks **“Add new Object,”** set `panel.visible = True`.

4. In `finalize_new_object()`, read `name_input.text`, etc., and do exactly what `addnew()` did (create the entity, attach `DebugBehaviour()`, append to `objects`). Then hide the panel.

> **Benefit:**
> • No more external windows popping up.
> • You can also add sliders right in this panel for initial scale, rotation, or position if you want more control.

---

## 2. Visual Move/Rotate/Scale Gizmos

### Why

Clicking and holding arrow keys works, but it’s hard to know exactly which axis you’re transforming at a glance. A gizmo (colored arrows/handles for X/Y/Z) gives clear, direct manipulation.

### How

* **Add a “Gizmo” entity** that appears around the selected object:

  1. When an entity is selected, spawn three arrow models (one for X, one for Y, one for Z) at its position. Color them:

     * X‐axis: red
     * Y‐axis: green
     * Z‐axis: blue
  2. Detect when the user clicks+drags on one of these arrows:

     * Raycast from the mouse into the world (using `mouse.point` or `mouse.world_point`) to see if the cursor intersects one of your arrow colliders.
     * If they click and drag along that arrow’s axis, move the object along that axis in real time.

Example approach (pseudocode):

```python
class Gizmo:
    def __init__(self, target_entity):
        self.target = target_entity
        self.arrows = {
            'x': Entity(model='arrow.obj', color=color.red, parent=target_entity, scale=0.5, rotation=Vec3(0,0,90)),
            'y': Entity(model='arrow.obj', color=color.green, parent=target_entity, scale=0.5),
            'z': Entity(model='arrow.obj', color=color.blue, parent=target_entity, scale=0.5, rotation=Vec3(90,0,0))
        }
        for e in self.arrows.values():
            e.collider = 'box'
            e.always_on_top = True  # so you can click it even if behind the mesh

        self.selected_axis = None

    def update(self):
        # Position the gizmo at target’s pivot each frame
        for axis, arrow in self.arrows.items():
            arrow.world_parent = None
            arrow.position = self.target.world_position
            arrow.rotation = arrow.rotation  # keep arrow oriented

        # Raycast to see if mouse is hovering any arrow; highlight it
        if held_keys['left mouse']:
            hit_info = raycast(camera.world_position, camera.forward, ignore=(self.target,), distance=100)
            if hit_info.entity in self.arrows.values():
                self.selected_axis = [k for k,v in self.arrows.items() if v == hit_info.entity][0]
        else:
            self.selected_axis = None

        if self.selected_axis:
            # While mouse is down, project mouse movement onto that axis and move target
            # e.g. compute delta = (mouse.world_point - last_point).dot(axis_vector)
            # target.position += axis_vector * delta
            pass
```

* **Attach the gizmo when an entity becomes selected** (inside `DebugBehaviour.toggle()`). Remove it when deselected or when entering Delete mode.

> **Benefit:**
> • More precise, visual control, just like in Unity/Blender.
> • Axis‐locking comes for free—drag only along the colored arrow.

---

## 3. Multi‐Select & Group Transforms

### Why

Often you want to move or rotate several objects together (e.g. a table + chairs). Right now you can only select one at a time.

### How

1. **Shift‐Click or Ctrl‐Click to Add to Selection**

   * Maintain a `selected_entities = []` list instead of a single `selecting`.
   * If you click an entity while holding **Shift**, append it to `selected_entities` if it isn’t already there; otherwise remove it from the list.
   * If you click without any modifier, clear `selected_entities` and only select that one.

2. **Drawing a Selection Rectangle**

   * On **mouse down**, record `mouse.screen_position`. On **mouse up**, measure the rectangle area and check which entities’ screen‐space bounding boxes fall inside, adding them to `selected_entities`.

3. **Transform All Together**

   * In your `update()` and `input()` logic, if `selected_entities` has more than one, apply the same delta to each entity.
   * You might also generate a single “group pivot” (e.g. the centroid) and rotate/scale around that.

Example snippet:

```python
selected_entities = []

def debug_toggle(self):
    global selected_entities
    if deleting:
        destroy(self.entity)
        if self.entity in objects: objects.remove(self.entity)
        return

    if held_keys['shift']:
        # multi‐select logic
        if self.entity in [d.entity for d in selected_entities]:
            # deselect this one
            for d in selected_entities:
                if d.entity == self.entity:
                    # restore its color
                    if d._orig_color: d.entity.color = d._orig_color
                    selected_entities.remove(d)
                    break
        else:
            # add to selection
            self._orig_color = self.entity.color
            self.entity.color = color.azure
            selected_entities.append(self)
    else:
        # single‐select mode: clear old selection, then pick this
        for d in selected_entities:
            if d._orig_color: d.entity.color = d._orig_color
        selected_entities = [self]
        if self._orig_color is None:
            self._orig_color = self.entity.color
        self.entity.color = color.azure
```

> **Benefit:**
> • Faster batch operations, e.g. line up chairs in one go.
> • More flexible scene composition.

---

## 4. Undo / Redo Stack

### Why

Everyone makes mistakes. If you accidentally move or delete something, it’s good to have an “undo” command (Ctrl+Z, Ctrl+Y).

### How

1. **Data Structure**

   * Maintain two stacks: `undo_stack` and `redo_stack`.
   * Each “action” you do (move, rotate, scale, delete, create) pushes a record onto `undo_stack` describing how to revert it. E.g. `{ type: 'move', entity: e, from: old_pos, to: new_pos }`.

2. **Capturing Actions**

   * In `DebugBehaviour.update()` or `input()`, detect the moment a transformation starts (e.g. first frame arrow key is pressed), record the entity’s original position/rotation/scale, then on key‐release, record the final state.
   * For deletes, record `{ type: 'delete', entity_repr: repr(e) }` so you can recreate it on undo. For create, record `{ type: 'create', entity: e }`.

3. **Implementing Undo**

   * Hook `input('control z')` at the top‐level. When triggered, pop from `undo_stack` and:

     * For `'move'`: set `entity.position = from`;
     * For `'rotate'`: set `entity.rotation = from`;
     * For `'scale'`: set `entity.scale = from`;
     * For `'delete'`: re‐`exec(entity_repr)` or regenerate the entity from the saved state;
     * For `'create'`: destroy the newly created entity.

   * Then push the inverse action onto `redo_stack` so you can redo it.

4. **Implementing Redo**

   * Hook `input('control y')`. Pop from `redo_stack` and reapply that action, then push back onto `undo_stack`.

> **Benefit:**
> • Safer editing—no accidental data loss.
> • Encourages “playful” experimentation because you know you can always step back.

---

## 5. JSON or Custom Scene Format (Instead of Raw Python)

### Why

Writing a `.py` via `repr(entity)` is simple, but brittle:

* If the user or engine changes default parameters, reloading might break.
* Arbitrary code injection risk if someone edits `scene.py` by hand.
* Harder to extend to lights, cameras, scripts with custom logic.

### How

1. **Define a JSON schema** for each entity:

   ```json
   {
     "name": "Cube",
     "model": "cube",
     "texture": "grass",
     "position": [1, 2, 3],
     "rotation": [0, 45, 0],
     "scale": [1, 1, 1],
     "collider": "box",
     "color": [255, 255, 255, 255]
   }
   ```
2. **Serialization** (`save()`):

   * Loop through `objects` and build a Python list of dicts, then `json.dump()` it to `scene.json`.

   ```python
   import json
   def save_json():
       data = []
       for e in objects:
           data.append({
               "name": e.name,
               "model": e.model.name if hasattr(e.model, 'name') else str(e.model),
               "texture": e.texture.name if hasattr(e.texture, 'name') else str(e.texture),
               "position": [e.x, e.y, e.z],
               "rotation": [e.rotation_x, e.rotation_y, e.rotation_z],
               "scale":    [e.scale_x, e.scale_y, e.scale_z],
               "collider": e.collider,
               "color":    [e.color.r, e.color.g, e.color.b, e.color.a],
           })
       with open('scene.json', 'w') as f:
           json.dump(data, f, indent=2)
   ```
3. **Deserialization** (`load_json()`):

   * `json.load()` the file, then for each entry do:

     ```python
     e = Entity(
         name     = obj["name"],
         model    = obj["model"],
         texture  = obj["texture"],
         position = tuple(obj["position"]),
         rotation = tuple(obj["rotation"]),
         scale    = tuple(obj["scale"]),
         collider = obj["collider"],
         color    = tuple(obj["color"]),
     )
     e.add_script(DebugBehaviour())
     objects.append(e)
     ```
   * Clear the scene exactly as before, then call `load_json()`.

> **Benefit:**
> • Safer and more portable format.
> • Easier for other tools or scripts to inspect/modify your scene.
> • You can extend it later (e.g. save lights, cameras, custom scripts).

---

## 6. Visual Feedback for Snap Grid and Axis

### Why

When snapping is on, it helps to see the grid spacing (especially if `snap_size` is something like 0.5 or 2.0). Also—if you do axis‐locked transforms—it’s good to see an indicator on the entity.

### How

1. **Grid Overlay**

   * When the user toggles Snap (and if `snap_size > 1`), render a thin wireframe grid on the ground that matches the snap spacing.

   * Example:

     ```python
     def show_grid_overlay():
         # destroy existing overlay if any
         if hasattr(self, 'grid_overlay'): destroy(self.grid_overlay)
         size = 20  # half‐extent in world units
         lines = []
         step = snap_size
         for i in range(-int(size/step), int(size/step)+1):
             # vertical lines
             lines.append(Entity(model=Mesh(vertices=[(-size, 0, i*step), (size, 0, i*step)]), color=color.gray))
             # horizontal lines
             lines.append(Entity(model=Mesh(vertices=[(i*step, 0, -size), (i*step, 0, size)]), color=color.gray))
         self.grid_overlay = Entity()  # parent for all lines
         for l in lines: l.parent = self.grid_overlay
     ```

   * Call `show_grid_overlay()` whenever `snap_enabled` toggles on, and hide/destroy those lines when you toggle off.

2. **Axis Highlight**

   * When you begin dragging on a gizmo arrow (from section 2), change that arrow’s color to a brighter shade (e.g. from `red` to `color.orange`) and/or throttle the other two arrows to a darker gray so you know which axis is active.

---

## 7. “Duplicate” / “Clone” Functionality

### Why

Rather than “Add new Object” from scratch, often you want to duplicate an existing object (including its position/rotation/scale/texture).

### How

1. When an entity is selected, offer a keyboard shortcut (e.g. **Ctrl+D**) or a button labeled “Duplicate.”
2. In your handler, do:

   ```python
   if selected_entity:
       orig = selected_entity.entity
       clone = Entity(
           name     = f"{orig.name}_copy",
           model    = orig.model.name if hasattr(orig.model, 'name') else orig.model,
           texture  = orig.texture.name if hasattr(orig.texture, 'name') else orig.texture,
           position = orig.position + Vec3(1,0,1),  # offset so they’re not exactly overlapped
           rotation = orig.rotation,
           scale    = orig.scale,
           collider = orig.collider,
           color    = orig.color
       )
       clone.add_script(DebugBehaviour())
       objects.append(clone)
       # Deselect the old one, select the clone
       selected_entity.entity.color = selected_entity._orig_color
       selecting = None

       # Now select clone:
       db = clone.scripts[-1]  # assuming it’s the only script
       db._orig_color = clone.color
       clone.color = color.azure
       selecting = db
   ```

   * This gives you a brand‐new object identical to the old one, just moved slightly.

> **Benefit:**
> • Speeds up scene building.
> • Encourages rapid iteration.

---

## 8. Context Menus & Right‐Click Actions

### Why

Right now you click to select or delete (if in Delete mode). It might be more intuitive if right‐clicking brought up a small menu (e.g. “Delete,” “Duplicate,” “Rename,” “Change Texture”).

### How

1. In `DebugBehaviour.input()`, watch for `key == 'right mouse down'` when `selecting == self`.
2. Spawn a tiny context panel near the mouse screen position:

   ```python
   def on_right_click(self):
       if self.menu: self.menu.enabled = False
       self.menu = Entity(parent=camera.ui, model='quad', scale=(.2,.2), color=color.rgba(50,50,50,200))
       # Position it at mouse.screen_position
       self.menu.position = mouse.screen_position
       Button('Delete', parent=self.menu, y=0.05, scale=(.9,.2),
              on_click=lambda: (toggleDelete(), self.menu.disable()))
       Button('Duplicate', parent=self.menu, y=-0.1, scale=(.9,.2),
              on_click=lambda: (duplicate_entity(self.entity), self.menu.disable()))
       # etc…
   ```
3. Tie that into `toggle()` logic so you don’t conflict with left‐click select.

> **Benefit:**
> • More discoverable options per‐object without cluttering the main UI.
> • Conveys additional operations (rename, change texture) right at the entity.

---

## 9. Property Inspector Panel

### Why

Seeing raw numbers for position/rotation/scale is nice, but sometimes you want exact control or to tweak something by typing “3.47” or “45°.”

### How

1. Create a second panel on the side (or bottom) that displays the currently selected entity’s properties in real time:

   * `InputField` for X, Y, Z
   * `InputField` for rotation\_x, rotation\_y, rotation\_z
   * `InputField` for scale\_x, scale\_y, scale\_z
   * Buttons or drop‐downs to change `model`, `texture`, `collider`, `color`.

2. Whenever `selecting` changes, populate those fields with the selected entity’s `.position`, `.rotation`, `.scale`.

3. Whenever you type into those fields and press Enter, immediately apply that value to the entity. For instance:

   ```python
   def on_pos_x_enter():
       if selecting:
           try:
               selecting.entity.x = float(pos_x_input.text)
           except:
               pass  # invalid number → ignore
   ```

4. Hook all six fields similarly, plus `on_attr_change` for `model_input`, `texture_input`, etc., so you can type a new model name (e.g. “sphere”) and it updates the mesh on the fly.

> **Benefit:**
> • Precise numeric control without relying solely on key-press increments.
> • A central “inspector” just like professional editors.

---

## 10. Improved Error Handling & Validation

### Why

Right now if you type a bogus model name, nothing appears, and you get no feedback. It’s better to give an error message or disable the “Create” button until inputs are valid.

### How

1. **Validate Model & Texture**

   * Before spawning, check `application.asset_folder` or `loader.models` to see if `model_input.text` actually exists. If not, show a small red warning text underneath the input.
   * Similarly for `texture_input.text`: verify `load_texture(texture_input.text)` succeeds or catch an exception and display an error.

2. **Disable “Create” Until Valid**

   * In your `on_text_changed` callback for `model_input`/`texture_input`, run validation. If everything is OK, set the “Create” button’s `enabled = True`; otherwise `enabled = False`.

> **Benefit:**
> • Prevents frustration from invisible objects.
> • Provides immediate feedback for typos.

---

## 11. Tooltips & Help Overlay

### Why

With all these advanced features (snap modes, gizmos, context menus), it helps to have a quick reference.

### How

1. **Tooltips on Hover**

   * For each button, set `button.tooltip = "…"`. Ursina will show a small popup text when the mouse lingers. E.g. `delete_button.tooltip = "Toggle delete mode (click object to delete)"`.

2. **Help Panel**

   * A small “?” icon on the UI that, when clicked, toggles a translucent overlay explaining:

     * “Arrows = move; Shift+arrows = scale; X/Z = rotate around Y; C/V = rotate around X; B/N = rotate around Z.”
     * “Alt + arrows = snap ±1; Ctrl + modifier = fine movement.”
     * “Esc = unselect; Ctrl+Z = undo; Ctrl+D = duplicate.”
     * “Right‐click entity = context menu….”

> **Benefit:**
> • Speeds up the learning curve for new users.
> • Reduces need for external documentation.

---

## 12. Performance & Clean‐Up

### Why

As scenes grow large, constantly updating every `DebugBehaviour` (and potentially dozens of gizmos, grid lines, etc.) can slow down the frame rate.

### How

1. **Only Update When Necessary**

   * In `DebugBehaviour.update()`, wrap heavy logic in a check so that if this entity isn’t near the camera or not selected, you skip certain checks (e.g. snapping or gizmo positioning).
   * For entities outside some radius, you might temporarily disable their scripts until the camera approaches.

2. **Batch Grid Drawing**

   * Instead of spawning hundreds of separate line entities for the snap grid overlay, use one `Mesh` with all lines in a single vertex buffer. This draws faster.

3. **Destroy Gizmos & Overlays Promptly**

   * When you deselect or close panels, make sure to call `destroy(gizmo_entity)` or `destroy(grid_overlay)`. Lingering hidden Entities still consume CPU/GPU time if they’re constantly in the render/update loop.

> **Benefit:**
> • Keeps the frame rate high even as complexity grows.
> • Avoids memory leaks from forgotten UI elements.

---

## 13. Custom Script Attachment & Parameterized Entities

### Why

Maybe you want some entities in your scene to run custom behavior scripts (e.g. a rotating fan, a bouncing ball). It’s convenient to let the editor assign scripts to objects.

### How

1. In your “Add New Object” panel (from section 1), add a drop‐down listing all available script classes (e.g. `SpinForever`, `FloatUpDown`, etc.).
2. When creating the entity, call `e.add_script(ChosenScript())`.
3. In your JSON or Python‐based save format, include a `"script": "SpinForever"` field so that on load you do:

   ```python
   if 'script' in obj:
       cls = getattr(sys.modules['my_game_scripts'], obj['script'])
       e.add_script(cls())
   ```

> **Benefit:**
> • Integrates level editing with gameplay logic.
> • You can prototype interactive objects directly in the editor.

---

## 14. Scene Hierarchy Panel (Parent‐Child Relationships)

### Why

Complex scenes often use parented objects (e.g. a car entity with child wheel entities). A visual hierarchy panel helps you see and reparent objects.

### How

1. Maintain a simple tree data structure (`scene.entities`) already has parent/child, but show it in a UI list:

   ```python
   hierarchy_panel = ScrollablePanel(parent=camera.ui, scale=(.3, .8), x=0.8, y=0)
   ```

2. Populate it with a `Text` widget for each entity, indented by depth:

   ```python
   def rebuild_hierarchy():
       for e in hierarchy_panel.children:
           destroy(e)
       for e in scene.entities:
           if e.eternal: continue
           depth = 0
           p = e.parent
           while p and not p.eternal:
               depth += 1
               p = p.parent
           txt = Text(e.name or e.model.name or 'entity', parent=hierarchy_panel,
                      x = -0.4 + depth * 0.1, y = start_y - index*line_height)
           # store a reference so clicking the text selects the entity
           txt.on_click = lambda ent=e: select_entity_by_reference(ent)
   ```

3. Allow drag‐&‐drop in that panel to reparent:

   * If you drag one text onto another and release, set `dragged.parent = dropped_on`.

> **Benefit:**
> • Clear overview of scene structure.
> • Easy to reorganize nested objects.

---

## 15. Built‐In Lighting & Material Editor

### Why

Beyond static colors/textures, you might want to tweak material parameters (metallic, roughness, emissive) or adjust light intensity/color from within the same editor.

### How

1. Add a “Material” tab in the property inspector (section 9). When the user selects an entity with a PBR material, display sliders for:

   * Metallic (0.0–1.0)
   * Roughness (0.0–1.0)
   * Emissive (0.0–1.0)
   * Color RGBA picker

   Example:

   ```python
   metallic_slider = Slider(parent=material_panel, min=0, max=1, step=0.01, value=e.metallic,
                            on_value_changed=lambda v: setattr(e, 'metallic', v))
   ```

2. Create a “Light” button that, when clicked, spawns a `PointLight` or `DirectionalLight` at the camera’s position; with its own gizmo you can reposition it or tweak intensity/color in an inspector.

> **Benefit:**
> • Turn your Ursina scene editor into a mini‐level authoring tool with materials and lighting.
> • You can craft the entire look and feel without writing extra code.

---

## 16. Version Control Integration & Auto‐Backups

### Why

If you accidentally overwrite or corrupt `scene.json` (or `scene.py`), having a history can save hours of rework.

### How

1. **Auto‐Incremented Backups**

   * Whenever you click “Save,” first copy the existing `scene.json` (if it exists) to `backups/scene_YYYYMMDD_HHMMSS.json`.
   * Then write the new file.

   ```python
   import shutil, datetime
   def auto_backup_and_save():
       if os.path.exists('scene.json'):
           t = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
           os.makedirs('backups', exist_ok=True)
           shutil.copy('scene.json', f'backups/scene_{t}.json')
       save_json()
   ```
2. **Git Hooks or External VCS**

   * If you keep your project in Git, add `scene.json` to the repository and commit after each “Save.”
   * You can even call `os.system('git add scene.json && git commit -m "Auto‐Save"')`—though be careful not to spam commits too rapidly.

> **Benefit:**
> • Never lose work if you save something invalid.
> • See a timeline of how your level evolved.

---

## 17. “Playtest” Button / Hot‐Swap

### Why

You might want to test how your scene looks in “game mode” without quitting the editor.

### How

1. Add a “Playtest” button in your UI.
2. When clicked, it:

   * Pauses or hides the editor UI and gizmos.
   * Switches the camera from `EditorCamera` to your “game camera” (e.g. a `FirstPersonController`).
   * Enables runtime scripts on entities (e.g. enemy AI, physics).
3. When you press **Esc** in playtest, revert to the editor:

   * Destroy the runtime camera, respawn `EditorCamera`.
   * Re‐spawn all gizmos and UI panels.

> **Benefit:**
> • Immediate feedback on how lighting, collisions, or scripts behave in the actual game.
> • No need to maintain two separate scripts.

---

## 18. Customizable Hotkeys & Preferences Panel

### Why

Different users have different muscle memory. Maybe you want “R” for rotate, “T” for translate, “S” for scale (like Unity).

### How

1. **Preferences Panel** (another UI panel) that lists keybindings:

   ```python
   translate_key_input = InputField(hint='Translate Key', text='arrow keys')
   rotate_key_input = InputField(hint='Rotate Keys', text='x/z, c/v, b/n')
   scale_key_input    = InputField(hint='Scale Key', text='shift + arrow keys')
   # Save these into a dict: keybindings = {'translate': 'arrow', 'rotate': ['x','z'], 'scale': 'shift+arrow'}
   ```
2. In your `DebugBehaviour.update()`/`input()`, refer to those keybinding settings instead of hardcoding `held_keys['shift']` or `held_keys['x']`.
3. Write a small helper that parses strings like `"shift+arrow"` into a test function `(held_keys['shift'] and (held_keys['...']))`.

> **Benefit:**
> • Users can remap keys to their liking.
> • More flexible for international keyboards or accessibility needs.

---

## 19. Modular Script Structure & Plugins

### Why

As the editor grows, it’s nice to keep features loosely coupled. Maybe someone wants to add a “Terrain Sculptor” plugin or a “Pathfinding NavMesh” generator without touching core code.

### How

1. Create a `plugins/` folder. Each plugin is a Python file with a defined API:

   ```python
   # plugins/terrain_sculptor.py
   def register(editor_api):
       # called on startup
       # e.g. create a “Sculpt” button in editor_api.ui_panel
       editor_api.add_button('Sculpt Terrain', on_click=lambda: open_terrain_tool())
   ```
2. In your main script, at startup do:

   ```python
   import os, importlib
   PLUGINS = []
   for fname in os.listdir('plugins'):
       if fname.endswith('.py'):
           module = importlib.import_module(f'plugins.{fname[:-3]}')
           if hasattr(module, 'register'):
               module.register(editor_api)
               PLUGINS.append(module)
   ```
3. Provide an `editor_api` object that exposes:

   * `add_button(…)`
   * `register_gizmo_type(…)`
   * `hook_on_save(…)`
   * etc.

> **Benefit:**
> • New features or community contributions can be dropped into `plugins/` without modifying the core.
> • Keeps your codebase maintainable.

---

## 20. Summary of Potential Improvements

1. **In‐UI Add/Edit Panel** instead of Tkinter dialogs
2. **Visual Move/Rotate/Scale Gizmos** (3D manipulators)
3. **Multi‐Select & Group Transforms** (Shift‐click, marquee select)
4. **Undo / Redo Stack** (Ctrl+Z, Ctrl+Y)
5. **JSON‐Based Save/Load** for safety and extensibility
6. **Grid Overlay & Axis Highlight** when snapping
7. **Duplicate/Clone** functionality (Ctrl+D)
8. **Context Menus** on right‐click (delete/duplicate/rename)
9. **Property Inspector Panel** for numeric entry (position, rotation, scale, material)
10. **Error Handling & Validation** (disable “Create” until inputs valid)
11. **Tooltips & Help Overlay** (keybinding cheat‐sheet)
12. **Performance Optimizations** (batch grid lines, cull off‐screen scripts)
13. **Script Attachment** (drop‐down in inspector for custom behaviors)
14. **Hierarchy Panel** (parent/child reorganization)
15. **Material & Lighting Editor** (sliders for PBR parameters)
16. **Version Control / Auto‐Backup** of scene files
17. **Playtest Mode** (swap from editor camera to game camera)
18. **Customizable Hotkeys** (preferences panel)
19. **Plugin System** (drop‐in feature modules)

Pick whichever features best fit your needs. Even adopting just a couple—like swapping Tkinter pop‐ups for an all‐in‐UI panel, adding a simple undo stack, or giving a gizmo for transforms—will make your editor feel significantly more polished and user‐friendly.

"""