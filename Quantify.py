import os
import numpy as np
import csv
import bpy
import bmesh
import re
from glob import glob
from pathlib import Path
from math import radians
from mathutils import (Matrix, Vector)
from random import randrange
from bpy_extras.io_utils import ImportHelper
from bpy.props import (IntProperty,
                       BoolProperty,
                       StringProperty,
                       EnumProperty,
                       PointerProperty,
                       CollectionProperty)

from bpy.types import (Operator,
                       Panel,
                       PropertyGroup,
                       UIList)
from . Process import find_collection
from . Utilities import (create_materials_palette, rgb_to_rgbaf, assign_color, retrieve_global_coordinates, bmesh_copy_from_object, Display2D_Image)

# ------------------------------------------------------------------------
#    Properties
# ------------------------------------------------------------------------
class QuantifyProperties(PropertyGroup):
    myBool: BoolProperty(
        name= "Move to collection",
        description = "Move the renamed files to a new collection.",
        default = False
    )
    export_meas_path: StringProperty(
        name = "Output",
        description = "Where to save the measurements",
        default = "",
        subtype = 'FILE_PATH'
        )
    mapping_palette: EnumProperty(
        name="",
        description="Palette used to colorize.",
        items=[ ('Seq_viridis', "Viridis", ""),
                ('Div_brownGreen', "BrownGreen diverging", ""),
                ('Div_lilaGreen', "LilaGreen diverging", ""),
                ('Div_violetGreen', "VioletGreen diverging", ""),
                ('Div_brownViolet', "BrownViolet diverging", ""),
                ('Div_french', "French diverging", ""),
                ('Div_redBlue', "RedBlue diverging", ""),
               ]
        )

    metric_choice: EnumProperty(
        name="",
        description="Metric available for coloring",
        items=[ ('VOLUME', "Volume", ""),
                ('AREA', "Area", ""),
               ]
        )
class MORPHOBLEND_objectCollection(PropertyGroup):
    coll_id: IntProperty()
    coll_item: StringProperty()

# ------------------------------------------------------------------------
#    Operators
# ------------------------------------------------------------------------
class MORPHOBLEND_OT_Morphometric(bpy.types.Operator):
    bl_idname = "morphoblend.morphometric"
    bl_label = "Measure"
    bl_descripton = "Compute diverse morphometric measures on selected cells."

    # Class properties
    chosen_palette: bpy.props.StringProperty()
    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.object.select_get() and context.object.type == 'MESH'

    def execute(self, context):
        scene  = context.scene
        quantify_op  = scene.quantify_tool
        headers = "Object    Collection  Volume  Area    Dim_x    Dim_y    Dim_z    Center_x    Center_y    Center_z"
        if not bool(context.scene.coll):
            bpy.ops.morphoblend.list_action(list_item = f"{headers}", action = 'ADD')
        for obj in bpy.context.selected_objects:
            bpy.context.view_layer.objects.active = obj
            if obj.type == 'MESH':
                obj_coll = find_collection(bpy.context, bpy.data.objects[obj.name]).name.replace(" ", "_")
                vol_obj, area_obj = volume_and_area_from_object(obj)
                dims = scaled_dimensions(obj)
                obj_center =  retrieve_global_coordinates(obj)
                #obj_center =  (obj.dimensions[0], obj.dimensions[1], obj.dimensions[2])
                line = f"{obj.name}  {obj_coll}    {vol_obj:.3f}  {area_obj:.3f}    {dims[0]:.3f}    {dims[1]:.3f}    {dims[2]:.3f}    {obj_center[0]:.3f}    {obj_center[1]:.3f}    {obj_center[2]:.3f}"
                bpy.ops.morphoblend.list_action(list_item = f"{line}", action = 'ADD')
        return{'FINISHED'}

class MORPHOBLEND_OT_ListActions(Operator):
    bl_idname = "morphoblend.list_action"
    bl_label = "List Actions"
    bl_description = "Move items up and down, add and remove"
    bl_options = {'REGISTER'}

    action: EnumProperty(
        items=(
            ('UP', "Up", ""),
            ('DOWN', "Down", ""),
            ('REMOVE', "Remove", ""),
            ('ADD', "Add", "")))

    list_item: StringProperty()
    def execute(self, context):
        return self.invoke(context, None)

    def invoke(self, context, event):
        scn = context.scene
        idx = scn.coll_index

        try:
            item = scn.coll[idx]
        except IndexError:
            pass
        else:
            if self.action == 'DOWN' and idx < len(scn.coll) - 1:
                item_next = scn.coll[idx+1].name
                scn.coll.move(idx, idx+1)
                scn.coll_index += 1
                info = 'Item "%s" moved to position %d' % (item.name, scn.coll_index + 1)
                self.report({'INFO'}, info)

            elif self.action == 'UP' and idx >= 1:
                item_prev = scn.coll[idx-1].name
                scn.coll.move(idx, idx-1)
                scn.coll_index -= 1
                info = 'Item "%s" moved to position %d' % (item.name, scn.coll_index + 1)
                self.report({'INFO'}, info)

            elif self.action == 'REMOVE':
                info = 'Item "%s" removed from list' % (scn.coll[idx].name)
                scn.coll_index -= 1
                scn.coll.remove(idx)
                self.report({'INFO'}, info)

        if self.action == 'ADD':
            if self.list_item:
                item = scn.coll.add()
                item.name = self.list_item
                item.coll_id = len(scn.coll)
                scn.coll_index = len(scn.coll)-1
                info = '"%s" added to list' % (item.name)
                self.report({'INFO'}, info)

        return {"FINISHED"}


