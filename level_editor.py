from ursina import *
from ursina.shaders import unlit_shader, lit_with_shadows_shader, matcap_shader, triplanar_shader, normals_shader
from time import perf_counter
import csv
import builtins
import pyperclip
import inspect

class LevelEditor(Entity):
    """
    LevelEditor is a comprehensive tool for managing, editing, and visualizing game scenes within a grid-based layout.
    It provides tools for object manipulation (move, scale, rotate), selection, camera controls, and scene hierarchy management.
    This editor is integrated into the Ursina Engine framework.
    """

    def __init__(self, **kwargs):
        """
        Initialize the LevelEditor with all its tools, UI, scene grid, and camera setup.
        """
        super().__init__()
        builtins.LEVEL_EDITOR = self  # Register the global editor instance (type: ignore due to dynamic global use)

        # Scene and grid setup
        self.scene_folder = application.asset_folder / 'scenes'
        self.scenes = [[LevelEditorScene(x, y, f'untitled_scene[{x},{y}]') for y in range(8)] for x in range(8)]
        self.current_scene = None

        # Visual editing grid
        self.grid = Entity(
            parent=self,
            model=Grid(16, 16),
            rotation_x=90,
            scale=64,
            collider='box',
            color=color.white33,
            enabled=False
        )

        self.origin_mode = 'center'
        self.editor_camera = EditorCamera(parent=self, rotation_x=20, eternal=False, rotation_smoothing=0)

        original_editor_camera_rotation_speed = self.editor_camera.rotation_speed

        # Disable rotation when left mouse is pressed
        def _update():
            self.editor_camera.rotation_speed = original_editor_camera_rotation_speed * int(not mouse.left)

        Entity(parent=self.editor_camera, update=_update)

        # UI and visual selection setup
        self.ui = Entity(parent=camera.ui, name='LEVEL_EDITOR.ui')  # type: ignore
        self.point_renderer = Entity(
            parent=self,
            model=Mesh([], mode='point', thickness=.1, render_points_in_3d=True),
            texture='circle_outlined',
            always_on_top=True,
            unlit=True,
            render_queue=1
        )

        # --- Dynamic scaling attributes for point_renderer ---
        self.point_renderer._init_w, self.point_renderer._init_h = window.size
        h = self.point_renderer._init_h or 1
        self.point_renderer._base_thickness = (40 / h) * 2  # 2px, adjust as needed
        self.point_renderer.model.thickness = self.point_renderer._base_thickness
        # ----------------------------------------------------

        # Cube outlines for selection highlighting
        self.cubes = [
            Entity(wireframe=True, color=color.azure, parent=self, enabled=True) for _ in range(128)
        ]

        # UI menus
        self.origin_mode_menu = ButtonGroup(['last', 'center', 'individual'], min_selection=1,
                                            position=window.top_left + Vec2(.45, 0), parent=self.ui)
        # After creating self.origin_mode_menu
        self.origin_mode_menu._init_w, self.origin_mode_menu._init_h = window.size
        h = self.origin_mode_menu._init_h or 1
        self.origin_mode_menu._base_ui_scale = (10 / h) * 2
        self.origin_mode_menu.scale = self.origin_mode_menu._base_ui_scale

        def _origin_mode_menu_update():
            cur_w, _ = window.size
            ratio = cur_w / (self.origin_mode_menu._init_w or cur_w)
            self.origin_mode_menu.scale = self.origin_mode_menu._base_ui_scale * ratio

        self.origin_mode_menu.update = _origin_mode_menu_update
        self.origin_mode_menu.scale = self.origin_mode_menu._base_ui_scale
        self.origin_mode_menu.on_value_changed = self.render_selection

        self.local_global_menu = ButtonGroup(['local', 'global'], default='global', min_selection=1,
                                             position=window.top_left + Vec2(.25, 0), parent=self.ui)
        
        # Dynamic scaling for local_global_menu
        self.local_global_menu._init_w, self.local_global_menu._init_h = window.size
        h = self.local_global_menu._init_h or 1
        self.local_global_menu._base_ui_scale = (10 / h) * 2  # Use 10px or adjust as needed
        self.local_global_menu.scale = self.local_global_menu._base_ui_scale

        def _local_global_menu_update():
            cur_w, _ = window.size
            ratio = cur_w / (self.local_global_menu._init_w or cur_w)
            self.local_global_menu.scale = self.local_global_menu._base_ui_scale * ratio

        self.local_global_menu.update = _local_global_menu_update

        self.local_global_menu.on_value_changed = self.render_selection

        self.target_fov = 90

        # Gizmos and manipulation tools
        self.sun_handler = SunHandler()
        self.sky = Sky(parent=scene)
        self.gizmo = Gizmo()
        self.rotation_gizmo = RotationGizmo()
        self.scale_gizmo = ScaleGizmo()
        self.box_gizmo = BoxGizmo()
        self.gizmo_toggler = GizmoToggler()

        self.quick_grabber = QuickGrabber()
        self.quick_scaler = QuickScaler()
        self.quick_rotator = QuickRotator()
        self.rotate_to_view = RotateRelativeToView(target_entity=None)
        self.selector = Selector()
        self.selection_box = SelectionBox(model=Quad(0, mode='line'), origin=(-.5, -.5, 0),
                                          scale=(0, 0, 1), color=color.white33, mode='new')

        # Prefab loading and prefab tool setup
        self.prefab_folder = application.asset_folder / 'prefabs'
        from ursina.editor.prefabs.poke_shape import PokeShape
        self.built_in_prefabs = [ClassSpawner, WhiteCube, TriplanarCube, Pyramid, PokeShape]
        self.prefabs = []

        # Editor tools
        self.spawner = Spawner()
        self.deleter = Deleter()
        self.grouper = Grouper()
        self.level_menu = LevelMenu()
        self.goto_scene = self.level_menu.goto_scene
        self.duplicator = Duplicator()
        self.copier = Copier()

        # Property and context menus
        self.model_menu = ModelMenu()
        self.texture_menu = TextureMenu()
        self.color_menu = ColorMenu()
        self.shader_menu = ShaderMenu()
        self.collider_menu = ColliderMenu()
        self.class_menu = ClassMenu()
        self.menu_handler = MenuHandler()
        self.right_click_menu = RightClickMenu()
        self.hierarchy_list = HierarchyList()
        self.inspector = Inspector()
        self.point_of_view_selector = PointOfViewSelector()
        self.help = Help()
        self.search = Search()  # <-- Add this line

        # After creating self.help
        self.help._init_w, self.help._init_h = window.size
        h = self.help._init_h or 1
        self.help._base_ui_scale = (8 / h) * 2  # 25px diameter, adjust as needed
        self.help.scale = self.help._base_ui_scale

        # For the tooltip
        self.help.tooltip._init_w, self.help.tooltip._init_h = window.size
        self.help.tooltip._base_ui_scale = (12 / h) * 2  # 50px text height, adjust as needed
        self.help.tooltip.scale = self.help.tooltip._base_ui_scale

        self._edit_mode = True


    def add_entity(self, entity):
        """
        Add an entity to the current scene and assign default editing properties.
        """
        try:
            for key, value in dict(original_parent=LEVEL_EDITOR, selectable=True,  # type: ignore
                                   collision=False, collider_type='None').items():  # type: ignore
                if not hasattr(entity, key):
                    setattr(entity, key, value)

            if self.current_scene and self.current_scene.scene_parent:  # type: ignore
                entity.parent = self.current_scene.scene_parent  # type: ignore
                self.current_scene.entities.append(entity)  # type: ignore
            else:
                print("Error adding entity: No current scene or scene parent.")
        except Exception as e:
            print(f"Error adding entity: {e}")


    @property
    def entities(self):
        """
        Get the list of entities in the current scene.
        """
        return self.current_scene.entities if self.current_scene else []

    @entities.setter
    def entities(self, value):
        """
        Set the list of entities in the current scene.
        """
        if self.current_scene:
            self.current_scene.entities = value

    @property
    def selection(self):
        """
        Get the list of currently selected entities.
        """
        return self.current_scene.selection if self.current_scene else []

    @selection.setter
    def selection(self, value):
        """
        Set the list of selected entities.
        """
        if self.current_scene:
            self.current_scene.selection = value


    def on_enable(self):
        """
        Called when the LevelEditor is enabled. Adjusts camera FOV and enables UI.
        """
        self._camera_original_fov = camera.fov
        camera.fov = self.target_fov
        if hasattr(self, 'ui'):
            self.ui.enabled = True
            

    def on_disable(self):
        """
        Called when the LevelEditor is disabled. Restores original camera FOV and disables UI.
        """
        camera.fov = getattr(self, '_camera_original_fov', camera.fov)
        if hasattr(self, 'ui'):
            self.ui.enabled = False


    def update(self):
        """
        Update is called every frame. It handles input-based rendering triggers.
        """
        for key in 'gsxyz':
            if held_keys[key]:
                self.render_selection()
                return

        if mouse.left:
            self.render_selection()

        cur_w, _ = window.size
        ratio = cur_w / (self.point_renderer._init_w or cur_w)
        self.point_renderer.model.thickness = max(0.01, self.point_renderer._base_thickness * ratio)

        # Dynamic scaling for help button
        ratio = cur_w / (self.help._init_w or cur_w)
        self.help.scale = max(0.05, self.help._base_ui_scale * ratio)
        
        # Dynamic scaling for tooltip
        ratio_tooltip = cur_w / (self.help.tooltip._init_w or cur_w)
        self.help.tooltip.scale = max(0.7, self.help.tooltip._base_ui_scale * ratio_tooltip)

        # Dynamic scaling for right-click menu
        ratio = cur_w / (self.right_click_menu.radial_menu._init_w or cur_w)
        self.right_click_menu.radial_menu.scale = self.right_click_menu.radial_menu._base_ui_scale * ratio
        
        # Optionally, scale each button
        for button in self.right_click_menu.radial_menu.buttons:
            ratio_btn = cur_w / (button._init_w or cur_w)
            button.scale = button._base_ui_scale * ratio_btn
        
        # Dynamic scaling for serach input field
        ratio = cur_w / (self.search.input_field._init_w or cur_w)
        self.search.input_field.scale = self.search.input_field._base_ui_scale * ratio


    def input(self, key):
        """
        Handle input keys for editor commands like save, undo, redo, toggle edit mode, and zoom UI.
        """
        combined_key = input_handler.get_combined_key(key)

        if combined_key == 'control+s':
            if not self.current_scene:
                print("No current_scene, can't save.")
                return
            self.current_scene.save()

        if self.current_scene:
            if combined_key == 'control+z':
                self.current_scene.undo.undo()
            elif combined_key == 'control+y':
                self.current_scene.undo.redo()

        if self.selection and combined_key == 'f':
            self.editor_camera.animate_position(self.gizmo.world_position, duration=.1, curve=curve.linear)

        elif combined_key == 'control+e':
            self.edit_mode = not self.edit_mode

        elif combined_key == 'control++':
            for e in self.ui.children:
                e.scale *= 1.1
        elif combined_key == 'control+-':
            for e in self.ui.children:
                e.scale /= 1.1


    @property
    def edit_mode(self):
        """
        Get the current edit mode state.
        """
        return self._edit_mode

    @edit_mode.setter
    def edit_mode(self, value):
        """
        Toggle between edit and play mode, updating all UI and entity visibility and behavior accordingly.
        """
        if not self.current_scene:
            return

        if not value and self._edit_mode:
            # Enter play mode
            for e in self.children:
                e.ignore = True
                e.visible = False

            self.editor_camera.original_target_z = self.editor_camera.target_z
            self.editor_camera.enabled = False
            self.ui.enabled = False

            for e in self.current_scene.entities:
                if hasattr(e, 'edit_mode') and e.edit_mode:
                    e.edit_mode = False

                e.editor_collider = e.collider
                if e.collider:
                    e.editor_collider = e.collider.name

                if hasattr(e, 'collider_type') and e.collider_type != 'None':
                    e.collider = e.collider_type
                else:
                    e.collider = None

                if hasattr(e, 'start') and callable(e.start):
                    e.start()

        elif value and not self._edit_mode:
            # Return to editor mode
            self.ui.enabled = True

            for e in self.current_scene.entities:
                if hasattr(e, 'stop') and callable(e.stop):
                    e.stop()
                e.collider = e.editor_collider

            for e in self.children:
                e.ignore = False
                e.visible = True

            self.editor_camera.enabled = True
            self.editor_camera.target_z = self.editor_camera.original_target_z
            camera.z = self.editor_camera.target_z

        self._edit_mode = value


    def render_selection(self, update_gizmo_position=True):
        """
        Update the visual and logical selection indicators, including gizmo and cubes.
        """
        # Remove invalid entities
        null_entities = [e for e in self.entities if e is None]
        for e in null_entities:
            print('Error: found None entity in entities')
            self.entities.remove(e)

        self.point_renderer.model.vertices = []
        self.point_renderer.model.colors = []

        for e in self.entities:
            if not e or (e.model and e.model.name == 'cube'):
                continue

            self.point_renderer.model.vertices.append(e.world_position)

            if e not in self.selection:
                gizmo_color = getattr(e.__class__, 'gizmo_color', color.orange)
            else:
                gizmo_color = getattr(e.__class__, 'gizmo_color_selected', color.azure)

            self.point_renderer.model.colors.append(gizmo_color)

        self.point_renderer.model.triangles = []
        self.point_renderer.model.generate()

        # Remove nulls from selection
        self.selection = [e for e in self.selection if e]

        if update_gizmo_position and self.selection:
            if self.origin_mode_menu.value in ('last', 'individual'):
                self.gizmo.world_position = self.selection[-1].world_position
            elif self.origin_mode_menu.value == 'center':
                self.gizmo.world_position = sum([e.world_position for e in self.selection]) / len(self.selection)

            if self.local_global_menu.value == 'local' and self.origin_mode_menu.value == 'last':
                self.gizmo.world_rotation = self.selection[-1].world_rotation
            else:
                self.gizmo.world_rotation = Vec3(0, 0, 0)

        # Render selection cube overlays
        [e.disable() for e in self.cubes]
        for i, e in enumerate([e for e in self.selection if e.collider]):
            if i < len(self.cubes):
                self.cubes[i].world_transform = e.world_transform
                self.cubes[i].origin = e.origin
                self.cubes[i].model = copy(e.model)
                self.cubes[i].enabled = True

        LEVEL_EDITOR.hierarchy_list.render_selection()  # type: ignore


class ErrorEntity(Entity):
    """
    A fallback entity used to represent an error state in the level editor.

    This class is typically instantiated when an entity fails to load properly,
    such as due to missing model or texture references. It serves as a visual
    cue in the scene that something has gone wrong.

    Attributes:
        model (str): The model used to represent the error entity. Defaults to 'wireframe_cube'.
        color (color): The color of the entity, defaulting to red to indicate an error.
        kwargs: Additional keyword arguments passed to the base Entity class.
    """

    def __init__(self, model='wireframe_cube', color=color.red, **kwargs):
        try:
            # Attempt to initialize the error entity with the given model and color.
            # This makes it visually distinct in the scene.
            super().__init__(model=model, color=color, **kwargs)

        except Exception as e:
            # In case something goes wrong during initialization, print a descriptive error.
            print(f"[ErrorEntity] Failed to initialize ErrorEntity with model='{model}': {e}")
            # Optionally, fall back to a default cube if 'wireframe_cube' is missing.
            try:
                super().__init__(model='cube', color=color.red, **kwargs)
            except Exception as fallback_error:
                print(f"[ErrorEntity] Failed to fallback to default cube model: {fallback_error}")


class LevelEditorScene:
    """
    Represents a single scene in the level editor grid.

    This class manages the loading, saving, and unloading of a scene's entity state,
    including undo tracking and metadata like coordinates and scene name.

    Attributes:
        coordinates (list[int, int]): The grid position (x, y) of the scene.
        name (str): The name of the scene.
        path (Path or None): Path to the saved scene file (.csv).
        entities (list): List of entities currently in the scene.
        selection (list): List of currently selected entities.
        scene_parent (Entity): The root entity for all scene content.
        undo (Undo): Undo handler for tracking changes within this scene.
    """

    def __init__(self, x, y, name, **kwargs):
        self.coordinates = [x, y]
        self.name = name
        self.path = None  # Must be set to a valid path before saving/loading
        self.entities = []
        self.selection = []
        self.scene_parent = None
        self.undo = Undo()
        # self.undo_handler may be assigned externally

    def save(self):
        """
        Save the scene's entities to a CSV file.

        Entities must provide a `get_changes(cls)` method to serialize properties.
        Skips saving if no `path` is set and no entities are available.
        """
        if not self.path and not self.entities:
            print('[LevelEditorScene] Cannot save: No path and no entities.')
            return

        try:
            LEVEL_EDITOR.scene_folder.mkdir(parents=True, exist_ok=True)  # type: ignore
        except Exception as e:
            print(f'[LevelEditorScene] Failed to create scene folder: {e}')
            return

        list_of_dicts = []
        fields = ['class']

        for e in LEVEL_EDITOR.current_scene.entities:  # type: ignore
            if hasattr(e, 'is_gizmo'):
                continue  # Skip gizmo tools

            changes = e.get_changes(e.__class__)
            # Replace None with False (likely a serialization decision)
            for key, value in changes.items():
                if value is None:
                    changes[key] = False

            changes['class'] = e.__class__.__name__

            if hasattr(e, 'collider_type'):
                # Wrap collider_type in quotes to preserve string literal during eval
                changes['collider_type'] = f"'{e.collider_type}'"

            print('[LevelEditorScene] changes:', changes)
            list_of_dicts.append(changes)

            # Collect all unique fields
            for key in changes:
                if key not in fields:
                    fields.append(key)

        name = LEVEL_EDITOR.current_scene.name  # type: ignore
        self.path = LEVEL_EDITOR.scene_folder / f'{name}.csv'  # type: ignore

        try:
            with self.path.open('w', encoding='UTF8') as file:
                writer = csv.DictWriter(file, fieldnames=fields, delimiter=';')
                writer.writeheader()
                writer.writerows(list_of_dicts)

            print(f'[LevelEditorScene] Saved scene: {self.path}')
        except Exception as e:
            print(f'[LevelEditorScene] Failed to save scene: {e}')

    def load(self):
        """
        Load the scene from the CSV file at `self.path`.

        Each line is parsed into an entity. If the class can't be found,
        a fallback ErrorEntity is used instead.
        """
        if not self.path:
            print('[LevelEditorScene] Cannot load: path is None.')
            return
        if self.scene_parent:
            print('[LevelEditorScene] Error: scene already loaded.')
            return

        # Collect all currently imported classes
        imported_classes = {}
        for module_name, module in list(sys.modules.items()):
            if hasattr(module, '__file__') and module.__file__ and not module.__file__.startswith(sys.prefix):
                for _, obj in inspect.getmembers(module):
                    if inspect.isclass(obj):
                        imported_classes[obj.__name__] = obj

        t = perf_counter()

        try:
            with self.path.open('r') as f:
                self.scene_parent = Entity()  # Root container for scene
                reader = csv.DictReader(f, delimiter=';')
                fields = reader.fieldnames[1:]  # Skip "class" column

                for line in reader:
                    # Convert line values to evaluated Python objects
                    kwargs = {k: v for k, v in line.items() if v and k != 'class'}
                    kwargs.setdefault('parent', self.scene_parent)

                    for key, value in kwargs.items():
                        if key == 'parent':
                            continue
                        try:
                            kwargs[key] = eval(value)
                        except Exception:
                            pass  # Leave as string if eval fails

                    # --- Fix: Ensure parent is always an Entity, not a string ---
                    if isinstance(kwargs.get('parent'), str):
                        kwargs['parent'] = self.scene_parent

                    class_name = line["class"]
                    target_class = imported_classes.get(class_name, ErrorEntity)

                    try:
                        instance = target_class(**kwargs)
                    except Exception as e:
                        print(f'[LevelEditorScene] Failed to instantiate {class_name}: {e}')
                        instance = ErrorEntity()

                    self.entities.append(instance)

                # Post-load adjustments
                for e in self.entities:
                    if not getattr(e, 'shader', None):
                        e.shader = lit_with_shadows_shader
                    e.selectable = True
                    e.original_parent = e.parent
                    if not hasattr(e, 'collider_type'):
                        e.collider_type = None

                    # Auto-assign colliders to cube models
                    if e.model and e.model.name == 'cube':
                        e.collider = 'box'
                        e.collision = False

            if self.scene_parent:
                print(f'[LevelEditorScene] Loaded scene "{self.name}" in {perf_counter() - t:.3f} seconds.')
                return self.scene_parent

        except Exception as e:
            print(f'[LevelEditorScene] Failed to load scene: {e}')

    def unload(self):
        """
        Unload the scene by destroying all its entities and resetting state.
        """
        try:
            # Reparent selection cubes to editor to keep them alive
            for e in LEVEL_EDITOR.cubes:  # type: ignore
                e.parent = LEVEL_EDITOR  # type: ignore

            # Destroy all scene entities
            for e in list(self.entities):
                destroy(e)

            # Reset scene state
            self.selection = []
            self.entities = []

            if self.scene_parent:
                destroy(self.scene_parent)
                self.scene = None

        except Exception as e:
            print(f'[LevelEditorScene] Error during unload: {e}')


class Undo(Entity):
    """
    Tracks undo/redo actions for the level editor by storing a history of actions
    and restoring the state of entities when triggered.

    Attributes:
        undo_data (list): A list of actions recorded for undo/redo.
        undo_index (int): The index of the current undo position.
    """

    def __init__(self, **kwargs):
        super().__init__(parent=LEVEL_EDITOR, undo_data=[], undo_index=-1)  # type: ignore

    def record_undo(self, data):
        """
        Record a new undo step.

        Args:
            data (any): Action data to be recorded. Format depends on action type.
        """
        print('[Undo] Record undo:', data)

        # Truncate forward history if undo() was used before recording again
        self.undo_data = self.undo_data[:self.undo_index + 1]

        self.undo_data.append(data)
        self.undo_index += 1

    def undo(self):
        """
        Undo the last recorded action, if any.
        """
        if self.undo_index < 0:
            return

        current_undo_data = self.undo_data[self.undo_index]

        try:
            if current_undo_data[0] == 'restore entities':
                # Restore previously deleted entities
                for id, recipe in zip(current_undo_data[1], current_undo_data[2]):
                    try:
                        clone = eval(recipe)
                        clone.selectable = True
                        clone.original_parent = clone.parent
                        clone.shader = lit_with_shadows_shader
                        LEVEL_EDITOR.entities.insert(id, clone)  # type: ignore
                    except Exception as e:
                        print(f'[Undo] Failed to restore entity from recipe: {e}')

            elif current_undo_data[0] == 'delete entities':
                # Delete newly created entities
                target_entities = [LEVEL_EDITOR.entities[id] for id in current_undo_data[1]]  # type: ignore

                for e in target_entities:
                    if e in LEVEL_EDITOR.selection:  # type: ignore
                        LEVEL_EDITOR.selection.remove(e)  # type: ignore
                for e in LEVEL_EDITOR.cubes:  # type: ignore
                    e.parent = LEVEL_EDITOR  # type: ignore
                for e in target_entities:
                    if e in LEVEL_EDITOR.entities:  # type: ignore
                        LEVEL_EDITOR.entities.remove(e)  # type: ignore
                    destroy(e)

            else:
                # Revert attribute changes (generic)
                for data in current_undo_data:
                    id, attr, original, _ = data
                    try:
                        setattr(LEVEL_EDITOR.entities[id], attr, original)  # type: ignore
                    except Exception as e:
                        print(f'[Undo] Failed to revert {attr} on entity {id}: {e}')

        except Exception as e:
            print(f'[Undo] Undo operation failed: {e}')

        LEVEL_EDITOR.render_selection()  # type: ignore
        self.undo_index -= 1

    def redo(self):
        """
        Redo the last undone action, if available.
        """
        if self.undo_index + 2 > len(self.undo_data):
            return

        current_undo_data = self.undo_data[self.undo_index + 1]

        try:
            if current_undo_data[0] == 'delete entities':
                # Re-instantiate entities that were deleted
                for id, recipe in zip(current_undo_data[1], current_undo_data[2]):
                    try:
                        clone = eval(recipe)
                        clone.selectable = True
                        clone.original_parent = clone.parent
                        clone.shader = lit_with_shadows_shader
                        LEVEL_EDITOR.entities.insert(id, clone)  # type: ignore
                    except Exception as e:
                        print(f'[Undo] Failed to redo delete entity: {e}')

            elif current_undo_data[0] == 'restore entities':
                # Delete re-restored entities again
                target_entities = [LEVEL_EDITOR.entities[id] for id in current_undo_data[1]]  # type: ignore

                for e in target_entities:
                    if e in LEVEL_EDITOR.selection:  # type: ignore
                        LEVEL_EDITOR.selection.remove(e)  # type: ignore
                for e in LEVEL_EDITOR.cubes:  # type: ignore
                    e.parent = LEVEL_EDITOR  # type: ignore
                for e in target_entities:
                    if e in LEVEL_EDITOR.entities:  # type: ignore
                        LEVEL_EDITOR.entities.remove(e)  # type: ignore
                    destroy(e)

            else:
                # Re-apply attribute changes
                for data in current_undo_data:
                    id, attr, _, new = data
                    try:
                        setattr(LEVEL_EDITOR.entities[id], attr, new)  # type: ignore
                    except Exception as e:
                        print(f'[Undo] Failed to reapply {attr} on entity {id}: {e}')

        except Exception as e:
            print(f'[Undo] Redo operation failed: {e}')

        LEVEL_EDITOR.render_selection()  # type: ignore
        self.undo_index += 1


