from ursina import *
from ursina.mesh_importer import *
from tkinter import simpledialog, messagebox
import importlib

app=Ursina()

deleting=False

selecting=None
def toggle_vis(self:Entity):
    if deleting:
        destroy(self)
        refresh_container()
    else:
        self.wireframe=not self.wireframe
Entity.toggle_vis=toggle_vis

class DebugBehaviour():
    def __init__(self) -> None:
        self.entity:Entity
    def update(self):
        self.entity.on_click=self.toggle
        if selecting!=self: return
        if held_keys["shift"]:
            self.entity.scale_z += (held_keys['up arrow'] - held_keys['down arrow']) * (time.dt * (1 if held_keys['control'] else 5) if not held_keys['alt'] else 0)
            self.entity.scale_y += (held_keys['page up'] - held_keys['page down']) * (time.dt * (1 if held_keys['control'] else 5) if not held_keys['alt'] else 0)
            self.entity.scale_x += (held_keys['right arrow'] - held_keys['left arrow']) * (time.dt * (1 if held_keys['control'] else 5) if not held_keys['alt'] else 0)
        else:
            self.entity.z += (held_keys['up arrow'] - held_keys['down arrow']) * (time.dt * (1 if held_keys['control'] else 5) if not held_keys['alt'] else 0)
            self.entity.y += (held_keys['page up'] - held_keys['page down']) * (time.dt * (1 if held_keys['control'] else 5) if not held_keys['alt'] else 0)
            self.entity.x += (held_keys['right arrow'] - held_keys['left arrow']) * (time.dt * (1 if held_keys['control'] else 5) if not held_keys['alt'] else 0)

        self.entity.rotation_y += (held_keys['x'] - held_keys['z']) * time.dt * (10 if held_keys['control'] else 20)
        self.entity.rotation_x += (held_keys['c'] - held_keys['v']) * time.dt * (10 if held_keys['control'] else 20)
        self.entity.rotation_z += (held_keys['b'] - held_keys['n']) * time.dt * (10 if held_keys['control'] else 20)
    def input(self, key):
        if selecting!=self: return
        if key=='f':
            print(f'\'{self.entity.name}\' pos : {self.entity.position}')
            print(f'\'{self.entity.name}\' rot : {self.entity.rotation}')
        if held_keys["shift"]:
            self.entity.scale_z += (int(key=='up arrow') - int(key=='down arrow')) * held_keys['alt']
            self.entity.scale_y += (int(key=='page up') - int(key=='page down')) * held_keys['alt']
            self.entity.scale_x += (int(key=='right arrow') - int(key=='left arrow')) * held_keys['alt']
            if held_keys['alt'] and key != 'alt':
                self.entity.scale_x=int(self.entity.scale_x)
                self.entity.scale_y=int(self.entity.scale_y)
                self.entity.scale_z=int(self.entity.scale_z)
        else:
            self.entity.z += (int(key=='up arrow') - int(key=='down arrow')) * held_keys['alt']
            self.entity.y += (int(key=='page up') - int(key=='page down')) * held_keys['alt']
            self.entity.x += (int(key=='right arrow') - int(key=='left arrow')) * held_keys['alt']
            if held_keys['alt'] and key != 'alt':
                self.entity.x=int(self.entity.x)
                self.entity.y=int(self.entity.y)
                self.entity.z=int(self.entity.z)
    def toggle(self):
        global selecting
        if deleting:
            destroy(self.entity)
            del self
        else:
            if selecting==self: selecting=None
            else: selecting=self

objects=[]

def addnew():
    name=simpledialog.askstring("Map Editor", "Enter Object's name")
    model=simpledialog.askstring("Map Editor", "Enter Object's Model name")
    texture=simpledialog.askstring("Map Editor", "Enter Object's Texture name")
    clr=None
    try:
        if isinstance(eval(texture), color.Color): clr=eval(texture)
    except: pass
    collider=simpledialog.askstring("Map Editor", "Enter Object's Collider type")
    double_sided=messagebox.askyesno("Map Editor", "Double Sided?")
    try:
        i=Entity(name=name if name!="" else None, model=model if model!="" else "cube", collider=collider if collider!="" else None, double_sided=double_sided, texture=texture)
        if clr: i.color=clr
        i.add_script(DebugBehaviour())
        if i.model==None: i.model='cube'
        objects.append(i)
    except:pass
    refresh_container()

def toggleDelete():
    global deleting
    deleting = not deleting

def save():
    if messagebox.askyesno("Map Editor", "Do you want to save?"):
        code=f"from ursina import *\n\n"
        for i in objects:
            code+=repr(i)+'\n'
        with open('scene.py', 'w') as file:
            file.write(code)

OBJECTS_PER_PAGE=5

def pg(i):
    global current_page
    if i==1:
        current_page=min(ceil(len(objects)/OBJECTS_PER_PAGE)-1, current_page+i)
    else: current_page=max(0, current_page+i)
    print(current_page)
    refresh_container()
container=Entity(model=Quad(.1, aspect=.7), color=color.black33, parent=camera.ui, scale=(.7,1), x=0.6479293, eternal=True)
Button('Previous', position=Vec3(0.4540579, -0.36839267, -1.3447969), color=color.white, on_click=lambda:pg(-1), scale=(.25,.1), text_color=color.black, eternal=True)
Button('Next', position=Vec3(0.736449, -0.36839267, -1.3447969), color=color.white, on_click=lambda:pg(1), scale=(.25,.1), text_color=color.black, eternal=True)
current_page=0
container_o=[]
def refresh_container():
    for i in container_o:
        destroy(i)
    container_o.clear()
    for i in range(current_page*OBJECTS_PER_PAGE, min((current_page+1)*OBJECTS_PER_PAGE,len(objects))):
        if objects[i]:container_o.append(Button(objects[i].name, position=Vec3(0.6342687, 0.40175405*(1-i/3), -0.90489095), on_click=objects[i].toggle_vis, color=color.white, scale=(.5,.1), text_color=color.black))
def load():
    if messagebox.askyesno("Map Editor", "Do you want to load?"):
        scene.clear()
        camera.overlay.color=color.clear
        if 'scene' in sys.modules:
            importlib.reload(sys.modules['scene'])
        else:
            importlib.import_module('scene')
        for i in scene.entities:
            i:Entity
            if not i.eternal:
                objects.append(i)
                i.add_script(DebugBehaviour())
        refresh_container()
Entity(model=Quad(.1, aspect=.7), color=color.black33, parent=camera.ui, scale=(.7,1), x=-0.6479293, eternal=True)
Button('Add new Object', position=Vec3(-0.61267745, 0.39322376, -0.8950644), color=color.white, on_click=addnew, scale=(.5,.1), text_color=color.black, eternal=True)
Button('Toggle Delete Mode', position=Vec3(-0.61267745, 0.19322376, -0.8950644), color=color.white, on_click=toggleDelete, scale=(.5,.1), text_color=color.black, eternal=True)
Button('Save', position=Vec3(-0.61267745, -0.19322376, -0.8950644), color=color.white, on_click=save, scale=(.5,.1), text_color=color.black, eternal=True)
Button('Load', position=Vec3(-0.61267745, -0.30322376, -0.8950644), color=color.white, on_click=load, scale=(.5,.1), text_color=color.black, eternal=True)

Entity(model=Grid(512,512), rotation_x=90, scale=512, color=color.white33, enabled=True, x=.5, z=.5, y=-.5, eternal=True)

Sky(eternal=True)
EditorCamera(eternal=True)

app.run()