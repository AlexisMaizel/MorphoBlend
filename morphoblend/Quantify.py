import csv
import re

import bpy
import numpy as np
from bpy.props import (CollectionProperty, EnumProperty,
                       IntProperty, PointerProperty, StringProperty, BoolProperty)

from .Utilities import (Display2D_LUT_image, assign_material, create_materials_palette,
                        get_collection, get_global_coordinates,
                        volume_and_area_from_object, scaled_dimensions)


# ------------------------------------------------------------------------
#    Properties
# ------------------------------------------------------------------------
class QuantifyProperties(bpy.types.PropertyGroup):
    export_meas_path: StringProperty(
        name='Output',
        description='Where to save the measurements',
        default='',
        subtype='FILE_PATH'
        )
    bool_qt_all: BoolProperty(
        name='Quantify all',
        description='Compute morphometric on all cells, even the non selected / visible ones',
        default=False
    )
    mapping_palette: EnumProperty(
        name='',
        description='Palette used to colorize.',
        items=[('Seq_viridis', 'Viridis', ''),
                ('Div_brownGreen', 'BrownGreen diverging', ''),
                ('Div_lilaGreen', 'LilaGreen diverging', ''),
                ('Div_violetGreen', 'VioletGreen diverging', ''),
                ('Div_brownViolet', 'BrownViolet diverging', ''),
                ('Div_french', 'French diverging', ''),
                ('Div_redBlue', 'RedBlue diverging', ''),
               ]
        )
    metric_choice: EnumProperty(
        name='',
        description="Metric available for coloring",
        items=[('VOLUME', 'Volume', ''),
                ('AREA', 'Area', ''),
                ('VSR', 'VSR', ''),
                ('DIM_X', 'X size', ''),
                ('DIM_Y', 'Y size', ''),
                ('DIM_Z', 'Z size', ''),
               ]
        )


class Quantify_results(bpy.types.PropertyGroup):
    coll_id: IntProperty()
    coll_item: StringProperty()


# ------------------------------------------------------------------------
#    Operators
# ------------------------------------------------------------------------
# TODO  Pimp the UiList prosps --> https://sinestesia.co/blog/tutorials/amazing-uilists-in-blender/
class MORPHOBLEND_OT_Morphometric(bpy.types.Operator):
    ''' Compute diverse morphometric measures on selected cells '''
    bl_idname = 'morphoblend.morphometric'
    bl_label = 'Measure'
    bl_descripton = 'Compute diverse morphometric measures on selected cells.'

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.object.select_get() and context.object.type == 'MESH'

    def format_line(self, LineArray):
        formatted_line = ' '.join(LineArray)
        return formatted_line

    def execute(self, context):
        process_op = context.scene.quantify_tool
        _apply_to_all = process_op.bool_qt_all
        headers = ['Object', 'Collection', 'Volume', 'Area', 'VSR', 'Dim_x', 'Dim_y', 'Dim_z', 'Center_x', 'Center_y', 'Center_z']
        if not bool(context.scene.results):
            bpy.ops.morphoblend.list_action(list_item=self.format_line(headers), action='ADD')
        if _apply_to_all:
            objects = bpy.context.scene.objects
        else:
            objects = bpy.context.selected_objects
        for obj in objects:
            bpy.context.view_layer.objects.active = obj
            obj_line = []
            if obj.type == 'MESH':
                obj.name.replace(' ', '_')
                obj_line.append(obj.name)
                obj_coll = get_collection(bpy.data.objects[obj.name]).name.replace(' ', '_')
                obj_line.append(obj_coll)
                vol_obj, area_obj = volume_and_area_from_object(obj)
                obj_line.extend([f'{vol_obj:.3f}', f'{area_obj:.3f}', f'{vol_obj/area_obj:.3f}'])
                dims = scaled_dimensions(obj)
                obj_line.extend([f'{dims[0]:.3f}', f'{dims[1]:.3f}', f'{dims[2]:.3f}'])
                obj_center = get_global_coordinates(obj) * bpy.context.scene.unit_settings.scale_length
                obj_line.extend([f'{obj_center[0]:.3f}', f'{obj_center[1]:.3f}', f'{obj_center[2]:.3f}'])
                print(obj_line)
                bpy.ops.morphoblend.list_action(list_item=self.format_line(obj_line), action='ADD')
        return{'FINISHED'}