axis_colors = {
    'x' : color.magenta,
    'y' : color.yellow,
    'z' : color.cyan
}

if not load_model('arrow', application.internal_models_compressed_folder):
    p = Entity(enabled=False)
    Entity(parent=p, model='cube', scale=(1,.05,.05))
    Entity(parent=p, model=Cone(4), x=.5, scale=.2, rotation=(0,90,0))
    arrow_model = p.combine()
    arrow_model.save('arrow.ursinamesh', folder=application.internal_models_compressed_folder, max_decimals=4)

if not load_model('scale_gizmo', application.internal_models_compressed_folder):
    p = Entity(enabled=False)
    Entity(parent=p, model='cube', scale=(.05,.05,1))
    Entity(parent=p, model='cube', z=.5, scale=.2)
    arrow_model = p.combine()
    arrow_model.save('scale_gizmo.ursinamesh', folder=application.internal_models_compressed_folder, max_decimals=4)


class GizmoArrow(Draggable):
    """
    A draggable arrow gizmo used in the level editor for transforming selected entities.

    Attributes:
        record_undo (bool): Whether dragging should record undo operations.
        original_rotation (Quaternion): The rotation state when initialized.
    """

    def __init__(self, model='arrow', collider='box', **kwargs):
        """
        Initialize the GizmoArrow with default arrow model and unlit shader.
        
        Args:
            model (str): Model used for the gizmo. Defaults to 'arrow'.
            collider (str): Collider shape. Defaults to 'box'.
            **kwargs: Additional arguments passed to the Draggable initializer.
        """
        super().__init__(
            model=model,
            origin_x=-0.55,
            always_on_top=True,
            render_queue=1,
            is_gizmo=True,
            shader=unlit_shader,
            **kwargs
        )

        # Allow override of any custom attributes passed via kwargs
        for key, value in kwargs.items():
            setattr(self, key, value)

        self.record_undo = True
        self.original_rotation = self.rotation

    def drag(self):
        """
        Triggered when the gizmo is dragged.
        Assigns proper parent and state to each selected entity.
        """
        self.world_parent = LEVEL_EDITOR  # type: ignore
        LEVEL_EDITOR.gizmo.world_parent = self  # type: ignore

        for e in LEVEL_EDITOR.selection:  # type: ignore
            # Determine original parent for undo
            if not hasattr(e.parent, 'is_gizmo') or not e.parent.is_gizmo:
                e.original_parent = e.parent
            else:
                e.original_parent = scene  # fallback to root

            # Assign new world parent based on editor mode
            if LEVEL_EDITOR.local_global_menu.value == 'global':  # type: ignore
                e.world_parent = self
            else:
                e.world_parent = LEVEL_EDITOR.gizmo.fake_gizmo  # type: ignore

            e.always_on_top = False
            e._original_world_transform = e.world_transform

    def drop(self):
        """
        Triggered when the gizmo is released after dragging.
        Restores parent relationships and records undo if transform changed.
        """
        LEVEL_EDITOR.gizmo.world_parent = LEVEL_EDITOR  # type: ignore

        for e in LEVEL_EDITOR.selection:  # type: ignore
            e.world_parent = e.original_parent
            print('[Drop] Original parent restored:', e.original_parent, isinstance(e.original_parent, GizmoArrow))

        if not LEVEL_EDITOR.selection:  # type: ignore
            return

        # Check if transform has changed
        first = LEVEL_EDITOR.selection[0]  # type: ignore
        try:
            changed = any(
                distance(first.world_transform[i], first._original_world_transform[i]) > 0.0001
                for i in range(3)
            )
        except Exception as e:
            print(f'[Drop] Error comparing transforms: {e}')
            changed = False

        # Record undo if applicable
        if self.record_undo and changed:
            changes = []
            for e in LEVEL_EDITOR.selection:  # type: ignore
                try:
                    index = LEVEL_EDITOR.entities.index(e)  # type: ignore
                    changes.append([index, 'world_transform', e._original_world_transform, e.world_transform])
                except ValueError:
                    print(f'[Drop] Entity not found in LEVEL_EDITOR.entities: {e}')
            LEVEL_EDITOR.current_scene.undo.record_undo(changes)  # type: ignore

        # Reset gizmo
        self.parent = LEVEL_EDITOR.gizmo.arrow_parent  # type: ignore
        self.position = (0, 0, 0)
        self.rotation = self.original_rotation
        LEVEL_EDITOR.render_selection()  # type: ignore

    def input(self, key):
        """
        Handle input events, such as snapping steps.

        Args:
            key (str): Input key string.
        """
        super().input(key)
        if key == 'control':
            self.step = (1, 1, 1)
        elif key == 'control up':
            self.step = (0, 0, 0)


class Gizmo(Entity):
    """
    The main gizmo controller used in the level editor for manipulating entities.

    Supports move handles for the X, Y, Z axes, XZ plane, and local/global transform handling
    using a 'fake gizmo' trick to allow local axis dragging.
    """

    def __init__(self, **kwargs):
        """
        Initialize the Gizmo object, including subgizmos for each axis and a fake gizmo
        used for local space transformations.
        """
        super().__init__(parent=LEVEL_EDITOR, enabled=False)  # type: ignore

        self.arrow_parent = Entity(parent=self)

        # Helper object used for locking movement to an axis (in local mode)
        self.lock_axis_helper_parent = Entity(parent=LEVEL_EDITOR)  # type: ignore
        self.lock_axis_helper = Entity(parent=self.lock_axis_helper_parent)

        # Subgizmos for individual axes and plane
        self.subgizmos = {
            'xz': GizmoArrow(
                parent=self.arrow_parent,
                gizmo=self,
                model='cube',
                collider='plane',
                scale=0.6,
                scale_y=0.05,
                origin=(-0.75, 0, -0.75),
                color=lerp(color.magenta, color.cyan, 0.5),
                plane_direction=(0, 1, 0)
            ),
            'x': GizmoArrow(
                parent=self.arrow_parent,
                gizmo=self,
                color=axis_colors['x'],
                lock=(0, 1, 1)
            ),
            'y': GizmoArrow(
                parent=self.arrow_parent,
                gizmo=self,
                rotation=(0, 0, -90),
                color=axis_colors['y'],
                lock=(1, 0, 1)
            ),
            'z': GizmoArrow(
                parent=self.arrow_parent,
                gizmo=self,
                rotation=(0, -90, 0),
                color=axis_colors['z'],
                plane_direction=(0, 1, 0),
                lock=(1, 1, 0)
            ),
        }

        # Set highlight and original scale for visual feedback
        for arrow in self.arrow_parent.children:
            arrow.highlight_color = color.white
            arrow.original_scale = arrow.scale

        # Fake gizmo: used for local transform locking without visual clutter
        self.fake_gizmo = Entity(parent=LEVEL_EDITOR, enabled=False)  # type: ignore
        self.fake_gizmo.subgizmos = {}
        for key, original in self.subgizmos.items():
            self.fake_gizmo.subgizmos[key] = duplicate(original, parent=self.fake_gizmo, collider=None, ignore=True)

    def input(self, key):
        """
        Called before subgizmo input is processed.
        Handles drag initiation and drop logic based on mouse input and mode.
        """
        if key == 'left mouse down' and mouse.hovered_entity in self.subgizmos.values():
            self.drag()

        if key == 'left mouse up' and LEVEL_EDITOR.local_global_menu.value == 'local':  # type: ignore
            self.drop()

    def drag(self, show_gizmo_while_dragging=True):
        """
        Called when user starts dragging one of the subgizmos.
        Prepares gizmo and sets plane direction / locking depending on local/global mode.
        """
        for i, axis in enumerate('xyz'):
            self.subgizmos[axis].plane_direction = self.up
            self.subgizmos[axis].lock = [0, 0, 0]

            if LEVEL_EDITOR.local_global_menu.value == 'global':  # type: ignore
                # Lock all except current axis in global mode
                self.subgizmos[axis].lock = [1, 1, 1]
                self.subgizmos[axis].lock[i] = 0

            if axis == 'y':
                self.subgizmos[axis].plane_direction = camera.back

        self.subgizmos['xz'].plane_direction = self.up

        # Show visible handles for dragging
        for gizmo in self.subgizmos.values():
            gizmo.visible_self = show_gizmo_while_dragging

        if LEVEL_EDITOR.local_global_menu.value == 'local':  # type: ignore
            # Use fake gizmo for local-axis locking
            self.lock_axis_helper_parent.world_transform = self.world_transform
            self.lock_axis_helper.position = (0, 0, 0)
            self.fake_gizmo.world_transform = self.world_transform

            self.fake_gizmo.enabled = True
            self.visible = False

            for g in self.fake_gizmo.subgizmos.values():
                g.visible_self = show_gizmo_while_dragging
            for g in self.subgizmos.values():
                g.visible_self = False

    def drop(self):
        """
        Called when dragging is finished.
        Restores visual and functional state.
        """
        self.fake_gizmo.enabled = False
        self.visible = True

        for g in self.fake_gizmo.subgizmos.values():
            g.visible_self = False
        for g in self.subgizmos.values():
            g.visible_self = True
            g.scale = g.original_scale

    def update(self):
        """
        Update the gizmo's state each frame.
        Handles gizmo scaling relative to camera, and position syncing when dragging.
        """
        if held_keys['r'] or held_keys['s']:
            return  # skip updating during rotation/scale modes

        # Scale the gizmo depending on distance to camera (screen-space size preservation)
        self.world_scale = distance(self.world_position, camera.world_position) * camera.fov * 0.0005

        # If dragging, update the fake gizmo's position based on axis locking
        for i, axis in enumerate('xyz'):
            if self.subgizmos[axis].dragging:
                self.lock_axis_helper.setattr(axis, self.subgizmos[axis].get_position(relative_to=self.lock_axis_helper_parent)[i])
                self.fake_gizmo.world_position = self.lock_axis_helper.world_position

        if self.subgizmos['xz'].dragging:
            self.fake_gizmo.world_position = self.subgizmos['xz'].world_position


class RotationGizmo(Entity):
    """
    A rotation gizmo tool used in the level editor to allow users to rotate selected entities
    along X, Y, or Z axes. Uses a visual ring model or fallback Pipe-based model for the rings.
    """
    model = None

    def __init__(self, **kwargs):
        super().__init__(parent=LEVEL_EDITOR.gizmo)  # type: ignore

        # Load or create the gizmo model (cached as class-level shared static)
        if not RotationGizmo.model:
            RotationGizmo.model = load_model('rotation_gizmo_model', application.internal_models_compressed_folder)
            if not RotationGizmo.model:
                path = Circle(24).vertices
                path.append(path[0])  # close the loop
                RotationGizmo.model = Pipe(
                    base_shape=Quad(radius=0),
                    path=[Vec3(v) * 32 for v in path]
                )
                RotationGizmo.model.save('rotation_gizmo_model.ursinamesh', application.internal_models_compressed_folder)

        self.rotator = Entity(parent=LEVEL_EDITOR.gizmo)  # type: ignore
        self.axis = Vec3(0, 1, 0)
        self.sensitivity = 36000
        self.dragging = False
        self.subgizmos = {}

        # Create one ring per axis (X, Y, Z)
        axis_dirs = [Vec3(-1, 0, 0), Vec3(0, 1, 0), Vec3(0, 0, -1)]
        for i, dir in enumerate(axis_dirs):
            axis = 'xyz'[i]
            button = Button(
                parent=self,
                model=copy(RotationGizmo.model),
                collider='mesh',
                color=axis_colors[axis],
                is_gizmo=True,
                always_on_top=True,
                render_queue=1,
                unlit=True,
                double_sided=True,
                name=f'rotation_gizmo_{axis}',
                scale=1 / 32,
                on_click=Sequence(
                    Func(setattr, self, 'axis', dir),
                    Func(self.drag)
                ),
                drop=self.drop
            )
            button.look_at(dir)
            button.original_color = button.color
            button.start_dragging = button.on_click

            # Highlight on hover
            button.on_mouse_enter = Func(setattr, button, 'color', color.white)
            button.on_mouse_exit = Func(setattr, button, 'color', button.original_color)

            self.subgizmos[axis] = button

    def drag(self):
        """
        Called when a rotation ring is clicked.
        Parents selected entities to the rotator for transform pivot grouping.
        """
        self.rotator.world_parent = scene

        for e in LEVEL_EDITOR.selection:  # type: ignore
            e.world_parent = self.rotator
            e._original_world_transform = e.world_transform

        self.dragging = True

    def drop(self):
        """
        Called on mouse release or manually to finalize rotation.
        Applies final transform and records undo.
        """
        self.rotator.world_parent = LEVEL_EDITOR.gizmo  # type: ignore
        changes = []

        for e in LEVEL_EDITOR.selection:  # type: ignore
            e.world_parent = e.original_parent
            changes.append([
                LEVEL_EDITOR.entities.index(e),  # type: ignore
                'world_transform',
                e._original_world_transform,
                e.world_transform
            ])  # type: ignore

        LEVEL_EDITOR.current_scene.undo.record_undo(changes)  # type: ignore
        self.dragging = False
        self.rotator.rotation = (0, 0, 0)
        LEVEL_EDITOR.render_selection()  # type: ignore

    def input(self, key):
        """
        Handle rotation stop via mouse button release.
        """
        if key == 'left mouse up' and self.dragging:
            self.drop()

    def update(self):
        """
        Called each frame to apply rotation to selected entities.
        Computes rotation amount from mouse movement and applies it depending on origin mode.
        """
        if not self.dragging:
            return

        # Calculate rotation delta
        delta = sum(mouse.velocity) * self.sensitivity * time.dt
        rotation_amount = Vec3(delta, delta, delta) * self.axis * Vec3(1, 1, -1)

        if LEVEL_EDITOR.origin_mode_menu.value == 'individual':  # type: ignore
            # Rotate entities individually around their own origin
            for e in LEVEL_EDITOR.selection:  # type: ignore
                e.rotation -= rotation_amount
        else:
            # Rotate around group center (via rotator parent)
            self.rotator.rotation -= rotation_amount


class ScaleGizmo(Draggable):
    """
    A gizmo for uniformly or axis-aligned scaling of selected entities in the level editor.
    Supports both group scaling via a scaler entity and individual scaling via direct manipulation.
    """
    def __init__(self, **kwargs):
        super().__init__(
            parent=LEVEL_EDITOR.gizmo,  # type: ignore
            model='cube',
            scale=0.25,
            color=color.orange,
            visible=True,
            always_on_top=True,
            render_queue=1,
            is_gizmo=True,
            dragging=False,
            shader=unlit_shader
        )
        self.scaler = Entity(parent=LEVEL_EDITOR.gizmo)  # Shared parent to scale as a group  # type: ignore
        self.axis = Vec3(1, 1, 1)  # Default to uniform scaling
        self.on_click = Func(setattr, self, 'axis', Vec3(1, 1, 1))  # Uniform scaling click
        self.subgizmos = {}
        self.sensitivity = 300
        self.dragging = False

        # Create one gizmo per axis
        axis_directions = [Vec3(1, 0, 0), Vec3(0, 1, 0), Vec3(0, 0, 1)]
        for i, direction in enumerate(axis_directions):
            axis = 'xyz'[i]
            button = Button(
                parent=self,
                model='scale_gizmo',
                origin_z=-0.5,
                scale=4,
                collider='box',
                color=axis_colors[axis],
                is_gizmo=True,
                always_on_top=True,
                render_queue=1,
                shader=unlit_shader,
                on_click=Sequence(
                    Func(setattr, self, 'axis', direction),
                    Func(self.drag)
                ),
                name=f'scale_gizmo_{axis}'
            )
            button.look_at(direction)
            self.subgizmos[axis] = button

    def drag(self):
        """
        Called when a scaling gizmo handle is clicked.
        Reparents selected entities to a shared scaler transform (if not in individual mode).
        """
        for e in LEVEL_EDITOR.selection:  # type: ignore
            e.world_parent = self.scaler
            e._original_world_transform = e.world_transform
        self.dragging = True

    def drop(self):
        """
        Called when the drag ends. Applies the scale and records an undo state.
        """
        changes = []
        for e in LEVEL_EDITOR.selection:  # type: ignore
            e.world_parent = e.original_parent
            changes.append([
                LEVEL_EDITOR.entities.index(e),  # type: ignore
                'world_transform',
                e._original_world_transform,
                e.world_transform
            ])  # type: ignore

        LEVEL_EDITOR.current_scene.undo.record_undo(changes)  # type: ignore
        self.dragging = False
        self.scaler.scale = 1
        LEVEL_EDITOR.render_selection()  # type: ignore

    def update(self):
        """
        Called every frame. Applies scale delta to selected objects.
        """
        if not self.dragging:
            return

        # Compute scale amount from mouse movement
        delta = Vec3(sum(mouse.velocity)) * self.sensitivity * time.dt * self.axis

        if LEVEL_EDITOR.origin_mode_menu.value == 'individual':  # type: ignore
            # Apply scale per object
            for e in LEVEL_EDITOR.selection:  # type: ignore
                e.scale += delta
        else:
            # Apply scale via group transform
            self.scaler.scale += delta


class BoxGizmo(Entity):
    """
    A gizmo for scaling entities in the 3D editor. It allows scaling from the center
    or from the edges, and scales based on the normal of the hovered entity's face.
    """
    def __init__(self):
        super().__init__(parent=LEVEL_EDITOR)  # type: ignore
        self.target = None
        self.scaler = Entity(parent=self)  # Scaler used for relative scaling
        self.helper = Entity(parent=self, model='cube', unlit=True, color=color.azure, enabled=False)  # Helper for scaling preview
        self.sensitivity = 600
        self.scale_from_center = False  # Flag for scaling from the center (Alt key)
        self.normal = None
        self.axis_name = None

    def input(self, key):
        """
        Handles input events for scaling. Allows starting and stopping the scaling process.
        """
        if key == 'a':  # Start scaling
            self.start_scaling()

        elif key == 'a up' and self.target:  # End scaling
            self.stop_scaling()

    def start_scaling(self):
        """
        Initializes scaling when the 'a' key is pressed. This involves:
        - Setting up the target and scaler.
        - Calculating which axis to scale based on the normal.
        - Setting the helper entity to show the scaling direction.
        """
        [setattr(e, 'collision', True) for e in LEVEL_EDITOR.entities]  # type: ignore
        mouse.update()

        # Check if the mouse is hovering over a valid entity with a normal vector
        if mouse.hovered_entity in LEVEL_EDITOR.entities and mouse.normal and mouse.normal != Vec3(0):  # type: ignore
            self.target = mouse.hovered_entity
            self.target._original_world_transform = self.target.world_transform

            self.normal = Vec3(mouse.normal)
            self.axis_name = 'xyz'[[abs(int(e)) for e in self.normal].index(1)]  # Determine which axis to scale along

            self.scale_from_center = held_keys['alt']  # Use center scaling if Alt is held

            # Position the scaler and helper entity based on scale mode
            if not self.scale_from_center:
                self.scaler.parent = self.target
                self.scaler.position = -self.normal * 0.5
                self.scaler.rotation = Vec3(0)
                self.scaler.world_parent = self
            else:
                self.scaler.position = self.target.world_position
                self.scaler.rotation = self.target.world_rotation

            self.target.world_parent = self.scaler

            # Set up the helper entity
            self.helper.parent = self.target
            self.helper.position = self.normal / 2
            self.helper.rotation = Vec3(0)
            self.helper.world_scale = 0.05

            # Switch to local coordinate system if not already set
            LEVEL_EDITOR.local_global_menu.original_value = LEVEL_EDITOR.local_global_menu.value  # type: ignore
            if LEVEL_EDITOR.local_global_menu.value != 'local':  # type: ignore
                LEVEL_EDITOR.local_global_menu.value = 'local'  # type: ignore

            # Update selection to only include the helper
            LEVEL_EDITOR.selection = [self.helper]  # type: ignore
            LEVEL_EDITOR.render_selection()  # type: ignore
            LEVEL_EDITOR.gizmo.enabled = True  # type: ignore
            LEVEL_EDITOR.gizmo.drag(show_gizmo_while_dragging=False)  # type: ignore
            LEVEL_EDITOR.gizmo.subgizmos[self.axis_name].start_dragging()  # type: ignore

    def stop_scaling(self):
        """
        Stops the scaling process by resetting the transformations, visibility, and selections.
        Records the undo state of the target entity.
        """
        [setattr(e, 'collision', False) for e in LEVEL_EDITOR.entities]  # type: ignore
        self.target.world_parent = self.target.original_parent  # Restore the original parent of the target
        self.normal = None
        self.helper.parent = self  # Detach helper entity
        self.scaler.scale = 1  # Reset scaler to default scale

        LEVEL_EDITOR.gizmo.drop()  # type: ignore
        LEVEL_EDITOR.gizmo.subgizmos[self.axis_name].record_undo = False  # type: ignore
        LEVEL_EDITOR.gizmo.subgizmos[self.axis_name].stop_dragging()  # type: ignore
        LEVEL_EDITOR.gizmo.subgizmos[self.axis_name].record_undo = True  # type: ignore
        LEVEL_EDITOR.selection = []  # Clear selection  # type: ignore
        LEVEL_EDITOR.local_global_menu.value = LEVEL_EDITOR.local_global_menu.original_value  # type: ignore
        LEVEL_EDITOR.gizmo.enabled = False  # Disable gizmo  # type: ignore
        self.helper.enabled = False  # Hide helper entity

        # Record undo state for the target entity
        LEVEL_EDITOR.current_scene.undo.record_undo([  # type: ignore
            (LEVEL_EDITOR.entities.index(self.target), 'world_transform', self.target._original_world_transform, self.target.world_transform)  # type: ignore
        ])  # type: ignore
        self.target = None

    def update(self):
        """
        Updates the scaling process by adjusting the target's scale based on the helper's position.
        """
        if self.target and held_keys['a'] and self.helper and self.scaler:
            relative_position = self.helper.get_position(relative_to=self.scaler)
            value = abs(relative_position[[abs(int(e)) for e in self.normal].index(1)])

            # Scale from the center if the Alt key is held
            if self.scale_from_center:
                value *= 2

            setattr(self.target, f'scale_{self.axis_name}', value)

            # Adjust target position if not scaling from the center
            if not self.scale_from_center:
                self.target.world_position = lerp(self.scaler.world_position, self.helper.world_position, 0.5)


class GizmoToggler(Entity):
    """
    A class to handle toggling between different gizmos (e.g., scale, rotation) based on key presses.
    The gizmos are assigned to specific keys, and the currently active gizmo is updated accordingly.
    """
    def __init__(self, **kwargs):
        """
        Initializes the GizmoToggler, setting up the key-to-gizmo mapping and the animator.
        """
        super().__init__(parent=LEVEL_EDITOR)  # type: ignore

        # Create an animator to control the gizmos based on key presses
        self.animator = Animator({
            'w': LEVEL_EDITOR.gizmo.arrow_parent,  # type: ignore (Translation Gizmo)
            'e': LEVEL_EDITOR.scale_gizmo,  # type: ignore (Scale Gizmo)
            'u': LEVEL_EDITOR.rotation_gizmo,  # type: ignore (Rotation Gizmo)
            # 't': box_gizmo,  # Commented out, can be added if box gizmo is implemented.

            'q': None,  # Key to disable all gizmos (or any other action you may wish)
        })

    def input(self, key):
        """
        Handles input events for toggling gizmos. Sets the active gizmo based on the key pressed.
        """
        # Normalize key input for consistency (e.g., handle combined key presses)
        key = input_handler.get_combined_key(key)

        # If the key corresponds to an available gizmo in the animator's mappings, update the state
        if key in self.animator.animations and not mouse.left:
            self.animator.state = key


