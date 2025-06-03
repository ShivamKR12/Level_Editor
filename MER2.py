from ursina import *
import importlib
import sys

app = Ursina()

# ─── Globals ────────────────────────────────────────────────────────────────
# Modes and selections
deleting         = False
selected_entities = []  # list of DebugBehaviour instances

# Snap settings
snap_enabled    = False
snap_size       = 1.0
rotation_snap   = 15.0

# Scene objects
objects         = []  # all non-eternal entities for saving
undo_stack      = []
redo_stack      = []

# Grid overlay handle
grid_overlay    = None

# Keybinding variables (customizable via preferences panel)
key_scale_mod   = 'shift'        # default: Shift for scale
key_rotate_y_pos = 'x'           # rotate positive around Y
key_rotate_y_neg = 'z'           # rotate negative around Y
key_rotate_x_pos = 'c'           # rotate positive around X
key_rotate_x_neg = 'v'           # rotate negative around X
key_rotate_z_pos = 'b'           # rotate positive around Z
key_rotate_z_neg = 'n'           # rotate negative around Z
key_snap_toggle = 's'            # key to toggle snap

# UI button references
delete_button   = None
snap_button     = None
add_button      = None

# Panels and UI elements (will be initialized later)
add_panel       = None
name_input      = None
model_input     = None
texture_input   = None
collider_input  = None
create_button   = None
cancel_button   = None

insp_panel      = None
pos_x_input     = None
pos_y_input     = None
pos_z_input     = None
rot_x_input     = None
rot_y_input     = None
rot_z_input     = None
scale_x_input   = None
scale_y_input   = None
scale_z_input   = None
color_r_input   = None
color_g_input   = None
color_b_input   = None
color_a_input   = None
apply_props_button = None
metallic_slider   = None
roughness_slider  = None
emissive_slider   = None

help_button     = None
help_panel      = None

hier_panel      = None

prefs_panel     = None
move_key_input  = None
scale_key_input = None
rotate_key_input = None
snap_key_input  = None
prefs_apply_btn = None
prefs_cancel_btn = None

# ─── Hierarchy Panel (Feature 14) ───────────────────────────────────────────
hier_panel = Entity(parent=camera.ui, model='quad', color=color.rgba(30,30,30,200),
                    scale=(.3, .8), x=0.45, y=0.0, visible=True,
                    eternal=True)
hier_start_y = 0.35
hier_line_height = 0.05

class HierarchyBuilder(Entity):
    """
    Incrementally builds the hierarchy panel one entry per frame.
    Once finished, it destroys itself so that the main loop remains responsive.
    """
    def __init__(self):
        super().__init__(parent=scene)  # attach to the scene so update() is called
        self.entities_to_build = [e for e in scene.entities if not getattr(e, 'eternal', False)]
        self.index = 0
        self.done = False

        # First, clear any existing children of the hierarchy panel
        for c in hier_panel.children:
            destroy(c)

    def update(self):
        if self.done:
            return

        if self.index < len(self.entities_to_build):
            e = self.entities_to_build[self.index]
            depth = 0
            p = e.parent
            while isinstance(p, Entity) and not getattr(p, 'eternal', False):
                depth += 1
                p = p.parent

            y_pos = hier_start_y - self.index * hier_line_height
            name = e.name or (e.model.name if hasattr(e.model, 'name') else 'entity')

            txt = Text(
                name,
                parent = hier_panel,
                x      = -0.4 + depth * 0.1,
                y      = y_pos,
                color  = color.white,
                scale  = 1.2,
                add_to_scene_entities = False  # so it doesn’t show up in scene.entities
            )

            def make_select_func(ent=e):
                def sel():
                    # Deselect all previous
                    for dbg in selected_entities:
                        if dbg._orig_color:
                            dbg.entity.color = dbg._orig_color
                        if dbg.gizmo:
                            destroy(dbg.gizmo)
                    selected_entities.clear()

                    # Find and select the DebugBehaviour for 'ent'
                    for ent2 in scene.entities:
                        if hasattr(ent2, 'scripts'):
                            for script in ent2.scripts:
                                if isinstance(script, DebugBehaviour) and script.entity == ent:
                                    script._orig_color = ent.color
                                    ent.color = color.azure
                                    selected_entities.append(script)
                                    script.gizmo = TransformGizmo(ent)
                                    refresh_inspector()
                                    return
                            else:
                                continue
                            break
                return sel

            btn_hier = Button(
                txt.text,
                parent     = hier_panel,
                x          = txt.x + 0.2,
                y          = y_pos,
                scale      = (.25, .04),
                text_color = color.black,
                add_to_scene_entities = False  # same here, keep it out of scene.entities
            )
            btn_hier.on_click = make_select_func(e)

            self.index += 1

        else:
            # All entries built; destroy this builder so update() no longer runs
            self.done = True
            destroy(self)

