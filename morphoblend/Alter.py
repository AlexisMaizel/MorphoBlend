import re

import bmesh
import bpy

from .Quantify import volume_and_area_from_object
from .Utilities import (ObjectNavigator, apply_modifiers)

# ------------------------------------------------------------------------
#    Keymaps
# ------------------------------------------------------------------------
PT_Alter_keymaps = []


# ------------------------------------------------------------------------
#    Global variable
# ------------------------------------------------------------------------
# The name of the work list
g_wl_name = 'Work List'


# ------------------------------------------------------------------------
#    Operators
# ------------------------------------------------------------------------
class MORPHOBLEND_OT_WorkListAdd(bpy.types.Operator):
    '''Add object to worklist '''
    bl_idname = 'morphoblend.worklist_add'
    bl_label = 'Add'
    bl_description = 'Add object to worklist'
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.object.select_get() and context.object.type == 'MESH'

    def execute(self, context):
        # If the g_wl_name collection does not exist create it
        if g_wl_name not in bpy.data.collections:
            wl_coll = bpy.data.collections.new(name=g_wl_name)
            bpy.context.scene.collection.children.link(wl_coll)
        else:
            wl_coll = bpy.data.collections[g_wl_name]
        for obj in bpy.context.selected_objects:
            # Make a COPY (SymLink) of the object to the Work List if it is not already there
            if bpy.data.collections[g_wl_name] not in obj.users_collection:
                wl_coll.objects.link(obj)
                info_mess = f"{obj.name} added!"
                self.report({'INFO'}, info_mess)
            else:
                info_mess = f"{obj.name} is already in the Work List!"
                self.report({'WARNING'}, info_mess)
        return{'FINISHED'}


class MORPHOBLEND_OT_WorkListRemove(bpy.types.Operator):
    ''' Remove object from worklist'''
    bl_idname = 'morphoblend.worklist_remove'
    bl_label = 'Remove'
    bl_description = 'Remove object from worklist'
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    @classmethod
    def poll(cls, context):
        if g_wl_name in bpy.data.collections:
            return context.active_object is not None and context.object.select_get() and context.object.type == 'MESH'

    def execute(self, context):
        for obj in bpy.context.selected_objects:
            if bpy.data.collections[g_wl_name] in obj.users_collection:
                # Remove the COPY (SymLink) of the object from the Work List
                wl_coll = bpy.data.collections[g_wl_name]
                wl_coll.objects.unlink(obj)
                info_mess = f"{obj.name} removed!"
                self.report({'INFO'}, info_mess)
            else:
                info_mess = f"{obj.name} is not in the Work List!"
                self.report({'WARNING'}, info_mess)
        return{'FINISHED'}


class MORPHOBLEND_OT_WorkListNext(bpy.types.Operator):
    ''' Fetch next object in Work List'''
    bl_idname = 'morphoblend.worklist_next'
    bl_label = 'Next'
    bl_description = 'Fetch next object in Work List'
    bl_options = {'REGISTER', 'INTERNAL'}

    @classmethod
    def poll(cls, context):
        # activate only if Work list exist and is not empty
        if g_wl_name in bpy.data.collections:
            obj_in_wp = bpy.data.collections[g_wl_name].objects[:]
            if len(obj_in_wp) > 0:
                return True

    def execute(self, context):
        if len(bpy.context.selected_objects) == 1:
            obj = bpy.context.selected_objects[0]
        elif len(bpy.context.selected_objects) == 0:
            obj = bpy.data.collections[g_wl_name].objects[0]
        else:
            obj = bpy.data.collections[g_wl_name].objects[0]
            self.report({'WARNING'}, 'Only one cell can be selected')
        result = ObjectNavigator(g_wl_name, obj, 'next')
        if result is not False:
            # deselect current obj and make the next one active & selected
            bpy.context.active_object.select_set(state=False)
            bpy.context.view_layer.objects.active = result
            bpy.context.active_object.select_set(state=True)
        else:
            self.report({'WARNING'}, 'Cell not in the Work List')
        return{'FINISHED'}


