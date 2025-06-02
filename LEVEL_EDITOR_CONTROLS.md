# Ursina Level Editor Controls Cheatsheet

This cheatsheet summarizes the main keyboard and mouse controls for the Ursina Level Editor, based on code analysis.

---

## Navigation & Camera

| Key / Mouse         | Action                                         |
|---------------------|------------------------------------------------|
| `Mouse Right Drag`  | Orbit camera around scene                      |
| `Mouse Middle Drag` | Pan camera                                     |
| `Scroll Wheel`      | Zoom camera in/out                             |
| `F`                 | Focus camera on selection                      |
| `Shift+1`           | Front view                                     |
| `Shift+3`           | Right view                                     |
| `Shift+7`           | Top view                                       |
| `Shift+5`           | Toggle orthographic/perspective camera         |

---

## Mode Switching

| Key                 | Action                                         |
|---------------------|------------------------------------------------|
| `Ctrl+E`            | Toggle Edit/Play mode                          |

---

## Selection

| Key / Mouse         | Action                                         |
|---------------------|------------------------------------------------|
| `Left Click`        | Select entity                                  |
| `Shift+Left Click`  | Add to selection                               |
| `Alt+Left Click`    | Remove from selection                          |
| `Left Click+drag`   | Box select                                     |
| `Ctrl+A`            | Select all entities                            |
| `Click empty`       | Deselect all                                   |

---

## Transform (Move/Scale/Rotate)

| Key                 | Action                                         |
|---------------------|------------------------------------------------|
| `G`                 | Grab/move mode                                 |
| `G` + `X/Y/Z`       | Move along X/Y/Z axis                          |
| `R`                 | Rotate mode (Y-axis, single selection)         |
| `T`                 | Rotate relative to camera (single selection)   |
| `S`                 | Scale mode (uniform)                           |
| `S` + `X/Y/Z`       | Scale along X/Y/Z axis                         |
| `Alt+S`             | Scale from center                              |
| `Middle Mouse`      | Toggle axis lock while moving/scaling/rotating |

---

## Gizmo Toggle

| Key                 | Action                                         |
|---------------------|------------------------------------------------|
| `Q`                 | Disable all gizmos                             |
| `G`                 | Move gizmo                                     |
| `S`                 | Scale gizmo                                    |
| `R`                 | Rotate gizmo                                   |

---

## Entity Management

| Key                 | Action                                         |
|---------------------|------------------------------------------------|
| `N`                 | Add new cube                                   |
| `I`                 | Start spawning prefab under mouse              |
| `Delete`            | Delete selected entities                       |
| `Ctrl+X`            | Delete selected entities                       |
| `Ctrl+D`            | Duplicate selected entities                    |
| `Shift+D`           | Duplicate selected entities                    |
| `Ctrl+C`            | Copy selection to clipboard                    |
| `Ctrl+V`            | Paste from clipboard                           |
| `Ctrl+G`            | Group selected entities                        |

---

## Undo/Redo & Save/Load

| Key                 | Action                                         |
|---------------------|------------------------------------------------|
| `Ctrl+S`            | Save current scene                             |
| `Ctrl+Z`            | Undo                                           |
| `Ctrl+Y`            | Redo                                           |

---

## Menus & UI

| Key                 | Action                                         |
|---------------------|------------------------------------------------|
| `Ctrl++`            | Scale UI up                                    |
| `Ctrl+-`            | Scale UI down                                  |
| `M`                 | Model Menu                                     |
| `V`                 | Texture Menu                                   |
| `C`                 | Color Menu                                     |
| `L`                 | Shader Menu                                    |
| `O`                 | Collider Menu                                  |
| `K`                 | Class Menu                                     |
| `Escape`            | Close all menus                                |
| `Shift+M`           | Toggle Level Menu                              |

---

## Inspector & Misc

| Key                 | Action                                         |
|---------------------|------------------------------------------------|
| `H`                 | Toggle point renderer visibility               |
| `Space`             | Activate search/input field                    |

---

## Scene Switching

| Key                 | Action                                         |
|---------------------|------------------------------------------------|
| `Click Scene`       | Go to clicked scene in Level Menu              |
| `Shift+Click`       | Append/Load scene                              |
| `Alt+Click`         | Unload/remove scene                            |
| `Shift+Alt+WASD`    | Load adjacent scenes (WASD navigation)         |

---

## Sun/Lighting

| Key                 | Action                                         |
|---------------------|------------------------------------------------|
| `L`                 | Toggle/update sun                              |

---

## Help

| Key                 | Action                                         |
|---------------------|------------------------------------------------|
| `?`                 | Show help/hotkeys tooltip                      |

---

**Note:**  
Some controls may be context-sensitive (e.g., only active when the mouse is over the scene, or when an entity is selected). Modifier keys like `Ctrl`, `Shift`, `Alt` must be held while pressing the main key.