# ─── Transform Gizmo ─────────────────────────────────────────────────────────
class TransformGizmo(Entity):
    def __init__(self, target: Entity):
        super().__init__()
        self.target = target
        self.arrows = {}
        # X-axis arrow (red)
        a_x = Entity(model='cube', color=color.red, scale=(.1, .1, 1),
                     parent=self, collider='box')
        a_x.rotation = (0, 0, 90)
        self.arrows['x'] = a_x
        # Y-axis arrow (green)
        a_y = Entity(model='cube', color=color.green, scale=(.1, .1, 1),
                     parent=self, collider='box')
        a_y.rotation = (0, 0, 0)
        self.arrows['y'] = a_y
        # Z-axis arrow (blue)
        a_z = Entity(model='cube', color=color.blue, scale=(.1, .1, 1),
                     parent=self, collider='box')
        a_z.rotation = (90, 0, 0)
        self.arrows['z'] = a_z

        for arr in self.arrows.values():
            arr.always_on_top = True
            arr.world_scale *= 0.5

        self.selected_axis = None
        self.dragging = False
        self.last_mouse_point = None

    def update(self):
        if not self.target or not self.target.enabled:
            destroy(self)
            return

        # Follow target’s world position
        self.position = self.target.world_position

        # Highlight hovered arrow if not dragging
        if not self.dragging:
            hovered = False
            for axis, arr in self.arrows.items():
                if mouse.hovered_entity == arr:
                    arr.color = color.yellow if snap_enabled else color.orange
                    hovered = True
                    self.selected_axis = axis
                else:
                    arr.color = {'x': color.red, 'y': color.green, 'z': color.blue}[axis]
                    if self.selected_axis == axis:
                        self.selected_axis = None
            if not hovered:
                self.selected_axis = None

        # Dragging: move target along selected axis
        if self.dragging and self.selected_axis:
            axis_vec = Vec3(1,0,0) if self.selected_axis == 'x' else \
                       Vec3(0,1,0) if self.selected_axis == 'y' else Vec3(0,0,1)
            hit = mouse.world_point
            if hit and self.last_mouse_point:
                delta = (hit - self.last_mouse_point).dot(axis_vec)
                self.target.position += axis_vec * delta
                self.last_mouse_point = hit

    def input(self, key):
        if key == 'left mouse down' and self.selected_axis:
            self.dragging = True
            self.last_mouse_point = mouse.world_point
        if key == 'left mouse up':
            self.dragging = False
            self.last_mouse_point = None