class MORPHOBLEND_OT_ListActions(bpy.types.Operator):
    ''' Move items up and down, add and remove in the list'''
    bl_idname = 'morphoblend.list_action'
    bl_label = 'List Actions'
    bl_description = 'Move items up and down, add and remove'
    bl_options = {'REGISTER'}

    action: EnumProperty(
        items=(
            ('UP', 'Up', ''),
            ('DOWN', 'Down', ''),
            ('REMOVE', 'Remove', ''),
            ('ADD', 'Add', '')))

    list_item: StringProperty()

    def execute(self, context):
        return self.invoke(context, None)

    def invoke(self, context, event):
        scn = context.scene
        idx = scn.results_index

        try:
            item = scn.results[idx]
        except IndexError:
            pass
        else:
            if self.action == 'DOWN' and idx < len(scn.coll) - 1:
                scn.results.move(idx, idx + 1)
                idx += 1

            elif self.action == 'UP' and idx >= 1:
                scn.results.move(idx, idx - 1)
                idx -= 1

            elif self.action == 'REMOVE':
                idx -= 1
                scn.results.remove(idx)

        if self.action == 'ADD':
            if self.list_item:
                item = scn.results.add()
                item.name = self.list_item
                item.coll_id = len(scn.results)
                idx = len(scn.results) - 1

        return {'FINISHED'}


class MORPHOBLEND_OT_clearList(bpy.types.Operator):
    ''' Clear all items of the list'''
    bl_idname = 'morphoblend.clear_list'
    bl_label = 'Clear List'
    bl_description = 'Clear all items of the list'
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return bool(context.scene.results)

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        if bool(context.scene.results):
            context.scene.results.clear()
            self.report({'INFO'}, 'All items removed')
        else:
            self.report({'INFO'}, 'Nothing to remove')
        return{'FINISHED'}


class MORPHOBLEND_OT_SaveItems(bpy.types.Operator):
    ''' Save all measurements to a CSV file'''
    bl_idname = 'morphoblend.save_measurements'
    bl_label = 'Save measurements to file'
    bl_description = 'Save all measurements to a CSV file'
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return bool(context.scene.results)

    def execute(self, context):
        scn = context.scene
        quantify_tool = scn.quantify_tool
        with open(bpy.path.abspath(quantify_tool.export_meas_path), 'w', newline='\n') as f:
            writer = csv.writer(f)
            for item in scn.results:
                writer.writerow(re.split('\s+', item.name))
        info_mess = f"{str(len(scn.results) - 1)} measurements saved!"
        self.report({'INFO'}, info_mess)
        return{'FINISHED'}


class MORPHOBLEND_OT_ColorizeMetric(bpy.types.Operator):
    ''' Colorize cells according to a metric'''
    bl_idname = 'morphoblend.colorize_metric'
    bl_label = ' colorize_metric'
    bl_description = 'Colorize cells according to a metric'
    bl_options = {'INTERNAL'}

    # Class properties
    mapping_palette: bpy.props.StringProperty()
    chosen_metric: bpy.props.StringProperty()
    chosen_metric: EnumProperty(
        items=(
            ('VOLUME', '', ''),
            ('AREA', '', ''))
        )

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.object.select_get() and context.object.type == 'MESH'

    def map_material_to_metric(self, inMeasRes, inPaletteName):
        '''Maps an array of results on the range of colors in a palette. Returns a dict with the index of each results in the palette and the palette of materials'''
        mat_palette = create_materials_palette(inPaletteName)
        names_list = list(inMeasRes.keys())
        values_list = list(inMeasRes.values())
        bins = np.linspace(min(values_list), max(values_list), len(mat_palette))
        digitized = np.digitize(values_list, bins)
        mapped_names = dict(zip(names_list, digitized))
        return mapped_names, mat_palette

    def execute(self, context):
        # Retrieve Volume & Area for all selected object, display in the results window
        names_array = []
        vol_array = []
        area_array = []

        # Parse all selected
        for obj in bpy.context.selected_objects:
            bpy.context.view_layer.objects.active = obj
            if obj.type == 'MESH':
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
        mapped_obj, mat_palette = self.map_material_to_metric(metric_to_map, self.mapping_palette)
        # Iterate over the Dict key assign materials to objects
        for key, index in mapped_obj.items():
            obj = bpy.data.objects[key]
            if obj.type == 'MESH':
                assign_material(obj, mat_palette, color_index=index - 1)
        Display2D_LUT_image(self.mapping_palette, inMinMax=(min(list(metric_to_map.values())), max(list(metric_to_map.values()))), inLabel=self.chosen_metric)
        # to stop drawing (triggered somehow...):
        # bpy.type.SpaceView3D.draw_handler_remove(LUTdrawhandler, 'WINDOW')
        info_mess = f"{str(len(bpy.context.selected_objects))} cells processed!"
        self.report({'INFO'}, info_mess)
        return{'FINISHED'}


