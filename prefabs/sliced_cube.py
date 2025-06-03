from ursina.editor.level_editor import *
from pathlib import Path
from copy import deepcopy


def stretch_model(mesh, scale, limit=0.25, scale_multiplier=1, regenerate=False):
    """
    Adjusts the vertices and UVs of a mesh to 'stretch' it based on a given scale vector.

    For each vertex coordinate component (x, y, z):
        - If the component is <= -limit, shift it positively by 0.5 + (scale_multiplier / 2),
          then subtract half of the corresponding scale component. Also adjust the U coordinate
          of UVs if present.
        - If the component is >= limit, shift it negatively by 0.5, then add half of the
          corresponding scale component.
        - Finally, divide the entire vertex position by the scale vector to normalize.

    Args:
        mesh (Mesh): The Ursina Mesh to be stretched. Must have `vertices` and `uvs` attributes.
        scale (Vec3): The scale vector (x, y, z) to apply when normalizing vertices.
        limit (float, optional): Threshold at which vertices are considered 'far' enough to shift.
                                 Defaults to 0.25.
        scale_multiplier (float, optional): Multiplier applied when shifting vertices. Defaults to 1.
        regenerate (bool, optional): If True, calls `mesh.generate()` at the end to re-upload data.
                                     Defaults to False.

    Raises:
        AttributeError: If `mesh` does not have expected `vertices` or `uvs` attributes.
        ValueError: If `scale` is zero in any component (would cause division by zero).
        RuntimeError: If any unexpected error occurs during stretching or regeneration.
    """
    # Validate that mesh has vertices and uvs
    if not hasattr(mesh, 'vertices') or not hasattr(mesh, 'uvs'):
        raise AttributeError("Provided mesh must have `vertices` and `uvs` attributes.")

    # Validate scale components to avoid division by zero
    try:
        if scale.x == 0 or scale.y == 0 or scale.z == 0:
            raise ValueError("Scale components must be non-zero for stretching.")
    except Exception:
        # If scale is not a Vec3 or lacks x,y,z, re-raise as ValueError
        raise ValueError("Scale must be a Vec3 with non-zero x, y, and z components.")

    # Copy original vertices into Vec3 list for manipulation
    try:
        verts = [Vec3(*e) for e in mesh.vertices]
    except Exception as e:
        raise RuntimeError(f"Failed to copy mesh.vertices into Vec3 list: {e}") from e

    # Copy original UVs into Vec2 list if UVs exist
    try:
        mesh.uvs = [Vec2(*e) for e in mesh.uvs]
    except Exception as e:
        raise RuntimeError(f"Failed to copy mesh.uvs into Vec2 list: {e}") from e

    # Iterate over each vertex and adjust based on limit and scale
    try:
        for i, v in enumerate(verts):
            for j in [0, 1, 2]:
                # v[j] accesses x, y, or z component dynamically
                if v[j] <= -limit:
                    # Shift vertex positively, then subtract half the scale component
                    verts[i][j] += 0.5 + (scale_multiplier / 2)
                    verts[i][j] -= scale[j] / 2
                    # Adjust UV U-coordinate if UVs exist
                    if mesh.uvs:
                        mesh.uvs[i][0] += 0.5 + (scale_multiplier / 2)

                elif v[j] >= limit:
                    # Shift vertex negatively, then add half the scale component
                    verts[i][j] -= 0.5
                    verts[i][j] += scale[j] / 2

            # Normalize the adjusted vertex by dividing by the scale vector
            verts[i] /= scale
    except Exception as e:
        raise RuntimeError(f"Error while adjusting vertex positions: {e}") from e

    # Assign the adjusted vertices back to the mesh
    try:
        mesh.vertices = verts
    except Exception as e:
        raise RuntimeError(f"Failed to assign adjusted vertices to mesh: {e}") from e

    # Debug print to inspect the final vertex positions
    print("----", mesh.vertices)

    # Optionally regenerate the mesh to upload changes to GPU
    if regenerate:
        try:
            mesh.generate()
        except Exception as e:
            raise RuntimeError(f"Failed to regenerate mesh after stretching: {e}") from e


# Attempt to load a pre-generated sliceable cube; if missing, load from .blend and save as .ursinamesh
try:
    # Path of the current file's directory
    asset_path = Path(__file__).parent