# ─── Debug Behaviour ─────────────────────────────────────────────────────────
class DebugBehaviour:
    def __init__(self) -> None:
        self.entity: Entity
        self._orig_color = None
        self._last_state = {
            'pos': (0,0,0),
            'rot': (0,0,0),
            'scale': (1,1,1)
        }
        self.gizmo = None

    def update(self):
        self.entity.on_click = self.toggle
        if self not in selected_entities:
            return

        # Continuous Scale vs. Move
        if held_keys[key_scale_mod]:
            dz = (held_keys['up arrow'] - held_keys['down arrow']) * \
                 (time.dt * (1 if held_keys['control'] else 5) if not held_keys['alt'] else 0)
            dy = (held_keys['page up'] - held_keys['page down']) * \
                 (time.dt * (1 if held_keys['control'] else 5) if not held_keys['alt'] else 0)
            dx = (held_keys['right arrow'] - held_keys['left arrow']) * \
                 (time.dt * (1 if held_keys['control'] else 5) if not held_keys['alt'] else 0)
            for dbg in selected_entities:
                dbg.entity.scale_z += dz
                dbg.entity.scale_y += dy
                dbg.entity.scale_x += dx
        else:
            dz = (held_keys['up arrow'] - held_keys['down arrow']) * \
                 (time.dt * (1 if held_keys['control'] else 5) if not held_keys['alt'] else 0)
            dy = (held_keys['page up'] - held_keys['page down']) * \
                 (time.dt * (1 if held_keys['control'] else 5) if not held_keys['alt'] else 0)
            dx = (held_keys['right arrow'] - held_keys['left arrow']) * \
                 (time.dt * (1 if held_keys['control'] else 5) if not held_keys['alt'] else 0)
            for dbg in selected_entities:
                dbg.entity.z += dz
                dbg.entity.y += dy
                dbg.entity.x += dx

        # Continuous Rotation
        ryd = (held_keys[key_rotate_y_pos] - held_keys[key_rotate_y_neg]) * \
              time.dt * (10 if held_keys['control'] else 20)
        rxd = (held_keys[key_rotate_x_pos] - held_keys[key_rotate_x_neg]) * \
              time.dt * (10 if held_keys['control'] else 20)
        rzd = (held_keys[key_rotate_z_pos] - held_keys[key_rotate_z_neg]) * \
              time.dt * (10 if held_keys['control'] else 20)
        for dbg in selected_entities:
            dbg.entity.rotation_y += ryd
            dbg.entity.rotation_x += rxd
            dbg.entity.rotation_z += rzd

        # Snap-on-release is handled in input()

    def input(self, key):
        if self not in selected_entities:
            return

        # Press F to print debug info for all selected
        if key == 'f':
            for dbg in selected_entities:
                e = dbg.entity
                print(f"'{e.name}' pos : {e.position}  rot : {e.rotation}")

        # Alt + arrows/page keys: discrete ±1 steps, then integer-snap
        if held_keys[key_scale_mod]:
            if held_keys['alt']:
                dz = (int(key == 'up arrow') - int(key == 'down arrow'))
                dy = (int(key == 'page up') - int(key == 'page down'))
                dx = (int(key == 'right arrow') - int(key == 'left arrow'))
                for dbg in selected_entities:
                    dbg.entity.scale_z += dz
                    dbg.entity.scale_y += dy
                    dbg.entity.scale_x += dx
                    if key not in (key_scale_mod,):
                        dbg.entity.scale_x = int(dbg.entity.scale_x)
                        dbg.entity.scale_y = int(dbg.entity.scale_y)
                        dbg.entity.scale_z = int(dbg.entity.scale_z)
                        # Record scale change
                        new_s = (dbg.entity.scale_x, dbg.entity.scale_y, dbg.entity.scale_z)
                        old_s = dbg._last_state['scale']
                        if new_s != old_s:
                            undo_stack.append({
                                'type': 'scale',
                                'entity': dbg.entity,
                                'from': old_s,
                                'to': new_s
                            })
                            redo_stack.clear()
                            dbg._last_state['scale'] = new_s
        else:
            if held_keys['alt']:
                dz = (int(key == 'up arrow') - int(key == 'down arrow'))
                dy = (int(key == 'page up') - int(key == 'page down'))
                dx = (int(key == 'right arrow') - int(key == 'left arrow'))
                for dbg in selected_entities:
                    dbg.entity.z += dz
                    dbg.entity.y += dy
                    dbg.entity.x += dx
                    if key not in ('alt',):
                        dbg.entity.x = int(dbg.entity.x)
                        dbg.entity.y = int(dbg.entity.y)
                        dbg.entity.z = int(dbg.entity.z)
                        # Record move change
                        new_pos = (dbg.entity.x, dbg.entity.y, dbg.entity.z)
                        old_pos = dbg._last_state['pos']
                        if new_pos != old_pos:
                            undo_stack.append({
                                'type': 'move',
                                'entity': dbg.entity,
                                'from': old_pos,
                                'to': new_pos
                            })
                            redo_stack.clear()
                            dbg._last_state['pos'] = new_pos

        # Snap-on-release if snap_enabled
        if snap_enabled:
            if key in ('up arrow up', 'down arrow up',
                       'left arrow up', 'right arrow up',
                       'page up up', 'page down up'):
                for dbg in selected_entities:
                    e = dbg.entity
                    px = round(e.x / snap_size) * snap_size
                    py = round(e.y / snap_size) * snap_size
                    pz = round(e.z / snap_size) * snap_size
                    old_pos = (e.x, e.y, e.z)
                    e.position = Vec3(px, py, pz)
                    new_pos = (e.x, e.y, e.z)
                    if new_pos != old_pos:
                        undo_stack.append({
                            'type': 'move',
                            'entity': e,
                            'from': old_pos,
                            'to': new_pos
                        })
                        redo_stack.clear()
                        dbg._last_state['pos'] = new_pos
            if key in (f'{key_rotate_y_pos} up', f'{key_rotate_y_neg} up',
                       f'{key_rotate_x_pos} up', f'{key_rotate_x_neg} up',
                       f'{key_rotate_z_pos} up', f'{key_rotate_z_neg} up'):
                for dbg in selected_entities:
                    e = dbg.entity
                    old_rot = (e.rotation_x, e.rotation_y, e.rotation_z)
                    ry = round(e.rotation_y / rotation_snap) * rotation_snap
                    rx = round(e.rotation_x / rotation_snap) * rotation_snap
                    rz = round(e.rotation_z / rotation_snap) * rotation_snap
                    e.rotation = Vec3(rx, ry, rz)
                    new_rot = (e.rotation_x, e.rotation_y, e.rotation_z)
                    if new_rot != old_rot:
                        undo_stack.append({
                            'type': 'rotate',
                            'entity': e,
                            'from': old_rot,
                            'to': new_rot
                        })
                        redo_stack.clear()
                        dbg._last_state['rot'] = new_rot

        # Right-click context menu if selected
        if key == 'right mouse down':
            ux, uy = mouse.screen_x, mouse.screen_y
            show_context_menu(ux, uy, self)
            return

        # Handle Delete on clicking entity
        if key == 'left mouse down' and self.entity.hovered:
            # This is handled in toggle()

            pass

    def toggle(self):
        global selected_entities, deleting

        if deleting:
            # Record deletion for undo
            entity_repr = repr(self.entity)
            undo_stack.append({
                'type': 'delete',
                'entity_repr': entity_repr,
                'entity_name': self.entity.name
            })
            redo_stack.clear()
            if self.entity in objects:
                objects.remove(self.entity)
            if self in selected_entities:
                selected_entities.remove(self)
            if hasattr(self, 'gizmo') and self.gizmo:
                destroy(self.gizmo)
            destroy(self.entity)
            return

        if held_keys['shift']:
            # Multi-select toggle
            if self in selected_entities:
                if self._orig_color is not None:
                    self.entity.color = self._orig_color
                if hasattr(self, 'gizmo') and self.gizmo:
                    destroy(self.gizmo)
                selected_entities.remove(self)
            else:
                if self._orig_color is None:
                    self._orig_color = self.entity.color
                self.entity.color = color.azure
                selected_entities.append(self)
                self.gizmo = TransformGizmo(self.entity)
            refresh_inspector()
            # rebuild_hierarchy()
            HierarchyBuilder()
            return

        # Single-select: deselect all others
        for dbg in selected_entities:
            if dbg._orig_color is not None:
                dbg.entity.color = dbg._orig_color
            if hasattr(dbg, 'gizmo') and dbg.gizmo:
                destroy(dbg.gizmo)
        selected_entities.clear()

        # Select this
        if self._orig_color is None:
            self._orig_color = self.entity.color
        self.entity.color = color.azure
        selected_entities.append(self)
        self.gizmo = TransformGizmo(self.entity)
        refresh_inspector()
        # rebuild_hierarchy()
        HierarchyBuilder()