# ------------------------------------------------------------------------
#    UI elements
# ------------------------------------------------------------------------
class MORPHOBLEND_UL_items(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        split = layout.split(factor=0.2)
        split.label(text='%d' % (index))
        split.label(text=item.name)

    def invoke(self, context, event):
        pass


class MORPHOBLEND_PT_Quantify(bpy.types.Panel):
    bl_idname = 'MORPHOBLEND_PT_Quantify'
    bl_label = 'Quantify'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'MorphoBlend'
    bl_parent_id = 'VIEW3D_PT_MorphoBlend'

    def draw_header(self, context):
        layout = self.layout
        layout.label(icon='SEQ_HISTOGRAM')

    def draw(self, context):
        layout = self.layout
        quantify_pt = context.scene.quantify_tool

        box = layout.box()
        row = box.row()

        if len(bpy.context.selected_objects) > 1:
            text_box = f"Morphometrics [{str(len(bpy.context.selected_objects))} selected cells]"
        else:
            text_box = f"Morphometrics [{str(len(bpy.context.selected_objects))} selected cell]"

        row.label(text=text_box, icon='OUTLINER_DATA_CURVE')

        row = box.row()
        row.prop(quantify_pt, 'bool_qt_all')
        row.operator(MORPHOBLEND_OT_Morphometric.bl_idname, text='Measure!')

        row = box.row()
        row.label(text='Results', icon='RIGHTARROW')

        rows = 5
        row = box.row()
        row.template_list('MORPHOBLEND_UL_items', '', context.scene, 'results', context.scene, 'results_index', rows=rows)

        row = box.row()
        row.prop(quantify_pt, 'export_meas_path')

        row = box.row()
        row.operator('morphoblend.clear_list', text='Clear Measurements', icon='X')
        row.operator(MORPHOBLEND_OT_SaveItems.bl_idname, icon='EXPORT', text='Save Measurements')

        box = layout.box()
        row = box.row()
        if len(bpy.context.selected_objects) > 1:
            text_box = f"Colorize metric [{str(len(bpy.context.selected_objects))} selected cells]"
        else:
            text_box = f"Colorize metric [{str(len(bpy.context.selected_objects))} selected cell]"
        row.label(text=text_box, icon='BRUSH_DATA')

        row = box.row()
        row.label(text='Palette:')
        row.prop(quantify_pt, 'mapping_palette', text='')
        row = box.row()
        row.label(text='Metric:')
        row.prop(quantify_pt, 'metric_choice', text='')

        row = box.row()
        op = row.operator(MORPHOBLEND_OT_ColorizeMetric.bl_idname, text='Colorize!')
        op.mapping_palette = quantify_pt.mapping_palette
        op.chosen_metric = quantify_pt.metric_choice


# ------------------------------------------------------------------------
#    Registrer/unregister calls
# ------------------------------------------------------------------------
quantify_classes = (QuantifyProperties,
    MORPHOBLEND_OT_Morphometric,
    MORPHOBLEND_OT_ListActions,
    MORPHOBLEND_OT_clearList,
    MORPHOBLEND_OT_SaveItems,
    MORPHOBLEND_OT_ColorizeMetric,
    MORPHOBLEND_UL_items,
    Quantify_results
)

register_classes, unregister_classes = bpy.utils.register_classes_factory(quantify_classes)


def register_quantify():
    register_classes()
    bpy.types.Scene.quantify_tool = PointerProperty(type=QuantifyProperties)
    bpy.types.Scene.results = CollectionProperty(type=Quantify_results)
    bpy.types.Scene.results_index = IntProperty()


def unregister_quantify():
    del bpy.types.Scene.results_index
    del bpy.types.Scene.results
    del bpy.types.Scene.quantify_tool
    unregister_classes()
