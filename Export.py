import bpy
from bpy.props import BoolProperty, PointerProperty, StringProperty
from .Utilities import  get_collection
# ------------------------------------------------------------------------
#    Properties
# ------------------------------------------------------------------------


class ExportProperties(bpy.types.PropertyGroup):
    bool_export_all: BoolProperty(
        name='Export all cells',
        description='Export all cells',
        default=False
    )
    export_path: StringProperty(
        name='Path',
        description='Path to export',
        default='',
        subtype='DIR_PATH'
    )


# ------------------------------------------------------------------------
#    Global variable
# ------------------------------------------------------------------------


# ------------------------------------------------------------------------
#    Operators
# ------------------------------------------------------------------------
class MORPHOBLEND_OT_Export(bpy.types.Operator):
    '''Export selected cells as PLY files.'''
    bl_idname = 'morphoblend.export'
    bl_label = 'Export'
    bl_descripton = 'Export selected cells as PLY files.'
    bl_options = {'REGISTER', 'INTERNAL'}

    @classmethod
    def poll(cls, context):
        export_op = context.scene.export_tool
        if export_op.bool_export_all:
            return True
        else:
            return context.active_object is not None and context.object.select_get() and context.object.type == 'MESH'

    def export_to_ply(self, obj, outfile_path):
        coll = get_collection(obj)
        _outfile = outfile_path + coll.name + '_' + obj.name + '.ply'
        bpy.ops.export_mesh.ply(filepath=_outfile, use_selection=True)

    def execute(self, context):
        export_op = context.scene.export_tool
        outfile_path = bpy.path.abspath(export_op.export_path)
        # get  objects to export (selection by default)
        obj_export_list = context.selected_objects
        if export_op.bool_export_all == True:
            obj_export_list = [i for i in context.scene.objects]
        # deselect all objects
        bpy.ops.object.select_all(action='DESELECT')
        for obj in obj_export_list:
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
            if obj.type == 'MESH':
                self.export_to_ply(obj, outfile_path)
        self.report({'INFO'}, 'Cell exported')
        return{'FINISHED'}


# ------------------------------------------------------------------------
#    UI elements
# ------------------------------------------------------------------------
class MORPHOBLEND_PT_Export(bpy.types.Panel):
    bl_idname = 'MORPHOBLEND_PT_Export'
    bl_label = 'Export'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'MorphoBlend'
    bl_parent_id = 'VIEW3D_PT_MorphoBlend'

    def draw_header(self, context):
        layout = self.layout
        layout.label(icon='EXPORT')

    def draw(self, context):
        layout = self.layout
        export_op = context.scene.export_tool

        box = layout.box()
        row = box.row()
        row.prop(export_op, "bool_export_all", text="All cells")
        row.prop(export_op, 'export_path')
        row.operator(MORPHOBLEND_OT_Export.bl_idname, text="Export", icon='EXPORT')


# ------------------------------------------------------------------------
#    Registrer/unregister calls
# ------------------------------------------------------------------------
classes = (ExportProperties,
MORPHOBLEND_OT_Export)

register_classes, unregister_classes = bpy.utils.register_classes_factory(classes)


def register_export():
    register_classes()
    bpy.types.Scene.export_tool = PointerProperty(type=ExportProperties)


def unregister_export():
    del bpy.types.Scene.export_tool
    unregister_classes()
