import re

import bpy
from bpy.props import (BoolProperty, EnumProperty,
                       IntVectorProperty, PointerProperty, StringProperty)

from .Quantify import volume_and_area_from_object
from .Utilities import (apply_modifiers, assign_material, col_hierarchy,
                        create_materials_palette,
                        move_obj_to_coll)


# ------------------------------------------------------------------------
#    Global variable
# ------------------------------------------------------------------------
g_filter_results_name = 'Filter Results'


# ------------------------------------------------------------------------
#    Properties
# ------------------------------------------------------------------------
class ProcessProperties(bpy.types.PropertyGroup):

    chosen_palette: EnumProperty(
        name='Palette',
        description='Palette used to colorize',
        items=[('Col_1', '[C] Light blue', ''),
                ('Col_2', '[C] Blue', ''),
                ('Col_3', '[C] Light green', ''),
                ('Col_4', '[C] Green', ''),
                ('Col_5', '[C] Light red', ''),
                ('Col_6', '[C] Red', ''),
                ('Col_7', '[C] Light Orange', ''),
                ('Col_8', '[C] Orange', ''),
                ('Qual_bright', '[P] Bright', ''),
                ('Qual_pastel', '[P] Pastel', ''),
                ('Seq_viridis', '[P] Viridis', ''),
                ('Seq_green', '[P] Green sequential', ''),
                ('Seq_lila', '[P] Lila sequential', ''),
                ('Seq_blueGreen', '[P] BlueGreen sequential', ''),
                ('Seq_red', '[P] Red sequential', ''),
                ('Seq_blue', '[P] Blue sequential', ''),
                ('Seq_blueYellow', '[P] BlueYellow sequential', ''),
                ('Seq_brown', '[P] Brown sequential', ''),
                ('Div_brownGreen', '[P] BrownGreen diverging', ''),
                ('Div_lilaGreen', '[P] LilaGreen diverging', ''),
                ('Div_violetGreen', '[P] VioletGreen diverging', ''),
                ('Div_brownViolet', '[P] BrownViolet diverging', ''),
                ('Div_french', '[P] French diverging', ''),
                ('Div_redBlue', '[P] RedBlue diverging', ''),
               ]
    )
    search_pattern: StringProperty(
        name='Search pattern',
        description='Pattern to be searched',
        default='',
        subtype='NONE'
    )

    replace_pattern: StringProperty(
        name='Replace pattern',
        description='Replacement',
        default='',
        subtype='NONE'
    )
    sort_pattern: StringProperty(
        name='Pattern',
        description='Regex pattern for files to sort',
        default='',
        subtype='NONE'
    )
    color_in_coll_pattern: StringProperty(
        name='Pattern',
        description='Regex pattern to select colllections',
        default='',
        subtype='NONE'
    )
    bool_vol_all: BoolProperty(
        name='Apply filter to all',
        description='Apply the filter to all cells, even the non selected / visible ones',
        default=False
    )
    vol_min_max: IntVectorProperty(
        size=2,
        name='',
        description='Min and Max volume (µm3)',
        default=(100, 2000),
        min=0,
        subtype='NONE'
    )


# ------------------------------------------------------------------------
#    Operators
# ------------------------------------------------------------------------
class MORPHOBLEND_OT_Colorize(bpy.types.Operator):
    '''Assign random color to selected objects.'''
    bl_idname = 'morphoblend.colorize'
    bl_label = 'Colorize'
    bl_descripton = 'Assign random color to selected objects.'

    @classmethod
    def poll(cls, context):
        return context.selected_objects is not None

    def execute(self, context):
        scene = context.scene
        process_op = scene.process_tool
        # Create Palette  if needed
        mat_palette = create_materials_palette(process_op.chosen_palette)
        for obj in bpy.context.selected_objects:
            bpy.context.view_layer.objects.active = obj
            if obj.type == 'MESH':
                assign_material(obj, mat_palette, rand_color=True)
        return {'FINISHED'}