# ─── Global Input: Escape, Undo/Redo, Duplicate (Ctrl+D), Preferences ───────
def input(key):
    global selected_entities, snap_enabled

    # Escape to deselect all
    if key == 'escape':
        for dbg in selected_entities:
            if dbg._orig_color is not None:
                dbg.entity.color = dbg._orig_color
            if hasattr(dbg, 'gizmo') and dbg.gizmo:
                destroy(dbg.gizmo)
        selected_entities.clear()
        refresh_inspector()
        return

    # Undo (Ctrl+Z)
    if key == 'control z' and undo_stack:
        record = undo_stack.pop()
        _apply_undo(record)
        redo_stack.append(record)
        return

    # Redo (Ctrl+Y)
    if key == 'control y' and redo_stack:
        record = redo_stack.pop()
        _apply_redo(record)
        undo_stack.append(record)
        return

    # Duplicate (Ctrl+D)
    if key == 'control d' and selected_entities:
        new_selection = []
        for dbg in selected_entities:
            orig = dbg.entity
            clone = Entity(
                name     = f"{orig.name}_copy" if orig.name else None,
                model    = orig.model.name if hasattr(orig.model, 'name') else orig.model,
                texture  = orig.texture.name if hasattr(orig.texture, 'name') else orig.texture,
                position = orig.position + Vec3(1, 0, 1),
                rotation = orig.rotation,
                scale    = orig.scale,
                collider = orig.collider,
                color    = orig.color
            )
            clone.add_script(DebugBehaviour())
            objects.append(clone)
            undo_stack.append({'type':'create', 'entity': clone})
            redo_stack.clear()
            # Deselect old, select clone
            dbg.entity.color = dbg._orig_color
            new_dbg = clone.scripts[-1]
            new_dbg._orig_color = clone.color
            clone.color = color.azure
            new_selection.append(new_dbg)
        for dbg in selected_entities:
            if hasattr(dbg, 'gizmo') and dbg.gizmo:
                destroy(dbg.gizmo)
        selected_entities = new_selection
        for dbg in selected_entities:
            dbg.gizmo = TransformGizmo(dbg.entity)
        refresh_inspector()
        # rebuild_hierarchy()
        HierarchyBuilder()
        return

    # Toggle Snap (customizable key)
    if key == key_snap_toggle:
        toggleSnap()
        return

# ─── Undo/Redo Helpers ───────────────────────────────────────────────────────
def _apply_undo(record):
    t = record['type']
    if t == 'move':
        e = record['entity']
        e.position = Vec3(*record['from'])
    elif t == 'rotate':
        e = record['entity']
        e.rotation = Vec3(*record['from'])
    elif t == 'scale':
        e = record['entity']
        e.scale = Vec3(*record['from'])
    elif t == 'create':
        e = record['entity']
        if e in objects:
            objects.remove(e)
        destroy(e)
    elif t == 'delete':
        code_line = record['entity_repr']
        exec(code_line)
        # Reattach DebugBehaviour
        for ent in scene.entities:
            if ent.name == record['entity_name'] and ent not in objects:
                objects.append(ent)
                ent.add_script(DebugBehaviour())
                break

def _apply_redo(record):
    t = record['type']
    if t == 'move':
        e = record['entity']
        e.position = Vec3(*record['to'])
    elif t == 'rotate':
        e = record['entity']
        e.rotation = Vec3(*record['to'])
    elif t == 'scale':
        e = record['entity']
        e.scale = Vec3(*record['to'])
    elif t == 'create':
        code_line = repr(record['entity'])
        exec(code_line)
        for ent in scene.entities:
            if ent.name == record['entity'].name and ent not in objects:
                objects.append(ent)
                ent.add_script(DebugBehaviour())
                break
    elif t == 'delete':
        for ent in scene.entities:
            if ent.name == record['entity_name']:
                if ent in objects:
                    objects.remove(ent)
                destroy(ent)
                break

# ─── Grid Overlay (Feature 6) ───────────────────────────────────────────────
def show_grid_overlay():
    global grid_overlay
    if grid_overlay:
        destroy(grid_overlay)
    grid_overlay = Entity()
    size = 20
    step = snap_size
    coords = [i * step for i in range(-int(size/step), int(size/step)+1)]
    for c in coords:
        # X-aligned line
        Entity(parent=grid_overlay,
               model=Mesh(vertices=[(-size, 0, c), (size, 0, c)]),
               color=color.gray)
        # Z-aligned line
        Entity(parent=grid_overlay,
               model=Mesh(vertices=[(c, 0, -size), (c, 0, size)]),
               color=color.gray)
    grid_overlay.eternal = True

def hide_grid_overlay():
    global grid_overlay
    if grid_overlay:
        destroy(grid_overlay)
        grid_overlay = None