class QuickGrabber(Entity):
    """
    A utility tool for quick translation (grabbing/moving) of entities in the LEVEL_EDITOR scene.

    Allows axis-based constrained movement of entities using keyboard shortcuts or mouse interactions.
    Movement is handled by creating a large interaction plane and calculating relative drag positions.

    Attributes:
        target_entity (Entity or None): The entity currently being moved.
        target_axis (str or None): Axis or axes currently being used for constrained movement.
        plane (Entity): A large invisible plane used to calculate drag direction.
        offset_helper (Entity): A helper to track mouse offset during drag.
        start_position (Vec3): The starting position of the drag.
        axis_lock (List[int]): Lock configuration per axis. 1 means locked.
        is_dragging (bool): True when currently dragging an entity.
        shortcuts (dict): Key bindings for axis-specific movement commands.
    """

    def __init__(self, **kwargs):
        super().__init__(parent=LEVEL_EDITOR)  # type: ignore

        self.target_entity = None
        self.target_axis = None

        # A large invisible plane for mouse dragging
        self.plane = Entity(
            model='quad', collider='box', scale=Vec3(999, 999, 1), 
            visible_self=False, enabled=False
        )

        self.offset_helper = Entity()  # Used to maintain offset during drag
        self.start_position = Vec3(0, 0, 0)
        self.axis_lock = [0, 1, 0]  # Locking Y by default
        self.is_dragging = False

        # Shortcut key bindings for triggering drag operations
        self.shortcuts = {
            'left mouse down': Func(self.start_moving_on_axis, 'xz'),
            'd': Func(self.start_moving_on_axis, 'xz'),
            'w': Func(self.start_moving_on_axis, 'xz', auto_select_hovered_entity=False),
            'x': Func(self.start_moving_on_axis, 'x'),
            'y': Func(self.start_moving_on_axis, 'y'),
            'z': Func(self.start_moving_on_axis, 'z'),
        }

    def start_moving_on_axis(self, axis, auto_select_hovered_entity=True):
        """
        Starts moving the selected entity along the specified axis or plane.

        Args:
            axis (str): Axis or plane to constrain movement to ('x', 'y', 'z', 'xy', 'xz', etc).
            auto_select_hovered_entity (bool): Whether to automatically select the entity under the mouse.
        """
        if not auto_select_hovered_entity and len(LEVEL_EDITOR.selection) > 1:  # type: ignore
            return

        try:
            self.target_entity = LEVEL_EDITOR.selector.get_hovered_entity()  # type: ignore
            LEVEL_EDITOR.gizmo.enabled = False  # Hide default gizmo while dragging  # type: ignore

            if self.target_entity:
                LEVEL_EDITOR.selection = [self.target_entity]  # Select target entity  # type: ignore
                self.plane.enabled = True
                self.plane.position = self.target_entity.world_position

                # Orient the plane for dragging based on selected axis
                if axis == 'y' or axis == 'xy':
                    self.plane.look_at(self.plane.position + Vec3(0, 0, -1))
                else:
                    self.plane.look_at(self.plane.position + Vec3(0, 1, 0))

                # If multiple axes, don't lock any
                self.axis_lock = [0, 0, 0] if len(axis) > 1 else [
                    axis != 'x', axis != 'y', axis != 'z'
                ]

                mouse.traverse_target = self.plane
                mouse.update()
                self.offset_helper.position = mouse.world_point
                self.start_position = self.offset_helper.world_position

                # Store original parent to restore later
                if not hasattr(self.target_entity.parent, 'is_gizmo') or not self.target_entity.parent.is_gizmo:
                    self.target_entity.original_parent = self.target_entity.parent
                else:
                    self.target_entity.original_parent = scene

                self.target_entity._original_world_position = self.target_entity.world_position
                self.target_entity.world_parent = self.offset_helper
                self.is_dragging = True
        except Exception as e:
            print(f"[QuickGrabber] Failed to start dragging: {e}")

    def input(self, key):
        """
        Handles input events and manages drag state transitions.

        Args:
            key (str): Key event name (e.g., 'x', 'left mouse up').
        """
        combined_key = input_handler.get_combined_key(key)

        # Ignore if other conflicting keys are held
        if not key.endswith(' up') and (held_keys['shift'] or held_keys['alt'] or held_keys['s'] or mouse.right or mouse.middle or held_keys['r']):
            return

        # Cancel drag if mouse barely moved after clicking (likely a selection, not a drag)
        if (
            combined_key == 'left mouse up'
            and self.target_entity
            and distance(self.target_entity._original_world_position, self.target_entity.world_position) < 0.1
            and (time.time() - mouse.prev_click_time) < 0.5
        ):
            self.is_dragging = False
            mouse.traverse_target = scene
            self.target_entity.world_parent = self.target_entity.original_parent
            self.target_entity.world_position = self.target_entity._original_world_position
            LEVEL_EDITOR.selection = [self.target_entity]  # type: ignore
            LEVEL_EDITOR.render_selection()  # type: ignore
            self.target_entity = None
            self.plane.enabled = False
            return

        # Check if the key is a valid shortcut
        if combined_key in self.shortcuts:
            if self.target_entity:
                return
            self.shortcuts[key]()

        # Drop entity if relevant key is released
        elif (key in [f'{e} up' for e in self.shortcuts] or key == 'left mouse up') and self.target_entity:
            self.drop()

    def drop(self):
        """
        Finalizes the dragging operation, restores parent, and records undo state.
        """
        self.is_dragging = False
        mouse.traverse_target = scene

        try:
            self.target_entity.world_parent = self.target_entity.original_parent

            if self.target_entity.world_position != self.target_entity._original_world_position:
                changes = []
                for e in LEVEL_EDITOR.selection:  # type: ignore
                    changes.append([
                        LEVEL_EDITOR.entities.index(e),   # type: ignore
                        'world_position', 
                        e._original_world_position, 
                        e.world_position
                    ])  # type: ignore

                LEVEL_EDITOR.current_scene.undo.record_undo(changes)  # type: ignore
                LEVEL_EDITOR.selection = []  # type: ignore
                LEVEL_EDITOR.render_selection()  # type: ignore
            else:
                LEVEL_EDITOR.selection = [self.target_entity]  # type: ignore
                LEVEL_EDITOR.render_selection()  # type: ignore

        except Exception as e:
            print(f"[QuickGrabber] Error while dropping entity: {e}")

        self.target_entity = None
        self.plane.enabled = False

    def on_disable(self):
        """
        Called automatically when the QuickGrabber is disabled. Ensures drag state is cleaned up.
        """
        self.drop()

    def update(self):
        """
        Called every frame. Updates the dragged entity's position according to mouse input.
        """
        if not self.is_dragging or not mouse.world_point:
            return

        if mouse.right:
            return  # Do not update during right-click

        try:
            pos = mouse.world_point

            if held_keys['control']:
                # If snapping is enabled, round the position
                pos = round(pos)

            # Apply axis constraints
            for i, e in enumerate(pos):
                if self.axis_lock[i]:
                    pos[i] = self.start_position[i]

            self.offset_helper.world_position = pos

            if held_keys['control']:
                snap_step = 1
                self.offset_helper.world_position = Vec3(*[
                    round(e * snap_step) / snap_step for e in self.offset_helper.world_position
                ])
                self.target_entity.world_position = Vec3(*[
                    round(e * snap_step) / snap_step for e in self.target_entity.world_position
                ])

        except Exception as e:
            print(f"[QuickGrabber] Error in update(): {e}")


class QuickScaler(Entity):
    """
    QuickScaler is a utility for scaling selected entities in the LEVEL_EDITOR 
    using shortcut keys (`s`, `sx`, `sy`, `sz`) for uniform or axis-constrained scaling.

    Attributes:
        gizmos_to_toggle (dict): Mapping of scale shortcut keys to their corresponding gizmo handlers.
        clear_selection (bool): Indicates if the selection should be cleared after scaling.
        dragging (bool): Unused flag, placeholder for potential dragging state.
        original_gizmo_state (str): Stores the original gizmo animator state to restore post-scaling.
    """
    
    def __init__(self, **kwargs):
        super().__init__(
            parent=LEVEL_EDITOR,  # type: ignore

            # Mapping key inputs to their respective gizmo handlers
            gizmos_to_toggle={
                's': LEVEL_EDITOR.scale_gizmo,     # type: ignore
                'sx': LEVEL_EDITOR.scale_gizmo,    # type: ignore
                'sy': LEVEL_EDITOR.scale_gizmo,    # type: ignore
                'sz': LEVEL_EDITOR.scale_gizmo     # type: ignore
            },

            clear_selection=False,
            dragging=False,
            original_gizmo_state='q'
        )

    def input(self, key):
        """
        Handles input events for scale commands, axis locking and triggering appropriate gizmo actions.

        Args:
            key (str): The input key pressed or released.
        """
        try:
            # Early exit if user is performing a conflicting action
            if (
                held_keys['control'] or held_keys['shift'] or held_keys['alt']
                or mouse.left or mouse.middle or held_keys['r']
                or held_keys['d'] or held_keys['t']
            ):
                return

            # Store original gizmo state when preparing for axis scaling
            if (held_keys['x'] or held_keys['y'] or held_keys['z']) and key == 's':
                self.original_gizmo_state = LEVEL_EDITOR.gizmo_toggler.animator.state  # type: ignore
                return

            # Convert s + axis key (x/y/z) into full key
            if held_keys['s'] and key in 'xyz':
                key = 's' + key

            if key in ('s', 'sx', 'sy', 'sz'):
                self.original_gizmo_state = LEVEL_EDITOR.gizmo_toggler.animator.state  # type: ignore
                LEVEL_EDITOR.gizmo_toggler.animator.state = 'e'  # type: ignore

                # Axis-specific scaling setup
                if key != 's':
                    LEVEL_EDITOR.scale_gizmo.axis = (  # type: ignore
                        Vec3(1, 0, 0), Vec3(0, 1, 0), Vec3(0, 0, 1)
                    )[('sx', 'sy', 'sz').index(key)]  # type: ignore

            # Begin scale operation using corresponding gizmo
            if key in self.gizmos_to_toggle:
                LEVEL_EDITOR.selector.enabled = False  # type: ignore
                LEVEL_EDITOR.selection_box.enabled = False  # type: ignore
                LEVEL_EDITOR.gizmo.arrow_parent.visible = False  # type: ignore
                LEVEL_EDITOR.scale_gizmo.visible = False  # type: ignore

                self.gizmos_to_toggle[key].visible_self = False

                if key not in ('sx', 'sy', 'sz'):
                    self.clear_selection = not LEVEL_EDITOR.selection  # type: ignore

                if not LEVEL_EDITOR.selection:  # type: ignore
                    LEVEL_EDITOR.selector.input('left mouse down')  # type: ignore

                self.gizmos_to_toggle[key].input('left mouse down')
                self.gizmos_to_toggle[key].start_dragging()

            # Cleanup on key release
            if key in ('s up', 'x up', 'y up', 'z up'):
                for gizmo in self.gizmos_to_toggle.values():
                    gizmo.input('left mouse up')

                if self.clear_selection:
                    LEVEL_EDITOR.selection.clear()  # type: ignore
                    LEVEL_EDITOR.render_selection()  # type: ignore

                LEVEL_EDITOR.gizmo.arrow_parent.visible = True  # type: ignore
                LEVEL_EDITOR.scale_gizmo.visible = True  # type: ignore
                LEVEL_EDITOR.scale_gizmo.axis = Vec3(1, 1, 1)  # type: ignore

                LEVEL_EDITOR.gizmo_toggler.animator.state = self.original_gizmo_state  # type: ignore
                LEVEL_EDITOR.selector.enabled = True  # type: ignore
                LEVEL_EDITOR.selection_box.enabled = True  # type: ignore
                mouse.traverse_target = scene

        except Exception as e:
            print(f"[QuickScaler] Error during input handling: {e}")

    def update(self):
        """
        Called every frame. Ensures the scale gizmo updates when user is actively scaling.
        """
        try:
            for key in self.gizmos_to_toggle:
                if held_keys[key] and not held_keys['control'] and not held_keys['shift'] and mouse.velocity != Vec3(0, 0, 0):
                    LEVEL_EDITOR.render_selection(update_gizmo_position=False)  # type: ignore
                    return
        except Exception as e:
            print(f"[QuickScaler] Error in update loop: {e}")


class QuickRotator(Entity):
    """
    QuickRotator is a helper class for rotating a single selected entity in the LEVEL_EDITOR.
    It triggers the rotation gizmo (Y-axis only) when the 'r' key is pressed.

    Attributes:
        target_entity (Entity): The currently selected entity for rotation, if any.
    """

    def __init__(self):
        """
        Initializes the QuickRotator, attaching it to the LEVEL_EDITOR.
        """
        super().__init__(parent=LEVEL_EDITOR)  # type: ignore

    def input(self, key):
        """
        Handles input keys to initiate or stop rotation.

        Args:
            key (str): The input key pressed or released.
        """
        try:
            # Abort rotation if modifier keys are held or scale key is active
            if held_keys['control'] or held_keys['shift'] or held_keys['alt'] or held_keys['s']:
                return

            # Begin rotation on 'r' key press with single or no selection
            if key == 'r' and len(LEVEL_EDITOR.selection) <= 1:  # type: ignore
                if not LEVEL_EDITOR.selection:  # type: ignore
                    # Auto-select hovered entity if nothing is selected
                    hovered = LEVEL_EDITOR.selector.get_hovered_entity()  # type: ignore
                    if hovered:
                        LEVEL_EDITOR.selection = [hovered]  # type: ignore
                        LEVEL_EDITOR.render_selection()  # type: ignore

                if not LEVEL_EDITOR.selection:  # type: ignore
                    return  # Nothing to rotate

                # Begin rotation using Y-axis subgizmo
                self.target_entity = LEVEL_EDITOR.selection[0]  # type: ignore
                LEVEL_EDITOR.rotation_gizmo.subgizmos['y'].input('left mouse down')  # type: ignore
                LEVEL_EDITOR.rotation_gizmo.subgizmos['y'].start_dragging()  # type: ignore

            # Stop rotation on 'r up'
            elif key == 'r up' and hasattr(self, 'target_entity') and self.target_entity:
                # Simulate mouse release for the rotation gizmo
                LEVEL_EDITOR.rotation_gizmo.subgizmos['y'].input('left mouse up')  # type: ignore
                LEVEL_EDITOR.rotation_gizmo.subgizmos['y'].drop()  # type: ignore

                # Clear selection after rotation
                LEVEL_EDITOR.selection.clear()  # type: ignore
                LEVEL_EDITOR.render_selection()  # type: ignore
                self.target_entity = None

        except Exception as e:
            print(f"[QuickRotator] Error in input: {e}")

    def update(self):
        """
        Called every frame. Ensures the gizmo updates its position if the user is rotating.
        """
        try:
            if held_keys['r'] and not held_keys['control'] and not held_keys['shift'] and mouse.velocity != Vec3(0, 0, 0):
                # Update gizmo position only if the mouse is moving while rotating
                LEVEL_EDITOR.render_selection(update_gizmo_position=False)  # type: ignore
        except Exception as e:
            print(f"[QuickRotator] Error in update: {e}")


class RotateRelativeToView(Entity):
    """
    A helper class that allows rotating an entity relative to the camera's view
    using mouse movement when the 'T' key is held. Intended to be used in a level editor.

    Attributes:
        _rotation_helper (Entity): A static helper entity that acts as a temporary parent
                                   to apply relative rotation.
        sensitivity (Vec2): Controls how sensitive the rotation is to mouse movement.
    """
    
    _rotation_helper = Entity(name='RotateRelativeToView_rotation_helper', add_to_scene_entities=False)
    sensitivity = Vec2(200, 200)

    def __init__(self, **kwargs):
        """
        Initialize the RotateRelativeToView component and attach it to the level editor.
        """
        super().__init__(parent=LEVEL_EDITOR, **kwargs)  # Attach this to the LEVEL_EDITOR  # type: ignore

    def input(self, key):
        """
        Handle input events related to rotation.

        Pressing 'T' starts the rotation process if one entity is selected or hovered.
        Releasing 'T' finalizes the rotation and resets the selection.

        Args:
            key (str): The input key event.
        """
        # Ignore rotation input if any modifier or other conflicting keys are held
        if held_keys['control'] or held_keys['shift'] or held_keys['alt'] or held_keys['s'] or held_keys['r']:
            return

        if key == 't':
            # Prevent multi-selection from being rotated simultaneously
            if len(LEVEL_EDITOR.selection) > 1:  # type: ignore
                return

            # If nothing is selected, try selecting the currently hovered entity
            if not LEVEL_EDITOR.selection:  # type: ignore
                hovered_entity = LEVEL_EDITOR.selector.get_hovered_entity()  # type: ignore
                if hovered_entity:
                    LEVEL_EDITOR.selection = [hovered_entity]  # type: ignore
                    LEVEL_EDITOR.render_selection()  # type: ignore

            # If selection still empty, exit
            if not LEVEL_EDITOR.selection:  # type: ignore
                return

            # Begin rotation setup
            try:
                self.target_entity = LEVEL_EDITOR.selection[0]  # type: ignore

                # Place the rotation helper at the selected entity's position
                __class__._rotation_helper.world_parent = scene
                __class__._rotation_helper.position = self.target_entity.world_position
                __class__._rotation_helper.rotation = Vec3(0, 0, 0)

                # Store original state
                self._entity_original_parent = self.target_entity.parent
                self._entity_original_rotation = self.target_entity.world_rotation

                # Parent entity to rotation helper to enable relative rotation
                self.target_entity.world_parent = __class__._rotation_helper

                # Store initial mouse position
                self._mouse_start_x = mouse.x
                self._mouse_start_y = mouse.y
            except Exception as e:
                print(f"[RotateRelativeToView] Error during rotation start: {e}")

        elif key == 't up' and hasattr(self, 'target_entity') and self.target_entity:
            # Finish rotation and restore original state
            try:
                self.target_entity.world_parent = self._entity_original_parent
                LEVEL_EDITOR.selection.clear()  # type: ignore
                LEVEL_EDITOR.render_selection()  # type: ignore

                # Reset state
                self.target_entity = None
                self.x_mov = 0
                self.y_mov = 0
            except Exception as e:
                print(f"[RotateRelativeToView] Error during rotation end: {e}")

    def update(self):
        """
        Called every frame. If the entity is currently being rotated, apply the rotation
        based on mouse movement and sensitivity settings.
        """
        # If an entity is actively selected and 'T' is held, apply rotation
        if hasattr(self, 'target_entity') and self.target_entity and held_keys['t']:
            try:
                # Adjust rotation helper's orientation based on mouse velocity
                __class__._rotation_helper.rotation_y -= mouse.velocity[0] * __class__.sensitivity.x / camera.aspect_ratio
                __class__._rotation_helper.rotation_x += mouse.velocity[1] * __class__.sensitivity.y
            except Exception as e:
                print(f"[RotateRelativeToView] Error during update: {e}")


class Selector(Entity):
    """
    Selector component responsible for handling entity selection logic
    in the level editor using mouse and keyboard inputs.
    """

    def __init__(self):
        """
        Initializes the selector and attaches it to the level editor.
        """
        super().__init__(parent=LEVEL_EDITOR)  # type: ignore

    def input(self, key):
        """
        Handles input for selecting, deselecting, and toggling visibility of selection aids.

        Args:
            key (str): The key event input.
        """
        try:
            # Left click down event
            if key == 'left mouse down':
                # Ignore clicks on hovered entities (e.g., UI elements or other overlays)
                if mouse.hovered_entity:
                    return

                clicked_entity = self.get_hovered_entity()

                if clicked_entity in LEVEL_EDITOR.entities and not held_keys['alt']:  # type: ignore
                    if held_keys['shift']:
                        # Multi-select: add to selection
                        if clicked_entity not in LEVEL_EDITOR.selection:  # type: ignore
                            LEVEL_EDITOR.selection.append(clicked_entity)  # type: ignore
                    else:
                        # Single-select: overwrite current selection
                        LEVEL_EDITOR.selection = [clicked_entity]  # type: ignore

                # Alt + click: remove from selection
                if held_keys['alt'] and clicked_entity in LEVEL_EDITOR.selection:  # type: ignore
                    LEVEL_EDITOR.selection.remove(clicked_entity)  # type: ignore

                # Clicked empty space without shift/alt: clear selection
                if not clicked_entity and not held_keys['shift'] and not held_keys['alt']:
                    LEVEL_EDITOR.selection.clear()  # type: ignore

                # Update visual selection state
                LEVEL_EDITOR.render_selection()  # type: ignore

            # Ctrl + A: select all entities
            if held_keys['control'] and key == 'a':
                LEVEL_EDITOR.selection = [e for e in LEVEL_EDITOR.entities]  # type: ignore
                LEVEL_EDITOR.render_selection()  # type: ignore

            # Press 'H': toggle point renderer visibility
            elif key == 'h':
                LEVEL_EDITOR.point_renderer.enabled = not LEVEL_EDITOR.point_renderer.enabled  # type: ignore

            # Left click release: enable gizmo only if something is selected
            if key == 'left mouse up':
                LEVEL_EDITOR.gizmo.enabled = bool(LEVEL_EDITOR.selection)  # type: ignore

        except Exception as e:
            print(f"[Selector.input] Error handling input '{key}': {e}")

    def get_hovered_entity(self):
        """
        Tries to determine the best candidate entity under the mouse cursor,
        using screen position and 3D collision data.

        Returns:
            Entity or None: The most relevant hovered entity or None.
        """
        try:
            # Filter out None values from the entity list
            LEVEL_EDITOR.entities = [e for e in LEVEL_EDITOR.entities if e]  # type: ignore

            # Find entities close to the cursor that are selectable and not collidable
            entities_in_range = [
                (distance_2d(e.screen_position, mouse.position), e)
                for e in LEVEL_EDITOR.entities  # type: ignore
                if e and e.selectable and not e.collider  # type: ignore
            ]
            # Filter to those within a small screen-space distance
            entities_in_range = [e for e in entities_in_range if e[0] < .03]
            entities_in_range.sort()

            # Return closest match (2D proximity-based)
            if entities_in_range:
                return entities_in_range[0][1]

            # If none found, try using collision-based hover detection
            for e in LEVEL_EDITOR.entities:  # type: ignore
                if not hasattr(e, 'is_gizmo'):  # Ignore gizmo tools
                    setattr(e, 'collision', True)  # Enable collision temporarily

            mouse.update()  # Update mouse state to reflect new collisions

            if mouse.hovered_entity in LEVEL_EDITOR.entities:  # type: ignore
                # Reset collisions and return the hovered entity
                for e in LEVEL_EDITOR.entities:  # type: ignore
                    if not hasattr(e, 'is_gizmo'):
                        setattr(e, 'collision', False)  # Disable collision again
                return mouse.hovered_entity

            # Cleanup: ensure collisions are reset even if nothing found
            for e in LEVEL_EDITOR.entities:  # type: ignore
                if not hasattr(e, 'is_gizmo'):
                    setattr(e, 'collision', False)

        except Exception as e:
            print(f"[Selector.get_hovered_entity] Error detecting hovered entity: {e}")


class SelectionBox(Entity):
    """
    UI-based rectangular selection tool used to select multiple entities
    by dragging a box over them within the level editor interface.
    """

    def __init__(self, **kwargs):
        """
        Initialize the SelectionBox entity.

        Args:
            **kwargs: Additional keyword arguments for the base Entity.
        """
        super().__init__(parent=LEVEL_EDITOR.ui, visible=False, **kwargs)  # Attach to UI layer # type: ignore

        # --- Dynamic scaling attributes ---
        self._init_w, self._init_h = window.size
        h = self._init_h or 1
        # Set your desired pixel thickness for the selection box border, e.g. 2px:
        self._base_thickness = (2 / h) * 2
        self.model.thickness = self._base_thickness
        # ----------------------------------

    def input(self, key):
        """
        Handles input for starting and ending the box selection.

        Args:
            key (str): The input event key.
        """
        try:
            if key == 'left mouse down':
                # Ignore box select if clicking a hovered (already selected) entity or gizmo
                if mouse.hovered_entity and mouse.hovered_entity not in LEVEL_EDITOR.selection:  # type: ignore
                    return

                # Initialize selection box at current mouse position
                self.position = mouse.position
                self.scale = .001  # Start tiny
                self.visible = True
                self.mode = 'new'  # Default mode

                # Check for selection modifier keys
                if held_keys['shift']:
                    self.mode = 'add'
                if held_keys['alt']:
                    self.mode = 'subtract'

            if key == 'left mouse up' and self.visible:
                self.visible = False  # Hide selection box

                # Normalize scale and position for negative drag directions
                if self.scale_x < 0:
                    self.x += self.scale_x
                    self.scale_x = abs(self.scale_x)
                if self.scale_y < 0:
                    self.y += self.scale_y
                    self.scale_y = abs(self.scale_y)

                # If the box is too small or movement is overridden, cancel selection
                if self.scale_x < .01 or self.scale_y < .01 or held_keys['w']:
                    return

                # Clear previous selection if not adding or subtracting
                if self.mode == 'new':
                    LEVEL_EDITOR.selection.clear()  # type: ignore

                # Loop over all entities and determine which are inside the selection box
                for e in LEVEL_EDITOR.entities:  # type: ignore
                    if not e.selectable:
                        continue

                    pos = e.screen_position
                    # Check if the entity is within box bounds
                    if (self.x < pos.x < self.x + abs(self.scale_x) and
                        self.y < pos.y < self.y + abs(self.scale_y)):

                        if self.mode in ('add', 'new') and e not in LEVEL_EDITOR.selection:  # type: ignore
                            LEVEL_EDITOR.selection.append(e)  # type: ignore
                        elif self.mode == 'subtract' and e in LEVEL_EDITOR.selection:  # type: ignore
                            LEVEL_EDITOR.selection.remove(e)  # type: ignore

                LEVEL_EDITOR.render_selection()  # type: ignore
                self.mode = 'new'  # Reset mode

        except Exception as e:
            print(f"[SelectionBox.input] Error processing input '{key}': {e}")

    def update(self):
        """
        Called every frame. Updates the dimensions of the selection box
        as the mouse is dragged while holding the left button.
        """
        try:
            # Only update if left mouse is being held
            if mouse.left:
                # Skip if mouse hasn't moved
                if mouse.x == mouse.start_x and mouse.y == mouse.start_y:
                    return

                # Update the selection box dimensions based on current mouse position
                self.scale_x = mouse.x - self.x
                self.scale_y = mouse.y - self.y

            # --- Dynamic scaling for border thickness ---
            cur_w, _ = window.size
            ratio = cur_w / (self._init_w or cur_w)
            self.model.thickness = self._base_thickness * ratio
            # --------------------------------------------

        except Exception as e:
            print(f"[SelectionBox.update] Error during update: {e}")


class WhiteCube(Entity):
    """
    A specialized Entity representing a white cube with predefined
    visual and physical properties such as model, shader, texture, and collider.

    Attributes:
        default_values (dict): A merged dictionary containing default
                               properties for the white cube entity.
    """

    # Merge the default Entity values with custom defaults for WhiteCube
    default_values = Entity.default_values | dict(
        model='cube',
        shader='lit_with_shadows_shader',
        texture='white_cube',
        collider='box',
        name='cube'
    )

    def __init__(self, **kwargs):
        """
        Initialize the WhiteCube with default properties overridden by any user-provided kwargs.

        Args:
            **kwargs: Additional or overriding attributes to apply to the entity.
        """
        # Pass a combined dictionary of default and user-defined values to the Entity constructor
        super().__init__(**__class__.default_values | kwargs)

    def __deepcopy__(self, memo):
        """
        Provide a custom deep copy behavior by evaluating the repr of the object.

        Args:
            memo (dict): The memoization dictionary for deepcopy.

        Returns:
            WhiteCube: A new instance of WhiteCube created from its repr string.
        """
        try:
            return eval(repr(self))
        except Exception as e:
            print(f"[WhiteCube.__deepcopy__] Error during deepcopy: {e}")
            return None