class MORPHOBLEND_OT_WorkListPrevious(bpy.types.Operator):
    ''' Fetch previous object in Work List'''
    bl_idname = 'morphoblend.worklist_previous'
    bl_label = 'Previous'
    bl_description = 'Fetch previous object in Work List'
    bl_options = {'REGISTER', 'INTERNAL'}

    @classmethod
    def poll(cls, context):
        # activate only if Work list exist and is not empty
        if g_wl_name in bpy.data.collections:
            obj_in_wp = bpy.data.collections[g_wl_name].objects[:]
            if len(obj_in_wp) > 0:
                return True

    def execute(self, context):
        if len(bpy.context.selected_objects) == 1:
            obj = bpy.context.selected_objects[0]
        elif len(bpy.context.selected_objects) == 0:
            obj = bpy.data.collections[g_wl_name].objects[0]
        else:
            obj = bpy.data.collections[g_wl_name].objects[0]
            self.report({'WARNING'}, 'Only one cell can be selected')
        result = ObjectNavigator(g_wl_name, obj, 'previous')
        if result is not False:
            # deselect current obj and make the next one active & selected
            bpy.context.active_object.select_set(state=False)
            bpy.context.view_layer.objects.active = result
            bpy.context.active_object.select_set(state=True)
        else:
            self.report({'WARNING'}, 'Cell not in the Work List')
        return{'FINISHED'}


class MORPHOBLEND_OT_Merge(bpy.types.Operator):
    ''' Merge selected cells.'''
    bl_idname = 'morphoblend.merge'
    bl_label = 'Merge'
    bl_descripton = 'Merge selected cells.'
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.object.select_get() and context.object.type == 'MESH' and len(context.view_layer.objects.selected) >= 2

    def execute(self, context):
        # Estimate the size of each object and make sure it is the 'master'
        names_array = []
        vol_array = []
        for obj in bpy.context.selected_objects:
            bpy.context.view_layer.objects.active = obj
            names_array.append(obj.name)
            vol, area = volume_and_area_from_object(obj)
            vol_array.append(vol)
        biggest_name = names_array[vol_array.index(max(vol_array))]
        biggest_ob = bpy.context.scene.objects[biggest_name]
        bpy.context.view_layer.objects.active = biggest_ob
        # Join the two objects
        bpy.ops.object.join()
        remesh = biggest_ob.modifiers.new(name='Remesh', type='REMESH')
        remesh.voxel_size = 0.9 / bpy.context.scene.unit_settings.scale_length
        remesh.use_smooth_shade = True
        remesh.mode = 'VOXEL'
        apply_modifiers(biggest_ob)
        self.report({'INFO'}, 'Merge completed!')
        return {'FINISHED'}


class MORPHOBLEND_OT_Split(bpy.types.Operator):
    ''' Split selected cell.'''
    bl_idname = 'morphoblend.split'
    bl_label = 'Split'
    bl_descripton = 'Split selected cell.'
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.object.select_get() and context.object.type == 'MESH' and len(context.view_layer.objects.selected) < 2

    def execute(self, context):
        ob = bpy.context.selected_objects[0]
        bpy.ops.object.mode_set(mode='EDIT')
        mesh = bmesh.from_edit_mesh(ob.data)
        for f in mesh.faces:
            f.select = True
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        row = self.layout
        row.label(text='1. Define plane of cut with Bisect tool, press [Enter]')
        row = self.layout
        row.label(text='2. Rip, press [V]')
        row = self.layout
        row.label(text='3. Move mesh 3 times with the keyboard, press [Enter]')
        row = self.layout
        row.label(text="4. Press 'Finish Split'")


