import re

import bpy
from bpy.props import BoolProperty, PointerProperty, EnumProperty, StringProperty

from .Utilities import (unique_colls_names_list,
                        col_hierarchy,
                        collections_from_pattern,
                        show_active_tp,
                        collection_navigator,
                        hide_display)

# ------------------------------------------------------------------------
#    Keymaps
# ------------------------------------------------------------------------
PT_Analyze_keymaps = []


# ------------------------------------------------------------------------
#    Properties
# ------------------------------------------------------------------------
def unique_colls_callback(scene, context):
    items = [('-', '', '')]
    unique_names = unique_colls_names_list()
    for name in unique_names:
        items.append((name, name, ''))
    return items


class RenderProperties(bpy.types.PropertyGroup):
    makeInvis: BoolProperty(
        name='Make collection visible',
        description='Make collection visible',
        default=False
    )
    selection: EnumProperty(
        name='Collections',
        description='Uniques collections',
        items=unique_colls_callback
    )
    tp_pattern: StringProperty(
        name='Time point pattern',
        description='Regex pattern describing time points',  # Matches time point (t1, T42, t09, etc...)
        default='[Tt]\d{1,}'
    )

# ------------------------------------------------------------------------
#    Global variable
# ------------------------------------------------------------------------


# ------------------------------------------------------------------------
#    Operators
# ------------------------------------------------------------------------
class MORPHOBLEND_OT_NextTimePoint(bpy.types.Operator):
    '''Make next time points collections visible.'''
    bl_idname = 'morphoblend.next_timepoint'
    bl_label = 'Next time points'
    bl_descripton = 'Make next time points collections visible.'
    bl_options = {'REGISTER', 'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        analyze_op = context.scene.render_tool
        # Get all TP collections at the topmost level
        all_tp_cols = collections_from_pattern(analyze_op.tp_pattern)
        # Retrieve the currently active TP collection and make it the only visible
        currentTPcoll = show_active_tp(context)
        # Get the next time point and display it
        next_tp = collection_navigator(all_tp_cols, currentTPcoll, "next")
        if next_tp is not False:
            info_mess = hide_display(currentTPcoll, next_tp)
            self.report({'INFO'}, info_mess)
        else:
            self.report({'WARNING'}, "Problem")
        return{'FINISHED'}


class MORPHOBLEND_OT_PreviousTimePoint(bpy.types.Operator):
    '''Make previous time points collections visible. '''
    bl_idname = 'morphoblend.previous_timepoint'
    bl_label = 'Previous time points'
    bl_descripton = 'Make previous time points collections visible.'
    bl_options = {'REGISTER', 'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        render_op = context.scene.render_tool
        # Get all TP collections at the topmost level
        all_tp_cols = collections_from_pattern(render_op.tp_pattern)
        # Retrieve the currently active TP collection and make it the only visible
        currentTPcoll = show_active_tp(context)
        # Get the previous time point and display it
        next_tp = collection_navigator(all_tp_cols, currentTPcoll, "previous")
        if next_tp is not False:
            info_mess = hide_display(currentTPcoll, next_tp)
            self.report({'INFO'}, info_mess)
        else:
            self.report({'WARNING'}, "Problem")
        return{'FINISHED'}

# TODO  THIS IS USELESS: REMOVE - Replace with the function to render over all TPs
class MORPHOBLEND_OT_ChangeVisibilityCollection(bpy.types.Operator):
    '''Set visibility of collections based on name pattern matching.'''
    bl_idname = 'morphoblend.toggle_visibility_collections'
    bl_label = 'Set'
    bl_descripton = 'Set visibility of collections based on name pattern matching.'

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        render_op = context.scene.render_tool
        _selection = render_op.selection
        _makeinvis = render_op.makeInvis

        # Retrieve hiearchy of all collection and their parents
        cols_tree = col_hierarchy(bpy.context.scene.collection, levels=9)
        all_cols = {i: k for k, v in cols_tree.items() for i in v}

        # Parse all collections and process the ones matching the pattern
        n_coll = 0
        for col in all_cols:
            if re.search(_selection, col.name):
                n_coll += 1
                col.hide_viewport = _makeinvis
                col.hide_render = _makeinvis

        if n_coll > 0:
            info_mess = f"{str(n_coll)} collections matched!"
        else:
            info_mess = 'No match'
        self.report({'INFO'}, info_mess)
        return {'FINISHED'}


# ------------------------------------------------------------------------
#    UI elements
# ------------------------------------------------------------------------
class MORPHOBLEND_PT_Render(bpy.types.Panel):
    bl_idname = 'MORPHOBLEND_PT_Render'
    bl_label = 'Render'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'MorphoBlend'
    bl_parent_id = 'VIEW3D_PT_MorphoBlend'

    def draw_header(self, context):
        layout = self.layout
        layout.label(icon='SHADING_RENDERED')

    def draw(self, context):
        layout = self.layout
        render_op = context.scene.render_tool

        box = layout.box()
        row = box.row()
        row.label(text="Show/hide collections", icon='RESTRICT_VIEW_ON')

        row = box.row()
        row.prop(render_op, 'selection', text='')
        row.prop(render_op, "makeInvis", text="Hide")
        row.operator(MORPHOBLEND_OT_ChangeVisibilityCollection.bl_idname, text="Set")


# ------------------------------------------------------------------------
#    Registrer/unregister calls
# ------------------------------------------------------------------------
classes = (RenderProperties,
MORPHOBLEND_OT_ChangeVisibilityCollection,
MORPHOBLEND_OT_NextTimePoint,
MORPHOBLEND_OT_PreviousTimePoint)

register_classes, unregister_classes = bpy.utils.register_classes_factory(classes)


def register_render():
    register_classes()
    bpy.types.Scene.render_tool = PointerProperty(type=RenderProperties)
    # Define  keymaps
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if kc:
        # MORPHOBLEND_OT_NextTimePoint --> Ctrl + Shift + down_arrow
        km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')
        kmi = km.keymap_items.new(MORPHOBLEND_OT_NextTimePoint.bl_idname, type='DOWN_ARROW', value='PRESS', ctrl=True, shift=True)
        PT_Analyze_keymaps.append((km, kmi))
    if kc:
        # MORPHOBLEND_OT_PreviousTimePoint --> Ctrl + Shift + up_arrow
        km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')
        kmi = km.keymap_items.new(MORPHOBLEND_OT_PreviousTimePoint.bl_idname, type='UP_ARROW', value='PRESS', ctrl=True, shift=True)
        PT_Analyze_keymaps.append((km, kmi))


def unregister_render():
    # handle the keymap
    for km, kmi in PT_Analyze_keymaps:
        km.keymap_items.remove(kmi)
    PT_Analyze_keymaps.clear()
    del bpy.types.Scene.render_tool
    unregister_classes()