class ClassSpawner(Entity):
    """
    A prefab entity that spawns another entity of a specified class when the game starts (on `start()`),
    and destroys it on stop. Used in the level editor to preview or instantiate specific classes.

    Attributes:
        default_values (dict): Default configuration including a placeholder `class_to_spawn`,
                               a wireframe model, blue color, and entity name.
        class_instance (Entity or None): Holds the spawned instance if one is created.
    """

    # Combine base Entity defaults with custom defaults for this spawner
    default_values = Entity.default_values | dict(
        class_to_spawn='',
        model='wireframe_cube',
        color=color.blue,
        name='ClassSpawner'
    )

    def __init__(self, **kwargs):
        """
        Initialize the ClassSpawner with merged default and provided properties.

        Args:
            **kwargs: Attributes that override the defaults.
        """
        super().__init__(**__class__.default_values | kwargs)
        self.class_instance = None  # Placeholder for the runtime-spawned instance

    def draw_inspector(self):
        """
        Draws an inspector UI field to allow setting the class to spawn.

        Returns:
            dict: A dictionary specifying 'class_to_spawn' should accept a class type.
        """
        return {'class_to_spawn': type}

    def start(self):
        """
        Called when the game starts. Spawns the selected class (if valid) using the current world transform.
        Disables the spawner itself to avoid interaction in play mode.
        """
        self.enabled = False  # Prevent interaction during play mode

        if self.class_to_spawn not in LEVEL_EDITOR.class_menu.available_classes:  # type: ignore
            print_warning('Class to spawn not found in LEVEL_EDITOR.class_menu.available_classes:', self.class_to_spawn)  # type: ignore
            return

        if self.class_to_spawn and self.class_to_spawn != 'None':
            print('spawn class', self.class_to_spawn)
            try:
                # Spawn the class using its world transform and avoid adding to scene entities list
                self.class_instance = LEVEL_EDITOR.class_menu.available_classes[self.class_to_spawn](  # type: ignore
                    world_transform=self.world_transform,
                    add_to_scene_entities=False
                )  # type: ignore
            except Exception as e:
                print(f"[ClassSpawner.start] Failed to instantiate class '{self.class_to_spawn}': {e}")

    def stop(self):
        """
        Called when the game stops. Destroys the runtime-spawned instance (if any) and re-enables the spawner.
        """
        if self.class_instance:
            try:
                destroy(self.class_instance)
            except Exception as e:
                print(f"[ClassSpawner.stop] Error destroying instance: {e}")
            self.class_instance = None

        self.enabled = True  # Re-enable after stop

    def __deepcopy__(self, memo):
        """
        Custom deep copy implementation using repr() and eval().
        Returns:
            A new ClassSpawner instance.
        """
        try:
            return eval(repr(self))
        except Exception as e:
            print(f"[ClassSpawner.__deepcopy__] Error during deepcopy: {e}")
            return None


class TriplanarCube(Entity):
    """
    A cube entity using triplanar mapping shader for texture projection.
    Automatically sets a side texture input on creation.

    Attributes:
        default_values (dict): Default configuration values including model, shader, texture,
                               collider, and name for the entity.
    """

    # Merge base Entity defaults with custom settings for this triplanar cube
    default_values = Entity.default_values | dict(
        model='cube',
        shader='triplanar_shader',
        texture='white_cube',
        collider='box',
        name='cube'
    )

    def __init__(self, **kwargs):
        """
        Initialize the TriplanarCube with the merged default values and any user-provided overrides.
        Also sets a shader input for triplanar side texture.

        Args:
            **kwargs: Additional entity properties to override the defaults.
        """
        super().__init__(**__class__.default_values | kwargs)
        try:
            # Set a texture input named 'side_texture' used by the triplanar shader
            self.set_shader_input('side_texture', load_texture('brick'))
        except Exception as e:
            print(f"[TriplanarCube.__init__] Error setting shader input: {e}")

    def __deepcopy__(self, memo):
        """
        Custom deep copy implementation that evaluates the result of repr(self).
        Used to clone this entity.

        Args:
            memo (dict): Deepcopy memoization dictionary.

        Returns:
            TriplanarCube: A new instance of TriplanarCube (or None on error).
        """
        try:
            return eval(repr(self))
        except Exception as e:
            print(f"[TriplanarCube.__deepcopy__] Error during deepcopy: {e}")
            return None


class Pyramid(Entity):
    """
    A simple pyramid-shaped entity, created using a Cone with 4 sides to simulate a pyramid.
    Applies default properties such as a brick texture and custom name.

    Attributes:
        default_values (dict): Default values including the name, model (as Cone with 4 sides),
                               and texture to use for the pyramid entity.
    """

    # Combine base Entity defaults with pyramid-specific defaults
    default_values = Entity.default_values | dict(
        name='pyramid',
        model=Cone(4),  # Create a 4-sided cone to simulate a pyramid
        texture='brick'
    )

    def __init__(self, **kwargs):
        """
        Initialize the Pyramid with default properties merged with any user-provided overrides.

        Args:
            **kwargs: Additional or overriding attributes for the entity.
        """
        super().__init__(**__class__.default_values | kwargs)

    def __deepcopy__(self, memo):
        """
        Custom deep copy method using eval(repr(self)) for duplicating this entity.

        Args:
            memo (dict): Dictionary used by deepcopy to avoid duplicate copies of the same object.

        Returns:
            Pyramid: A new instance created by evaluating its repr, or None if it fails.
        """
        try:
            return eval(repr(self))
        except Exception as e:
            print(f"[Pyramid.__deepcopy__] Error during deepcopy: {e}")
            return None


class Rock(Entity):
    """
    A simple rock entity using a procedural rock model, with default collider and color.
    Designed for use in environments where varied terrain or natural objects are needed.

    Attributes:
        default_values (dict): Combined defaults including name, model, collider type, and color.
        gizmo_color (color): Color used for rendering gizmos in the editor.
    """

    # Merge base Entity defaults with rock-specific configuration
    default_values = Entity.default_values | dict(
        name='rock',
        model='procedural_rock_0',
        collider='box',
        color=hsv(20, .2, .45)
    )

    # Used by editor tools to render outlines or selection gizmos
    gizmo_color = color.brown

    def __init__(self, **kwargs):
        """
        Initialize the Rock entity with default or overridden values.

        Args:
            **kwargs: Additional attributes to override default properties.
        """
        super().__init__(**__class__.default_values | kwargs)

    def __deepcopy__(self, memo):
        """
        Custom deep copy implementation using eval(repr(self)).
        Useful for duplicating the entity during editor operations.

        Args:
            memo (dict): Deep copy memo dictionary.

        Returns:
            Rock: A new instance of the Rock entity (or None on error).
        """
        try:
            return eval(repr(self))
        except Exception as e:
            print(f"[Rock.__deepcopy__] Error during deepcopy: {e}")
            return None


class Spawner(Entity):
    """
    A utility class in the level editor for spawning prefab entities.
    Allows spawning via hotkeys and displays a UI menu of available prefabs.

    Attributes:
        target (Entity): The currently spawning entity, if any.
        ui (Entity): Container for the prefab spawn buttons.
    """

    def __init__(self):
        """Initialize the Spawner UI and prefab menu."""
        super().__init__(parent=LEVEL_EDITOR)  # type: ignore
        self.target = None
        self.ui = Entity(parent=LEVEL_EDITOR.ui, position=window.bottom)  # type: ignore

        # --- Add this block ---
        self.ui._init_w, self.ui._init_h = window.size
        # ----------------------

        self.update_menu()

    def update_menu(self):
        """
        Clear the current UI and generate buttons for all available prefabs.
        This includes both built-in and custom prefabs.
        """
        # Clear any existing buttons from the UI
        [destroy(e) for e in self.ui.children]

        # Import all classes from the prefab folder
        import_all_classes(LEVEL_EDITOR.prefab_folder, debug=True)  # type: ignore

        # Generate buttons for each prefab
        for i, prefab in enumerate(LEVEL_EDITOR.built_in_prefabs + LEVEL_EDITOR.prefabs):  # type: ignore
            button = Button(
                parent=self.ui,
                scale=.075 / 2,
                text=' ',
                text_size=.5,
                on_click=Func(self.spawn_entity, prefab)
            )

            # ...inside the for loop that creates each prefab button...
            button._init_w, button._init_h = window.size
            h = button._init_h or 1
            # Set your desired pixel size for the button, e.g. 40px:
            button._base_ui_scale = (30 / h) * 2
            button.scale = button._base_ui_scale

            if hasattr(prefab, 'icon'):
                button.icon = prefab.icon
            else:
                # Fallback text display if icon is unavailable
                button.text = '\n'.join(chunk_list(prefab.__name__, 5))

        # Arrange buttons in a grid layout
        grid_layout(self.ui.children, origin=(0, -0.5), spacing=(.005, 0), max_x=32)

    def input(self, key):
        """
        Handles key-based input for spawning and placing prefabs.

        Supported keys:
            'i'      : Start spawning entity under mouse.
            'i up'   : Drop the spawned entity.
            'left mouse up' : Drop entity if dragging.
        """
        if key == 'i':
            mouse.traverse_target = LEVEL_EDITOR.grid  # type: ignore
            self.spawn_entity()

        elif key == 'i up' and self.target:
            self.drop_entity()
            mouse.traverse_target = scene

        elif self.target and key == 'left mouse up':
            self.drop_entity()

    def spawn_entity(self, _class=Entity):
        """
        Instantiates an entity of the specified class at the current mouse world position.

        Args:
            _class (type): The class to instantiate (defaults to base Entity).
        """
        if not LEVEL_EDITOR.current_scene:  # type: ignore
            print_on_screen('<red>select a scene first', position=(0, 0), origin=(0, 0))
            return

        LEVEL_EDITOR.grid.enabled = True  # type: ignore

        # Spawn the target entity at the mouse position
        position = mouse.world_point if mouse.world_point is not None else Vec3(0,0,0)
        self.target = _class(
            parent=LEVEL_EDITOR.current_scene.scene_parent,  # <-- add this!  # type: ignore
            position=position,
            original_parent=LEVEL_EDITOR,  # type: ignore
            selectable=True,
            collision=False
        )  # type: ignore

        # Set default collider type if not defined
        if not hasattr(self.target, 'collider_type'):
            self.target.collider_type = 'None'

        # Assign default shader if none is set
        if not self.target.shader:
            self.target.shader = lit_with_shadows_shader

        # Add entity to the current scene's entity list
        LEVEL_EDITOR.current_scene.entities.append(self.target)  # type: ignore
        LEVEL_EDITOR.render_selection()  # type: ignore

    def drop_entity(self):
        """
        Finalizes placement of the spawned entity and records the operation for undo.
        """
        try:
            # Record undo action for dropping entity
            LEVEL_EDITOR.current_scene.undo.record_undo(  # type: ignore
                ('delete entities',
                 [LEVEL_EDITOR.current_scene.entities.index(self.target)],  # type: ignore
                 [repr(self.target)])
            )  # type: ignore

            LEVEL_EDITOR.selection = [self.target]  # type: ignore
            self.target = None
            LEVEL_EDITOR.grid.enabled = False  # type: ignore

        except Exception as e:
            print(f"[Spawner.drop_entity] Error while finalizing entity placement: {e}")

    def update(self):
        """
        Update method for real-time entity positioning while dragging.
        Allows live positioning of the spawned entity at the mouse world point.
        """
        if mouse.world_point and self.target:
            if held_keys['n'] or mouse.left:
                self.target.position = mouse.world_point

        # --- Add this block to define ratio ---
        cur_w, _ = window.size
        ratio = cur_w / (self.ui._init_w or cur_w)
        # ---------------------------------------

        # Dynamically scale all prefab buttons
        for button in self.ui.children:
            if hasattr(button, '_base_ui_scale'):
                button.scale = button._base_ui_scale * ratio


class Deleter(Entity):
    """
    A class that handles the deletion of selected entities in the level editor.
    Supports deleting entities using keyboard shortcuts like 'delete' or 'Ctrl + X'.
    """

    def __init__(self):
        """
        Initializes the Deleter class and sets up keyboard shortcuts.
        """
        super().__init__(parent=LEVEL_EDITOR)  # type: ignore
        self.shortcuts = ['delete', 'control+x']  # Supported shortcuts for deletion

    def input(self, key):
        """
        Handles input keys for deleting selected entities.

        Args:
            key (str): The key that was pressed.
        """
        combined_key = input_handler.get_combined_key(key)  # Get combined key (e.g., 'control+x')
        
        # If there is a selection and the key matches a delete shortcut, delete the selected entities
        if LEVEL_EDITOR.selection and combined_key in self.shortcuts:  # type: ignore
            self.delete_selected()

    def delete_selected(self):
        """
        Deletes the currently selected entities from the scene.
        Also records the undo action for restoring the deleted entities.
        """
        try:
            # Record undo action so we can restore the entities if needed
            LEVEL_EDITOR.current_scene.undo.record_undo(  # type: ignore
                ('restore entities',
                 [LEVEL_EDITOR.entities.index(e) for e in LEVEL_EDITOR.selection],  # type: ignore
                 [repr(e) for e in LEVEL_EDITOR.selection])  # type: ignore
            )

            # Track the number of entities before deletion for debugging
            before = len(LEVEL_EDITOR.entities)  # type: ignore

            # Remove the selected entities from the level editor's entity list
            for e in LEVEL_EDITOR.selection:  # type: ignore
                if e in LEVEL_EDITOR.entities:  # type: ignore
                    LEVEL_EDITOR.entities.remove(e)  # type: ignore

            # Update the parent of all cubes (assumed logic) and destroy the selected entities
            [setattr(e, 'parent', LEVEL_EDITOR) for e in LEVEL_EDITOR.cubes]  # type: ignore
            [destroy(e) for e in LEVEL_EDITOR.selection]  # type: ignore

            # Clear the selection and render the updated selection
            LEVEL_EDITOR.selection.clear()  # type: ignore
            LEVEL_EDITOR.render_selection()  # type: ignore

            # Optionally, log how many entities were deleted for debugging
            print(f"Deleted {before - len(LEVEL_EDITOR.entities)} entities.")  # type: ignore
        
        except Exception as e:
            # In case of any error during deletion, log it for debugging purposes
            print(f"[Deleter.delete_selected] Error during deletion: {e}")


class Grouper(Entity):
    """
    A class that handles grouping of selected entities in the level editor.
    Allows multiple entities to be grouped together by pressing 'Ctrl + G'.
    """

    def __init__(self):
        """
        Initializes the Grouper class, setting the parent entity to LEVEL_EDITOR.
        """
        super().__init__(parent=LEVEL_EDITOR)  # type: ignore

    def input(self, key):
        """
        Handles input keys for grouping selected entities.

        Args:
            key (str): The key that was pressed.
        """
        try:
            # Check if 'Ctrl' is held and the 'G' key is pressed, and if there are selected entities
            if held_keys['control'] and key == 'g' and LEVEL_EDITOR.selection:  # type: ignore
                # Create a new group entity
                group_entity = Entity(parent=LEVEL_EDITOR.current_scene.scene_parent, name='[group]', selectable=True)  # type: ignore
                LEVEL_EDITOR.entities.append(group_entity)  # type: ignore

                # Get the parents of the selected entities
                parents = tuple(set([e.parent for e in LEVEL_EDITOR.selection]))  # type: ignore
                
                # If all selected entities have the same parent, set the group's parent to that parent
                if len(parents) == 1:
                    group_entity.world_parent = parents[0]

                # Calculate the average position of the selected entities to place the group at that position
                group_entity.world_position = sum([e.world_position for e in LEVEL_EDITOR.selection]) / len(LEVEL_EDITOR.selection)  # type: ignore
                
                # Set the group entity as the parent for all selected entities
                for e in LEVEL_EDITOR.selection:  # type: ignore
                    e.world_parent = group_entity

                # Update the selection to only include the newly created group entity
                LEVEL_EDITOR.selection = [group_entity, ]  # type: ignore
                LEVEL_EDITOR.render_selection()  # type: ignore

        except Exception as e:
            # In case of any error, log the error message for debugging purposes
            print(f"[Grouper.input] Error during grouping: {e}")


class PointOfViewSelector(Entity):
    """
    A class that allows the user to quickly change the camera's point of view
    in the level editor using mouse clicks or specific keyboard shortcuts.
    """

    def __init__(self, **kwargs):
        """
        Initializes the PointOfViewSelector, placing it in the top-right corner of the screen.

        Args:
            kwargs: Additional keyword arguments to customize the PointOfViewSelector.
        """
        super().__init__(parent=LEVEL_EDITOR.ui, model='cube', collider='box', texture='white_cube', scale=.05, position=window.top_right-Vec2(.1, .05))  # type: ignore
        self.front_text = Text(parent=self, text='front', z=-.5, scale=10, origin=(0, 0), color=color.azure)

        # Apply any additional attributes passed through kwargs
        for key, value in kwargs.items():
            setattr(self, key, value)

    def on_click(self):
        """
        Handles camera rotation when clicking on different faces of the selector.
        The camera rotates to various predefined orientations depending on the selected face.
        """
        try:
            # Determine the new camera rotation based on the selected mouse face
            if mouse.normal == Vec3(0, 0, -1):   # Front view
                LEVEL_EDITOR.editor_camera.animate_rotation((0, 0, 0))  # type: ignore
            elif mouse.normal == Vec3(0, 0, 1):  # Back view
                LEVEL_EDITOR.editor_camera.animate_rotation((0, 180, 0))  # type: ignore
            elif mouse.normal == Vec3(1, 0, 0):  # Right view
                LEVEL_EDITOR.editor_camera.animate_rotation((0, 90, 0))  # type: ignore
            elif mouse.normal == Vec3(-1, 0, 0): # Left view
                LEVEL_EDITOR.editor_camera.animate_rotation((0, -90, 0))  # type: ignore
            elif mouse.normal == Vec3(0, 1, 0):  # Top view
                LEVEL_EDITOR.editor_camera.animate_rotation((90, 0, 0))  # type: ignore
            elif mouse.normal == Vec3(0, -1, 0): # Bottom view
                LEVEL_EDITOR.editor_camera.animate_rotation((-90, 0, 0))  # type: ignore

        except Exception as e:
            print(f"[PointOfViewSelector.on_click] Error during camera rotation: {e}")

    def update(self):
        """
        Updates the rotation of the PointOfViewSelector to match the camera's rotation.
        This keeps the selector aligned with the current camera view.
        """
        try:
            self.rotation = -LEVEL_EDITOR.editor_camera.rotation  # type: ignore
        except Exception as e:
            print(f"[PointOfViewSelector.update] Error while updating rotation: {e}")

    def input(self, key):
        """
        Handles user input for rotating the camera using keyboard shortcuts.

        Args:
            key (str): The key that was pressed.
        """
        try:
            # If the shift key is held, check for camera rotation shortcuts
            if held_keys['shift']:
                if key == '1':  # Front view
                    LEVEL_EDITOR.editor_camera.animate_rotation((0, 0, 0))  # type: ignore
                elif key == '3':  # Right view
                    LEVEL_EDITOR.editor_camera.animate_rotation((0, 90, 0))  # type: ignore
                elif key == '7':  # Top view
                    LEVEL_EDITOR.editor_camera.animate_rotation((90, 0, 0))  # type: ignore
                elif key == '5':  # Toggle orthographic view
                    camera.orthographic = not camera.orthographic

        except Exception as e:
            print(f"[PointOfViewSelector.input] Error during input handling: {e}")


# class PaintBucket(Entity):
#     def input(self, key):
#         if held_keys['alt'] and key == 'c' and mouse.hovered_entity:
#             self.color = mouse.hovered_entity.color

class Copier(Entity):
    """
    A class that enables copying and pasting of selected entities within the level editor.
    It works by serializing selected entities into a code format, copying it to the clipboard,
    and then pasting the entities back into the scene.

    Attributes:
        prefix (str): A string used to prefix the copied data for easy identification.
    """
    prefix = 'ursina_editor_copy_data:```py\n'

    def input(self, key):
        """
        Handles the input for copying and pasting selected entities using keyboard shortcuts.

        Args:
            key (str): The key that was pressed.
        """
        try:
            if held_keys['control'] and key == 'c':
                if LEVEL_EDITOR.selection:  # Check if there are any selected entities  # type: ignore
                    code = __class__.prefix
                    for e in LEVEL_EDITOR.selection:  # Loop through selected entities  # type: ignore
                        entity_repr = repr(e)
                        
                        # Ensure 'collider_type' is included for entities that have it
                        if not 'collider_type=' in entity_repr and hasattr(e, 'collider_type'):
                            entity_repr = f'{entity_repr[:-1]}collider_type=\'{e.collider_type}\')'
                        
                        code += entity_repr + '\n'

                    pyperclip.copy(f'{code}\n```')  # Copy the serialized code to the clipboard

            if held_keys['control'] and key == 'v':
                value = pyperclip.paste()  # Paste the copied content from clipboard
                
                # If the content is in the expected copied format, process it
                if value.startswith('ursina_editor_copy_data:```py\n') and value.endswith('\n```'):
                    cleaned_code = value[len(__class__.prefix):-4].strip().split('\n')
                    clones = []

                    # Loop through the cleaned code and instantiate each entity from the copied representation
                    for line in cleaned_code:
                        instance = eval(line)
                        instance.selectable = True  # Make the cloned entity selectable
                        LEVEL_EDITOR.current_scene.entities.append(instance)  # Add to the scene  # type: ignore
                        clones.append(instance)

                    LEVEL_EDITOR.entities.extend(clones)  # Add cloned entities to global entity list  # type: ignore
                    LEVEL_EDITOR.selection = clones  # Set the clones as the new selection  # type: ignore

                    # Record undo action for deleting the cloned entities
                    LEVEL_EDITOR.current_scene.undo.record_undo((  # type: ignore
                        'delete entities',
                        [LEVEL_EDITOR.entities.index(en) for en in clones],  # type: ignore
                        [repr(e) for e in clones]
                    ))

                    print('------------------------')  # Just a separator for the console logs
                    LEVEL_EDITOR.render_selection()  # Re-render the selection in the editor  # type: ignore

        except Exception as e:
            print(f"[Copier.input] Error during copy/paste operation: {e}")