# ─── Context Menu (Feature 8) ───────────────────────────────────────────────
def show_context_menu(x, y, target_dbg: DebugBehaviour):
    # Remove existing context menus
    for c in scene.entities:
        if hasattr(c, 'is_context') and c.is_context:
            destroy(c)

    menu = Entity(parent=camera.ui, model='quad', color=color.rgba(20,20,20,200),
                  scale=(.2, .25), x=x, y=y, is_context=True)

    btn_del = Button('Delete', parent=menu, y=0.07, scale=(.9, .2))
    btn_del.on_click = lambda: (do_delete(target_dbg), hide_context_menu())

    btn_dup = Button('Duplicate', parent=menu, y=0.0, scale=(.9, .2))
    btn_dup.on_click = lambda: (do_duplicate(target_dbg), hide_context_menu())

    btn_ren = Button('Rename', parent=menu, y=-0.07, scale=(.9, .2))
    btn_ren.on_click = lambda: (open_rename_field(target_dbg), hide_context_menu())

def hide_context_menu():
    for c in scene.entities:
        if hasattr(c, 'is_context') and c.is_context:
            destroy(c)

def do_delete(dbg: DebugBehaviour):
    global deleting
    deleting = True
    dbg.toggle()
    deleting = False
    # rebuild_hierarchy()
    HierarchyBuilder()

def do_duplicate(dbg: DebugBehaviour):
    orig = dbg.entity
    clone = Entity(
        name     = f"{orig.name}_copy" if orig.name else None,
        model    = orig.model.name if hasattr(orig.model, 'name') else orig.model,
        texture  = orig.texture.name if hasattr(orig.texture, 'name') else orig.texture,
        position = orig.position + Vec3(1, 0, 1),
        rotation = orig.rotation,
        scale    = orig.scale,
        collider = orig.collider,
        color    = orig.color
    )
    clone.add_script(DebugBehaviour())
    objects.append(clone)
    undo_stack.append({'type':'create', 'entity': clone})
    redo_stack.clear()
    for dbg2 in selected_entities:
        if hasattr(dbg2, 'gizmo') and dbg2.gizmo:
            destroy(dbg2.gizmo)
    selected_entities.clear()
    new_dbg = clone.scripts[-1]
    new_dbg._orig_color = clone.color
    clone.color = color.azure
    selected_entities.append(new_dbg)
    new_dbg.gizmo = TransformGizmo(new_dbg.entity)
    refresh_inspector()
    # rebuild_hierarchy()
    HierarchyBuilder()

def open_rename_field(dbg: DebugBehaviour):
    rename_if = InputField(parent=camera.ui,
                           position=dbg.entity.screen_position,
                           scale=(.15, .04),
                           text=dbg.entity.name or '')
    def finalize_rename(text):
        dbg.entity.name = text
        # rebuild_hierarchy()
        HierarchyBuilder()
    rename_if.on_submit = finalize_rename

# ─── Save/Load (Python repr) ─────────────────────────────────────────────────
def save():
    global selected_entities
    # Deselect all to restore colors
    for dbg in selected_entities:
        if dbg._orig_color is not None:
            dbg.entity.color = dbg._orig_color
        if dbg.gizmo:
            destroy(dbg.gizmo)
    selected_entities.clear()
    refresh_inspector()

    code = "from ursina import *\n\n"
    for i in objects:
        code += repr(i) + "\n"
    with open('scene.py', 'w') as file:
        file.write(code)

def load():
    global objects, selected_entities

    # ─── Destroy only non-eternal entities ─────────────────────────────────
    for e in scene.entities[:]:        # iterate over a shallow copy
        if not getattr(e, 'eternal', False):
            destroy(e)

    # Reset any selection state and inspector
    selected_entities.clear()
    refresh_inspector()

    # ─── (Re)import the saved scene.py module ──────────────────────────────
    if 'scene' in sys.modules:
        importlib.reload(sys.modules['scene'])
    else:
        importlib.import_module('scene')

    # ─── Re‐collect all newly created non-eternal entities ─────────────────
    objects = []
    for e in scene.entities:
        # anything that was just re‐created from scene.py
        if not getattr(e, 'eternal', False):
            objects.append(e)
            e.add_script(DebugBehaviour())

    HierarchyBuilder()

# ─── Add/Edit Panel (Feature 1 & 10) ──────────────────────────────────────────
add_panel = Entity(parent=camera.ui, model='quad', color=color.rgba(30,30,30,200),
                   scale=(.6, .7), x=0.2, y=0.2, visible=False,
                    eternal=True)

name_input = InputField(parent=add_panel, hint='Name', x=-.2, y=0.25, scale=(.4, .07))
model_input = InputField(parent=add_panel, hint='Model (e.g. cube)', x=-.2, y=0.1, scale=(.4, .07))
texture_input = InputField(parent=add_panel, hint='Texture (e.g. grass)', x=-.2, y=-0.05, scale=(.4, .07))
collider_input = InputField(parent=add_panel, hint='Collider (box/sphere…) or blank', x=-.2, y=-0.2, scale=(.4, .07))

create_button = Button('Create', parent=add_panel, x=0.25, y=-0.35, scale=(.3, .1), enabled=False)
cancel_button = Button('Cancel', parent=add_panel, x=-0.25, y=-0.35, scale=(.3, .1))

def validate_inputs():
    model_ok = model_input.text.strip() != ''
    if model_ok:
        try:
            load_model(model_input.text.strip())
        except:
            model_ok = False
    tex = texture_input.text.strip()
    if tex:
        try:
            load_texture(tex)
            tex_ok = True
        except:
            tex_ok = False
    else:
        tex_ok = True
    create_button.enabled = (model_ok and tex_ok)

