from ursina.editor.level_editor import *
from ursina import Ursina, Entity, invoke
from ursina.vec3 import Vec3
from ursina import input_handler

class PipeEditor(Entity):
    """
    Editor Entity for creating and modifying a Pipe in the Ursina Level Editor.

    Attributes:
        _point_gizmos (LoopingList[Entity]): List of gizmo Entities representing control points of the pipe.
        model (Pipe): The visual model of the pipe, updated whenever control points change.
        _edit_mode (bool): Flag indicating whether the editor is in point-edit mode.
        add_collider (bool): Flag indicating whether to add a collider to the pipe model.
    """

    def __init__(self, points=None, **kwargs):
        """
        Initialize a new PipeEditor.

        Args:
            points (list[Vec3], optional): List of Vec3 positions for initial control points.
                Defaults to two points at (0,0,0) and (0,1,0).
            **kwargs: Additional keyword arguments passed to the base Entity constructor.

        Raises:
            TypeError: If `points` is not a list of Vec3 instances.
            RuntimeError: If LEVEL_EDITOR is not defined or does not have the expected attributes.
        """
        # Default two-point straight vertical pipe if none provided
        if points is None:
            points = [Vec3(0, 0, 0), Vec3(0, 1, 0)]

        # Validate `points` argument
        if not isinstance(points, list) or not all(isinstance(p, Vec3) for p in points):
            raise TypeError("`points` must be a list of Vec3 instances.")

        # Ensure LEVEL_EDITOR exists and has necessary attributes
        if 'LEVEL_EDITOR' not in globals() or not hasattr(LEVEL_EDITOR, 'entities'): # type: ignore
            raise RuntimeError("LEVEL_EDITOR is not initialized or missing required attributes.")

        # Call base Entity constructor: place this PipeEditor under LEVEL_EDITOR
        super().__init__(
            original_parent=LEVEL_EDITOR, # type: ignore
            selectable=True,
            name='Pipe',
            **kwargs
        )

        # Add this editor to the global entity list so it participates in selection/rendering
        LEVEL_EDITOR.entities.append(self) # type: ignore

        # Create gizmo Entities for each control point, parented to this PipeEditor
        try:
            self._point_gizmos = LoopingList([
                Entity(
                    parent=self,
                    original_parent=self,
                    position=point,
                    selectable=False,
                    name='PipeEditor_point',
                    is_gizmo=True
                )
                for point in points
            ])
        except Exception as e:
            # Catch any unexpected errors constructing gizmo entities
            raise RuntimeError(f"Failed to create point gizmos: {e}") from e

        # Initialize the pipe model and state flags
        self.model = None
        self._edit_mode = False
        self.add_collider = False

        # Generate initial geometry
        self.generate()

    def generate(self):
        """
        Generate or update the pipe model based on current control points and their scales.

        - Updates `self.model` to a new Pipe with the current path and thicknesses.
        - Applies a default 'grass' texture.
        - Adds a collider if `self.add_collider` is True.

        Raises:
            ValueError: If there are fewer than two control points (cannot form a pipe).
            AttributeError: If a gizmo is missing required attributes (position or scale).
        """
        # Gather positions for the path relative to this entity
        try:
            path = [gizmo.get_position(relative_to=self) for gizmo in self._point_gizmos]
        except Exception as e:
            raise AttributeError(f"Failed to retrieve gizmo positions: {e}") from e

        # Ensure enough points to define a pipe
        if len(path) < 2:
            raise ValueError("At least two control points are required to generate a pipe.")

        # Gather thickness values from each gizmo's scale.xz (assuming scale is a Vec3)
        try:
            thicknesses = [gizmo.scale.xz for gizmo in self._point_gizmos]
        except Exception as e:
            raise AttributeError(f"Failed to retrieve gizmo scale for thickness: {e}") from e

        # Create or replace the existing Pipe model
        try:
            self.model = Pipe(path=path, thicknesses=thicknesses)
        except Exception as e:
            raise RuntimeError(f"Error constructing Pipe model: {e}") from e

        # Apply a default texture
        self.texture = 'grass'

        # Conditionally add a collider if requested
        if self.add_collider:
            try:
                # Assign the pipe mesh itself as a collider
                self.collider = self.model
            except Exception as e:
                raise RuntimeError(f"Failed to set collider on Pipe: {e}") from e

    def __deepcopy__(self, memo):
        """
        Create a deep copy of this PipeEditor by evaluating its repr.

        Warning:
            This implementation relies on repr() returning a valid Python expression.
            If repr is not overridden appropriately, this may fail.

        Returns:
            PipeEditor: A new instance duplicating this instance's data.

        Raises:
            NotImplementedError: If repr(self) is not evaluable to recreate the object.
        """
        try:
            return eval(repr(self))
        except Exception as e:
            raise NotImplementedError(
                "Deep copying via repr(e) failed. "
                "Ensure __repr__ is implemented to return a valid constructor call."
            ) from e

    @property
    def points(self):
        """
        List of current control point positions for external use.

        Returns:
            list[Vec3]: Positions of all gizmo control points in world space.
        """
        return [gizmo.position for gizmo in self._point_gizmos]

    @property
    def edit_mode(self):
        """
        Get the current edit mode status.

        Returns:
            bool: True if in edit mode, False otherwise.
        """
        return self._edit_mode

    @edit_mode.setter
    def edit_mode(self, value):
        """
        Enable or disable edit mode.

        In edit mode:
            - All other LEVEL_EDITOR entities become non-selectable.
            - This PipeEditor's control-point gizmos are added to LEVEL_EDITOR.entities and become selectable.

        On exiting edit mode:
            - Control-point gizmos are removed from LEVEL_EDITOR.entities.
            - All remaining LEVEL_EDITOR.entities become selectable.
            - If any gizmo was selected at the moment of exit, the pipe itself is re-selected.

        Args:
            value (bool): True to enter edit mode; False to exit.
        """
        # Validate type
        if not isinstance(value, bool):
            raise TypeError("edit_mode must be set to a boolean value.")

        self._edit_mode = value

        if value:
            # Disable selection on all other entities
            for ent in LEVEL_EDITOR.entities: # type: ignore
                if ent is not self:
                    setattr(ent, 'selectable', False)

            # Add gizmos to level editor if not already present, then make them selectable
            for gizmo in self._point_gizmos:
                if gizmo not in LEVEL_EDITOR.entities: # type: ignore
                    LEVEL_EDITOR.entities.append(gizmo) # type: ignore
                setattr(gizmo, 'selectable', True)
        else:
            # Exiting edit mode: remove each gizmo from level editor and restore selectability
            for gizmo in list(self._point_gizmos):
                if gizmo in LEVEL_EDITOR.entities: # type: ignore
                    LEVEL_EDITOR.entities.remove(gizmo) # type: ignore

            for ent in LEVEL_EDITOR.entities: # type: ignore
                setattr(ent, 'selectable', True)

            # If any gizmo was selected while exiting, re-select the pipe itself
            if any(gizmo in LEVEL_EDITOR.selection for gizmo in self._point_gizmos): # type: ignore
                LEVEL_EDITOR.selection = [self] # type: ignore

        # Update visual selection indicators in the level editor
        LEVEL_EDITOR.render_selection() # type: ignore

    def input(self, key):
        """
        Handle user input events when this PipeEditor (or its gizmos) are active.

        Supported keys:
            - 'tab': Toggle edit mode if this pipe or any of its gizmos is selected.
            - '+': Insert a new control point halfway between the selected gizmo and the next one.
            - 'space': Regenerate the pipe mesh immediately.
            - '<any> up' (mouse key release) while in edit mode: Regenerate the pipe mesh after a short delay.

        Args:
            key (str): The input key or mouse event descriptor.

        Raises:
            IndexError: If attempting to add a point at the last gizmo (no next point exists).
        """
        try:
            combined_key = input_handler.get_combined_key(key)
        except Exception:
            combined_key = None  # If input_handler is missing or fails, ignore combined key

        # Toggle edit mode on 'tab' press if relevant entity is selected
        if combined_key == 'tab':
            if self in LEVEL_EDITOR.selection or any(gizmo in LEVEL_EDITOR.selection for gizmo in self._point_gizmos): # type: ignore
                self.edit_mode = not self.edit_mode
                return

        # Add a new control point between the selected gizmo and the next one
        if key == '+' and len(LEVEL_EDITOR.selection) == 1: # type: ignore
            selected = LEVEL_EDITOR.selection[0] # type: ignore
            if selected in self._point_gizmos:
                idx = self._point_gizmos.index(selected)
                # Ensure there is a "next" gizmo to interpolate with
                if idx + 1 >= len(self._point_gizmos):
                    raise IndexError("Cannot add a point after the last control point.")
                try:
                    # Compute the midpoint between two gizmos
                    pos_a = self._point_gizmos[idx].position
                    pos_b = self._point_gizmos[idx + 1].position
                    midpoint = lerp(pos_a, pos_b, 0.5)
                except Exception as e:
                    raise RuntimeError(f"Failed to compute midpoint for new control point: {e}") from e

                # Create the new point gizmo
                try:
                    new_point = Entity(
                        parent=self,
                        original_parent=self,
                        position=midpoint,
                        selectable=True,
                        is_gizmo=True,
                        name='PipeEditor_point'
                    )
                except Exception as e:
                    raise RuntimeError(f"Failed to create new control point entity: {e}") from e

                # Insert into editor lists and update selection rendering
                LEVEL_EDITOR.entities.append(new_point) # type: ignore
                self._point_gizmos.insert(idx + 1, new_point)
                LEVEL_EDITOR.render_selection() # type: ignore

        # Regenerate the mesh on spacebar press
        elif key == 'space':
            try:
                self.generate()
            except Exception as e:
                # Log or print an error but do not crash the editor
                print(f"[PipeEditor] Error regenerating pipe: {e}")

        # If in edit mode and any mouse button is released, schedule a regeneration
        elif self.edit_mode and key.endswith(' up'):
            try:
                # Delay a few frames to allow gizmo movements to settle
                invoke(self.generate, delay=3/60)
            except Exception as e:
                print(f"[PipeEditor] Failed to schedule mesh regeneration: {e}")


if __name__ == '__main__':
    """
    Example standalone usage of the PipeEditor within an Ursina application.
    Launches the Ursina window, initializes the LevelEditor, and adds a PipeEditor.
    """
    try:
        # Initialize the Ursina application with window border enabled
        app = Ursina(borderless=False)

        # Create the global level editor and navigate to scene origin
        level_editor = LevelEditor()
        level_editor.goto_scene(0, 0)

        # Append a PipeEditor instance to the level editor's entities
        level_editor.entities.append(PipeEditor())

        # Run the Ursina main loop
        app.run()
    except Exception as e:
        # Catch any top-level errors during initialization
        print(f"[PipeEditor __main__] Failed to launch application: {e}")