class LevelMenu(Entity):
    """
    A class that handles the level menu interface for the level editor. 
    It allows the user to navigate between scenes, load new scenes, and interact with the scene grid.

    Attributes:
        menu (Entity): The base menu entity containing the grid and UI elements.
        content_renderer (Entity): An entity used for rendering the scene grid and content.
        cursor (Entity): The cursor that follows the user's mouse within the menu.
        current_scene_indicator (Entity): An indicator to show the current scene's position in the grid.
        current_scene_label (Text): A label displaying the current scene's name.
    """

    def __init__(self, **kwargs):
        """
        Initialize the LevelMenu with the menu structure and setup for the scene grid.
        """
        super().__init__(parent=LEVEL_EDITOR)  # type: ignore

        # Base menu setup
        self.menu = Entity(
            parent=LEVEL_EDITOR.ui, model=Quad(radius=.05), color=color.black, scale=.2,  # type: ignore
            origin=(.5, 0), x=camera.aspect_ratio * .495, y=-.3, collider='box'  # type: ignore
        )

        # After creating self.menu in LevelMenu.__init__
        self.menu._init_w, self.menu._init_h = window.size
        h = self.menu._init_h or 1
        # Let's say you want the menu to be 300px wide and 150px tall:
        self.menu._base_ui_scale = Vec2((90 / h) * 2, (90 / h) * 2)
        self.menu.scale = self.menu._base_ui_scale

        # Grid for scene selection
        self.menu.grid = Entity(parent=self.menu, model=Grid(8, 8), z=-1, origin=self.menu.origin, color=color.dark_gray)

        # Content renderer for scene grid and cursor
        self.content_renderer = Entity(
            parent=self.menu, scale=1 / 8, position=(-1, -0.5, -1), model=Mesh(), color='#222222'
        )

        # Cursor entity
        self.cursor = Entity(parent=self.content_renderer, model='quad', color=color.lime, origin=(-.5, -.5), z=-2, alpha=.5)

        # Current scene indicator (shows current scene in the grid)
        self.current_scene_indicator = Entity(
            parent=self.content_renderer, model='circle', color=color.azure, origin=(-.5, -.5), z=-1, enabled=False
        )

        # Current scene label
        self.current_scene_label = Text(parent=self.menu, x=-1, y=-.5, text='current scene:', z=-10, scale=2.5)

        # Load available scenes
        self.load_scenes()
        self.draw()

    def load_scenes(self):
        """
        Loads the available scenes from the scene folder and updates their paths in the scene grid.
        """
        for scene_file in LEVEL_EDITOR.scene_folder.glob('*.csv'):  # type: ignore
            if '__' in scene_file.name:
                continue  # Skip internal files

            name = scene_file.stem
            if '[' in name and ']' in name:
                x, y = (int(e) for e in name.split('[')[1].split(']')[0].split(','))
                LEVEL_EDITOR.scenes[x][y].path = scene_file  # type: ignore

    def draw(self):
        """
        Draws the grid of scenes, and updates the content renderer with scene tiles.
        """
        if not hasattr(self, 'quad_vertices'):
            # Load the quad model and scale its vertices
            self.quad_vertices = load_model('quad', application.internal_models_compressed_folder, use_deepcopy=True).vertices
            self.quad_vertices = [Vec3(*e) * .75 for e in self.quad_vertices]

        # Clear existing model content
        self.content_renderer.model.clear()

        # Populate the model with scene grid vertices
        for x in range(8):
            for y in range(8):
                if LEVEL_EDITOR.scenes[x][y].path:  # type: ignore
                    self.content_renderer.model.vertices += [Vec3(*v) + Vec3(x + .5, y + .5, 0) for v in self.quad_vertices]

        self.content_renderer.model.generate()

    def update(self):
        """
        Updates the cursor's position based on the mouse's position within the menu.
        """

        # --- Dynamic scaling for menu ---
        cur_w, _ = window.size
        ratio = cur_w / (self.menu._init_w or cur_w)
        self.menu.scale = self.menu._base_ui_scale * ratio

        self.cursor.enabled = self.menu.hovered  # Show cursor only when hovering over the menu
        if self.menu.hovered:
            grid_pos = [floor((mouse.point.x + 1) * 8), floor((mouse.point.y + .5) * 8)]
            self.cursor.position = grid_pos

    def input(self, key):
        """
        Handles input events such as key presses for scene navigation and interactions.
        """
        combined_key = input_handler.get_combined_key(key)

        if combined_key == 'shift+m':
            # Toggle menu visibility with Shift+M
            self.menu.enabled = not self.menu.enabled

        if key == 'left mouse down' and self.menu.hovered:
            x, y = [int((mouse.point.x + 1) * 8), int((mouse.point.y + .5) * 8)]

            if not held_keys['shift'] and not held_keys['alt']:
                # Navigate to the clicked scene
                self.goto_scene(x, y)

            elif held_keys['shift'] and not held_keys['alt']:
                # Append the scene by loading it
                LEVEL_EDITOR.scenes[x][y].load()  # type: ignore

            elif held_keys['alt'] and not held_keys['shift']:
                # Remove the scene by unloading it
                LEVEL_EDITOR.scenes[x][y].unload()  # type: ignore

        # Hotkeys for loading adjacent scenes (WASD with Shift+Alt)
        if held_keys['shift'] and held_keys['alt'] and key in 'wasd':
            if not LEVEL_EDITOR.current_scene:  # type: ignore
                return

            coords = copy(LEVEL_EDITOR.current_scene.coordinates)  # type: ignore

            if key == 'd': coords[0] += 1
            if key == 'a': coords[0] -= 1
            if key == 'w': coords[1] += 1
            if key == 's': coords[1] -= 1

            coords[0] = clamp(coords[0], 0, 8)
            coords[1] = clamp(coords[1], 0, 8)

            self.goto_scene(coords[0], coords[1])

    def goto_scene(self, x, y):
        """
        Navigates to the specified scene coordinates and updates the scene indicator and label.
        """
        self.current_scene_indicator.enabled = True
        self.current_scene_indicator.position = (x, y)

        # Unload all scenes before loading the selected one
        [[LEVEL_EDITOR.scenes[_x][_y].unload() for _x in range(8)] for _y in range(8)]  # type: ignore
        LEVEL_EDITOR.current_scene = LEVEL_EDITOR.scenes[x][y]  # type: ignore
        loaded_scene = LEVEL_EDITOR.current_scene.load()  # type: ignore

        if loaded_scene is None:
            LEVEL_EDITOR.current_scene.scene_parent = Entity()  # type: ignore

        # Update the label to reflect the current scene
        self.current_scene_label.text = LEVEL_EDITOR.current_scene.name  # type: ignore
        self.draw()
        LEVEL_EDITOR.render_selection()  # type: ignore

        # Update the inspector and sun handler for the new scene
        LEVEL_EDITOR.inspector.update_inspector()  # type: ignore
        LEVEL_EDITOR.sun_handler.update_bounds(LEVEL_EDITOR.current_scene.scene_parent)  # type: ignore


class HierarchyList(Entity):
    """
    A class that represents a hierarchy list of entities in a scene, typically used
    for displaying and selecting entities within a level editor.

    Attributes:
        quad_model (Model): A model for rendering a quad.
        bg (Entity): The background entity for the hierarchy list.
        entity_list_text (Text): The text entity used to display entity names in the list.
        selected_renderer (Entity): The renderer used to visually indicate selected entities.
        prev_y (int): The previously selected index in the list, used for multi-selection.
        i (int): The current index in the entity list.
    """
    
    def __init__(self):
        """
        Initializes the HierarchyList object, setting up necessary components 
        like background, text, and selection renderer.
        """
        super().__init__(parent=LEVEL_EDITOR.ui, position=window.top_left + Vec2(0, -0.05))  # type: ignore
        self.quad_model = load_model('quad', application.internal_models_folder, use_deepcopy=True)
        self.bg = Entity(parent=self, model='quad', collider='box', origin=(-0.5, 0.5), color=color.black90, scale=(0.15, 10))
        self.entity_list_text = Text(font=Text.default_monospace_font, parent=self, scale=0.6, line_height=1, position=Vec2(0.005, 0), z=-2)
        self.selected_renderer = Entity(parent=self.entity_list_text, scale=(0.25, Text.size), model=Mesh(vertices=[]), color=hsv(210, 0.9, 0.6), origin=(-0.5, 0.5), x=-0.01, z=-1)
        self.selected_renderer.world_parent = self
        self.selected_renderer.z = -0.1
        self.prev_y = None
        self.i = 0

        # --- Dynamic scaling attributes ---
        self._init_w, self._init_h = window.size
        h = self._init_h or 1
        # Set your desired pixel size for the hierarchy panel, e.g. 220x500:
        self._base_ui_scale = Vec2((220 / h) * 2, (500 / h) * 2)
        self.scale = self._base_ui_scale
        # ----------------------------------

    def update(self):
        # --- Dynamic scaling for hierarchy list ---
        cur_w, _ = window.size
        ratio = cur_w / (self._init_w or cur_w)
        self.scale = self._base_ui_scale * ratio
        # ------------------------------------------
        # Scale the background and text to match the panel's scaling
        self.bg.scale = Vec2(0.15, 10) * ratio  # Adjust 0.15, 10 as needed for your design
        self.entity_list_text.scale = 0.7 * ratio  # Adjust 0.6 as needed for your design
        # Dynamically scale the selected_renderer highlight
        self.selected_renderer.scale = Vec2(0.15, Text.size) * ratio  # Adjust 0.25, Text.size as needed

    def input(self, key):
        """
        Handles user input for selecting entities using mouse clicks.
        
        Args:
            key (str): The input key (e.g., 'left mouse down', 'left mouse up').
        """
        # Handle 'left mouse down' event for entity selection
        if key == 'left mouse down' and self.bg.hovered:
            try:
                y = int(-mouse.point.y * self.bg.scale_y / Text.size / self.entity_list_text.scale_y)
                
                # Check if y is within bounds
                if y < len(LEVEL_EDITOR.entities):  # type: ignore
                    # Handle selection based on control or shift key
                    if not held_keys['control'] and not held_keys['shift']:  # select one
                        LEVEL_EDITOR.selection = [LEVEL_EDITOR.entities[self.entity_indices[y]], ]  # type: ignore
                    elif held_keys['control'] and not held_keys['shift']:  # add one
                        LEVEL_EDITOR.selection.append(LEVEL_EDITOR.entities[self.entity_indices[y]])  # type: ignore
                    elif held_keys['shift'] and self.prev_y:  # add multiple
                        from_y = min(self.prev_y, y)
                        to_y = max(self.prev_y, y)
                        for _ in range(from_y, to_y + 1):
                            LEVEL_EDITOR.selection.append(LEVEL_EDITOR.entities[self.entity_indices[_]])  # type: ignore

            except IndexError as e:
                # Error handling in case of an invalid index (e.g., out of bounds)
                print(f"Error in input selection: {e}")
            
            # Deselect all if neither control nor shift is held
            if not held_keys['control'] and not held_keys['shift']:
                LEVEL_EDITOR.selection.clear()  # type: ignore

            # Update the previous y index for multi-selection
            self.prev_y = y
            LEVEL_EDITOR.render_selection()  # type: ignore

        # Handle 'left mouse up' event to finalize selection
        if key == 'left mouse up':
            LEVEL_EDITOR.render_selection()  # type: ignore

    def draw(self, entity, indent=0):
        """
        Draws the entity's name in the hierarchy list, with the appropriate indentation 
        and selection highlighting.
        
        Args:
            entity (Entity): The entity to draw in the hierarchy.
            indent (int): The indentation level for the entity in the hierarchy.
        """
        # Check if entity exists in the level editor entities list
        if entity not in LEVEL_EDITOR.entities:  # type: ignore
            return
        
        try:
            # Update entity index for drawing
            self.entity_indices[self.i] = LEVEL_EDITOR.entities.index(entity)  # type: ignore
        except ValueError:
            # Handle case if the entity is not found in LEVEL_EDITOR.entities
            print(f"Entity {entity} not found in LEVEL_EDITOR.entities.")
            return

        # Check if the entity is selected and update the renderer accordingly
        if entity not in LEVEL_EDITOR.selection:  # type: ignore
            self._text += f'<gray>{" " * indent}{entity.name if entity.name else "Unnamed Entity"}\n'
        else:
            self.selected_renderer.model.vertices.extend([Vec3(v) - Vec3(0, self.i, 0) for v in self.quad_model.vertices])
            self._text += f'<white>{" " * indent}{entity.name}\n'

        self.i += 1

    def render_selection(self):
        """
        Renders the selected entities in the hierarchy, updating the text and renderer 
        for each entity.
        """
        self._text = ''
        self.selected_renderer.model.vertices = []
        self.entity_indices = [-1 for e in LEVEL_EDITOR.entities]  # type: ignore

        self.i = 0
        current_node = None
        
        # Early return if no valid scene exists
        if LEVEL_EDITOR.current_scene is None or LEVEL_EDITOR.current_scene.scene_parent is None:  # type: ignore
            return

        # Iterate through the descendants of the scene parent and draw each entity
        for entity in LEVEL_EDITOR.current_scene.scene_parent.get_descendants():  # type: ignore
            if hasattr(entity, 'is_gizmo') and entity.is_gizmo:
                continue  # Skip gizmo entities

            # If the entity is a direct child of the scene parent, draw it
            if entity.parent == LEVEL_EDITOR.current_scene.scene_parent:  # type: ignore
                self.draw(entity, indent=0)

        # Set the updated text in the entity list
        self.entity_list_text.text = self._text
        self.selected_renderer.model.generate()


Text.default_font = 'VeraMono.ttf'
class InspectorInputField(InputField):
    """
    A class representing an input field for an inspector in a UI, extending the base
    InputField class. This class customizes the position, scale, and color of the text field
    to better suit the inspector's UI layout.
    
    Attributes:
        highlight_color (Color): The color used for highlighting the input field.
    """
    
    def __init__(self, **kwargs):
        """
        Initializes the InspectorInputField object, configuring its position, 
        scale, color, and highlight color based on custom settings.

        Args:
            **kwargs: Additional keyword arguments passed to the parent class constructor.
        """
        # Call the parent class constructor to initialize the base InputField
        super().__init__(**kwargs)

        try:
            # Customize the position of the text field relative to its parent container
            self.text_field.x = 0.05
            self.text_field.y = -0.25
            
            # Set the world scale of the text field, adjusting it based on a factor (e.g., 0.75)
            self.text_field.world_scale = 25 * 0.75
            
            # Change the text color to a lighter gray for the text entity in the field
            self.text_field.text_entity.color = color.light_gray
            
            # Set the highlight color to a specific shade of blue (for focus/interaction)
            self.highlight_color = color._32

        except AttributeError as e:
            # Handle case where expected attributes are missing in the parent class or other initialization issues
            print(f"Error initializing InspectorInputField: {e}")
        except Exception as e:
            # Generic error handling for unforeseen issues during initialization
            print(f"Unexpected error in InspectorInputField initialization: {e}")


class InspectorButton(Button):
    """
    A class representing a customized button for the inspector in a UI, extending the base 
    Button class. This class allows further customization of the button's default appearance,
    text, and behavior for use in the inspector's UI.

    Attributes:
        defaults (dict): A dictionary containing the default properties for the button.
    """
    
    # Default properties for the button such as model, color, and text appearance.
    defaults = dict(
        model='quad', 
        origin=(-0.5, 0.5), 
        text='?', 
        text_origin=(-0.5, 0), 
        text_color=color.light_gray, 
        color=color.black90, 
        highlight_color=color._32
    )

    def __init__(self, **kwargs):
        """
        Initializes the InspectorButton object, customizing its appearance and 
        text properties based on the provided keyword arguments.

        Args:
            **kwargs: Additional keyword arguments passed to the parent class constructor.
        """
        try:
            # Merge default properties with any provided arguments to initialize the button
            kwargs = __class__.defaults | kwargs
            super().__init__(**kwargs)
            
            # Customize the position of the text entity inside the button
            self.text_entity.x = 0.025

            # Scale the text down by 75% for better fit or design consistency
            self.text_entity.scale *= 0.75

        except AttributeError as e:
            # Handle case where expected attributes or methods are missing in the parent class
            print(f"Error initializing InspectorButton: {e}")
        except Exception as e:
            # Generic error handling for unforeseen issues during initialization
            print(f"Unexpected error in InspectorButton initialization: {e}")


class ColorField(InspectorButton):
    """
    A class representing a color field button in the inspector UI, allowing the user
    to select or preview a color. The color field has a preview area where the selected
    color is shown and can be clicked to open a color menu.

    Attributes:
        attr_name (str): The name of the attribute associated with this color field (default is 'color').
        is_shader_input (bool): A flag indicating whether this field is used for shader input (default is False).
        preview (Entity): The entity representing the preview box where the selected color is displayed.
        value (Color): The current color value displayed in the preview box.
    """
    
    def __init__(self, attr_name='color', is_shader_input=False, value=color.white, **kwargs):
        """
        Initializes the ColorField object, setting the default attributes and creating a preview 
        entity for the color display.

        Args:
            attr_name (str): The name of the attribute this color field represents. Defaults to 'color'.
            is_shader_input (bool): Whether this field is used for shader input. Defaults to False.
            value (Color): The initial color value for the preview. Defaults to color.white.
            **kwargs: Additional keyword arguments passed to the parent class constructor.
        """
        try:
            # Initialize the parent class (InspectorButton) with provided arguments
            super().__init__(**kwargs)

            # Set up the attribute name and shader input flag
            self.attr_name = attr_name
            self.is_shader_input = is_shader_input

            # Create the color preview box (an entity with a quad model)
            self.preview = Entity(
                parent=self, model=Quad(aspect=2/1), scale=(0.5, 0.8), origin=(0.5, 0.5),
                x=1, z=-0.1, y=-0.05, collider='box', on_click=self.on_click
            )

            # Set the initial color value
            self.value = value

        except Exception as e:
            # Handle any initialization errors and print them for debugging
            print(f"Error initializing ColorField: {e}")

    @property
    def value(self):
        """
        Property getter for the color value of the preview entity.
        
        Returns:
            Color: The current color of the preview entity.
        """
        return self.preview.color

    @value.setter
    def value(self, value):
        """
        Property setter for the color value of the preview entity.
        
        Args:
            value (Color): The new color to set for the preview entity.
        """
        self.preview.color = value

    def on_click(self):
        """
        Event handler for when the color field is clicked. It opens the color menu 
        and positions it near the clicked color field.

        This method updates the color menu state and assigns the current color field 
        to the color menu for further interactions.
        """
        try:
            # Set the color field as the current color field in the LEVEL_EDITOR color menu
            LEVEL_EDITOR.color_menu.color_field = self  # type: ignore

            # Position the color menu relative to the current position of the color field
            LEVEL_EDITOR.color_menu.position = (  # type: ignore
                self.preview.get_position(relative_to=camera.ui).xy + Vec2(0.025, -0.01)  # type: ignore
            )

            # Change the state of the menu handler to 'color_menu' to show the color selection menu
            LEVEL_EDITOR.menu_handler.state = 'color_menu'  # type: ignore

        except Exception as e:
            # Handle any errors that might occur during the click event (e.g., issues with menu or color field)
            print(f"Error in on_click handler for ColorField: {e}")


class Inspector(Entity):
    """
    Inspector UI for editing properties of selected entities in the level editor.

    This class creates a panel within the LEVEL_EDITOR that displays various input fields
    (position, rotation, scale, name, model, texture, color, etc.) for the currently selected entity.
    It listens for user inputs (e.g., left mouse button releases) to detect when the selection
    changes and updates the UI accordingly. It also dynamically generates shader-specific and
    custom inspector fields for entities that implement a `draw_inspector` method.

    Attributes:
        selected_entity (Entity or None): The currently selected entity being inspected.
        ui (Entity): Root UI container for all inspector elements.
        name_field (InspectorInputField): Text input field for the entity's name.
        input_fields (list[InspectorInputField]): List of generic input fields (currently only name).
        transform_fields (list[InspectorInputField]): List of input fields for transform attributes
            in the order: x, y, z, rotation_x, rotation_y, rotation_z, scale_x, scale_y, scale_z.
        fields (dict[str, InspectorButton or ColorField]): Mapping of additional property fields
            ('model', 'texture', 'color', 'collider_type', 'shader') to their UI elements.
        shader_inputs_parent (Entity): Container for dynamically generated shader input fields.
        scale (float): UI scaling factor for the entire inspector.
    """

    def __init__(self):
        """
        Initialize the Inspector panel, create all standard input fields, and set up callbacks.

        Does not change any entity logic; only constructs UI elements and hooks them into
        LEVEL_EDITOR selection logic.
        """
        # Call base class constructor, attaching this inspector to the level editor's hierarchy UI.
        try:
            super().__init__(parent=LEVEL_EDITOR.hierarchy_list, x=.15)  # type: ignore

            # --- Dynamic scaling attributes ---
            self._init_w, self._init_h = window.size
            h = self._init_h or 1
            # Set your desired pixel size for the inspector panel, e.g. 300x500:
            self._base_ui_scale = Vec2((300 / h) * 2, (500 / h) * 2)
            self.scale = self._base_ui_scale
            # ----------------------------------

        except Exception as e:
            # If the parent doesn't exist or LEVEL_EDITOR is not set up, fail silently.
            # We do not alter logic; we simply ensure the inspector can still be constructed without crashing.
            print(f"Inspector: Error initializing base Entity: {e}")

        # Currently no entity is selected
        self.selected_entity = None

        # Root container for UI components
        self.ui = Entity(parent=self)

        # Name field: allows editing of the entity's name
        self.name_field = InspectorInputField(
            parent=self.ui,
            default_value='name',
            origin=(-.5, .5),
            scale_x=.15 * 3,
            scale_y=.05 * .75,
            color=hsv(210, .9, .6)
        )
        # Keep track of all generic input fields (currently only name)
        self.input_fields = [self.name_field]

        # List to store transform-related input fields: position, rotation, scale
        self.transform_fields = []

        # Create 3x3 grid of input fields for x,y,z, rotation_x, rotation_y, rotation_z, scale_x, scale_y, scale_z
        for y, names in enumerate((
            ('x', 'y', 'z'),
            ('rotation_x', 'rotation_y', 'rotation_z'),
            ('scale_x', 'scale_y', 'scale_z')
        )):
            for x in range(3):
                # Default value is '0' for position and rotation, '1' for scale
                default = '0'
                if y == 2:
                    default = '1'

                # Create a small input field as a child of the name_field
                field = InspectorInputField(
                    max_width=8,
                    model='quad',
                    parent=self.name_field,
                    scale=(1/3, 1),
                    origin=(-.5, .5),
                    default_value=default,
                    limit_content_to=ContentTypes.math,
                    x=x / 3,
                    y=-y - 1,
                    color=color._8
                )

                def on_submit(names=names, x=x, field=field):
                    """
                    Callback for when a transform field is submitted or its value changes.

                    Attempts to evaluate the field's text as a float. If successful, updates
                    the corresponding transform attribute on all selected entities.
                    Ignores invalid or incomplete math expressions.
                    """
                    try:
                        # Evaluate the text (up to 8 characters) as a Python expression
                        value = float(eval(field.text[:8]))
                        # Confirm it's indeed a float
                        if isinstance(value, float):
                            # Truncate the displayed text to 8 characters
                            field.text_field.text_entity.text = str(value)[:8]
                            # Apply this transform to all selected entities
                            for e in LEVEL_EDITOR.selection:  # type: ignore
                                try:
                                    setattr(e, names[x], float(field.text_field.text_entity.text))
                                except Exception:
                                    # If the attribute does not exist or cannot be set, ignore
                                    continue
                    except Exception:
                        # If eval fails (invalid/incomplete math), ignore without crashing
                        return

                # Hook the same callback to both enter-key submission and value-change events
                field.on_submit = on_submit
                field.on_value_changed = on_submit

                # Add this field to the list of transform fields
                self.transform_fields.append(field)

        # Link each transform field to the next one, so tabbing or navigation can move focus
        for i in range(len(self.transform_fields) - 1):
            try:
                self.transform_fields[i].next_field = self.transform_fields[i + 1]
            except Exception:
                # If a transform field is missing or not focusable, ignore linking
                continue

        # Create buttons and fields for other properties: model, texture, color, collider_type, shader
        try:
            self.fields = dict(
                model=InspectorButton(
                    parent=self.name_field,
                    text='model: ',
                    y=-4,
                    on_click=Func(setattr, LEVEL_EDITOR.menu_handler, 'state', 'model_menu')  # type: ignore
                ),  # type: ignore
                texture=InspectorButton(
                    parent=self.name_field,
                    text='texture: ',
                    y=-5,
                    on_click=Sequence(
                        Func(setattr, LEVEL_EDITOR.menu_handler, 'state', 'texture_menu'),  # type: ignore
                        Func(setattr, LEVEL_EDITOR.texture_menu, 'target_attr', 'texture')  # type: ignore
                    )
                ),  # type: ignore
                color=ColorField(
                    parent=self.name_field,
                    text='c:color: ',
                    y=-6,
                    attr_name='color',
                    is_shader_input=False
                ),
                collider_type=InspectorButton(
                    parent=self.name_field,
                    text='collider_type: ',
                    y=-7,
                    on_click=Func(setattr, LEVEL_EDITOR.menu_handler, 'state', 'collider_menu')  # type: ignore
                ),  # type: ignore
                shader=InspectorButton(
                    parent=self.name_field,
                    text='shader: ',
                    y=-8,
                    on_click=Func(setattr, LEVEL_EDITOR.menu_handler, 'state', 'shader_menu')  # type: ignore
                ),  # type: ignore
            )
        except Exception as e:
            # If LEVEL_EDITOR.menu_handler or texture_menu is not set up yet, fields may fail to create.
            print(f"Inspector: Error creating property fields: {e}")
            self.fields = {}

        # Add a visual 3x3 grid under the first transform field to indicate axes
        try:
            Entity(
                model=Grid(3, 3),
                parent=self.transform_fields[0],
                scale=3,
                origin=(-.5, .5),
                z=-.1,
                color=color._64
            )
        except Exception:
            # If transform_fields is empty or Grid not available, skip drawing
            pass

        # Container for shader-specific inputs, positioned below other fields
        self.shader_inputs_parent = Entity(parent=self.name_field, y=-9)

        # Scale factor for UI, can be adjusted as needed
        self.scale = .6

        # Initialize the inspector to reflect current selection (if any)
        self.update_inspector()

    def input(self, key):
        """
        Handle input events. Specifically, reacts to left mouse button releases to update
        the inspector if the selection in LEVEL_EDITOR changes.

        Args:
            key (str): The input event identifier (e.g., 'left mouse up', 'right mouse down').
        """
        # Only respond to left mouse-up events
        if key != 'left mouse up':
            return

        try:
            # If there is a selection and either the left mouse was clicked or 'd' is held
            if LEVEL_EDITOR.selection and (mouse.left or held_keys['d']):  # type: ignore
                # If no entity is currently selected in this inspector, update UI
                if not self.selected_entity:
                    self.update_inspector()
                # If the selected entity in LEVEL_EDITOR changed, update UI
                elif self.selected_entity != LEVEL_EDITOR.selection[0]:  # type: ignore
                    self.update_inspector()
        except Exception:
            # If LEVEL_EDITOR.selection or input states are not defined, ignore input handling
            return

    def update_inspector(self):
        """
        Refresh all UI fields to match the currently selected entity's properties.

        If no entity is selected in LEVEL_EDITOR, hide the inspector UI. Otherwise, populate
        name, transform, model, texture, color, collider, shader, shader inputs, and any custom
        inspector fields provided by the entity's `draw_inspector` method.
        """
        # Enable or disable the inspector UI based on whether any entity is selected
        try:
            self.ui.enabled = bool(LEVEL_EDITOR.selection)  # type: ignore
        except Exception:
            # If LEVEL_EDITOR.selection doesn't exist, disable UI and return
            self.ui.enabled = False
            return

        # If nothing is selected, clear any internal state and exit
        if not LEVEL_EDITOR.selection:  # type: ignore
            return

        # Update the currently selected entity reference
        try:
            self.selected_entity = LEVEL_EDITOR.selection[0]  # type: ignore
        except Exception:
            # If selection list is unexpectedly malformed, do nothing
            return

        # Update color preview for the selected entity
        try:
            self.fields['color'].preview.color = self.selected_entity.color  # type: ignore
        except Exception:
            # If the entity has no color attribute, skip
            pass

        # Update the name text field to match the entity's name
        try:
            self.name_field.text_field.text_entity.text = self.selected_entity.name
        except Exception:
            # If no name attribute, leave the default text intact
            pass

        # Update transform fields (x, y, z, rotation_x, rotation_y, rotation_z, scale_x, scale_y, scale_z)
        for i, attr_name in enumerate((
            'x', 'y', 'z',
            'rotation_x', 'rotation_y', 'rotation_z',
            'scale_x', 'scale_y', 'scale_z'
        )):
            try:
                # Get the value from the selected entity, round to 4 decimal places, convert to string
                value = getattr(self.selected_entity, attr_name)
                self.transform_fields[i].text_field.text_entity.text = str(round(value, 4))
            except Exception:
                # If the attribute is missing or not numeric, skip updating that field
                continue

        # Update additional property fields: model, texture, collider_type, shader
        for name in ('model', 'texture', 'collider_type', 'shader'):
            try:
                # Collect unique values of this attribute among all selected entities
                unique_field_values = tuple(
                    set(
                        getattr(e, name)
                        for e in LEVEL_EDITOR.selection  # type: ignore
                        if hasattr(e, name)
                    )
                )  # type: ignore
            except Exception:
                # If selection is malformed or attribute access fails, show error text
                unique_field_values = ()

            if unique_field_values == ():
                text = '*error*'
            elif len(unique_field_values) == 1:
                # All selected entities share the same value: display it
                text = unique_field_values[0]
                # If this value has a 'name' attribute (e.g., a Model or Texture object), use it
                if hasattr(text, 'name'):
                    try:
                        text = text.name
                    except Exception:
                        # If accessing name fails, leave as-is
                        pass
            else:
                # Mixed values among selection
                text = '--- mixed ---'

            # Update the button or field's displayed text
            try:
                self.fields[name].text_entity.text = f'{name[0]}:{text}'
            except Exception:
                # Skip if the field is missing
                continue

        # Clear any existing shader-specific input fields
        try:
            for child in list(self.shader_inputs_parent.children):
                destroy(child)
        except Exception:
            # If children list is inaccessible, ignore
            pass

        # Dynamically generate shader input
        from ursina.prefabs.vec_field import VecField

        i = 0
        if self.selected_entity.shader:
            shader_inputs = {key: value for key, value in self.selected_entity.shader.default_input.items() if key != 'shadow_color'}
            for name, value in shader_inputs.items():
                instance_value = self.selected_entity.get_shader_input(name)
                if instance_value:
                    value = instance_value

                # Handle different types of shader inputs (texture, vector, color, etc.)
                if isinstance(value, str):  # Texture input
                    b = InspectorButton(parent=self.shader_inputs_parent, text=f' {name}: {value}', highlight_color=color.black90, y=-i)
                    b.text_entity.scale *= .6
                    b.on_click = Sequence(
                        Func(setattr, LEVEL_EDITOR.menu_handler, 'state', 'texture_menu'),  # type: ignore
                        Func(setattr, LEVEL_EDITOR.texture_menu, 'target_attr', name)  # type: ignore
                    )
                elif isinstance(value, Vec2) or (hasattr(value, '__len__') and len(value) == 2):  # Vector input
                    field = VecField(default_value=instance_value, parent=self.shader_inputs_parent, model='quad', scale=(1, 1), x=.5, y=-i - .5, text=f'  {name}')
                    for e in field.fields:
                        e.text_field.scale *= .6
                        e.text_field.text_entity.color = color.light_gray
                    field.text_entity.scale *= .6 * .75
                    field.text_entity.color = color.light_gray

                    def on_submit(name=name, field=field):
                        for e in LEVEL_EDITOR.selection:  # type: ignore
                            e.set_shader_input(name, field.value)
                    field.on_value_changed = on_submit

                elif isinstance(value, Color):  # Color input
                    color_field = ColorField(parent=self.shader_inputs_parent, text=f' {name}', y=-i, is_shader_input=True, attr_name=name, value=value)
                    color_field.text_entity.scale *= .6

                i += 1

        # Handle custom inspector fields from the selected entity
        i += 0
        if hasattr(self.selected_entity, 'draw_inspector'):
            divider = Entity(parent=self.shader_inputs_parent, model='quad', collider='box', origin=(-.5, .5), scale=(1, .5), color=color.black90, y=-i)
            i += 1
            # Custom fields provided by the entity
            for name, _type in self.selected_entity.draw_inspector().items():
                if not hasattr(self.selected_entity, name):
                    continue
                attr = getattr(self.selected_entity, name)
                if attr is False or attr is True:  # Boolean field
                    b = InspectorButton(parent=self.shader_inputs_parent, text=f' {name}:', highlight_color=color.red, y=-i, origin=(-.5, 0))
                    b.text_entity.scale *= .6
                    def toggle_value(name=name):
                        new_value = not getattr(self.selected_entity, name)
                        for e in LEVEL_EDITOR.selection:  # type: ignore
                            setattr(e, name, new_value)
                            if hasattr(e, 'generate'):
                                e.generate()

                    b.on_click = toggle_value

                elif _type in (float, int):  # Numeric fields
                    field = VecField(default_value=attr, parent=self.shader_inputs_parent, model='quad', scale=(1, 1), x=.5, y=-i, text=f'  {name}')
                    for e in field.fields:
                        e.text_field.scale *= .6
                        e.text_field.text_entity.color = color.light_gray
                    field.text_entity.scale *= .6 * .75
                    field.text_entity.color = color.light_gray

                    def on_submit(name=name, field=field):
                        for e in LEVEL_EDITOR.selection:  # type: ignore
                            setattr(e, name, field.value)

                    field.on_value_changed = on_submit

                elif isinstance(_type, type):  # Custom class fields
                    text = attr
                    if hasattr(attr, 'name'):
                        text = attr.__name__

                    b = InspectorButton(parent=self.shader_inputs_parent, text=f' {name}: {text}', y=-i, origin=(-.5, 0))
                    b.text_entity.scale *= .6
                    b.on_click = Func(setattr, LEVEL_EDITOR.menu_handler, 'state', 'class_menu')  # type: ignore

                i += 1

        def update(self):
            cur_w, _ = window.size
            ratio = cur_w / (self._init_w or cur_w)
            self.scale = self._base_ui_scale * ratio
        
            # Optionally scale the name field and its children
            self.name_field.scale = Vec2(.5, .04) * ratio  # adjust as needed
            for field in self.transform_fields:
                field.scale = Vec2(.2, .04) * ratio  # adjust as needed
        
            # Optionally scale property fields (model, texture, color, etc.)
            for field in self.fields.values():
                field.scale = Vec2(.5, .04) * ratio  # adjust as needed
        
            # Optionally scale shader input fields
            for child in self.shader_inputs_parent.children:
                child.scale = Vec2(.5, .04) * ratio  # adjust as needed