model_input.on_value_changed = lambda: validate_inputs()
texture_input.on_value_changed = lambda: validate_inputs()

def show_add_panel():
    name_input.text = ''
    model_input.text = ''
    texture_input.text = ''
    collider_input.text = ''
    create_button.enabled = False
    add_panel.visible = True

def hide_add_panel():
    add_panel.visible = False

def finalize_new_object():
    e = Entity(
        name     = name_input.text.strip() or None,
        model    = model_input.text.strip() or 'cube',
        texture  = texture_input.text.strip() or 'grass',
        collider = collider_input.text.strip() or None
    )
    e.add_script(DebugBehaviour())
    if e.model is None:
        e.model = 'cube'
    objects.append(e)
    undo_stack.append({'type':'create', 'entity': e})
    redo_stack.clear()
    hide_add_panel()
    # rebuild_hierarchy()
    HierarchyBuilder()

create_button.on_click = finalize_new_object
cancel_button.on_click = hide_add_panel

# ─── Inspector Panel (Feature 9 & 15) ────────────────────────────────────────
insp_panel = Entity(parent=camera.ui, model='quad', color=color.rgba(30,30,30,200),
                    scale=(.3, .8), x=0.8, y=0.0, visible=False,
                    eternal=True)

pos_x_input = InputField(parent=insp_panel, hint='Pos X', x=-.1, y=0.3, scale=(.25,.05))
pos_y_input = InputField(parent=insp_panel, hint='Pos Y', x=0.0,  y=0.3, scale=(.25,.05))
pos_z_input = InputField(parent=insp_panel, hint='Pos Z', x=0.1,  y=0.3, scale=(.25,.05))

rot_x_input = InputField(parent=insp_panel, hint='Rot X', x=-.1, y=0.2, scale=(.25,.05))
rot_y_input = InputField(parent=insp_panel, hint='Rot Y', x=0.0,   y=0.2, scale=(.25,.05))
rot_z_input = InputField(parent=insp_panel, hint='Rot Z', x=0.1,   y=0.2, scale=(.25,.05))

scale_x_input = InputField(parent=insp_panel, hint='Scale X', x=-.1, y=0.1, scale=(.25,.05))
scale_y_input = InputField(parent=insp_panel, hint='Scale Y', x=0.0,  y=0.1, scale=(.25,.05))
scale_z_input = InputField(parent=insp_panel, hint='Scale Z', x=0.1,  y=0.1, scale=(.25,.05))

color_r_input = InputField(parent=insp_panel, hint='Color R (0-255)', x=-.1, y=0.0, scale=(.25,.05))
color_g_input = InputField(parent=insp_panel, hint='Color G (0-255)', x=0.0,  y=0.0, scale=(.25,.05))
color_b_input = InputField(parent=insp_panel, hint='Color B (0-255)', x=0.1,  y=0.0, scale=(.25,.05))
color_a_input = InputField(parent=insp_panel, hint='Alpha (0-255)', x=0.0, y=-0.1, scale=(.25,.05))

apply_props_button = Button('Apply', parent=insp_panel, y=-0.2, scale=(.4,.1))

metallic_slider  = Slider(parent=insp_panel, min=0, max=1, step=0.01, x=0.0, y=-0.3, scale=(.4,.05))
roughness_slider = Slider(parent=insp_panel, min=0, max=1, step=0.01, x=0.0, y=-0.4, scale=(.4,.05))
emissive_slider  = Slider(parent=insp_panel, min=0, max=1, step=0.01, x=0.0, y=-0.5, scale=(.4,.05))

def refresh_inspector():
    if not selected_entities:
        insp_panel.visible = False
        return
    dbg = selected_entities[-1]
    e = dbg.entity
    insp_panel.visible = True

    pos_x_input.text = f"{e.x:.2f}"
    pos_y_input.text = f"{e.y:.2f}"
    pos_z_input.text = f"{e.z:.2f}"

    rot_x_input.text = f"{e.rotation_x:.2f}"
    rot_y_input.text = f"{e.rotation_y:.2f}"
    rot_z_input.text = f"{e.rotation_z:.2f}"

    scale_x_input.text = f"{e.scale_x:.2f}"
    scale_y_input.text = f"{e.scale_y:.2f}"
    scale_z_input.text = f"{e.scale_z:.2F}"

    cr, cg, cb, ca = int(e.color.r * 255), int(e.color.g * 255), int(e.color.b * 255), int(e.color.a * 255)
    color_r_input.text = str(cr)
    color_g_input.text = str(cg)
    color_b_input.text = str(cb)
    color_a_input.text = str(ca)

    if hasattr(e, 'metallic'):
        metallic_slider.value = e.metallic
    else:
        metallic_slider.value = 0

    if hasattr(e, 'roughness'):
        roughness_slider.value = e.roughness
    else:
        roughness_slider.value = 0

    if hasattr(e, 'emissive'):
        emissive_slider.value = e.emissive
    else:
        emissive_slider.value = 0