class MORPHOBLEND_OT_ColorizeInColl(bpy.types.Operator):
    '''Assign color to all cells in collections matching the search pattern.'''
    bl_idname = 'morphoblend.colorize_in_coll'
    bl_label = 'Colorize'
    bl_descripton = 'Assign color to all cells in collections matching the search pattern.'

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        max_levels = 9                          # Max Levels to parse
        scn_col = bpy.context.scene.collection  # Root collection
        scene = context.scene
        process_op = scene.process_tool
        _pattern = process_op.color_in_coll_pattern
        # Create Palette  if needed
        mat_palette = create_materials_palette(process_op.chosen_palette)

        # Retrieve hiearchy of all & parents collections
        cols_tree = col_hierarchy(scn_col, levels=max_levels)
        all_col = {i: k for k, v in cols_tree.items() for i in v}

        # Parse all collection and process the ones matching the pattern
        n_obj = 0
        n_coll = 0
        for col in all_col:
            if re.search(_pattern, col.name):
                n_coll += 1
                for obj in col.all_objects:
                    bpy.context.view_layer.objects.active = obj
                    if obj.type == 'MESH':
                        assign_material(obj, mat_palette, rand_color=False)
                        n_obj += 1
        info_mess = f"{str(n_obj)} cells in {str(n_coll)} collections modified!"
        self.report({'INFO'}, info_mess)
        return {'FINISHED'}


class MORPHOBLEND_OT_SelectOnVolume(bpy.types.Operator):
    '''Select objects below a volume threshold'''
    bl_idname = 'morphoblend.selectvolume'
    bl_label = 'Select on Volume'
    bl_descripton = 'Select objects below a volume threshold.'

    @classmethod
    def poll(cls, context):
        scene = context.scene
        process_op = scene.process_tool
        if process_op.bool_vol_all:
            return True
        else:
            return context.selected_objects is not None

    def execute(self, context):
        filter_coll_name = g_filter_results_name
        scene = context.scene
        process_op = scene.process_tool
        _apply_to_all = process_op.bool_vol_all
        (_min_vol, _max_vol) = process_op.vol_min_max
        # Create the  FILTERED collection if it does not exist, empty it if it exists
        if filter_coll_name not in bpy.data.collections:
            filt_coll = bpy.data.collections.new(name=filter_coll_name)
            bpy.context.scene.collection.children.link(filt_coll)
        else:
            filt_coll = bpy.data.collections[filter_coll_name]
            while filt_coll.objects:
                filt_coll.objects.unlink(filt_coll.objects[0])

        k = 0
        if _apply_to_all:
            # Parse all objects of the scene
            for obj in bpy.context.scene.objects:
                if obj.type == 'MESH':
                    (o_vol, o_area) = volume_and_area_from_object(obj)
                    if _min_vol <= o_vol <= _max_vol:
                        # Make a COPY (SymLink) of the object to the Filtered list
                        filt_coll.objects.link(obj)
                        k += 1
        else:
            # Parse selection
            for obj in bpy.context.selected_objects:
                if obj.type == 'MESH':
                    (o_vol, o_area) = volume_and_area_from_object(obj)
                    if _min_vol <= o_vol <= _max_vol:
                        # Make a COPY (SymLink) of the object to the Filtered list
                        filt_coll.objects.link(obj)
                        k += 1

        # Deselect all objects and select the ones filtered
        bpy.ops.object.select_all(action='DESELECT')
        for obj in bpy.data.collections[filter_coll_name].all_objects:
            obj.select_set(True)

        info_mess = f"{str(k)} object(s) identified!"
        self.report({'INFO'}, info_mess)
        return {'FINISHED'}