class MenuHandler(Entity):
    """
    The MenuHandler class manages the state of various menus in the level editor (e.g., model, texture, shader, color, collider, class menus).
    It listens for keyboard input to toggle menus on and off and ensures only one menu is active at a time.
    """

    def __init__(self):
        """
        Initializes the MenuHandler instance.

        - Attaches this handler to the LEVEL_EDITOR entity as its parent.
        - Initializes the internal `_state` to None (meaning no menu is active).
        - Defines a mapping `states` from state names to the corresponding menu Entity.
        - Defines `keybinds` to allow keyboard shortcuts to open specific menus, provided no modifier keys are held.

        Error handling:
        - If a state name is missing from `states` when setting, a KeyError will be raised. A try-except block in the setter elegantly logs the error.
        """
        super().__init__(parent=LEVEL_EDITOR)  # type: ignore
        self._state = None  # Current active state (menu name as a string)

        # Map of state name to the actual Entity that represents that menu.
        # NOTE: The 'None' state maps to a dummy Entity (disabled by default).
        self.states = {
            'None': Entity(),
            'model_menu': LEVEL_EDITOR.model_menu,      # type: ignore
            'texture_menu': LEVEL_EDITOR.texture_menu,  # type: ignore
            'shader_menu': LEVEL_EDITOR.shader_menu,    # type: ignore
            'color_menu': LEVEL_EDITOR.color_menu,      # type: ignore
            'collider_menu': LEVEL_EDITOR.collider_menu,  # type: ignore
            'class_menu': LEVEL_EDITOR.class_menu       # type: ignore
        }

        # Keyboard shortcuts for quick menu toggling (only works if no modifier keys are held).
        self.keybinds = {
            'm': 'model_menu',
            'v': 'texture_menu',
            'n': 'shader_menu',
            'b': 'color_menu',
            'escape': 'None'
        }

    @property
    def state(self):
        """
        Getter for the current state name.

        Returns:
            str or None: The name of the currently active menu state, or None if no state is active.
        """
        return self._state

    @state.setter
    def state(self, value):
        """
        Setter for the state property.

        Args:
            value (str): The name of the state to switch to (e.g., 'model_menu', 'texture_menu', or 'None').

        Behavior:
        - If `value` is the same as the current state (`self._state`), it toggles the `enabled` flag on the corresponding menu Entity.
        - Otherwise, it disables all menu Entities except the one corresponding to `value`, and then updates `_state`.

        Error handling:
        - If `value` is not a key in `self.states`, logs an error message and does nothing.
        """
        try:
            target_state = self.states[value]
        except KeyError:
            # Log an error if an invalid state name is provided
            print(f"[MenuHandler] Invalid state '{value}' requested. No such state exists.")
            return

        print('toggle:', value, 'from:', self._state)

        # If clicking on the currently active state, just toggle its enabled status
        if self._state == value:
            target_state.enabled = not target_state.enabled
            return

        # Otherwise, disable all menu Entities except the one corresponding to `value`
        for key, e in self.states.items():
            if e:  # Some states might map to None or be uninitialized
                e.enabled = (key == value)

        # Update the internal state name
        self._state = value

    def input(self, key):
        """
        Handles keyboard input for menu navigation.

        Args:
            key (str): The key that was pressed (e.g., 'escape', 'm', 'v', etc.).

        Behavior:
        - If 'escape' is pressed and a menu is active (state != 'None'), reset to 'None' (close menus).
        - If no menu is active ('None'), check if the pressed key is in `self.keybinds` and no modifier keys (Ctrl, Shift, Alt) are held.
          If so and there is at least one entity selected in the level editor, switch to the corresponding menu state.

        Error handling:
        - Catches any unexpected exceptions during state changes and logs them without breaking the application.
        """
        try:
            # If escape is pressed while a menu is open, close all menus.
            if key == 'escape' and self.state != 'None':
                self.state = 'None'
                return

            # If any menu is active, ignore other inputs
            if self.state != 'None':
                return

            # Only open a menu via keybind if no modifier keys are held and there is a selection
            if (not held_keys['control'] and not held_keys['shift'] and not held_keys['alt']
                    and key in self.keybinds and LEVEL_EDITOR.selection):  # type: ignore
                self.state = self.keybinds[key]
        except Exception as e:
            # Log any unexpected errors during input handling for debugging
            print(f"[MenuHandler] Error processing input '{key}': {e}")


class AssetMenu(ButtonList):
    """
    AssetMenu is a popup menu that displays a list of available assets (e.g., textures, models) as buttons.
    It inherits from ButtonList and, when enabled, populates its button dictionary based on the current assets
    and positions itself at the mouse cursor for quick selection.

    Attributes:
        button_dict (dict): A mapping from asset names to callback functions that handle asset selection.
        asset_names (list or iterable): A list of asset names available to populate the menu. Expected to be provided
            by some higher-level code or inherited from ButtonList.
    """

    def __init__(self):
        """
        Initializes the AssetMenu instance.

        - Calls the parent ButtonList __init__ with an empty button_dict (buttons will be populated when the menu is enabled).
        - Attaches this menu as a child of LEVEL_EDITOR.ui so it is part of the editor's UI.
        - Starts disabled (enabled=False) so it does not appear until explicitly triggered.
        - Sets popup=True so it behaves as a transient popup window.
        - Names this entity after the class name for easy debugging/identification.
        - Scales the menu to half size for better on-screen fit.

        Error handling:
        - None required here since super().__init__ is expected to set up a valid ButtonList.
        """
        super().__init__(
            button_dict=dict(),                 # Start with no buttons; populate on_enable
            parent=LEVEL_EDITOR.ui,             # type: ignore
            enabled=False,                      # Initially hidden
            popup=True,                         # Behave like a popup
            z=-2,                               # Render behind other UI elements if needed
            name=__class__.__name__,           # Name the entity "AssetMenu"
            scale=.5                            # Scale down to half size
        )

    def on_enable(self):
        """
        Called automatically when this AssetMenu is enabled (i.e., when it becomes visible).

        - Checks if there are any assets to display. If asset_names is empty or missing, logs a message.
        - Populates self.button_dict with a mapping from each asset name to a Func that calls on_select_asset(name).
        - Positions the menu at the current mouse cursor location for quick user access.

        Error handling:
        - Catches AttributeError if `asset_names` does not exist.
        - Catches any exceptions when populating button_dict or accessing mouse coordinates and logs them.
        """
        try:
            # Attempt to retrieve the list of asset names. asset_names should be provided by parent or inherited.
            assets = self.asset_names
        except AttributeError:
            # If asset_names isn't defined, log and return early.
            print(f"[AssetMenu] No attribute 'asset_names' found on {self!r}. Cannot populate menu.")
            return

        # If there are no assets, inform the user via console. The menu will still open, but be empty.
        if not assets:
            print('no texture assets found')

        # Populate the button dictionary so each asset name triggers on_select_asset(asset_name) when clicked.
        try:
            self.button_dict = {
                name: Func(self.on_select_asset, name)
                for name in assets
            }
        except Exception as e:
            # Catch any unexpected errors (e.g., assets not iterable, on_select_asset missing).
            print(f"[AssetMenu] Error populating button_dict: {e}")
            # Leave button_dict as empty or partially filled, so that menu does not crash.
            self.button_dict = {}

        # Attempt to position the popup at the mouse cursor. If mouse is undefined or has no x/y, catch and log.
        try:
            self.x = mouse.x  # type: ignore
            self.y = mouse.y  # type: ignore
        except Exception as e:
            print(f"[AssetMenu] Could not position menu at mouse location: {e}")


class ModelMenu(AssetMenu):
    """
    ModelMenu is a specialized AssetMenu for selecting and assigning 3D models to entities in the level editor.
    
    When enabled, it gathers available model assets (including built-in placeholders and any files with extensions
    .bam, .obj, or .ursinamesh in the application.asset_folder) and populates the asset_names list accordingly.
    Upon selection of a model, it records the change (old vs. new model name) for each selected entity in LEVEL_EDITOR.selection,
    and then closes the menu.
    """

    def on_enable(self):
        """
        Called automatically when this ModelMenu is enabled (i.e., becomes visible).

        - Initializes `self.asset_names` with a set of default placeholder names: 'None', 'cube', 'sphere', 'plane'.
        - Scans the application.asset_folder for files ending with .bam, .obj, or .ursinamesh (excluding any whose stem
          contains 'animation'), and appends their stems to `self.asset_names`.
        - Finally, calls the parent on_enable() to actually build the button dictionary and position the menu.

        Error handling:
        - If `application.asset_folder` is missing or cannot be accessed, logs an error and proceeds with the default names.
        - If a glob operation fails for any particular file type, logs the exception and continues collecting other types.
        """
        # Start with some placeholder model names that the engine recognizes
        self.asset_names = ['None', 'cube', 'sphere', 'plane']

        try:
            # Attempt to scan for model files in the asset folder
            for file_type in ('.bam', '.obj', '.ursinamesh'):
                try:
                    # Glob for files matching the extension, excluding names containing 'animation'
                    found_files = application.asset_folder.glob(f'**/*{file_type}')
                    # Extract the stem (filename without extension) for each file
                    for e in found_files:
                        if 'animation' not in e.stem:
                            self.asset_names.append(e.stem)
                except Exception as file_error:
                    # Log issues with scanning this particular file type
                    print(f"[ModelMenu] Error scanning for '{file_type}' files: {file_error}")
        except Exception as folder_error:
            # If the asset_folder attribute doesn't exist or is not accessible
            print(f"[ModelMenu] Could not access application.asset_folder: {folder_error}")

        # Delegate to the parent class to set up the buttons and position the menu
        super().on_enable()

    def on_select_asset(self, name):
        """
        Called when the user clicks on one of the model names in the menu.

        Args:
            name (str): The model name selected by the user. Can be 'None' or any string from `self.asset_names`.

        Behavior:
        - If the selected name is 'None', it translates that to a Python None to indicate no model.
        - Iterates through each entity in LEVEL_EDITOR.selection and records a tuple containing:
            (entity_index, 'model', old_model_name_or_None, new_model_name_or_None).
        - Finally, closes the menu by setting LEVEL_EDITOR.menu_handler.state to 'None'.

        Error handling:
        - If LEVEL_EDITOR.selection or LEVEL_EDITOR.entities is missing, logs an error and aborts gracefully.
        """
        # Interpret 'None' as removing the model
        if name == 'None':
            name = None

        changes = []
        try:
            # Ensure there is a selection to process
            selected_list = LEVEL_EDITOR.selection  # type: ignore
            all_entities = LEVEL_EDITOR.entities    # type: ignore
        except Exception as e:
            print(f"[ModelMenu] Cannot access LEVEL_EDITOR.selection or LEVEL_EDITOR.entities: {e}")
            return

        # Record the old and new model names for each selected entity
        for e in selected_list:
            try:
                index = all_entities.index(e)
            except ValueError:
                # If this entity is not found in LEVEL_EDITOR.entities, skip it
                print(f"[ModelMenu] Entity {e} not found in LEVEL_EDITOR.entities.")
                continue

            # Determine the old model name (or None if no model)
            old_model_name = e.model.name if hasattr(e, 'model') and e.model else None
            # Append a tuple: (entity_index, attribute_name, old_value, new_value)
            changes.append((index, 'model', old_model_name, name))
        # At this point, `changes` holds entries that could be used by an undo/redo system or similar.

        # Close the ModelMenu by resetting the menu handler's state
        try:
            LEVEL_EDITOR.menu_handler.state = 'None'  # type: ignore
        except Exception as e:
            print(f"[ModelMenu] Could not close menu (setting state to 'None'): {e}")


class TextureMenu(AssetMenu):
    """
    TextureMenu is a specialized AssetMenu for selecting and assigning textures (or other shader inputs) to entities in the level editor.

    Attributes:
        target_attr (str): The attribute name that the selected texture will be applied to. Defaults to 'texture', 
                           but can be changed (e.g., to a shader uniform name) before the menu is enabled.
        asset_names (list): A list of texture asset names to populate the menu. Populated in on_enable().
    """

    def __init__(self, **kwargs):
        """
        Initializes the TextureMenu instance.

        - Calls the parent AssetMenu __init__ with any provided keyword arguments.
        - Initializes target_attr to 'texture', indicating that by default, clicking an asset sets the 'texture' attribute.
        
        Error handling:
        - No specific error handling needed here; relies on AssetMenu to set up the UI.
        """
        super().__init__(**kwargs)
        self.target_attr = 'texture'

    def on_enable(self):
        """
        Called automatically when this TextureMenu is enabled (i.e., becomes visible).

        - Sets up `self.asset_names` with a default list of placeholder texture names: 'None', 'white_cube', 'brick', 'grass_tintable', 'radial_gradient', 'cog'.
        - Scans the application.asset_folder for files ending with .png, .jpg, or .jpeg (optionally filtering by search_for, currently an empty string).
        - Appends each discovered file's stem (filename without extension) to `self.asset_names`.
        - Calls the parent on_enable() to build the button dictionary and position the menu.

        Error handling:
        - If `application.asset_folder` is missing or not accessible, logs an error and proceeds with the default names.
        - If a glob operation fails for any particular file type, logs the exception and continues collecting other types.
        """
        search_for = ''  # Currently empty; could be used to filter by prefix

        # Start with some placeholder texture names that the engine recognizes
        self.asset_names = ['None', 'white_cube', 'brick', 'grass_tintable', 'radial_gradient', 'cog']

        try:
            # Attempt to scan for image files in the asset folder
            for file_type in ('.png', '.jpg', '.jpeg'):
                try:
                    found_files = application.asset_folder.glob(f'**/{search_for}*{file_type}')
                    for e in found_files:
                        self.asset_names.append(e.stem)
                except Exception as file_error:
                    # Log issues with scanning this particular image type
                    print(f"[TextureMenu] Error scanning for '{file_type}' files: {file_error}")
        except Exception as folder_error:
            # If asset_folder does not exist or is not accessible
            print(f"[TextureMenu] Could not access application.asset_folder: {folder_error}")

        # Delegate to the parent class to populate buttons and position the menu
        super().on_enable()

    def on_select_asset(self, name):
        """
        Called when the user clicks on one of the texture names in the menu.

        Args:
            name (str): The texture name selected by the user. Can be 'None' or any string from `self.asset_names`.

        Behavior:
        - If the selected name is 'None', translates that to None to indicate no texture.
        - If `self.target_attr` is 'texture', records an undo entry for each selected entity's current texture and then sets the new texture.
        - Otherwise, treats `self.target_attr` as a shader input name: records an undo entry for the current shader input and sets the shader input to the new value.
        - After applying changes, updates the inspector UI and closes the menu by setting LEVEL_EDITOR.menu_handler.state to 'None'.

        Error handling:
        - If LEVEL_EDITOR.selection or LEVEL_EDITOR.current_scene.undo is missing, logs an error and aborts gracefully.
        - If any attribute assignment fails, logs the exception for debugging.
        """
        # Interpret 'None' as removing the texture (or shader input)
        if name == 'None':
            name = None

        try:
            selection = LEVEL_EDITOR.selection  # type: ignore
            entities = LEVEL_EDITOR.entities     # type: ignore
            undo_system = LEVEL_EDITOR.current_scene.undo  # type: ignore
        except Exception as e:
            print(f"[TextureMenu] Unable to access selection, entities, or undo system: {e}")
            return

        # Apply texture change
        if self.target_attr == 'texture':
            try:
                # Record an undo entry: (entity_index, 'texture', old_value, new_value)
                undo_entries = [
                    (entities.index(e), 'texture', e.texture, name)
                    for e in selection
                ]
                undo_system.record_undo(undo_entries)
            except Exception as e:
                print(f"[TextureMenu] Error recording undo for texture change: {e}")
                # Even if undo fails, proceed to set the texture
            for e in selection:
                try:
                    e.texture = name
                except Exception as e:
                    print(f"[TextureMenu] Could not set texture '{name}' on entity {e}: {e}")

        # Apply shader input change
        else:
            try:
                # Record an undo entry: (entity_index, shader_input_name, old_value, new_value)
                undo_entries = [
                    (entities.index(e), self.target_attr, e.get_shader_input(self.target_attr), name)
                    for e in selection
                ]
                undo_system.record_undo(undo_entries)
            except Exception as e:
                print(f"[TextureMenu] Error recording undo for shader input '{self.target_attr}': {e}")
            for e in selection:
                try:
                    e.set_shader_input(self.target_attr, name)
                except Exception as e:
                    print(f"[TextureMenu] Could not set shader input '{self.target_attr}' to '{name}' on entity {e}: {e}")

        # Update the inspector UI to reflect changes
        try:
            LEVEL_EDITOR.inspector.update_inspector()  # type: ignore
        except Exception as e:
            print(f"[TextureMenu] Error updating inspector: {e}")

        # Close the menu by resetting the menu handler's state
        try:
            LEVEL_EDITOR.menu_handler.state = 'None'  # type: ignore
        except Exception as e:
            print(f"[TextureMenu] Could not close menu (setting state to 'None'): {e}")


class ShaderMenu(AssetMenu):
    """
    ShaderMenu is a specialized AssetMenu for selecting and assigning shaders to entities in the level editor.

    When enabled, it defines a fixed list of available shaders and populates the menu accordingly. Upon selection
    of a shader, it records the change for undo, applies the new shader to each selected entity via dynamic import
    (using exec), and updates the inspector UI.
    """

    def on_enable(self):
        """
        Called automatically when this ShaderMenu is enabled (i.e., becomes visible).

        - Initializes `self.asset_names` with a predefined list of shader names that the engine supports.
        - Delegates to the parent on_enable() to build the button dictionary and position the menu.

        Error handling:
        - Catches any exceptions during the call to super().on_enable() and logs them without preventing the menu from opening.
        """
        # Define the list of built-in shaders available for assignment
        self.asset_names = [
            'unlit_shader',
            'lit_with_shadows_shader',
            'triplanar_shader',
            'matcap_shader',
            'normals_shader',
        ]

        try:
            # Populate buttons and position the menu via the parent class
            super().on_enable()
        except Exception as e:
            # Log any unexpected error during parent setup
            print(f"[ShaderMenu] Error during on_enable: {e}")

    def on_select_asset(self, name):
        """
        Called when the user clicks on one of the shader names in the menu.

        Args:
            name (str): The shader name selected by the user (e.g., 'unlit_shader').

        Behavior:
        - Closes the ShaderMenu by setting LEVEL_EDITOR.menu_handler.state to 'None'.
        - Records an undo entry: for each selected entity, store (entity_index, 'shader', old_shader, new_shader).
        - For each selected entity:
            - Dynamically import the chosen shader module/class using exec.
            - Assign the imported shader class to the entity's `shader` attribute via exec.
        - Updates the inspector UI to reflect the shader change.

        Error handling:
        - If LEVEL_EDITOR.selection or LEVEL_EDITOR.current_scene.undo is missing, logs an error and aborts gracefully.
        - Catches any exceptions during the dynamic import or assignment (exec) and logs them without halting execution.
        - Catches exceptions when updating the inspector and logs them.
        """
        # Close the menu immediately for user feedback
        try:
            LEVEL_EDITOR.menu_handler.state = 'None'  # type: ignore
        except Exception as e:
            print(f"[ShaderMenu] Could not close menu (setting state to 'None'): {e}")

        # Attempt to record undo entries
        try:
            selection = LEVEL_EDITOR.selection  # type: ignore
            entities = LEVEL_EDITOR.entities     # type: ignore
            undo_system = LEVEL_EDITOR.current_scene.undo  # type: ignore
        except Exception as e:
            print(f"[ShaderMenu] Unable to access selection, entities, or undo system: {e}")
            return

        try:
            # Record an undo entry: (entity_index, 'shader', old_shader, new_shader)
            undo_entries = [
                (entities.index(e), 'shader', e.shader, name)
                for e in selection
            ]
            undo_system.record_undo(undo_entries)
        except Exception as e:
            print(f"[ShaderMenu] Error recording undo for shader change: {e}")
            # Continue even if undo recording fails

        # Apply the shader to each selected entity
        for e in selection:
            try:
                # Dynamically import the selected shader from ursina.shaders
                exec(f'from ursina.shaders import {name}')
                # Assign the imported shader class to the entity's shader attribute
                exec(f'e.shader = {name}')
            except Exception as e:
                print(f"[ShaderMenu] Could not set shader '{name}' on entity {e}: {e}")

        # Update the inspector UI to reflect the change
        try:
            LEVEL_EDITOR.inspector.update_inspector()  # type: ignore
        except Exception as e:
            print(f"[ShaderMenu] Error updating inspector: {e}")


