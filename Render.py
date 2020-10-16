import re

import bpy
from bpy.props import BoolProperty, PointerProperty, StringProperty, EnumProperty

from .Utilities import col_hierarchy, unique_colls_names_list


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

# ------------------------------------------------------------------------
#    Global variable
# ------------------------------------------------------------------------


# ------------------------------------------------------------------------
#    Operators
# ------------------------------------------------------------------------
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
MORPHOBLEND_OT_ChangeVisibilityCollection)

register_classes, unregister_classes = bpy.utils.register_classes_factory(classes)


def register_render():
    register_classes()
    bpy.types.Scene.render_tool = PointerProperty(type=RenderProperties)


def unregister_render():
    del bpy.types.Scene.render_tool
    unregister_classes()