class MORPHOBLEND_OT_ClearFilter(bpy.types.Operator):
    '''Clear the Filter Result list'''
    bl_idname = 'morphoblend.clearfilter'
    bl_label = 'Clear results filter on Volume'
    bl_descripton = 'Clear the Filter Result list.'

    filter_coll_name = g_filter_results_name

    @classmethod
    def poll(cls, context):
        return cls.filter_coll_name in bpy.data.collections

    def execute(self, context):
        filt_coll = bpy.data.collections[self.filter_coll_name]
        while filt_coll.objects:
            filt_coll.objects.unlink(filt_coll.objects[0])

        info_mess = f"{self.filter_coll_name} emptied!"
        self.report({'INFO'}, info_mess)
        return {'FINISHED'}


class MORPHOBLEND_OT_FinalizeModifiers(bpy.types.Operator):
    '''Apply all modifiers of selected objects'''
    bl_idname = 'morphoblend.finalizemodifiers'
    bl_label = 'Finalize Modifiers'
    bl_descripton = 'Apply all modifiers of selected objects.'

    @classmethod
    def poll(cls, context):
        return context.selected_objects is not None

    def execute(self, context):
        for obj in bpy.context.selected_objects:
            bpy.context.view_layer.objects.active = obj
            if obj.type == 'MESH':
                obj = apply_modifiers(obj)
        info_mess = f"{str(len(bpy.context.selected_objects))} cells modified!"
        self.report({'INFO'}, info_mess)
        return {'FINISHED'}


class MORPHOBLEND_OT_Rename(bpy.types.Operator):
    '''Batch rename objects, use regex'''
    bl_idname = 'morphoblend.renamemove'
    bl_label = 'Rename'
    bl_descripton = 'Batch rename objects, use regex.'

    @classmethod
    def poll(cls, context):
        return context.selected_objects is not None

    def execute(self, context):
        scene = context.scene
        process_op = scene.process_tool
        _search_pattern = process_op.search_pattern
        _replace_pattern = process_op.replace_pattern
        for obj in bpy.context.selected_objects:
            bpy.context.view_layer.objects.active = obj
            if obj.type == 'MESH':
                obj.name = re.sub(_search_pattern, _replace_pattern, obj.name)
        info_mess = f"{str(len(bpy.context.selected_objects))} cells renamed!"
        self.report({'INFO'}, info_mess)
        return {'FINISHED'}


class MORPHOBLEND_OT_Arrange(bpy.types.Operator):
    '''Moves files with name matching pattern to a subcollection.'''
    bl_idname = 'morphoblend.arrange'
    bl_label = 'Sort'
    bl_descripton = 'Moves files with name matching pattern to a subcollection.'

    @classmethod
    def poll(cls, context):
        return context.selected_objects is not None

    def execute(self, context):
        scene = context.scene
        process_op = scene.process_tool
        _pattern = process_op.sort_pattern
        for obj in bpy.context.selected_objects:
            bpy.context.view_layer.objects.active = obj
            if obj.type == 'MESH' and re.search(_pattern, obj.name):
                move_obj_to_coll(obj, 'Sorted')
        info_mess = f"{str(len(bpy.context.selected_objects))} cells sorted!"
        self.report({'INFO'}, info_mess)
        return {'FINISHED'}


# ------------------------------------------------------------------------
#    UI elements
# ------------------------------------------------------------------------