class ColorMenu(Entity):
    """
    ColorMenu provides an interactive HSV and Alpha slider interface for selecting and applying colors to entities
    in the level editor. It allows the user to adjust hue, saturation, value, and alpha values dynamically and
    applies the chosen color to the selected entities (or their shader input, if applicable). It also supports
    undo functionality for color changes.
    """

    def __init__(self):
        """
        Initializes the ColorMenu instance.

        - Creates a semi-transparent background panel (`self.bg`) behind the sliders for visual grouping.
        - Initializes four sliders: H (hue), S (saturation), V (value/brightness), and A (alpha/transparency).
          Each slider is configured with its name, range, step size, and a callback (`on_slider_changed`).
        - Configures the background models of each slider to visually represent their color gradients or masks.
        - Positions the sliders vertically and sets their knob colors.
        - Adds an invisible full-screen quad behind the sliders to capture clicks and close the menu (`self.bg` overlay).
        - Introduces an `apply_color` flag to control whether slider movements immediately update entity colors.
        
        Error handling:
        - Wraps potentially unsafe operations (e.g., accessing `self.s_slider.bg.model.vertices`) in try-except blocks
          to avoid crashes if the underlying model or its vertices list is missing.
        """
        super().__init__(parent=LEVEL_EDITOR.ui, enabled=False)  # type: ignore

        # Semi-transparent background rectangle for the slider panel
        self.bg = Entity(
            parent=self,
            collider='box',
            z=.1,
            color=color.black,
            alpha=.8,
            origin=(-.5, .5),
            scale=(.6, .15),
            position=(-.05, .03),
            model=Quad(aspect=.6 / .15)
        )

        # Hue slider: range 0–360, displays a rainbow texture
        self.h_slider = Slider(
            name='h', min=0, max=360, step=1, text='h', dynamic=True,
            world_parent=self, on_value_changed=self.on_slider_changed
        )
        try:
            self.h_slider.bg.color = color.white
            self.h_slider.bg.texture = 'rainbow'
            self.h_slider.bg.texture.filtering = True
        except Exception as e:
            print(f"[ColorMenu] Error configuring h_slider background: {e}")

        # Saturation slider: range 0–100, initial default 50, colored white background
        self.s_slider = Slider(
            name='s', min=0, max=100, step=1, default=50, text='s', dynamic=True,
            world_parent=self, on_value_changed=self.on_slider_changed
        )
        try:
            self.s_slider.bg.color = color.white
            # Set all vertices of the background model to white initially
            self.s_slider.bg.model.colors = [color.white for _ in self.s_slider.bg.model.vertices]
        except Exception as e:
            print(f"[ColorMenu] Error configuring s_slider background: {e}")

        # Value (brightness) slider: range 0–100, initial default 50, black-to-white gradient background
        self.v_slider = Slider(
            name='v', min=0, max=100, default=50, step=1, text='v', dynamic=True,
            world_parent=self, on_value_changed=self.on_slider_changed
        )
        try:
            # Initially color all vertices black, then overlay white background to allow dynamic update
            self.v_slider.bg.model.colors = [color.black for _ in self.v_slider.bg.model.vertices]
            self.v_slider.bg.color = color.white
        except Exception as e:
            print(f"[ColorMenu] Error configuring v_slider background: {e}")

        # Alpha slider: range 0–100, initial default 100, white background with left side transparent
        self.a_slider = Slider(
            name='a', min=0, max=100, default=100, step=1, text='a', dynamic=True,
            world_parent=self, on_value_changed=self.on_slider_changed
        )
        try:
            # Start by setting all vertices of the alpha background to white
            self.a_slider.bg.model.colors = [color.white for _ in self.a_slider.bg.model.vertices]
            self.a_slider.bg.color = color.white
            # Make the left half of the alpha slider background transparent to represent 0% alpha
            for i, v in enumerate(self.a_slider.bg.model.vertices):
                if v[0] < 0:
                    self.a_slider.bg.model.colors[i] = color.clear
            self.a_slider.bg.model.generate()
        except Exception as e:
            print(f"[ColorMenu] Error configuring a_slider background: {e}")

        # Position each slider vertically underneath the top of the panel and set knob color
        for i, slider in enumerate((self.h_slider, self.s_slider, self.v_slider, self.a_slider)):
            try:
                slider.y = -i * .03
                slider.knob.color = color.white
            except Exception as e:
                print(f"[ColorMenu] Error positioning slider '{slider.name}': {e}")

        # Scale the entire ColorMenu interface down to half size for compactness
        self.scale *= .5

        # Invisible full-screen entity that closes the menu when clicked
        self.bg = Entity(
            parent=self,
            model='quad',
            collider='box',
            visible_self=False,
            scale=10,
            z=1,
            on_click=self.close
        )

        # Control whether slider changes immediately update entity colors.
        # When False, moving sliders does not affect entity color until after on_enable finishes.
        self.apply_color = True

    def on_slider_changed(self):
        """
        Callback invoked whenever any of the H, S, V, or A sliders change value.

        - Computes the combined HSV + alpha color from the slider values.
        - If `self.apply_color` is True, updates:
            - The preview color in the Inspector's color field.
            - The actual color (or shader input) of all selected entities in LEVEL_EDITOR.selection.
        - Dynamically updates the saturation and value slider backgrounds to reflect the newly chosen hue/value.
        - Updates the alpha slider's knob color to match the chosen color.

        Error handling:
        - Wraps entity updates and model color regenerations in try-except blocks to log and skip errors
          without stopping the application.
        """
        try:
            # Compute the new color from HSV + alpha sliders
            h = self.h_slider.value
            s = self.s_slider.value / 100
            v = self.v_slider.value / 100
            a = self.a_slider.value / 100
            value = color.hsv(h, s, v, a)
        except Exception as e:
            print(f"[ColorMenu] Error computing HSV color: {e}")
            return

        # If apply_color is True, propagate the new color to inspector preview and selected entities
        if self.apply_color:
            try:
                # Update the Inspector's color preview
                inspector_color_field = LEVEL_EDITOR.inspector.fields['color']  # type: ignore
                inspector_color_field.preview.color = value
                # If the color field is not a shader input, assign the direct color attribute
                if not inspector_color_field.is_shader_input:
                    for e in LEVEL_EDITOR.selection:  # type: ignore
                        try:
                            e.color = value
                        except Exception as ent_e:
                            print(f"[ColorMenu] Could not set entity color for {e}: {ent_e}")
                else:
                    # If the Inspector's color field represents a shader input, set_shader_input instead
                    attr_name = inspector_color_field.attr_name
                    for e in LEVEL_EDITOR.selection:  # type: ignore
                        try:
                            e.set_shader_input(attr_name, value)
                        except Exception as ent_e:
                            print(f"[ColorMenu] Could not set shader input '{attr_name}' for {e}: {ent_e}")
            except Exception as insp_e:
                print(f"[ColorMenu] Error updating inspector preview or applying to entities: {insp_e}")

        # Update saturation slider background to reflect new hue and value
        try:
            for i, vertex in enumerate(self.s_slider.bg.model.vertices):
                if vertex[0] < 0:
                    # Grayed-out area for negative x-coordinates (unused region)
                    self.s_slider.bg.model.colors[i] = color.gray
                else:
                    # Color the vertex with full saturation, current hue, and current value
                    self.s_slider.bg.model.colors[i] = color.hsv(value.h, 1, value.v)
            self.s_slider.bg.model.generate()
        except Exception as e:
            print(f"[ColorMenu] Error updating saturation slider background: {e}")

        # Update value slider background to reflect new hue and saturation
        try:
            for i, vertex in enumerate(self.v_slider.bg.model.vertices):
                if vertex[0] > 0:
                    # Color the vertex with current hue, current saturation, and full brightness
                    self.v_slider.bg.model.colors[i] = color.hsv(value.h, value.s, 1)
            self.v_slider.bg.model.generate()
        except Exception as e:
            print(f"[ColorMenu] Error updating value slider background: {e}")

        # Set the alpha slider's background color to the newly selected color (to show transparency effect)
        try:
            self.a_slider.bg.color = value
        except Exception as e:
            print(f"[ColorMenu] Error updating alpha slider color: {e}")

    def on_enable(self):
        """
        Called automatically when the ColorMenu is enabled (made visible).

        - Records the original color of each selected entity in `e.original_color` so undo can revert later.
        - Temporarily disables color application (`apply_color = False`) while sliders are synced to the current color.
        - Reads the current HSV and alpha values from the Inspector's color preview and sets the slider values.
        - Re-enables color application (`apply_color = True`) so further slider movements update entity colors.

        Error handling:
        - Wraps all operations in try-except blocks to avoid crashing if selection is empty or Inspector fields are missing.
        """
        try:
            # Save each selected entity's current color for undo
            for e in LEVEL_EDITOR.selection:  # type: ignore
                try:
                    e.original_color = e.color
                except Exception as ent_e:
                    print(f"[ColorMenu] Could not record original color for {e}: {ent_e}")
        except Exception as sel_e:
            print(f"[ColorMenu] Error iterating over LEVEL_EDITOR.selection: {sel_e}")

        # Prevent slider changes from immediately updating entity colors
        self.apply_color = False

        try:
            # Fetch the current color from the Inspector's preview and decompose into HSV + alpha
            preview_color = LEVEL_EDITOR.inspector.fields['color'].preview.color  # type: ignore
            # Set slider values based on the preview color
            self.h_slider.value = preview_color.h
            self.s_slider.value = preview_color.s * 100
            self.v_slider.value = preview_color.v * 100
            self.a_slider.value = preview_color.a * 100
        except Exception as insp_e:
            print(f"[ColorMenu] Error syncing sliders to inspector preview: {insp_e}")

        # Re-enable color application so that moving sliders now updates entity colors
        self.apply_color = True

    def close(self):
        """
        Closes the ColorMenu and finalizes the color change.

        - Sets the menu handler's state to 'None' to hide this menu.
        - Records an undo entry for each selected entity as (entity_index, 'color', old_color, new_color).
        
        Error handling:
        - Wraps state change and undo recording in try-except blocks to log errors without crashing.
        """
        try:
            LEVEL_EDITOR.menu_handler.state = 'None'  # type: ignore
        except Exception as e:
            print(f"[ColorMenu] Could not close menu (setting state to 'None'): {e}")

        try:
            # Build a list of undo tuples for the selected entities
            undo_entries = [
                (LEVEL_EDITOR.entities.index(e), 'color', e.original_color, e.color)  # type: ignore
                for e in LEVEL_EDITOR.selection  # type: ignore
            ]
            LEVEL_EDITOR.current_scene.undo.record_undo(undo_entries)  # type: ignore
        except Exception as e:
            print(f"[ColorMenu] Error recording undo for color change: {e}")


class ColliderMenu(AssetMenu):
    """
    ColliderMenu is a specialized AssetMenu for selecting and assigning collider types to entities in the level editor.

    When enabled, it defines a fixed list of collider types and populates the menu accordingly. Upon selection
    of a collider type, it assigns that collider_type to each selected entity, updates the inspector, and closes the menu.
    """

    def on_enable(self):
        """
        Called automatically when this ColliderMenu is enabled (i.e., becomes visible).

        - Initializes `self.asset_names` with a predefined list of collider types: 'None', 'box', 'sphere', 'mesh'.
        - Delegates to the parent on_enable() to build the button dictionary and position the menu.

        Error handling:
        - Catches any exceptions during the call to super().on_enable() and logs them without preventing the menu from opening.
        """
        # Define the list of collider types that the engine supports
        self.asset_names = ['None', 'box', 'sphere', 'mesh']

        try:
            # Populate buttons and position the menu via the parent class
            super().on_enable()
        except Exception as e:
            # Log any unexpected error during parent setup
            print(f"[ColliderMenu] Error during on_enable: {e}")

    def on_select_asset(self, name):
        """
        Called when the user clicks on one of the collider type names in the menu.

        Args:
            name (str): The collider type selected by the user (e.g., 'box', 'sphere'). Can be 'None' to clear.

        Behavior:
        - If the selected name is 'None', translates that to None to indicate no collider.
        - Iterates through each entity in LEVEL_EDITOR.selection and assigns the new collider_type.
        - Updates the inspector UI to reflect the new collider_type.
        - Closes the menu by setting LEVEL_EDITOR.menu_handler.state to 'None'.

        Error handling:
        - If LEVEL_EDITOR.selection is missing or empty, logs an error and aborts gracefully.
        - Catches any exceptions when assigning collider_type or updating the inspector and logs them.
        - Ensures the menu is closed even if errors occur when applying changes.
        """
        # Interpret 'None' as removing the collider_type
        if name == 'None':
            name = None

        try:
            # Ensure there is a selection to process
            selection = LEVEL_EDITOR.selection  # type: ignore
        except Exception as e:
            print(f"[ColliderMenu] Unable to access LEVEL_EDITOR.selection: {e}")
            # Attempt to close the menu even if selection cannot be accessed
            try:
                LEVEL_EDITOR.menu_handler.state = 'None'  # type: ignore
            except Exception:
                pass
            return

        # Assign the new collider_type to each selected entity
        for e in selection:
            try:
                e.collider_type = name
            except Exception as ent_e:
                print(f"[ColliderMenu] Could not set collider_type '{name}' on entity {e}: {ent_e}")

        # Update the inspector UI to reflect the change
        try:
            LEVEL_EDITOR.inspector.update_inspector()  # type: ignore
        except Exception as insp_e:
            print(f"[ColliderMenu] Error updating inspector: {insp_e}")

        # Close the menu by resetting the menu handler's state
        try:
            LEVEL_EDITOR.menu_handler.state = 'None'  # type: ignore
        except Exception as mh_e:
            print(f"[ColliderMenu] Could not close menu (setting state to 'None'): {mh_e}")


class ClassMenu(AssetMenu):
    """
    ClassMenu is a specialized AssetMenu for selecting and assigning a "class_to_spawn" attribute to entities
    in the level editor. The available classes (as strings or actual class references) are provided via
    the `available_classes` dictionary. When the menu is enabled, it displays the keys of this dictionary
    as selectable items. Upon selection, it assigns the chosen class name to the `class_to_spawn` attribute
    of each selected entity (if they have that attribute), updates the inspector UI, and closes the menu.
    """

    def __init__(self, **kwargs):
        """
        Initializes the ClassMenu instance.

        - Calls the parent AssetMenu __init__ to set up base popup behavior.
        - Initializes `available_classes` as a dictionary mapping display names (strings) to actual class references
          or None. By default, only 'None' is available, meaning no class will be spawned.
        
        Error handling:
        - None required here, as logic is straightforward. Any missing parent functionality will raise normally.
        """
        super().__init__(**kwargs)
        # A mapping from asset name (string) to the actual class reference or None
        self.available_classes = {'None': None}

    def on_enable(self):
        """
        Called automatically when this ClassMenu is enabled (i.e., becomes visible).

        - Populates `self.asset_names` with the keys from `available_classes` so that each entry
          becomes a button in the popup.
        - Delegates to the parent on_enable() to build the button dictionary and position the menu.

        Error handling:
        - Catches any exceptions during the call to super().on_enable() and logs them without preventing the menu from opening.
        """
        # Use the keys of available_classes as the list of names to display
        self.asset_names = self.available_classes.keys()

        try:
            # Populate buttons and position the menu via the parent class
            super().on_enable()
        except Exception as e:
            print(f"[ClassMenu] Error during on_enable: {e}")

    def on_select_asset(self, name):
        """
        Called when the user clicks on one of the class names in the menu.

        Args:
            name (str): The class name selected by the user. Must be one of the keys in `available_classes`.

        Behavior:
        - Looks up the selected name in `available_classes` to get the actual class reference or None.
        - Iterates through each entity in LEVEL_EDITOR.selection and, if the entity has a `class_to_spawn` attribute,
          assigns it to the selected class reference (which may be None).
        - Updates the inspector UI to reflect any changes.
        - Closes the menu by setting LEVEL_EDITOR.menu_handler.state to 'None'.

        Error handling:
        - If LEVEL_EDITOR.selection or LEVEL_EDITOR.inspector cannot be accessed, logs an error and attempts to close the menu.
        - If an entity does not have the `class_to_spawn` attribute or assignment fails, logs an error but continues.
        - Ensures the menu is closed even if errors occur during assignment or inspector update.
        """
        # Determine the actual class reference (or None) from the available_classes mapping
        selected_class = self.available_classes.get(name, None)

        # Attempt to apply the selected class to each selected entity
        try:
            selection = LEVEL_EDITOR.selection  # type: ignore
        except Exception as e:
            print(f"[ClassMenu] Unable to access LEVEL_EDITOR.selection: {e}")
            # Close the menu even if selection can't be accessed
            try:
                LEVEL_EDITOR.menu_handler.state = 'None'  # type: ignore
            except Exception:
                pass
            return

        for e in selection:
            try:
                # Only set if the entity supports this attribute
                if hasattr(e, 'class_to_spawn'):
                    e.class_to_spawn = selected_class
                else:
                    print(f"[ClassMenu] Entity {e} has no attribute 'class_to_spawn'. Skipping.")
            except Exception as ent_e:
                print(f"[ClassMenu] Could not set class_to_spawn='{name}' on entity {e}: {ent_e}")

        # Update the inspector UI to reflect changes, if possible
        try:
            LEVEL_EDITOR.inspector.update_inspector()  # type: ignore
        except Exception as insp_e:
            print(f"[ClassMenu] Error updating inspector: {insp_e}")

        # Close the menu by resetting the menu handler's state
        try:
            LEVEL_EDITOR.menu_handler.state = 'None'  # type: ignore
        except Exception as mh_e:
            print(f"[ClassMenu] Could not close menu (setting state to 'None'): {mh_e}")


class Help(Button):
    """
    Help is a clickable button in the level editor UI that displays a tooltip listing various hotkeys.

    Attributes:
        tooltip (Text): A Text entity that appears near the Help button and shows hotkey information when enabled.
        tooltip.original_scale (float): Stores the intended scale for the tooltip text, for potential future toggling.
    """

    def __init__(self, **kwargs):
        """
        Initializes the Help button and its associated tooltip.

        - Creates a Button with a question mark ('?') icon, positioned at the top-left of the window.
        - Creates a Text entity for the tooltip, positioned slightly offset from the button, initially disabled.
        - Sets the tooltip's background color to black and records its original scale.

        Error handling:
        - Catches exceptions when accessing LEVEL_EDITOR.ui or window.top_left to avoid crashes if those references are missing.
        - Wraps Text creation and attribute assignments in try-except blocks to log any errors during initialization.
        """
        try:
            # Create the Help button, anchored at the top-left of the window
            super().__init__(
                parent=LEVEL_EDITOR.ui,         # type: ignore  # Attach to the editor's UI root
                text='?',                       # Display a question mark on the button
                scale=.025,                     # Very small scale so the button is unobtrusive
                model='circle',                 # Circular button model
                origin=(-.5, .5),               # Origin at the top-left corner of the button
                text_origin=(0, 0),             # Center the '?' text inside the circle
                position=window.top_left        # Position at the top-left of the window
            )
        except Exception as e:
            # If LEVEL_EDITOR.ui or window.top_left is missing or any other error occurs, log and continue
            print(f"[Help] Error creating Help button: {e}")
            # Call Button.__init__ without parent or position to avoid breaking the application
            super().__init__(text='?', scale=.025, model='circle', origin=(-.5, .5), text_origin=(0, 0))

        # Build the multi-line hotkeys string using dedent
        try:
            hotkeys_text = dedent('''
                Hotkeys:
                n:          add new cube

                d:          quick drag
                w:          move tool
                x/y/z:      hold to quick move on axis

                c:          quick rotate on y axis
                t:          tilt

                e:          scale tool
                s:          quick scale
                s + x/y/z:  quick scale on axis

                f:          move editor camera to point
                shift+f:    reset editor camera position
                shift+p:    toggle perspective/orthographic
                shift+d:    duplicate
            ''').strip()
        except Exception as e:
            print(f"[Help] Error preparing tooltip text: {e}")
            hotkeys_text = "Hotkeys information unavailable."

        try:
            # Create the tooltip Text entity, positioned offset from the button
            self.tooltip = Text(
                position=self.position + Vec3(.05, - .05, -10),  # Slightly to the right and down, and behind in z
                font=Text.default_monospace_font,                # Use a monospace font for alignment
                enabled=False,                                    # Tooltip is hidden initially
                text=hotkeys_text,                                # The hotkey information string
                background=True,                                  # Show a background rectangle behind the text
                scale=.5                                          # Scale down the tooltip text for readability
            )
        except Exception as e:
            print(f"[Help] Error creating tooltip Text entity: {e}")
            # As a fallback, create a simple Text with minimal settings
            try:
                self.tooltip = Text(enabled=False, text="Hotkeys tool unavailable", background=True, scale=.5)
            except Exception as e2:
                print(f"[Help] Failed to create fallback tooltip Text: {e2}")
                self.tooltip = None

        # If tooltip was created successfully, set its background color to black
        if self.tooltip:
            try:
                self.tooltip.background.color = color.black
            except Exception as e:
                print(f"[Help] Error setting tooltip background color: {e}")

            try:
                # Record the intended scale for future reference (e.g., toggling visibility or resizing)
                self.tooltip.original_scale = .75
            except Exception as e:
                print(f"[Help] Error setting tooltip.original_scale: {e}")