except NameError:
    # In some contexts, __file__ may not exist
    asset_path = Path(".")

try:
    # Full path (relative or absolute) to the mesh
    cube_path = asset_path / 'sliceable_cube.ursinamesh'
    blend_path = asset_path / 'sliceable_cube.blend'

    # Try loading the .ursinamesh file
    if cube_path.exists():
        loaded = load_model(str(cube_path))
    else:
        # If not found, try loading from blend and save .ursinamesh
        loaded = load_model(str(blend_path))
        if loaded:
            loaded.save(str(cube_path))

except Exception as e:
    print(f"[stretch_model] Warning: Failed to load or save sliceable_cube models: {e}")


@generate_properties_for_class()
class SlicedCube(Entity):
    """
    Editor-friendly Entity that displays a cube whose mesh is dynamically 'stretched'
    whenever the entity's scale changes.

    The cube's base mesh (sliceable_cube) is loaded once. On initialization, a deep copy
    of that mesh is assigned to self.model. Whenever the entity's scale or transform
    changes, the mesh is re-stretched so that its UVs and vertices update accordingly,
    preventing texture stretching artifacts.

    Attributes:
        default_values (dict): Combined with Entity.default_values to define:
            - model (None | str): Model identifier (overridden at runtime).
            - shader (str): Shader to use (default 'lit_with_shadows_shader').
            - texture (str): Texture name (default 'white_cube').
            - collider (str): Collider type (default 'box').
            - name (str): Entity name (default 'sliced_cube').
            - scale_multiplier (float): Factor to multiply when stretching UVs.
        stretchable_mesh (Mesh): The original Mesh to be used as a base for stretching.
        scale_multiplier (float): Multiplier applied during mesh stretching.
        scale (Vec3): The entity's scale (inherited from Entity).
        texture (str): Texture name applied to this entity's model.
    """

    default_values = Entity.default_values | dict(
        model=None,
        shader='lit_with_shadows_shader',
        texture='white_cube',
        collider='box',
        name='sliced_cube',
        scale_multiplier=1
    )  # combine dicts

    def __init__(self, stretchable_mesh='sliceable_cube', **kwargs):
        """
        Initialize a SlicedCube instance.

        Args:
            stretchable_mesh (str | Mesh): 
                - If a string, `load_model` is called to retrieve a Mesh by that name.
                - If already a Mesh, it's used directly.
            **kwargs: Additional properties to override default_values, including:
                - scale_multiplier (float): Factor used when stretching UVs.
                - scale (Vec3): Initial scale of the cube.
                - texture (str): Texture name for the cube.
                - shader, collider, name, etc.
        
        Raises:
            TypeError: If `stretchable_mesh` is not a string or a Mesh instance.
            RuntimeError: If loading or copying the stretchable_mesh fails.
            KeyError: If required keys (e.g., 'scale_multiplier', 'scale', 'texture') are missing.
        """
        # Merge provided kwargs with default_values
        try:
            config = __class__.default_values | kwargs
        except Exception as e:
            raise RuntimeError(f"Failed to merge default properties: {e}") from e

        # Determine the base mesh to use for stretching
        if isinstance(stretchable_mesh, str):
            try:
                # Load the mesh by name; use a deepcopy to avoid modifying the global asset
                stretchable_mesh = load_model(stretchable_mesh, use_deepcopy=True)
                if not stretchable_mesh:
                    raise RuntimeError(f"load_model returned None for '{stretchable_mesh}'")
                print("Loaded stretchable mesh:", stretchable_mesh)
            except Exception as e:
                pass
                # raise RuntimeError(f"Failed to load mesh '{stretchable_mesh}': {e}") from e
        elif not hasattr(stretchable_mesh, 'vertices'):
            # If not a string, expect a Mesh-like object with 'vertices' attribute
            raise TypeError("stretchable_mesh must be a string model name or a Mesh instance.")

        # Store the base mesh; will be deep-copied for this instance's model
        self.stretchable_mesh = stretchable_mesh

        # Call base Entity constructor with merged configuration
        try:
            super().__init__(**config)
        except Exception as e:
            raise RuntimeError(f"Failed to initialize base Entity: {e}") from e

        # Assign a deep copy of the stretchable mesh to this entity's model
        try:
            self.model = deepcopy(self.stretchable_mesh)
            self.model.name = 'cube'
        except Exception as e:
            raise RuntimeError(f"Failed to deepcopy stretchable_mesh for model: {e}") from e

        # Assign runtime properties from config
        try:
            self.scale_multiplier = config['scale_multiplier']
            self.scale = config['scale']
            self.texture = config['texture']
        except KeyError as e:
            raise KeyError(f"Missing required property '{e.args[0]}' in kwargs.") from e
        except Exception as e:
            raise RuntimeError(f"Failed to assign runtime properties: {e}") from e

    def __deepcopy__(self, memo):
        """
        Create a deep copy of this SlicedCube by evaluating its repr.

        Returns:
            SlicedCube: A new instance with identical properties.

        Raises:
            RuntimeError: If repr(self) is not evaluable to recreate the object.
        """
        try:
            return eval(repr(self))
        except Exception as e:
            raise RuntimeError("Deepcopy failed: repr(self) could not recreate the object.") from e

    def generate(self):
        """
        Re-stretches the cube's mesh based on the current world_scale and scale_multiplier.

        Steps:
            1. Reset the mesh's vertices and uvs to the original unmodified base mesh.
            2. Call `stretch_model` to adjust vertices and uvs based on world_scale.
            3. Call `self.model.generate()` to upload new data to the GPU.

        Raises:
            RuntimeError: If any step in regeneration fails (e.g., missing attributes).
        """
        print("update model", self.scale)

        # Reset vertices and UVs from the base stretchable_mesh
        try:
            self.model.vertices = self.stretchable_mesh.vertices
            self.model.uvs = self.stretchable_mesh.uvs
        except Exception as e:
            raise RuntimeError(f"Failed to reset model vertices/uvs from stretchable_mesh: {e}") from e

        # Stretch the mesh using current world_scale
        try:
            stretch_model(self.model, self.world_scale, scale_multiplier=self.scale_multiplier)
        except Exception as e:
            raise RuntimeError(f"Error in stretch_model during generate(): {e}") from e

        # Upload the modified mesh data to the GPU
        try:
            self.model.generate()
        except Exception as e:
            raise RuntimeError(f"Failed to generate mesh after stretching: {e}") from e

    def __setattr__(self, name, value):
        """
        Override setattr to regenerate the mesh automatically when certain attributes change.

        If `name` is one of 'scale', 'scale_x', 'scale_y', 'scale_z', 'transform', or
        'world_transform', then after setting the attribute, call `self.generate()` to
        update the stretched mesh.

        Args:
            name (str): The attribute name to set.
            value: The new value of the attribute.
        
        Raises:
            RuntimeError: If automatic regeneration fails.
        """
        # Always perform the normal attribute assignment first
        super().__setattr__(name, value)

        # Check if we need to regenerate the mesh based on which attribute changed
        if hasattr(self, 'model') and name in (
            'scale',
            'scale_x',
            'scale_y',
            'scale_z',
            'transform',
            'world_transform',
        ):
            try:
                self.generate()
            except Exception as e:
                raise RuntimeError(f"Automatic regeneration in __setattr__ failed: {e}") from e


if __name__ == '__main__':
    """
    Example standalone usage of the SlicedCube within an Ursina application.

    - Initializes Ursina.
    - Creates a LevelEditor and navigates to the origin.
    - Adds a SlicedCube with selectable=True to the editor.
    - On pressing spacebar, manually regenerate the cube's mesh.
    """
    try:
        app = Ursina(borderless=False)

        # Initialize the LevelEditor and move to scene (0,0)
        level_editor = LevelEditor()
        level_editor.goto_scene(0, 0)

        # Create a SlicedCube entity with custom texture and scale_multiplier
        sliced_cube = SlicedCube(
            selectable=True,
            texture='sliceable_cube_template',
            shader='unlit_shader',
            scale_multiplier=1.5
        )

        # Define a simple input handler to regenerate on spacebar
        def input(key):
            if key == 'space':
                try:
                    sliced_cube.generate()
                except Exception as e:
                    print(f"[Main Input] Failed to regenerate sliced_cube: {e}")

        # Register the cube with the level editor
        level_editor.add_entity(sliced_cube)

        # Run the Ursina application
        app.run()
    except Exception as e:
        print(f"[SlicedCube __main__] Application failed to start: {e}")