class MORPHOBLEND_OT_clearList(Operator):
    bl_idname = "morphoblend.clear_list"
    bl_label = "Clear List"
    bl_description = "Clear all items of the list"
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return bool(context.scene.coll)

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        if bool(context.scene.coll):
            context.scene.coll.clear()
            self.report({'INFO'}, "All items removed")
        else:
            self.report({'INFO'}, "Nothing to remove")
        return{'FINISHED'}

class MORPHOBLEND_OT_SaveItems(Operator):
    bl_idname = "morphoblend.save_measurements"
    bl_label = "Save measurements to file"
    bl_description = "Save all measurements to a file"
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return bool(context.scene.coll)

    def execute(self, context):
        scn = context.scene
        quantify_tool = scn.quantify_tool
        with open(bpy.path.abspath(quantify_tool.export_meas_path), 'w', newline='\n') as f:
            writer = csv.writer(f)
            for item in scn.coll:
                writer.writerow(re.split("\s+", item.name))
        info_mess = str(len(scn.coll)-1) + " measurements saved!"
        self.report({'INFO'}, info_mess)
        return{'FINISHED'}

class MORPHOBLEND_OT_ColorizeMetric(Operator):
    bl_idname = "morphoblend.colorize_metric"
    bl_label = "Colorize cells according to a metric"
    bl_description = ""
    bl_options = {'INTERNAL'}

    # Class properties
    mapping_palette: bpy.props.StringProperty()
    chosen_metric: bpy.props.StringProperty()
    chosen_metric: EnumProperty(
        items=(
            ('VOLUME', "", ""),
            ('AREA', "", ""))
        )

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.object.select_get() and context.object.type == 'MESH'

    def execute(self, context):
        scene  = context.scene
        quantify_op  = scene.quantify_tool
        # Retrieve Volume & Area for all selected object, display in the results window
        headers = "Label    Collection  Volume  Area"
        names_array = []
        vol_array = []
        area_array = []
        #if not bool(context.scene.coll):
        #    bpy.ops.morphoblend.list_action(list_item = f"{headers}", action = 'ADD')
        for obj in bpy.context.selected_objects:
            bpy.context.view_layer.objects.active = obj
            if obj.type == 'MESH':
                obj_coll = find_collection(bpy.context, bpy.data.objects[obj.name]).name
                vol_obj, area_obj = volume_and_area_from_object(obj)
                names_array.append(obj.name)
                vol_array.append(vol_obj)
                area_array.append(area_obj)
        if self.chosen_metric == 'VOLUME':
            metric_to_map = vol_array
        if self.chosen_metric == 'AREA':
            metric_to_map = area_array
        # Store metric in a Dict as Obj.name / metric
        metric_to_map = dict(zip(names_array, metric_to_map))
        mapped_obj, mat_palette = map_material_to_metric(metric_to_map, self.mapping_palette)
        # Iterate over the Dict key assign materials to objects
        for key, index in mapped_obj.items():
            obj = bpy.data.objects[key]
            if obj.type == 'MESH':
                assign_color(obj, mat_palette, color_index= index-1)
        Display2D_Image(self.mapping_palette, inMinMax=(min(list(metric_to_map.values())), max(list(metric_to_map.values()))), inLabel= self.chosen_metric)
        # to stop drawing (triggered somehow...):
        # bpy.type.SpaceView3D.draw_handler_remove(LUTdrawhandler, 'WINDOW')
        info_mess = str(len(bpy.context.selected_objects)) + " cells processed!"
        self.report({'INFO'}, info_mess)
        return{'FINISHED'}