class Duplicator(Entity):
    """
    Duplicator enables the user to duplicate selected entities in the level editor and drag the duplicates
    around before finalizing their positions. It creates a temporary plane and a draggable gizmo to facilitate
    positioning, and supports axis locking for constrained movement.
    """

    def __init__(self, **kwargs):
        """
        Initializes the Duplicator instance.

        - Attaches this entity to LEVEL_EDITOR as its parent.
        - Creates a large invisible plane to act as the dragging surface.
        - Creates a Draggable gizmo to represent the dragging handle.
        - Initializes state variables for tracking dragging, cloning, and axis locking.
        - Creates three axis-lock gizmos (magenta for X, yellow for Y, cyan for Z), parented to the dragger.

        Error handling:
        - Wraps critical entity creation in try-except blocks to log failures without crashing.
        """
        try:
            super().__init__(parent=LEVEL_EDITOR, clones=None)  # type: ignore
        except Exception as e:
            print(f"[Duplicator] Error attaching to LEVEL_EDITOR: {e}")
            super().__init__(clones=None)

        # Create an invisible plane that will capture mouse interactions when dragging clones
        try:
            self.plane = Entity(
                model='plane',
                collider='box',
                scale=Vec3(100, .1, 100),
                enabled=False,
                visible=False
            )
        except Exception as e:
            print(f"[Duplicator] Error creating plane entity: {e}")
            self.plane = None

        # Create a Draggable handle to move clones across the plane
        try:
            self.dragger = Draggable(
                parent=scene,
                model=None,
                collider=None,
                enabled=False
            )
        except Exception as e:
            print(f"[Duplicator] Error creating dragger: {e}")
            self.dragger = None

        # State variables
        self.dragging = False              # Whether we are currently dragging clones
        self.start_position = None         # The starting world position of the drag
        self.clone_from_position = None    # The original position of the cloned entity (for reference)
        self.axis_lock = None              # Which axis is locked (0=X, 1=Y, 2=Z), or None for no lock

        # Create axis-lock gizmos: large thin cubes along each axis, initially disabled
        self.axis_lock_gizmos = []
        try:
            # X-axis gizmo (magenta)
            gizmo_x = Entity(
                model='cube',
                scale=Vec3(100, .01, .01),
                color=color.magenta,
                parent=self.dragger,
                unlit=True,
                enabled=False
            )
            # Y-axis gizmo (yellow)
            gizmo_y = Entity(
                model='cube',
                scale=Vec3(.01, 100, .01),
                color=color.yellow,
                parent=self.dragger,
                unlit=True,
                enabled=False
            )
            # Z-axis gizmo (cyan)
            gizmo_z = Entity(
                model='cube',
                scale=Vec3(.01, .01, 100),
                color=color.cyan,
                parent=self.dragger,
                unlit=True,
                enabled=False
            )
            self.axis_lock_gizmos = [gizmo_x, gizmo_y, gizmo_z]
        except Exception as e:
            print(f"[Duplicator] Error creating axis lock gizmos: {e}")
            # If gizmos cannot be created, leave the list empty
            self.axis_lock_gizmos = []

    def update(self):
        """
        Called every frame by the engine.

        - If the plane is enabled (we are currently dragging clones) and there is a valid mouse world point:
            - Move the dragger to the current mouse world point.
            - If an axis lock is active, enable and position the corresponding axis gizmo,
              and constrain the dragger's movement along the locked axis.

        Error handling:
        - Wraps all references to mouse.world_point and gizmos in try-except so unexpected issues do not crash the update loop.
        """
        try:
            # Only proceed if the plane is active and we have a valid world point under the mouse cursor
            if self.plane and self.plane.enabled and mouse.world_point:
                self.dragger.position = mouse.world_point
                # If an axis is locked, constrain movement and show the appropriate gizmo
                if self.axis_lock is not None:
                    # Enable only the locked axis gizmo
                    try:
                        self.axis_lock_gizmos[self.axis_lock].enabled = True
                    except Exception as e:
                        print(f"[Duplicator] Error enabling axis gizmo: {e}")
                    # Lock movement along X (axis_lock == 0)
                    if self.axis_lock == 0:
                        try:
                            self.dragger.z = self.start_position.z
                        except Exception as e:
                            print(f"[Duplicator] Error locking Z position: {e}")
                    # Lock movement along Z (axis_lock == 2)
                    if self.axis_lock == 2:
                        try:
                            self.dragger.x = self.start_position.x
                        except Exception as e:
                            print(f"[Duplicator] Error locking X position: {e}")
        except Exception as e:
            print(f"[Duplicator] Error in update(): {e}")

    def input(self, key):
        """
        Handles input events.

        - Listens for 'shift+d' combined key to begin duplication of selected entities:
            - Duplicates each selected entity via deepcopy, copies over important attributes, disables collision,
              and stores them in self.clones.
            - Adds clones to LEVEL_EDITOR.entities and updates LEVEL_EDITOR.selection.
            - Records an undo action for 'delete entities' with indices and representations of clones.
            - Activates the plane for dragging, sets up the dragger at the mouse position, and parents clones to the dragger.
        - While the plane is active:
            - On 'left mouse up' event: finalize duplication, reparent clones back to their original parents,
              disable plane and dragger, clear clones, reset mouse traversal, hide axis gizmos, and re-render selection.
            - On 'middle mouse down' event: toggle axis lock based on the direction of the drag so far.

        Args:
            key (str): The input key event (e.g., 'left mouse up', 'middle mouse down', or character keys).

        Error handling:
        - Wraps all references to LEVEL_EDITOR, clones, mouse, etc., in try-except to prevent runtime errors from breaking input handling.
        """
        try:
            # Determine combined key (e.g., 'shift+d', 'd', etc.)
            combined_key = input_handler.get_combined_key(key)
        except Exception as e:
            print(f"[Duplicator] Error getting combined key: {e}")
            return

        # Start duplication when Shift+D is pressed and there is a selection
        try:
            selection = LEVEL_EDITOR.selection  # type: ignore
        except Exception as e:
            print(f"[Duplicator] Could not access LEVEL_EDITOR.selection: {e}")
            selection = []

        # Begin duplication process
        if combined_key == 'shift+d' and selection:
            try:
                # Close any open menus
                LEVEL_EDITOR.menu_handler.state = 'None'  # type: ignore
            except Exception as e:
                print(f"[Duplicator] Error closing menu: {e}")

            # Create an empty list to hold clones
            self.clones = []

            # Duplicate each selected entity
            for e in selection:
                try:
                    print(repr(e))
                    clone = deepcopy(e)
                    # Store the original parent to reparent later
                    clone.original_parent = e.parent
                    # Copy over display and shader attributes
                    clone.color = e.color
                    clone.shader = e.shader
                    clone.origin = e.origin
                    clone.selectable = True
                    # Copy shader inputs individually
                    for shader_key, shader_val in e._shader_inputs.items():
                        clone.set_shader_input(shader_key, shader_val)
                    # Disable collision on the clone and copy collider type
                    clone.collision = False
                    clone.collider_type = e.collider_type
                    self.clones.append(clone)
                except Exception as clone_e:
                    print(f"[Duplicator] Error duplicating entity {e}: {clone_e}")

            # Add clones to the editor's entity list and select them
            try:
                LEVEL_EDITOR.entities.extend(self.clones)  # type: ignore
                LEVEL_EDITOR.selection = self.clones  # type: ignore
            except Exception as e:
                print(f"[Duplicator] Error adding clones to LEVEL_EDITOR: {e}")

            # Record an undo action to delete the newly created entities if undone
            try:
                indices = [LEVEL_EDITOR.entities.index(en) for en in self.clones]  # type: ignore
                representations = [repr(en) for en in self.clones]
                LEVEL_EDITOR.current_scene.undo.record_undo(  # type: ignore
                    ('delete entities', indices, representations)
                )  # type: ignore
            except Exception as e:
                print(f"[Duplicator] Error recording undo for clones: {e}")

            # Prepare the plane and dragger for positioning the clones
            try:
                # Use the last clone's position as a reference point
                self.clone_from_position = self.clones[-1].position
                # Position the plane at the same Y level as the clone to ensure the dragger is on the same plane
                self.plane.y = LEVEL_EDITOR.selection[-1].world_y  # type: ignore
                self.plane.enabled = True
            except Exception as e:
                print(f"[Duplicator] Error activating plane for dragging: {e}")

            try:
                # Direct mouse raycasts to the plane so we can pick a point on it
                mouse.traverse_target = self.plane
                mouse.update()
                self.start_position = mouse.world_point
                # Move the dragger to the starting world point and enable it
                self.dragger.world_position = self.start_position
                self.dragger.enabled = True
                # Reset axis lock
                self.axis_lock = None
            except Exception as e:
                print(f"[Duplicator] Error setting up dragger: {e}")

            # Parent all clones to the dragger, so they follow the dragger's movement
            for e in LEVEL_EDITOR.selection:  # type: ignore
                try:
                    e.world_parent = self.dragger
                except Exception as e:
                    print(f"[Duplicator] Error parenting clone {e} to dragger: {e}")

        # Finalize duplication on left mouse release once the plane is active
        elif self.plane and self.plane.enabled and key == 'left mouse up':
            # Reparent clones back to their original parents
            for e in getattr(self, 'clones', []):
                try:
                    e.world_parent = e.original_parent
                except Exception as e:
                    print(f"[Duplicator] Error reparenting clone {e}: {e}")

            # Disable plane and dragger
            try:
                self.plane.enabled = False
                self.dragger.enabled = False
            except Exception as e:
                print(f"[Duplicator] Error disabling plane or dragger: {e}")

            # Clear clone list
            self.clones = []
            try:
                mouse.traverse_target = scene
            except Exception as e:
                print(f"[Duplicator] Error resetting mouse traverse target: {e}")

            # Hide all axis lock gizmos
            try:
                for gizmo in self.axis_lock_gizmos:
                    gizmo.disable()
            except Exception as e:
                print(f"[Duplicator] Error disabling axis lock gizmos: {e}")

            # Re-render the selection highlight in the editor
            try:
                LEVEL_EDITOR.render_selection()  # type: ignore
            except Exception as e:
                print(f"[Duplicator] Error re-rendering selection: {e}")

        # Handle middle mouse to toggle axis lock while dragging
        elif self.plane and self.plane.enabled and key == 'middle mouse down':
            try:
                if self.axis_lock is None:
                    # Calculate absolute delta since drag start in each axis
                    dx = abs(self.dragger.x - self.start_position.x)
                    dy = abs(self.dragger.y - self.start_position.y)
                    dz = abs(self.dragger.z - self.start_position.z)
                    delta_position = (dx, dy, dz)
                    max_val = max(delta_position)
                    # Lock to the axis with the greatest movement
                    self.axis_lock = delta_position.index(max_val)
                    # Move gizmos to the world position of the last clone for visibility
                    for gizmo in self.axis_lock_gizmos:
                        gizmo.world_position = self.clones[-1].world_position
                else:
                    # Unlock if already locked
                    self.axis_lock = None
            except Exception as e:
                print(f"[Duplicator] Error toggling axis lock: {e}")


class SunHandler(Entity):
    """
    SunHandler manages a directional light ("sun") in the level editor, allowing for dynamic updating of its
    bounding volume and toggling behavior via input. It automatically attaches a high-resolution shadow map
    and orients the light to a default direction.
    """

    def __init__(self, **kwargs):
        """
        Initializes the SunHandler instance.

        - Attaches this entity to LEVEL_EDITOR as its parent (so it is part of the editor hierarchy).
        - Creates a DirectionalLight (`self.sun`) with a 2048×2048 shadow map resolution for high-quality shadows.
        - Orients the light to look at a default direction (Vec3(-2, -1, -1)).

        Error handling:
        - Wraps access to LEVEL_EDITOR and creation of DirectionalLight in try-except to log any initialization failures.
        """
        try:
            super().__init__(parent=LEVEL_EDITOR, **kwargs)  # type: ignore
        except Exception as e:
            print(f"[SunHandler] Error attaching to LEVEL_EDITOR: {e}")
            super().__init__(**kwargs)

        try:
            # Create a directional light with high-resolution shadows
            self.sun = DirectionalLight(shadow_map_resolution=(2048, 2048))
            # Orient the sun toward a default vector so it casts light diagonally downward
            self.sun.look_at(Vec3(-2, -1, -1))
        except Exception as e:
            print(f"[SunHandler] Error creating or orienting DirectionalLight: {e}")
            # As a fallback, attempt to create a default light without shadow settings
            try:
                self.sun = DirectionalLight()
                self.sun.look_at(Vec3(-2, -1, -1))
            except Exception as inner_e:
                print(f"[SunHandler] Fallback creation of DirectionalLight failed: {inner_e}")

    def update_bounds(self, entity=None):
        """
        Updates the bounding volume of the sun's shadow frustum to encompass the given entity (or the entire scene
        if no entity is provided). This ensures that shadows are computed for the relevant region.

        Args:
            entity (Entity, optional): The entity whose bounds will be used to update the sun's shadow frustum.
                                       If None, uses the root of the current scene.

        Behavior:
        - If `entity` is None:
            - Attempts to retrieve LEVEL_EDITOR.current_scene.scene_parent as the root entity.
            - If no current_scene exists, returns early.
        - Calls `self.sun.update_bounds(entity)` to recalculate shadow-casting bounds.

        Error handling:
        - If LEVEL_EDITOR.current_scene or scene_parent is missing, logs a message and returns without error.
        - Wraps the call to `self.sun.update_bounds` in try-except to catch any runtime errors.
        """
        try:
            # If no specific entity is provided, attempt to use the root of the current scene
            if entity is None:
                if not getattr(LEVEL_EDITOR, 'current_scene', None):  # type: ignore
                    print("[SunHandler] No current scene found; cannot update bounds.")
                    return
                entity = LEVEL_EDITOR.current_scene.scene_parent  # type: ignore

            # Update the sun's shadow frustum to cover the given entity
            try:
                self.sun.update_bounds(entity)
            except Exception as e:
                print(f"[SunHandler] Error calling sun.update_bounds on {entity}: {e}")
        except Exception as e:
            print(f"[SunHandler] Error determining entity for update_bounds: {e}")

    def input(self, key):
        """
        Handles input events for the SunHandler.

        Args:
            key (str): The input key event. Listening specifically for 'l' to toggle or update the sun.

        Behavior:
        - If the 'l' key is pressed, prints a debug message and calls `self.update_bounds()` to refresh shadow bounds.

        Error handling:
        - Wraps the key check and subsequent call in try-except to avoid crashes if `self.update_bounds` fails.
        """
        try:
            if key == 'l':
                print('toggle sun')
                self.update_bounds()
        except Exception as e:
            print(f"[SunHandler] Error processing input '{key}': {e}")


from ursina.prefabs.radial_menu import RadialMenu
class RightClickMenu(Entity):
    """
    RightClickMenu provides a context-sensitive radial menu when the user right-clicks on a selected entity
    in the level editor. It displays options such as changing model, texture, color, shader, deleting the entity,
    or modifying collider settings. The menu appears only if the right-click is a click (i.e., minimal mouse movement)
    and the hovered entity is part of the current selection.
    """

    def __init__(self):
        """
        Initializes the RightClickMenu instance.

        - Attaches this entity to the LEVEL_EDITOR UI as its parent.
        - Creates a RadialMenu with buttons for various actions (Model, Tex, Col, Sh, del, Coll).
          Each button is configured with an on_click callback to the appropriate LEVEL_EDITOR handler.
        - Starts with the radial menu disabled; it will be enabled on a valid right-click event.

        Error handling:
        - Wraps the creation of the RadialMenu and its buttons in try-except blocks to catch any errors
          (e.g., missing LEVEL_EDITOR attributes, mouse references). Logs errors without breaking the application.
        """
        try:
            super().__init__(parent=LEVEL_EDITOR.ui)  # type: ignore
        except Exception as e:
            print(f"[RightClickMenu] Error attaching to LEVEL_EDITOR.ui: {e}")
            super().__init__()  # Fall back to default parent

        # Attempt to create the radial menu and its buttons
        try:
            self.radial_menu = RadialMenu(
                parent=LEVEL_EDITOR.ui,  # type: ignore
                buttons=(
                    # Button to open the Model menu
                    Button(
                        highlight_color=color.azure,
                        model='circle',
                        text='Model',
                        scale=1.5,
                        on_click=Func(setattr, LEVEL_EDITOR.menu_handler, 'state', 'model_menu')  # type: ignore
                    ),
                    # Button to open the Texture menu, and set target_attr to 'texture'
                    Button(
                        highlight_color=color.azure,
                        model='circle',
                        text='Tex',
                        scale=1.5,
                        on_click=Sequence(
                            Func(setattr, LEVEL_EDITOR.menu_handler, 'state', 'texture_menu'),  # type: ignore
                            Func(setattr, LEVEL_EDITOR.texture_menu, 'target_attr', 'texture')  # type: ignore
                        )
                    ),
                    # Button to open the Color menu, positioning it at the current mouse position
                    Button(
                        highlight_color=color.azure,
                        model='circle',
                        text='Col',
                        scale=1.5,
                        on_click=Sequence(
                            Func(setattr, LEVEL_EDITOR.menu_handler, 'state', 'color_menu'),  # type: ignore
                            Func(setattr, LEVEL_EDITOR.color_menu, 'position', mouse.position)  # type: ignore
                        )
                    ),
                    # Button to open the Shader menu
                    Button(
                        highlight_color=color.azure,
                        model='circle',
                        text='Sh',
                        scale=1.5,
                        on_click=Func(setattr, LEVEL_EDITOR.menu_handler, 'state', 'shader_menu')  # type: ignore
                    ),
                    # Button to delete the selected entity(ies)
                    Button(
                        highlight_color=color.black,
                        model='circle',
                        text='del',
                        scale=.75,
                        color=color.red,
                        on_click=LEVEL_EDITOR.deleter.delete_selected  # type: ignore
                    ),
                    # Button for "Coll" (collider) – currently a placeholder without callback
                    Button(
                        highlight_color=color.azure,
                        model='circle',
                        text='Coll',
                        scale=1.5
                    ),
                ),
                enabled=False,  # Start hidden; enabled on right-click
                scale=.05
            )

            # After creating self.radial_menu
            self.radial_menu._init_w, self.radial_menu._init_h = window.size
            h = self.radial_menu._init_h or 1
            self.radial_menu._base_ui_scale = (20 / h) * 2  # 80px diameter, adjust as needed
            self.radial_menu.scale = self.radial_menu._base_ui_scale
            
            # Optionally, scale each button if you want them to scale individually:
            for button in self.radial_menu.buttons:
                button._init_w, button._init_h = window.size
                button._base_ui_scale = (240 / h) * 2  # 24px diameter, adjust as needed
                button.scale = button._base_ui_scale

        except Exception as e:
            print(f"[RightClickMenu] Error creating RadialMenu: {e}")
            self.radial_menu = None

    def input(self, key):
        """
        Handles input events related to right-clicking.

        - On 'right mouse down', records the mouse position (to detect click vs. drag).
        - On 'right mouse up', checks if:
            1. There is at least one entity currently selected.
            2. The mouse has not moved more than a small threshold since right mouse down.
            3. The currently hovered entity (if any) is part of the selection.
          If all conditions hold, enables the radial menu so it appears under the mouse.

        Args:
            key (str): The input key event (e.g., 'right mouse down', 'right mouse up').

        Error handling:
        - Wraps references to LEVEL_EDITOR, mouse, and self.radial_menu in try-except blocks to prevent
          unexpected missing attributes or NoneType errors from crashing the application.
        """
        # Record the starting mouse position when right mouse button is pressed
        if key == 'right mouse down':
            try:
                self.start_click_pos = mouse.position
            except Exception as e:
                print(f"[RightClickMenu] Error recording start_click_pos: {e}")
                self.start_click_pos = None

        # Detect a right-click release to show the radial menu
        if key == 'right mouse up':
            try:
                # Ensure we have a valid starting position recorded
                if not hasattr(self, 'start_click_pos') or self.start_click_pos is None:
                    return

                # Conditions to open the radial menu:
                # 1. There is a selection in the LEVEL_EDITOR
                # 2. Mouse movement since right-down is minimal (i.e., a click, not a drag)
                # 3. The hovered entity is part of the current selection
                selection_exists = bool(LEVEL_EDITOR.selection)  # type: ignore
                movement_delta = mouse.position - self.start_click_pos
                moved_distance = sum(abs(e) for e in movement_delta)
                hovered_entity = LEVEL_EDITOR.selector.get_hovered_entity()  # type: ignore

                if selection_exists and moved_distance < .005 and hovered_entity in LEVEL_EDITOR.selection:  # type: ignore
                    if self.radial_menu:
                        self.radial_menu.enabled = True
            except Exception as e:
                print(f"[RightClickMenu] Error processing right mouse up: {e}")
                # If anything goes wrong, ensure the radial menu does not unintentionally enable
                if self.radial_menu:
                    self.radial_menu.enabled = False


class Search(Entity):
    """
    Search provides a simple input field that appears when the user presses the space bar while one or more entities
    are selected in the level editor. It allows the user to type search queries (or other commands) into the input field.

    Attributes:
        input_field (InputField): The text input field that is shown or hidden based on user input.
    """

    def __init__(self, **kwargs):
        """
        Initializes the Search instance.

        - Attaches this entity to LEVEL_EDITOR.ui as its parent so that it is part of the editor's UI hierarchy.
        - Creates an InputField that is initially disabled (hidden). This field is activated when the user presses space
          while entities are selected.

        Error handling:
        - Wraps access to LEVEL_EDITOR.ui in a try-except block to avoid crashes if LEVEL_EDITOR or its UI is missing.
        - Wraps the creation of InputField to log errors if construction fails.
        """
        try:
            super().__init__(parent=LEVEL_EDITOR.ui, **kwargs)  # type: ignore
        except Exception as e:
            print(f"[Search] Error attaching to LEVEL_EDITOR.ui: {e}")
            # Fall back to no parent so the entity still exists
            super().__init__(**kwargs)

        try:
            # Create the input field, but keep it disabled until space is pressed
            self.input_field = InputField(parent=LEVEL_EDITOR.ui, enabled=False)  # type: ignore

            # After creating self.input_field
            self.input_field._init_w, self.input_field._init_h = window.size
            h = self.input_field._init_h or 1
            self.input_field._base_ui_scale = (20 / h) * 2  # 20px height, adjust as needed
            self.input_field.scale = self.input_field._base_ui_scale

        except Exception as e:
            print(f"[Search] Error creating InputField: {e}")
            self.input_field = None

    def input(self, key):
        """
        Handles keyboard input for the Search functionality.

        Args:
            key (str): The key event that was pressed by the user.

        Behavior:
        - When the 'space' key is pressed and there is at least one entity currently selected, enable the input field
          and clear any existing text, allowing the user to begin typing.
        - Additional logic (commented out) could handle other single-character inputs if needed.

        Error handling:
        - Wraps access to LEVEL_EDITOR.selection in a try-except block to avoid errors if LEVEL_EDITOR or selection is missing.
        - Checks that the input_field exists before attempting to modify its properties.
        """
        try:
            # Only show the input field if the space bar is pressed and there is a selection
            if key == 'space' and getattr(LEVEL_EDITOR, 'selection', None):  # type: ignore
                if self.input_field:
                    try:
                        self.input_field.enabled = True   # Make the input field visible and focusable
                        self.input_field.text = ''       # Clear any existing text
                    except Exception as field_e:
                        print(f"[Search] Error enabling or clearing InputField: {field_e}")
        except Exception as e:
            # Log unexpected errors when checking the selection or key
            print(f"[Search] Error processing input '{key}': {e}")

        # Placeholder for additional input handling (e.g., printing the current text on any single-character key)
        # elif len(key) == 1:
        #     try:
        #         print('---', self.input_field.text)
        #     except Exception as e:
        #         print(f"[Search] Error accessing input_field.text: {e}")


def get_major_axis_relative_to_view(entity):
    """
    Determine which principal axis of an entity (right, up, or forward) is most aligned with the camera's viewing direction.

    This function computes the dot products between the camera's back vector and the entity's local axes:
    - entity.right  (X-axis)
    - entity.up     (Y-axis)
    - entity.forward(X-axis)

    It rounds each dot product to one decimal place, then selects the axis whose absolute dot value is largest,
    indicating that, relative to the camera, that axis is closest to facing the viewer.

    Args:
        entity (Entity): The entity whose local axes ('right', 'up', 'forward') are used for alignment tests.

    Returns:
        tuple:
            - axis_index (int): 
                0 if the entity's right axis is the primary axis relative to the view (i.e., left/right),
                1 if the up axis is primary (i.e., top/bottom),
                2 if the forward axis is primary (i.e., front/back).
            - is_positive_direction (bool): 
                True if the dot product along the chosen axis is positive (the axis points toward the camera back vector),
                False if negative (it points away).

    Error Handling:
        - If any required attribute is missing or any dot product calculation fails, a message is printed, and the function
          returns (None, False). This ensures the caller can handle missing or invalid data gracefully without crashing.
    """
    try:
        # Compute the dot product between camera.back and each local axis, rounding to one decimal place.
        r = round(camera.back.dot(entity.right), 1)
        u = round(camera.back.dot(entity.up), 1)
        f = round(camera.back.dot(entity.forward), 1)

        # Put them in a tuple so we can find the index of the maximal absolute value.
        dir = (r, u, f)

        # Determine which axis has the largest absolute alignment value.
        axis_index = dir.index(max(dir, key=abs))

        # Determine if that dot product is positive (axis points toward camera.back).
        is_positive_direction = dir[axis_index] > 0

        return axis_index, is_positive_direction

    except Exception as e:
        # If any attribute is missing or dot fails, log the error for debugging.
        print(f"[get_major_axis_relative_to_view] Error computing major axis: {e}")
        return None, False


if __name__ == '__main__':
    """
    Entry point for running the level editor as a standalone application.

    This script sets up the Ursina application, defines a simple Tree prefab,
    initializes the LevelEditor, registers additional classes for spawnable prefabs,
    and starts the application loop.
    """

    # Attempt to import the Ursina engine; exit if unavailable
    try:
        from ursina import *
    except ImportError as e:
        print(f"[main] Failed to import Ursina engine: {e}")
        import sys
        sys.exit(1)

    # Create the main Ursina application (disable vsync for performance testing)
    try:
        app = Ursina(vsync=False)
    except Exception as e:
        print(f"[main] Error creating Ursina application: {e}")
        import sys
        sys.exit(1)

    class Tree(Entity):
        """
        Tree prefab class consisting of a brown trunk cube (self) and a green top cube (self.top).

        When instantiated, the top cube (representing foliage) is appended to LEVEL_EDITOR.entities
        so that it can be selected and manipulated in the level editor.
        """

        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            # Configure the trunk
            self.model = 'cube'
            self.color = color.brown

            # Create the tree top as a child entity and position it above the trunk
            self.top = Entity(
                name='tree_top',
                parent=self,
                y=1.5,
                model='cube',
                color=color.green,
                selectable=True
            )

            # Append the top entity to LEVEL_EDITOR.entities for selection
            try:
                LEVEL_EDITOR.entities.append(self.top)  # type: ignore
            except Exception as e:
                print(f"[Tree] Could not append tree top to LEVEL_EDITOR.entities: {e}")

    # Initialize the LevelEditor
    try:
        level_editor = LevelEditor()
    except Exception as e:
        print(f"[main] Error creating LevelEditor: {e}")
        import sys
        sys.exit(1)

    # Register additional classes for the class_menu so they can be spawned in-editor
    try:
        from ursina.prefabs.first_person_controller import FirstPersonController
        # Extend the available_classes dictionary with new prefab options
        level_editor.class_menu.available_classes |= {
            'WhiteCube': WhiteCube,
            'EditorCamera': EditorCamera,
            'FirstPersonController': FirstPersonController
        }
    except Exception as e:
        print(f"[main] Error registering additional classes: {e}")

    # Optionally apply a screen-space ambient occlusion shader to the main camera
    try:
        from ursina.shaders import ssao_shader
        # Uncomment the following lines to tweak camera settings or apply the SSAO shader:
        # camera.clip_plane_far = 100
        # camera.clip_plane_near = 1
        # camera.shader = ssao_shader
    except Exception as e:
        print(f"[main] Could not import ssao_shader: {e}")

    # Run the application loop
    try:
        app.run()
    except Exception as e:
        print(f"[main] Unexpected error during app.run(): {e}")