def apply_properties():
    if not selected_entities:
        return
    e = selected_entities[-1].entity
    dbg = selected_entities[-1]
    try:
        x_new = float(pos_x_input.text)
        y_new = float(pos_y_input.text)
        z_new = float(pos_z_input.text)
        old_pos = dbg._last_state['pos']
        e.position = Vec3(x_new, y_new, z_new)
        new_pos = (e.x, e.y, e.z)
        if new_pos != old_pos:
            undo_stack.append({'type':'move','entity':e,'from':old_pos,'to':new_pos})
            redo_stack.clear()
            dbg._last_state['pos'] = new_pos
    except:
        pass

    try:
        rx_new = float(rot_x_input.text)
        ry_new = float(rot_y_input.text)
        rz_new = float(rot_z_input.text)
        old_rot = dbg._last_state['rot']
        e.rotation = Vec3(rx_new, ry_new, rz_new)
        new_rot = (e.rotation_x, e.rotation_y, e.rotation_z)
        if new_rot != old_rot:
            undo_stack.append({'type':'rotate','entity':e,'from':old_rot,'to':new_rot})
            redo_stack.clear()
            dbg._last_state['rot'] = new_rot
    except:
        pass

    try:
        sx_new = float(scale_x_input.text)
        sy_new = float(scale_y_input.text)
        sz_new = float(scale_z_input.text)
        old_s = dbg._last_state['scale']
        e.scale = Vec3(sx_new, sy_new, sz_new)
        new_s = (e.scale_x, e.scale_y, e.scale_z)
        if new_s != old_s:
            undo_stack.append({'type':'scale','entity':e,'from':old_s,'to':new_s})
            redo_stack.clear()
            dbg._last_state['scale'] = new_s
    except:
        pass

    try:
        r = max(0, min(255, int(color_r_input.text)))
        g = max(0, min(255, int(color_g_input.text)))
        b = max(0, min(255, int(color_b_input.text)))
        a = max(0, min(255, int(color_a_input.text)))
        e.color = color.rgba(r, g, b, a)
    except:
        pass

    if hasattr(e, 'metallic'):
        e.metallic = metallic_slider.value
    if hasattr(e, 'roughness'):
        e.roughness = roughness_slider.value
    if hasattr(e, 'emissive'):
        e.emissive = emissive_slider.value

apply_props_button.on_click = apply_properties

# ─── Help Overlay & Tooltips (Feature 11) ────────────────────────────────────
help_button = Button('?', parent=camera.ui, scale=(.05, .05), x=0.95, y=0.95)
help_panel = Entity(parent=camera.ui, model='quad', color=color.rgba(0,0,0,180),
                    scale=(.6,.6), visible=False, x=0.0, y=0.0,
                    eternal=True)
help_text = Text(
    "Keybindings:\n"
    "Move: Arrow keys\n"
    "Scale: Shift + arrows\n"
    f"Rotate: {key_rotate_y_pos}/{key_rotate_y_neg} (Y-axis), {key_rotate_x_pos}/{key_rotate_x_neg} (X-axis), {key_rotate_z_pos}/{key_rotate_z_neg} (Z-axis)\n"
    f"Snap Toggle: '{key_snap_toggle}'\n"
    "Select: click; multi-select: Shift+click; Escape: deselect\n"
    "Delete Mode: Toggle Delete ON (click to delete)\n"
    "Duplicate: Ctrl+D\n"
    "Undo: Ctrl+Z   Redo: Ctrl+Y\n"
    "\n"
    "UI Panels:\n"
    "- Add/Edit: Left\n"
    "- Inspector: Right\n"
    "- Hierarchy: Center Right\n"
    "\n"
    "Right-click on selected entity: Context Menu (Delete/Duplicate/Rename)\n",
    parent=help_panel, x=0, y=0.25, color=color.white, line_height=1.2, scale=1.5
)
help_button.on_click = lambda: setattr(help_panel, 'visible', not help_panel.visible)

# ─── Hierarchy Panel (Feature 14) ───────────────────────────────────────────
# hier_panel = Entity(parent=camera.ui, model='quad', color=color.rgba(30,30,30,200),
#                     scale=(.3, .8), x=0.45, y=0.0, visible=True,
#                     eternal=True)
# hier_start_y = 0.35
# hier_line_height = 0.05

# def rebuild_hierarchy():
#     for c in hier_panel.children:
#         destroy(c)
#     idx = 0
#     for e in scene.entities:
#         if e.eternal:
#             continue
#         depth = 0
#         p = e.parent
#         while isinstance(p, Entity) and not p.eternal:
#             depth += 1
#             p = p.parent
#         y_pos = hier_start_y - idx * hier_line_height
#         name = e.name or (e.model.name if hasattr(e.model, 'name') else 'entity')
#         txt = Text(name, parent=hier_panel,
#                    x=-0.4 + depth * 0.1, y=y_pos,
#                    color=color.white, scale=1.2)
#         def make_select_func(ent=e):
#             def sel():
#                 for dbg in selected_entities:
#                     if dbg._orig_color:
#                         dbg.entity.color = dbg._orig_color
#                     if dbg.gizmo:
#                         destroy(dbg.gizmo)
#                 selected_entities.clear()
#                 for ent2 in scene.entities:
#                     if hasattr(ent2, 'scripts'):
#                         for script in ent2.scripts:
#                             if isinstance(script, DebugBehaviour) and script.entity == ent:
#                                 script._orig_color = ent.color
#                                 ent.color = color.azure
#                                 selected_entities.append(script)
#                                 script.gizmo = TransformGizmo(ent)
#                                 refresh_inspector()
#                                 break
#                         else:
#                             continue
#                         break
#             return sel
#         btn_hier = Button(txt.text, parent=hier_panel,
#                           x=txt.x + 0.2, y=y_pos,
#                           scale=(.25, .04), text_color=color.black)
#         btn_hier.on_click = make_select_func(e)
#         idx += 1