class MORPHOBLEND_OT_Split_finish(bpy.types.Operator):
    '''Finishes the spliting of selected cell.'''
    bl_idname = 'morphoblend.split_finish'
    bl_label = 'Split_finish'
    bl_descripton = 'Finishes the spliting of selected cell.'
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.object.select_get() and context.object.type == 'MESH' and len(context.view_layer.objects.selected) < 2 and bpy.context.active_object.mode == 'EDIT'

    def invoke(self, context, event):
        # List of all objects before separating the split object in two
        all_objects = [ob for ob in bpy.data.objects if ob.type == 'MESH']

        loc = event.mouse_region_x, event.mouse_region_y
        bpy.ops.view3d.select(location=loc)
        bpy.ops.mesh.select_linked()
        # Fill
        bpy.ops.mesh.edge_face_add()
        # Inverse selection to select other object
        bpy.ops.mesh.select_all(action='INVERT')
        # Fill
        bpy.ops.mesh.edge_face_add()
        # Make 2 objects based on selection
        bpy.context.active_object.select_set(state=False)
        # L to select one of the two object where the mouse is
        bpy.ops.mesh.separate(type='SELECTED')
        # Back to Object Mode and redefine center of each object
        # Get the list of all objects after separation
        split_objects = [ob for ob in bpy.data.objects if ob.type == 'MESH']
        # Get the name of the newly separated object
        for i in all_objects:
            split_objects.remove(i)
        # Get the name of the object is was separated from
        split_object = split_objects[0]
        re_end_number = re.search('\.(\d{3})$', split_object.name)
        if re_end_number:
            split_end_number = int(re_end_number.group(1))
            if split_end_number > 1:
                orig_end_number = split_end_number - 1
                orig_end_str = f'.{orig_end_number:03d}'
            else:
                orig_end_str = ''
            original_object_name = re.sub('\.\d{3}$', orig_end_str, split_object.name)
        else:
            self.report({'WARNING'}, 'Something went wrong in renaming!')
        # Create a list with the two objects resulting from the split
        original_split_objects = []
        original_split_objects.append(split_object)
        original_split_objects.append(bpy.context.scene.objects[original_object_name])
        # Switch to Object mode to respecify their centers
        bpy.ops.object.mode_set(mode='OBJECT')
        for ob in original_split_objects:
            bpy.data.objects[ob.name].select_set(True)
            bpy.ops.object.origin_set(type='ORIGIN_CENTER_OF_VOLUME', center='MEDIAN')
        # Rename the split object
        split_object.name = f"{bpy.context.scene.objects[original_object_name].name}_split"
        self.report({'INFO'}, 'Split completed!')
        return {'FINISHED'}


# ------------------------------------------------------------------------
#    UI elements
# ------------------------------------------------------------------------
class MORPHOBLEND_PT_Alter(bpy.types.Panel):
    bl_idname = 'MORPHOBLEND_PT_Alter'
    bl_label = 'Alter'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'MorphoBlend'
    bl_parent_id = 'VIEW3D_PT_MorphoBlend'

    def draw_header(self, context):
        layout = self.layout
        layout.label(icon='MOD_BEVEL')

    def draw(self, context):
        layout = self.layout

        box = layout.box()
        row = box.row()
        if g_wl_name in bpy.data.collections:
            obj_in_wp = bpy.data.collections[g_wl_name].objects[:]
            if len(obj_in_wp) > 1:
                text_box = f"Work List ({str(len(obj_in_wp))} cells) - [{str(len(bpy.context.selected_objects))} selected cell(s)]"
            else:
                text_box = f"Work List ({str(len(obj_in_wp))} cell) - [{str(len(bpy.context.selected_objects))} selected cell(s)]"
        else:
            text_box = f"Work List (0 cell) [{str(len(bpy.context.selected_objects))} selected cell(s)]"
        row.label(text=text_box, icon='PRESET')
        row = box.row()
        row.operator(MORPHOBLEND_OT_WorkListAdd.bl_idname, text='Add')
        row.operator(MORPHOBLEND_OT_WorkListRemove.bl_idname, text='Remove')
        row = box.row()
        row.operator(MORPHOBLEND_OT_WorkListNext.bl_idname, text='Next')
        row.operator(MORPHOBLEND_OT_WorkListPrevious.bl_idname, text='Previous')

        box = layout.box()
        row = box.row()
        if len(bpy.context.selected_objects) > 1:
            text_box = f"Merge/Split [{str(len(bpy.context.selected_objects))} selected cells]"
        else:
            text_box = f"Merge/Split [{str(len(bpy.context.selected_objects))} selected cell]"
        row.label(text=text_box, icon='AUTOMERGE_ON')
        row = box.row()
        row.operator(MORPHOBLEND_OT_Merge.bl_idname, text='Merge')
        row = box.row()
        row.operator(MORPHOBLEND_OT_Split.bl_idname, text='Start Split')
        row.operator(MORPHOBLEND_OT_Split_finish.bl_idname, text='Finish Split')


