from ursina.editor.level_editor import *
from ursina.shaders import colored_lights_shader
from ursina.scripts.property_generator import generate_properties_for_class


@generate_properties_for_class()
class PokeShape(Entity):
    """
    Editor entity for creating and editing a 2D polygonal shape with optional walls (poke shape) in the Ursina Level Editor.

    Attributes:
        default_values (dict): Default property values combined with Entity defaults, including:
            - name (str): Default entity name.
            - wall_height (float): Height of the generated walls.
            - subdivisions (int): Number of smoothing subdivisions to apply to the polygon.
            - smoothing_distance (float): Interpolation distance when smoothing.
            - points (list[Vec3]): Initial list of control-point positions (Vec3) defining the base polygon.
            - collider_type (str): Type of collider to apply ('None', etc.).
            - texture (str): Default texture for the mesh.
            - texture_scale (Vec2): UV scaling factor for texture mapping.
        gizmo_color (color): Color used for gizmo handles when editing.
        ready (bool): Indicates whether initial generation is complete.
        _point_gizmos (LoopingList[Entity]): Gizmo entities representing polygon vertices.
        add_new_point_renderer (Entity): Temporary renderer showing potential new point positions.
        add_collider (bool): Whether to add a collider to the mesh.
        _wall_parent (Entity | None): Parent entity for generated wall mesh, if any.
        wall_height (float): Height for wall extrusion.
        subdivisions (int): Number of smoothing passes for polygon edges.
        smoothing_distance (float): Interpolation factor for smoothing.
        texture (str): Texture name applied to the mesh.
        position (Vec3): World position of this entity.
        edit_mode (bool): Whether the shape is currently in edit mode.
    """

    default_values = Entity.default_values | dict(
        name='poke_shape',
        # make_wall=True,
        wall_height=1.0,
        # wall_thickness=.1,
        subdivisions=0,
        smoothing_distance=0.1,
        points=[Vec3(-0.5, 0, -0.5),
                Vec3(0.5, 0, -0.5),
                Vec3(0.5, 0, 0.5),
                Vec3(-0.5, 0, 0.5)],
        collider_type='None',
        texture='grass',
        texture_scale=Vec2(0.125, 0.125),
        # shader_inputs={'side_texture':Func(load_texture, 'grass'), }
    )  # combine dicts

    gizmo_color = color.violet

    def __init__(self, edit_mode=False, **kwargs):
        """
        Initialize a new PokeShape.

        Args:
            edit_mode (bool): Whether to start in edit mode (default False).
            **kwargs: Property overrides, merged with default_values. Recognized keys include:
                - points (list[Vec3]): Initial control-point positions.
                - wall_height (float): Height for walls.
                - subdivisions (int): Number of smoothing subdivisions.
                - smoothing_distance (float): Interpolation factor for smoothing.
                - texture (str): Texture name.
                - texture_scale (Vec2): UV scaling.
                - position (Vec3): Entity world position.
                - Any other Entity parameters (e.g., scale, rotation).

        Raises:
            TypeError: If 'points' is provided and is not a list of Vec3.
            RuntimeError: If LEVEL_EDITOR is not initialized or required attributes are missing.
        """
        # Merge provided kwargs with the class default values
        try:
            # __class__ refers to PokeShape
            merged = __class__.default_values | kwargs
        except Exception as e:
            raise RuntimeError(f"Failed to merge default properties: {e}") from e

        # Extract control-point list from merged properties, if present
        points = merged.pop('points', None)

        # Mark as not yet fully generated
        self.ready = False

        # Call base Entity constructor with remaining properties (including name, position, texture, etc.)
        try:
            super().__init__(**merged)
        except Exception as e:
            raise RuntimeError(f"Failed to initialize base Entity: {e}") from e

        # Ensure LEVEL_EDITOR exists and has expected attributes for gizmo management
        # if 'LEVEL_EDITOR' not in globals() or not hasattr(LEVEL_EDITOR, 'entities'): # type: ignore
        #     raise RuntimeError("LEVEL_EDITOR is not initialized or missing required attributes.")

        # Set parent to LEVEL_EDITOR so this entity participates in the editor
        self.original_parent = LEVEL_EDITOR # type: ignore
        self.selectable = True
        self.highlight_color = color.blue

        # Initialize an empty list to hold gizmo handles for each polygon vertex
        self._point_gizmos = []

        # Create a Mesh model placeholder for the base polygon
        try:
            self.model = Mesh()
        except Exception as e:
            raise RuntimeError(f"Failed to create Mesh for PokeShape: {e}") from e

        # Create a renderer entity for showing potential new point locations (points between edges)
        try:
            self.add_new_point_renderer = Entity(
                model=Mesh(mode='point', vertices=[], thickness=0.075),
                color=color.white,
                alpha=0.5,
                texture='circle',
                unlit=True,
                is_gizmo=True,
                selectable=False,
                enabled=False,
                always_on_top=True
            )
        except Exception as e:
            raise RuntimeError(f"Failed to create add_new_point_renderer entity: {e}") from e

        # Initialize wall-related fields
        self.add_collider = False
        self._wall_parent = None

        # Set wall and smoothing parameters from merged properties
        try:
            self.wall_height = merged['wall_height']
            self.subdivisions = merged['subdivisions']
            self.smoothing_distance = merged['smoothing_distance']
        except KeyError as e:
            raise RuntimeError(f"Missing expected property {e} in initialization.") from e

        # Assign initial control-point gizmos based on provided 'points' or defaults
        if not points:
            # Use default four-corner square if 'points' was not provided
            self.points = __class__.default_values['points']
        else:
            # Validate provided points
            if not isinstance(points, list) or not all(isinstance(p, Vec3) for p in points):
                raise TypeError("'points' must be a list of Vec3 instances.")
            self.points = points

        # Apply other Entity default attributes (excluding 'model', which is already set)
        for key in Entity.default_values.keys():
            if key == 'model':
                continue
            # Only set attributes present in merged if they were part of default_values or kwargs
            if key in merged:
                try:
                    setattr(self, key, merged[key])
                except Exception as e:
                    raise RuntimeError(f"Failed to set attribute '{key}' on PokeShape: {e}") from e

        # Enter edit mode if requested
        self.edit_mode = edit_mode

        # Generate the initial mesh and walls
        try:
            self.generate()
        except Exception as e:
            raise RuntimeError(f"PokeShape initial generation failed: {e}") from e

        # Mark as fully ready
        self.ready = True

    def draw_inspector(self):
        """
        Provide a mapping of editable properties for the inspector GUI.

        Returns:
            dict: Keys are property names; values are Python types for UI widgets.
                  Example: {'edit_mode': bool, 'wall_height': float, ...}
        """
        return {
            'edit_mode': bool,
            'wall_height': float,
            'subdivisions': int,
            'smoothing_distance': float
        }

    def generate(self):
        """
        Generate or update the polygon mesh and optional wall extrusion.

        Steps:
            1. Clean up any deleted gizmo references from _point_gizmos.
            2. Build a 2D LoopingList of Vec2 from gizmo positions to represent the polygon.
            3. If subdivisions > 0, apply smoothing by linear interpolation between neighbors.
            4. Triangulate the polygon using ear clipping (tripy.earclip).
            5. Construct 3D vertices (Vec3) from the 2D triangles and assign them to self.model.
            6. Set UVs and normals for the mesh and call generate() on the mesh to upload to GPU.
            7. If wall_height > 0, build a wall mesh by extruding edges downward and assign to _wall_parent.
            8. If edit_mode is True, compute midpoints of each edge and update add_new_point_renderer vertices.

        Raises:
            RuntimeError: If any step of mesh or wall generation fails.
        """
        try:
            import tripy
        except ImportError as e:
            raise RuntimeError(f"Failed to import tripy for triangulation: {e}") from e

        # Step 1: Remove any None references (deleted gizmos) from the list
        self._point_gizmos = LoopingList([e for e in self._point_gizmos if e])

        # Step 2: Build a 2D polygon from gizmo positions (xz-plane)
        try:
            polygon = LoopingList(
                Vec2(*e.get_position(relative_to=self).xz) for e in self._point_gizmos
            )
        except Exception as e:
            raise RuntimeError(f"Failed to construct 2D polygon from gizmos: {e}") from e

        # Step 3: Apply smoothing subdivisions if requested
        if self.subdivisions:
            try:
                for _ in range(self.subdivisions):
                    smooth_polygon = LoopingList()
                    for i, p in enumerate(polygon):
                        # Interpolate towards previous and next points
                        smooth_polygon.append(lerp(p, polygon[i - 1], self.smoothing_distance))
                        smooth_polygon.append(lerp(p, polygon[i + 1], self.smoothing_distance))
                    polygon = smooth_polygon
            except Exception as e:
                raise RuntimeError(f"Error during smoothing subdivisions: {e}") from e

        # Step 4: Triangulate the polygon using ear clipping
        try:
            triangles = tripy.earclip(polygon)
        except Exception as e:
            raise RuntimeError(f"Triangulation (earclip) failed: {e}") from e

        # Step 5: Build mesh vertices from triangulated 2D data (set y = 0 for flat base)
        try:
            self.model.vertices = []
            for tri in triangles:
                for v in tri:
                    self.model.vertices.append(Vec3(v[0], 0, v[1]))
        except Exception as e:
            raise RuntimeError(f"Failed to construct mesh vertices from triangles: {e}") from e

        # Step 6: Assign UVs and normals, then generate mesh data
        try:
            # Simple UV mapping: use xz components for UV
            self.model.uvs = [Vec2(v[0], v[2]) * 1 for v in self.model.vertices]
            # Flat upward normals for all vertices
            self.model.normals = [Vec3(0, 1, 0) for _ in range(len(self.model.vertices))]
            # Upload vertex/normal/UV data to GPU
            self.model.generate()
        except Exception as e:
            raise RuntimeError(f"Failed to assign UVs/normals or generate mesh: {e}") from e

        # Step 7: Build or update the wall extrusion if wall_height is non-zero
        try:
            # If an old wall parent exists, destroy it and reset
            if self._wall_parent:
                destroy(self._wall_parent)
                self._wall_parent = None

            if self.wall_height:
                # Create new parent entity for walls if missing
                if not self._wall_parent:
                    self._wall_parent = Entity(
                        parent=self,
                        model=Mesh(),
                        color=color.dark_gray,
                        add_to_scene_entities=False,
                        shader=colored_lights_shader
                    )

                # Build wall vertices by extruding each edge downward
                wall_verts = []
                for i, vert2d in enumerate(polygon):
                    # Base vertex at y=0
                    vert = Vec3(vert2d[0], 0, vert2d[1])
                    # Next vertex for edge
                    next_vert2d = polygon[i + 1]
                    next_vert = Vec3(next_vert2d[0], 0, next_vert2d[1])

                    # Two triangles per quad (six vertices) for wall face
                    wall_verts.extend((
                        vert,
                        vert + Vec3(0, -self.wall_height, 0),
                        next_vert,
                        next_vert,
                        vert + Vec3(0, -self.wall_height, 0),
                        next_vert + Vec3(0, -self.wall_height, 0),
                    ))

                # Assign vertices to wall mesh and generate normals and data
                self._wall_parent.model.vertices = wall_verts
                # Generate normals automatically or skip smoothing
                self._wall_parent.model.generate_normals(False)
                self._wall_parent.model.generate()
        except Exception as e:
            raise RuntimeError(f"Failed to generate or update wall mesh: {e}") from e

        # Step 8: If in edit mode, compute midpoints of each edge for potential new points
        if self.edit_mode:
            try:
                # Clear previous midpoints
                self.add_new_point_renderer.model.vertices = []
                for i, e in enumerate(self._point_gizmos):
                    # Compute midpoint between vertex i and i+1 (wrap-around)
                    midpoint = lerp(
                        self._point_gizmos[i].world_position,
                        self._point_gizmos[i + 1].world_position,
                        0.5
                    )
                    self.add_new_point_renderer.model.vertices.append(midpoint)
                # Upload new point vertices to GPU
                self.add_new_point_renderer.model.generate()
            except Exception as e:
                raise RuntimeError(f"Failed to update add_new_point_renderer vertices: {e}") from e

    def __deepcopy__(self, memo):
        """
        Create a deep copy of this PokeShape using its get_changes() representation.

        Returns:
            PokeShape: A new instance with the same property changes applied.

        Raises:
            RuntimeError: If copying fails due to missing methods or invalid data.
        """
        try:
            # Extract dictionary of property changes relative to default_values
            changes = self.get_changes(__class__)
        except Exception as e:
            raise RuntimeError(f"Failed to get changes for deepcopy: {e}") from e

        try:
            # Create a new instance with the same changes, preserving texture_scale
            _copy = __class__(texture_scale=self.texture_scale, **changes)
            _copy.texture_scale = self.texture_scale
            return _copy
        except Exception as e:
            raise RuntimeError(f"Failed to construct deepcopy of PokeShape: {e}") from e

    def points_getter(self):
        """
        Getter for the 'points' property representing control-point positions.

        Returns:
            list[Vec3]: Current local positions of each gizmo point.
        """
        return [e.position for e in self._point_gizmos]

    def points_setter(self, value):
        """
        Setter for the 'points' property.

        - Destroys existing gizmo entities.
        - Creates new gizmos at specified positions.
        - Registers gizmos with LEVEL_EDITOR.entities for selection.

        Args:
            value (list[Vec3]): List of Vec3 positions for new control points.

        Raises:
            TypeError: If 'value' is not a list of Vec3.
            RuntimeError: If gizmo creation or destruction fails.
        """
        # Validate input list
        if not isinstance(value, list) or not all(isinstance(p, Vec3) for p in value):
            raise TypeError("'points' must be set to a list of Vec3 instances.")

        # Destroy existing gizmo entities
        try:
            [destroy(e) for e in self._point_gizmos]
        except Exception as e:
            raise RuntimeError(f"Failed to destroy existing gizmo entities: {e}") from e

        # Create new gizmo entities for each provided position
        try:
            self._point_gizmos = LoopingList([
                Entity(
                    parent=self,
                    original_parent=self,
                    position=e,
                    selectable=False,
                    name='PokeShape_point',
                    is_gizmo=True,
                    enabled=False
                ) for e in value
            ])
        except Exception as e:
            raise RuntimeError(f"Failed to create new gizmo entities: {e}") from e

        # Register each new gizmo with the level editor so they appear in the scene
        try:
            LEVEL_EDITOR.entities.extend(self._point_gizmos) # type: ignore
        except Exception as e:
            raise RuntimeError(f"Failed to register gizmos with LEVEL_EDITOR: {e}") from e

    def edit_mode_getter(self):
        """
        Getter for the 'edit_mode' property.

        Returns:
            bool: True if in edit mode; False otherwise.
        """
        return getattr(self, '_edit_mode', False)

    def edit_mode_setter(self, value):
        """
        Setter for the 'edit_mode' property.

        Toggles the ability to edit polygon vertices:
         - When entering edit mode:
            * Disable selection on all other LEVEL_EDITOR.entities.
            * Add this shape's gizmos to LEVEL_EDITOR.entities and make them selectable.
            * Disable Y-axis movement on global gizmos to restrict edit to XZ plane.
            * Enable the add_new_point_renderer to show midpoints for adding new vertices.
            * Remove any existing collider so it does not interfere with editing.
         - When exiting edit mode:
            * Remove gizmos from LEVEL_EDITOR.entities.
            * Restore selection on all remaining LEVEL_EDITOR.entities.
            * If any gizmo was selected on exit, reselect this PokeShape.
            * Re-enable Y-axis movement on global gizmos.
            * Disable the add_new_point_renderer visuals.
            * Restore collider to 'mesh' so the shape can be used in the scene.

        Args:
            value (bool): True to enter edit mode; False to exit.

        Raises:
            TypeError: If `value` is not a boolean.
        """
        if not isinstance(value, bool):
            raise TypeError("edit_mode must be set to a boolean value.")

        # Store mode flag
        self._edit_mode = value

        # Debug print
        print('set edit mode', value)

        if value:
            # Entering edit mode
            # Disable selection on all other entities in the editor
            for e in LEVEL_EDITOR.entities: # type: ignore
                if e is not self:
                    setattr(e, 'selectable', False)

            # Add each gizmo to LEVEL_EDITOR.entities if not already present, and make selectable
            for gizmo in self._point_gizmos:
                if gizmo not in LEVEL_EDITOR.entities: # type: ignore
                    LEVEL_EDITOR.entities.append(gizmo) # type: ignore
                setattr(gizmo, 'selectable', True)

            # Disable Y-axis on the global gizmo to restrict dragging to XZ plane
            try:
                LEVEL_EDITOR.gizmo.subgizmos['y'].enabled = False # type: ignore
                LEVEL_EDITOR.gizmo.fake_gizmo.subgizmos['y'].enabled = False # type: ignore
            except Exception:
                # If global gizmo is not available, ignore
                pass

            # Show midpoints for adding new points
            self.add_new_point_renderer.enabled = True

            # Remove collider so it does not interfere with editing
            self.collider = None
        else:
            # Exiting edit mode
            # Remove each gizmo from LEVEL_EDITOR.entities
            for gizmo in list(self._point_gizmos):
                if gizmo in LEVEL_EDITOR.entities: # type: ignore
                    LEVEL_EDITOR.entities.remove(gizmo) # type: ignore

            # Restore selection on all remaining entities
            for e in LEVEL_EDITOR.entities: # type: ignore
                setattr(e, 'selectable', True)

            # If any gizmo was selected at exit, reselect the PokeShape itself
            if any(gizmo in LEVEL_EDITOR.selection for gizmo in self._point_gizmos): # type: ignore
                LEVEL_EDITOR.selection = [self] # type: ignore

            # Re-enable Y-axis on the global gizmo
            try:
                LEVEL_EDITOR.gizmo.subgizmos['y'].enabled = True # type: ignore
                LEVEL_EDITOR.gizmo.fake_gizmo.subgizmos['y'].enabled = True # type: ignore
            except Exception:
                # If global gizmo is missing, ignore
                pass

            # Hide midpoint renderer
            self.add_new_point_renderer.enabled = False

            # Restore collider so the shape can interact physically
            self.collider = 'mesh'

        # Refresh selection visuals in the editor
        LEVEL_EDITOR.render_selection() # type: ignore

    points = property(points_getter, points_setter)
    edit_mode = property(edit_mode_getter, edit_mode_setter)

    def update(self):
        """
        Called every frame. If in edit mode and the left mouse is held or 'd' is pressed,
        re-render selection outlines and regenerate mesh (to reflect gizmo movement).

        Raises:
            RuntimeError: If generation fails during update.
        """
        if self.edit_mode:
            try:
                # Re-highlight selected entities
                if mouse.left or held_keys['d']:
                    LEVEL_EDITOR.render_selection() # type: ignore
                    self.generate()
            except Exception as e:
                raise RuntimeError(f"Update regeneration failed: {e}") from e

    def input(self, key):
        """
        Handle input events when this PokeShape or its gizmos are active in the editor.

        Supported keys:
            - 'tab': Toggle edit mode if this shape or any of its gizmos is selected, or exit edit mode if nothing selected.
            - 'left mouse down' or 'd' while in edit mode:
                * If no entity is currently hovered, find the closest midpoint vertex within a threshold.
                * Create a new gizmo at that midpoint, register it, and re-render selection.
                * If 'd' was pressed, forward 'd' to quick_grabber for drag-and-drop behavior.
            - 'space': Regenerate the mesh immediately.
            - '<any> up' while in edit mode: Schedule a delayed regeneration after gizmo movement.

        Args:
            key (str): The input key descriptor (e.g., 'tab', 'space', 'left mouse down', etc.).

        Raises:
            RuntimeError: If any step in the input handling fails unexpectedly.
        """
        try:
            combined_key = input_handler.get_combined_key(key)
        except Exception:
            combined_key = None  # Safely ignore if input_handler is unavailable

        # Toggle edit mode on 'tab' press
        if combined_key == 'tab':
            if not LEVEL_EDITOR.selection: # type: ignore
                # If nothing is selected, exit edit mode
                self.edit_mode = False

            # If this shape or any gizmo is selected, toggle edit mode
            if self in LEVEL_EDITOR.selection or any(g in LEVEL_EDITOR.selection for g in self._point_gizmos): # type: ignore
                self.edit_mode = not self.edit_mode

        # In edit mode, handle adding new points via left-click or 'd' key
        if self.edit_mode and (key == 'left mouse down' or key == 'd'):
            try:
                # If the editor's selector is currently hovering an entity, do nothing
                if LEVEL_EDITOR.selector.get_hovered_entity(): # type: ignore
                    return
            except Exception:
                # If selector is unavailable or fails, proceed to handle midpoints
                pass

            try:
                # Compute screen-space distances from mouse to each midpoint vertex
                points_in_range = [
                    (distance_2d(world_position_to_screen_position(v), mouse.position), v)
                    for v in self.add_new_point_renderer.model.vertices
                ]
                # Filter to only those within a small threshold
                points_in_range = [e for e in points_in_range if e[0] < 0.075 / 2]
                # Sort by distance ascending
                points_in_range.sort()
            except Exception:
                # If computation fails or there are no midpoints, do nothing
                return

            if not points_in_range:
                return

            # The closest midpoint to the mouse
            _, closest_point = points_in_range[0]
            try:
                i = self.add_new_point_renderer.model.vertices.index(closest_point)
            except ValueError:
                # If the point is not found, abort
                return

            # Create a new gizmo entity at the midpoint between vertices i and i+1
            try:
                new_point = Entity(
                    parent=self,
                    original_parent=self,
                    position=lerp(
                        self._point_gizmos[i].position,
                        self._point_gizmos[i + 1].position,
                        0.5
                    ),
                    selectable=True,
                    is_gizmo=True
                )
                LEVEL_EDITOR.entities.append(new_point) # type: ignore
                self._point_gizmos.insert(i + 1, new_point)
                LEVEL_EDITOR.render_selection() # type: ignore
            except Exception as e:
                raise RuntimeError(f"Failed to create or register new point gizmo: {e}") from e

            # If the key was 'd', forward it to the quick_grabber for immediate dragging
            if key == 'd':
                try:
                    LEVEL_EDITOR.quick_grabber.input('d') # type: ignore
                except Exception:
                    # If quick_grabber is not available, ignore
                    pass

        # Regenerate the mesh instantly on spacebar press
        elif key == 'space':
            try:
                self.generate()
            except Exception as e:
                raise RuntimeError(f"Regeneration on 'space' failed: {e}") from e

        # On any '<key> up' event while editing, schedule a regeneration after a short delay
        elif self.edit_mode and key.endswith(' up'):
            try:
                invoke(self.generate, delay=3 / 60)
            except Exception as e:
                raise RuntimeError(f"Failed to schedule delayed generation: {e}") from e

    # Uncommenting __setattr__ customization could intercept model assignments, but logic is unchanged.
    # def __setattr__(self, name, value):
    #     if name == 'model' and hasattr(self, 'model') and self.model and not isinstance(value, Mesh):
    #         print_info('can\'t set model of PokeShape')
    #         return
    #     super().__setattr__(name, value)