class MORPHOBLEND_PT_Process(bpy.types.Panel):
    bl_idname = 'MORPHOBLEND_PT_Process'
    bl_label = 'Process'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'MorphoBlend'
    bl_parent_id = 'VIEW3D_PT_MorphoBlend'

    def draw_header(self, context):
        layout = self.layout
        layout.label(icon='MOD_PARTICLE_INSTANCE')

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        process_op = scene.process_tool

        box = layout.box()
        row = box.row()
        if len(bpy.context.selected_objects) > 1:
            text_box = f"Assign color [{str(len(bpy.context.selected_objects))} selected cells]"
        else:
            text_box = f"Assign color [{str(len(bpy.context.selected_objects))} selected cell]"
        row.label(text=text_box, icon='COLORSET_07_VEC')

        row = box.row()
        row.label(text='Palette [P] or Color [C]:')
        row.prop(process_op, 'chosen_palette', text='')
        row.operator(MORPHOBLEND_OT_Colorize.bl_idname, text='Colorize')

        box = layout.box()
        row = box.row()
        row.label(text='Bulk color cells in collection', icon='COLORSET_08_VEC')

        row = box.row()
        row.label(text='Palette [P] or Color [C]:')
        row.prop(process_op, 'chosen_palette', text='')
        row = box.row()
        row.prop(process_op, 'color_in_coll_pattern')
        row.operator(MORPHOBLEND_OT_ColorizeInColl.bl_idname, text='Colorize')

        box = layout.box()
        row = box.row()
        if len(bpy.context.selected_objects) > 1:
            text_box = f"Finalize Modifiers [{str(len(bpy.context.selected_objects))} selected cells]"
        else:
            text_box = f"Finalize Modifiers [{str(len(bpy.context.selected_objects))} selected cell]"
        row.label(text=text_box, icon='MODIFIER_ON')

        row = box.row()
        row.operator(MORPHOBLEND_OT_FinalizeModifiers.bl_idname, text='Finalize')

        box = layout.box()
        row = box.row()
        if len(bpy.context.selected_objects) > 1:
            text_box = f"Rename [{str(len(bpy.context.selected_objects))} selected cells]"
        else:
            text_box = f"Rename [{str(len(bpy.context.selected_objects))} selected cell]"
        row.label(text=text_box, icon='OUTLINER_DATA_GP_LAYER')

        row = box.row()
        row.prop(process_op, 'search_pattern')
        row.prop(process_op, 'replace_pattern')
        row = box.row()
        row.operator(MORPHOBLEND_OT_Rename.bl_idname, text='Rename')

        box = layout.box()
        row = box.row()
        if len(bpy.context.selected_objects) > 1:
            text_box = f"Group into collection [{str(len(bpy.context.selected_objects))} selected cells]"
        else:
            text_box = f"Group into collection [{str(len(bpy.context.selected_objects))} selected cell]"
        row.label(text=text_box, icon='GRAPH')

        row = box.row()
        row.prop(process_op, 'sort_pattern')
        row = box.row()
        row.operator(MORPHOBLEND_OT_Arrange.bl_idname, text='Sort')

        box = layout.box()
        row = box.row()
        if len(bpy.context.selected_objects) > 1:
            text_box = f"Filter on volume [{str(len(bpy.context.selected_objects))} selected cells]"
        else:
            text_box = f"Filter on volume [{str(len(bpy.context.selected_objects))} selected cell]"
        row.label(text=text_box, icon='FILTER')

        row = box.row()
        row.label(text='Select cells based on [min, max] volume:')
        row = box.row()
        row.prop(process_op, 'vol_min_max')
        row = box.row()
        row.prop(process_op, 'bool_vol_all')
        row.operator(MORPHOBLEND_OT_SelectOnVolume.bl_idname, text='Filter')
        row.operator(MORPHOBLEND_OT_ClearFilter.bl_idname, text='Clear Results')


# ------------------------------------------------------------------------
#    Registrer/unregister calls
# ------------------------------------------------------------------------


process_classes = (ProcessProperties,
    MORPHOBLEND_OT_Colorize,
    MORPHOBLEND_OT_ColorizeInColl,
    MORPHOBLEND_OT_FinalizeModifiers,
    MORPHOBLEND_OT_Rename,
    MORPHOBLEND_OT_Arrange,
    MORPHOBLEND_OT_SelectOnVolume,
    MORPHOBLEND_OT_ClearFilter,)

register_classes, unregister_classes = bpy.utils.register_classes_factory(process_classes)


def register_process():
    register_classes()
    bpy.types.Scene.process_tool = PointerProperty(type=ProcessProperties)


def unregister_process():
    unregister_classes()
    del bpy.types.Scene.process_tool
