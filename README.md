# Ursina Level Editor

[`level_editor.py`](level_editor.py) implements a comprehensive, extensible 3D level editor for the [Ursina Engine](https://www.ursinaengine.org/). It provides a grid-based scene system, interactive entity manipulation, prefab support, undo/redo, and a robust UI for rapid prototyping and editing of game levels.

---

## Table of Contents

- [Features](#features)
- [Getting Started](#getting-started)
- [Usage](#usage)
  - [Controls & Hotkeys](#controls--hotkeys)
  - [Menus & Inspector](#menus--inspector)
  - [Prefab System](#prefab-system)
  - [Scene Management](#scene-management)
  - [Undo/Redo](#undoredo)
- [Extending the Editor](#extending-the-editor)
- [Limitations](#limitations)
- [File Structure](#file-structure)
- [License](#license)

---

## Features

- **Grid-based Scene System:** Organize your world into an 8x8 grid of scenes, each saved as a CSV file.
- **Entity Manipulation:** Move, scale, rotate, duplicate, group, and delete entities with intuitive gizmos and hotkeys.
- **Prefab Support:** Easily add and spawn custom prefabs from the `prefabs/` directory.
- **Inspector Panel:** Edit properties (position, rotation, scale, model, texture, color, collider, shader, etc.) of selected entities.
- **Asset Menus:** Pop-up menus for models, textures, shaders, colliders, and class assignment.
- **Undo/Redo:** Robust undo/redo system for all entity and property changes.
- **Radial Context Menu:** Right-click menu for quick access to common actions.
- **Search Bar:** Quick search field for commands or entity filtering.
- **Lighting:** Sun handler for dynamic directional light and shadow bounds.
- **Custom Inspector Fields:** Entities can define custom inspector UI via `draw_inspector`.
- **Extensible:** Add new prefabs, shaders, and menu options with minimal code changes.

---

## Getting Started

### Requirements

- Python 3.7+
- [Ursina Engine](https://www.ursinaengine.org/) (installed via `pip install ursina`)
- (Optional) Custom prefabs in `prefabs/` directory

### Running the Editor

To launch the editor as a standalone application:

```sh
python level_editor.py
```

This opens the Ursina window with the editor UI.

---

## Usage

### Controls & Hotkeys

The editor supports a wide range of keyboard and mouse shortcuts for efficient workflow. Here are some essentials:

#### Navigation & Camera

| Key / Mouse         | Action                                         |
|---------------------|------------------------------------------------|
| Mouse Right Drag    | Orbit camera                                   |
| Mouse Middle Drag   | Pan camera                                     |
| Scroll Wheel        | Zoom camera                                    |
| F                   | Focus camera on selection                      |
| Shift+1/3/7         | Front/Right/Top view                           |
| Shift+5             | Toggle ortho/perspective                       |

#### Selection

| Key / Mouse         | Action                                         |
|---------------------|------------------------------------------------|
| Left Click          | Select entity                                  |
| Shift+Left Click    | Add to selection                               |
| Alt+Left Click      | Remove from selection                          |
| Left Click+drag     | Box select                                     |
| Ctrl+A              | Select all entities                            |
| Click empty         | Deselect all                                   |

#### Transform (Move/Scale/Rotate)

| Key                 | Action                                         |
|---------------------|------------------------------------------------|
| G                   | Grab/move mode                                 |
| G + X/Y/Z           | Move along X/Y/Z axis                          |
| R                   | Rotate mode (Y-axis, single selection)         |
| T                   | Rotate relative to camera (single selection)   |
| S                   | Scale mode (uniform)                           |
| S + X/Y/Z           | Scale along X/Y/Z axis                         |
| Alt+S               | Scale from center                              |
| Middle Mouse        | Toggle axis lock while moving/scaling/rotating |

#### Entity Management

| Key                 | Action                                         |
|---------------------|------------------------------------------------|
| N                   | Add new cube                                   |
| I                   | Start spawning prefab under mouse              |
| Delete/Ctrl+X       | Delete selected entities                       |
| Ctrl+D/Shift+D      | Duplicate selected entities                    |
| Ctrl+C/Ctrl+V       | Copy/Paste selection                           |
| Ctrl+G              | Group selected entities                        |

#### Undo/Redo & Save/Load

| Key                 | Action                                         |
|---------------------|------------------------------------------------|
| Ctrl+S              | Save current scene                             |
| Ctrl+Z              | Undo                                           |
| Ctrl+Y              | Redo                                           |

#### Menus & UI

| Key                 | Action                                         |
|---------------------|------------------------------------------------|
| M                   | Model Menu                                     |
| V                   | Texture Menu                                   |
| C                   | Color Menu                                     |
| L                   | Shader Menu                                    |
| O                   | Collider Menu                                  |
| K                   | Class Menu                                     |
| Escape              | Close all menus                                |
| Shift+M             | Toggle Level Menu                              |
| Space               | Activate search/input field                    |
| H                   | Toggle point renderer visibility               |
| ?                   | Show help/hotkeys tooltip                      |

For a full list, see [`LEVEL_EDITOR_CONTROLS.md`](LEVEL_EDITOR_CONTROLS.md).

---

### Menus & Inspector

- **Inspector Panel:** Shows and allows editing of properties for the selected entity/entities.
- **Asset Menus:** Click property buttons or use hotkeys to open menus for models, textures, shaders, colliders, and classes.
- **Radial Menu:** Right-click a selected entity to open a context-sensitive radial menu for quick actions.

---

### Prefab System

- **Built-in Prefabs:** Includes cubes, pyramids, triplanar cubes, and more.
- **Custom Prefabs:** Add Python files to the [`prefabs/`](prefabs/) directory. Prefabs are auto-loaded and appear in the spawn menu.
- **Prefab Spawning:** Press `I` to spawn a prefab under the mouse, or use the prefab menu.

---

### Scene Management

- **Grid System:** The world is divided into an 8x8 grid of scenes, each saved as a CSV in [`scenes/`](scenes/).
- **Switching Scenes:** Use the Level Menu (`Shift+M`) or click on the grid to load/unload scenes.
- **Saving/Loading:** Scenes are saved automatically as CSV files. Entities are serialized using their `repr()`.

---

### Undo/Redo

- **Undo/Redo:** All property changes and entity operations are recorded. Use `Ctrl+Z` to undo and `Ctrl+Y` to redo.
- **Undo System:** Tracks entity creation, deletion, and property changes.

---

## Extending the Editor

- **Add Prefabs:** Place new prefab classes in [`prefabs/`](prefabs/). They will be auto-loaded.
- **Custom Inspector:** Implement a `draw_inspector` method on your entity to add custom fields to the Inspector.
- **Menus:** Extend asset menus by modifying the relevant menu classes in [`level_editor.py`](level_editor.py).
- **Custom Shaders:** Add new shaders to the `ShaderMenu` by editing its `asset_names` list.

---

## Limitations

- **Serialization:** Entities must be serializable via `repr()` and reconstructible via `eval()`. Complex or non-standard entities may not serialize correctly.
- **No Hierarchical Prefab Editing:** Prefabs are instantiated as entities; editing prefab definitions in-place is not supported.
- **No Built-in Asset Importer:** Models and textures must be placed in the asset folder manually.
- **No Physics/Scripted Behaviors:** The editor is focused on static level design; runtime behaviors must be added in code.
- **Limited Error Handling:** While many operations are wrapped in try/except, some errors (especially in custom prefabs) may not be recoverable.
- **No Multi-user Collaboration:** The editor is single-user and does not support real-time collaboration.

---

## File Structure

```
level_editor.py
map_editor.py
add_type_ignore.py
__init__.py
README.md
LEVEL_EDITOR_CONTROLS.md
prefabs/
    __init__.py
    pipe_editor.py
    poke_shape.py
    sliced_cube.py
    ...
scenes/
    untitled_scene[0,0].csv
    untitled_scene[1,0].csv
    ...
```

- [`level_editor.py`](level_editor.py): Main editor implementation.
- [`prefabs/`](prefabs/): Custom prefab entity definitions.
- [`scenes/`](scenes/): Scene data files (CSV).
- [`LEVEL_EDITOR_CONTROLS.md`](LEVEL_EDITOR_CONTROLS.md): Full controls cheatsheet.

---

## License

See the Ursina Engine license for details. This editor is intended for use with Ursina-based projects.

---

For more information, see the code documentation in [`level_editor.py`](level_editor.py) and the controls cheatsheet in [`LEVEL_EDITOR_CONTROLS.md`](LEVEL_EDITOR_CONTROLS.md).