if __name__ == '__main__':
    """
    Example standalone usage of the PokeShape within an Ursina application.
    Launches the Ursina window, initializes the LevelEditor, and adds a PokeShape with a predefined point list.
    """
    try:
        app = Ursina(borderless=False)

        # Initialize the global level editor and go to origin
        level_editor = LevelEditor()
        level_editor.goto_scene(0, 0)

        # Example point list for a more complex shape
        sample_points = [
            Vec3(-6.89023, 0, -5.93539),
            Vec3(-5.63213, 0, -6.72360),
            Vec3(-3.06749, 0, -7.45143),
            Vec3(0.883525, 0, -6.64059),
            Vec3(6.21342, 0.000496293, -5.19114),
            Vec3(11.1816, 0.000748294, -1.60608),
            Vec3(13.0414, 0.000874294, 0.223267),
            Vec3(12.6511, 0.001000400, 2.84322),
            Vec3(9.07899, 0.000750429, 5.98706),
            Vec3(5.59802, 0.000500321, 5.69713),
            Vec3(3.45835, 0.000375334, 7.03647),
            Vec3(2.95372, 0.000250343, 9.16615),
            Vec3(4.31376, 0.000125260, 9.91672),
            Vec3(5.60310, 0,         12.53580),
            Vec3(4.99113, 0.000499940, 13.88730),
            Vec3(3.37031, 0.000749853, 15.66450),
            Vec3(-0.513243, 0.000874871, 16.54250),
            Vec3(-2.08884, 0.000999762, 15.34090),
            Vec3(-3.86994, 0.000500111, 16.23540),
            Vec3(-5.61374, 0.000375315, 18.77850),
            Vec3(-5.64462, 0.000250529, 22.51970),
            Vec3(-18.97180, 0.000125618, 15.97560),
            Vec3(-14.68120, 0,         10.56400),
            Vec3(-14.25550, 0,          7.90265),
            Vec3(-13.58660, 0,          4.08694),
            Vec3(-10.79910, 0,          1.16432),
            Vec3(-9.05981,  0,          1.75484),
            Vec3(-7.52061,  0,          0.920164),
            Vec3(-6.02536,  0,         -1.79266),
            Vec3(-7.24740,  0,         -3.23652),
        ]

        # Add the PokeShape entity to the level editor with sample points
        level_editor.add_entity(PokeShape(points=sample_points))

        app.run()
    except Exception as e:
        print(f"[PokeShape __main__] Failed to launch application: {e}")