# ------------------------------------------------------------------------
#    Registrer/unregister calls
# ------------------------------------------------------------------------
classes = (MORPHOBLEND_OT_WorkListAdd,
MORPHOBLEND_OT_WorkListRemove,
MORPHOBLEND_OT_WorkListNext,
MORPHOBLEND_OT_WorkListPrevious,
MORPHOBLEND_OT_Merge,
MORPHOBLEND_OT_Split,
MORPHOBLEND_OT_Split_finish,)

register_classes, unregister_classes = bpy.utils.register_classes_factory(classes)


def register_alter():
    register_classes()
    # Define  keymaps
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    # MORPHOBLEND_OT_WorkListAdd --> Ctrl + Shift + A
    if kc:
        km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')
        kmi = km.keymap_items.new(MORPHOBLEND_OT_WorkListAdd.bl_idname, type='A', value='PRESS', ctrl=True, shift=True)
        PT_Alter_keymaps.append((km, kmi))
    # MORPHOBLEND_OT_WorkListRemove --> Ctrl + Shift + R
    if kc:
        km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')
        kmi = km.keymap_items.new(MORPHOBLEND_OT_WorkListRemove.bl_idname, type='R', value='PRESS', ctrl=True, shift=True)
        PT_Alter_keymaps.append((km, kmi))
    # MORPHOBLEND_OT_WorkListNext --> Shift + N
    if kc:
        km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')
        kmi = km.keymap_items.new(MORPHOBLEND_OT_WorkListNext.bl_idname, type='N', value='PRESS', ctrl=False, shift=True)
        PT_Alter_keymaps.append((km, kmi))
    # MORPHOBLEND_OT_WorkListRemove --> Shift + P
    if kc:
        km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')
        kmi = km.keymap_items.new(MORPHOBLEND_OT_WorkListPrevious.bl_idname, type='P', value='PRESS', ctrl=False, shift=True)
        PT_Alter_keymaps.append((km, kmi))
    # MORPHOBLEND_OT_Merge --> Ctrl + Shift + M
    if kc:
        km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')
        kmi = km.keymap_items.new(MORPHOBLEND_OT_Merge.bl_idname, type='M', value='PRESS', ctrl=True, shift=True)
        PT_Alter_keymaps.append((km, kmi))
    # MORPHOBLEND_OT_Split --> Ctrl + Shift + Y
    if kc:
        km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')
        kmi = km.keymap_items.new(MORPHOBLEND_OT_Split.bl_idname, type='Y', value='PRESS', ctrl=True, shift=True)
        PT_Alter_keymaps.append((km, kmi))
    # MORPHOBLEND_OT_Split Finish --> Ctrl + Shift + T
    if kc:
        km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')
        kmi = km.keymap_items.new(MORPHOBLEND_OT_Split_finish.bl_idname, type='P', value='PRESS', ctrl=True, shift=True)
        PT_Alter_keymaps.append((km, kmi))


def unregister_alter():
    # handle the keymap
    for km, kmi in PT_Alter_keymaps:
        km.keymap_items.remove(kmi)
    PT_Alter_keymaps.clear()
    unregister_classes()