# ─── Preferences Panel (Feature 18) ──────────────────────────────────────────
prefs_panel = Entity(parent=camera.ui, model='quad', color=color.rgba(30,30,30,200),
                     scale=(.5, .5), x=0.0, y=0.0, visible=False,
                    eternal=True)

move_key_input = InputField(parent=prefs_panel, hint='(unused)', x=0.0, y=0.2, scale=(.5,.07))
scale_key_input = InputField(parent=prefs_panel, hint='Scale Modifier (e.g. shift)', x=0.0, y=0.1, scale=(.5,.07))
rotate_key_input = InputField(parent=prefs_panel, hint='Rotate Keys Y (x/z)', x=0.0, y=0.0, scale=(.5,.07))
snap_key_input = InputField(parent=prefs_panel, hint='Snap Toggle Key (e.g. s)', x=0.0, y=-0.1, scale=(.5,.07))

prefs_apply_btn = Button('Apply', parent=prefs_panel, y=-0.25, scale=(.3,.1))
prefs_cancel_btn = Button('Cancel', parent=prefs_panel, y=-0.35, scale=(.3,.1))

def apply_prefs():
    global key_scale_mod, key_rotate_y_pos, key_rotate_y_neg, key_rotate_x_pos, key_rotate_x_neg, key_rotate_z_pos, key_rotate_z_neg, key_snap_toggle
    sk = scale_key_input.text.strip()
    if sk:
        key_scale_mod = sk
    rot = rotate_key_input.text.strip().split('/')
    if len(rot) == 2:
        key_rotate_y_pos, key_rotate_y_neg = rot[0], rot[1]
    sz = snap_key_input.text.strip()
    if sz:
        key_snap_toggle = sz
    prefs_panel.visible = False

prefs_apply_btn.on_click = apply_prefs
prefs_cancel_btn.on_click = lambda: setattr(prefs_panel, 'visible', False)

prefs_button = Button('Prefs', parent=camera.ui, scale=(.05,.05), x=0.9, y=0.9)
prefs_button.on_click = lambda: setattr(prefs_panel, 'visible', not prefs_panel.visible)

# ─── UI Setup (Buttons & Panels) ─────────────────────────────────────────────
# Background for left panel
Entity(model=Quad(.1, aspect=.7), color=color.black33, parent=camera.ui,
       scale=(.7,1), x=-0.6479, eternal=True)

# “Add new Object” button
add_button = Button('Add new Object', parent=camera.ui,
                    position=Vec3(-0.6127, 0.3932, -0.895),
                    color=color.white, highlight_color=color.light_gray,
                    scale=(.5,.1), text_color=color.black, eternal=True)
add_button.on_click = show_add_panel

# “Toggle Delete Mode” button
delete_button = Button('Delete: OFF', parent=camera.ui,
                       position=Vec3(-0.6127, 0.1932, -0.895),
                       color=color.white, highlight_color=color.light_gray,
                       scale=(.5,.1), text_color=color.black, eternal=True)
delete_button.on_click = lambda: toggleDelete()

# “Snap-to-Grid” button
snap_button = Button('Snap: OFF', parent=camera.ui,
                     position=Vec3(-0.6127, 0.05, -0.895),
                     color=color.white, highlight_color=color.light_gray,
                     scale=(.5,.1), text_color=color.black, eternal=True)
snap_button.on_click = lambda: toggleSnap()

# “Save” button
Button('Save', parent=camera.ui,
       position=Vec3(-0.6127, -0.1932, -0.895),
       color=color.white, highlight_color=color.light_gray,
       on_click=save, scale=(.5,.1), text_color=color.black, eternal=True)

# “Load” button
Button('Load', parent=camera.ui,
       position=Vec3(-0.6127, -0.3032, -0.895),
       color=color.white, highlight_color=color.light_gray,
       on_click=load, scale=(.5,.1), text_color=color.black, eternal=True)

# “Help” and “Prefs” buttons were defined above

# Ground grid (eternal)
Entity(model=Grid(512,512), rotation_x=90, scale=512, color=color.white33,
       x=.5, z=.5, y=-.5, eternal=True)

# Sky and Editor Camera
Sky(eternal=True)
EditorCamera(eternal=True)

# ─── Delete and Snap Toggle Functions ─────────────────────────────────────────
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

def toggleSnap():
    global snap_enabled
    snap_enabled = not snap_enabled
    if snap_enabled:
        snap_button.text = 'Snap: ON'
        snap_button.color = color.azure
        snap_button.text_color = color.white
        show_grid_overlay()
    else:
        snap_button.text = 'Snap: OFF'
        snap_button.color = color.white
        snap_button.text_color = color.black
        hide_grid_overlay()

# ─── Hierarchy & Inspector Refresh Calls on Startup ───────────────────────────
# rebuild_hierarchy()
# refresh_inspector()

def initialize_ui():
    # First build the hierarchy entry by entry
    HierarchyBuilder()
    # Then refresh the inspector for whatever is selected (if anything)
    refresh_inspector()

# Schedule it a frame later so Ursina’s font/UI systems are ready
invoke(initialize_ui, delay=5)

print(">>> Reached end of script, about to call app.run()")
app.run()