# ------------------------------------------------------------------------
#    UI elements
# ------------------------------------------------------------------------
class MORPHOBLEND_UL_items(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        split = layout.split(factor=0.2)
        split.label(text="%d" % (index))
        split.label(text=item.name)

    def invoke(self, context, event):
        pass


class MORPHOBLEND_PT_Quantify(bpy.types.Panel):
    bl_idname = "MORPHOBLEND_PT_Quantify"
    bl_label = "Quantify"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "MorphoBlend"
    bl_parent_id = 'VIEW3D_PT_MorphoBlend'

    def draw_header(self, context):
        layout = self.layout
        layout.label(icon='SEQ_HISTOGRAM')

    def draw(self, context):
        layout = self.layout
        scene  = context.scene
        quantify_pt  = scene.quantify_tool
        coll = scene.coll
        coll_index = scene.coll_index

        box = layout.box()
        row = box.row()

        if len(bpy.context.selected_objects) > 1:
            text_box = "Morphometrics [" + str(len(bpy.context.selected_objects)) + " selected cells]"
        else:
            text_box = "Morphometrics [" + str(len(bpy.context.selected_objects)) + " selected cell]"

        row.label(text= text_box, icon='OUTLINER_DATA_CURVE')

        row = box.row()
        row.operator(MORPHOBLEND_OT_Morphometric.bl_idname, text = "Measure!")

        row = box.row()
        row.label(text="Results", icon='RIGHTARROW')

        rows = 6
        row = box.row()
        row.template_list("MORPHOBLEND_UL_items", "", scene, "coll", scene, "coll_index", rows=rows)


        row = box.row()
        row.prop(quantify_pt , "export_meas_path")

        row = box.row()
        row.operator("morphoblend.clear_list", text = "Clear Measurements",  icon="X")
        row.operator(MORPHOBLEND_OT_SaveItems.bl_idname, icon="EXPORT", text="Save Measurements")

        box = layout.box()
        row = box.row()
        if len(bpy.context.selected_objects) > 1:
            text_box = "Colorize metric [" + str(len(bpy.context.selected_objects)) + " selected cells]"
        else:
            text_box = "Colorize metric [" + str(len(bpy.context.selected_objects)) + " selected cell]"
        row.label(text= text_box, icon='BRUSH_DATA')

        row = box.row()
        row.label(text="Palette:")
        row.prop(quantify_pt, "mapping_palette", text="")
        row = box.row()
        row.label(text="Metric:")
        row.prop(quantify_pt, "metric_choice", text="")

        row = box.row()
        op = row.operator(MORPHOBLEND_OT_ColorizeMetric.bl_idname, text = "Colorize!")
        op.mapping_palette = quantify_pt.mapping_palette
        op.chosen_metric = quantify_pt.metric_choice
# ------------------------------------------------------------------------
#    Registrer/unregister calls
# ------------------------------------------------------------------------
classes = (QuantifyProperties,
    MORPHOBLEND_OT_Morphometric,
    MORPHOBLEND_OT_ListActions,
    MORPHOBLEND_OT_clearList,
    MORPHOBLEND_OT_SaveItems,
    MORPHOBLEND_OT_ColorizeMetric,
    MORPHOBLEND_UL_items,
    MORPHOBLEND_objectCollection
)

register_classes, unregister_classes = bpy.utils.register_classes_factory(classes)

def register_quantify():
    register_classes()
    bpy.types.Scene.quantify_tool = PointerProperty(type=QuantifyProperties)
    bpy.types.Scene.coll = CollectionProperty(type=MORPHOBLEND_objectCollection)
    bpy.types.Scene.coll_index = IntProperty()


def unregister_quantify():
    del bpy.types.Scene.coll_index
    del bpy.types.Scene.coll
    del bpy.types.Scene.quantify_tool
    unregister_classes()



# ------------------------------------------------------------------------
#    Operator modules
# ------------------------------------------------------------------------

def volume_and_area_from_object(inObj):
    bm = bmesh.new()   # create an empty BMesh
    bm = bmesh_copy_from_object(inObj, apply_modifiers=True)
    volume = bm.calc_volume()
    area = sum(f.calc_area() for f in bm.faces)
    bm.free()
    scaled_volume = volume * bpy.context.scene.unit_settings.scale_length ** 3
    scaled_area = area * bpy.context.scene.unit_settings.scale_length ** 2
    return abs(scaled_volume), abs(scaled_area)

def scaled_dimensions(inObj):
    dims = inObj.dimensions
    return dims * bpy.context.scene.unit_settings.scale_length


def map_material_to_metric(inMeasRes, inPaletteName):
    mat_palette = create_materials_palette(inPaletteName)
    names_list = list(inMeasRes.keys())
    values_list = list(inMeasRes.values())
    bins = np.linspace(min(values_list), max(values_list), len(mat_palette))
    digitized = np.digitize(values_list, bins)
    mapped_names = dict(zip(names_list, digitized))
    return  mapped_names, mat_palette
