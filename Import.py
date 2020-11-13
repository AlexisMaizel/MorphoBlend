import re
from math import radians
from pathlib import Path

import bpy
from bpy.props import (BoolProperty, EnumProperty, FloatProperty,
                       FloatVectorProperty, IntProperty, IntVectorProperty,
                       PointerProperty, StringProperty)
from mathutils import Matrix

from .Utilities import (apply_modifiers, assign_material,
                        create_materials_palette, translate_to_origin)


# ------------------------------------------------------------------------
#    Global variables
# ------------------------------------------------------------------------
g_tp_pattern = '^[Tt]\d{2,}'


# ------------------------------------------------------------------------
#    Properties
# ------------------------------------------------------------------------
class ImportProperties(bpy.types.PropertyGroup):

    def update_mag_pixel_size(self, context):
        '''update the (x,y) dimensions of the voxel from the camera pixel size and magnification used'''
        self.vox_dim[0] = self.pixel_size / self.magnification
        self.vox_dim[1] = self.pixel_size / self.magnification
        self.vox_dim[2] = self.pixel_size / self.magnification

    def update_progress_bar(self, context):
        ''' update function to force redraw of the progress bar'''
        areas = context.window.screen.areas
        for area in areas:
            if area.type == 'INFO':
                area.tag_redraw()

    import_path: StringProperty(
        name='Path',
        description='Path to the folder containing the files to import',
        default='',
        subtype='FILE_PATH'
        )
    pixel_size: FloatProperty(
        name='',
        description='Camera pixel size (µm)',
        default=6.5,
        min=1,
        max=10,
        update=update_mag_pixel_size
        )
    magnification: IntProperty(
        name='',
        description='The magnification used for imaging.',
        default=40,
        min=1,
        max=100,
        update=update_mag_pixel_size
        )
    vox_dim: FloatVectorProperty(
        name='',
        description='Voxel size (µm)',
        default=(0.1625, 0.1625, 0.2500),
        min=0.0,
        max=5,
        precision=4,
        subtype='XYZ'
        )
    rot_xyz: IntVectorProperty(
        name='',
        description='Rotation (deg)',
        default=(-90, 0, 0),
        min=-180,
        max=180,
        subtype='EULER'
        )
    finalize_smoothing: BoolProperty(
        name='Finalize smoothing',
        description='Apply destructively the smoothing procedure. Unticking results in LARGE files',
        default=True
        )
    color_upon_import: BoolProperty(
        name='Color cells',
        description='Assign a random color to each cell',
        default=True
        )
    chosen_palette: EnumProperty(
        name='Palette:',
        description='Palette used to colorize.',
        items=[('Qual_bright', 'Bright', ''),
                ('Qual_pastel', 'Pastel', ''),
                ('Seq_viridis', 'Viridis', ''),
                ('Seq_green', 'Green sequential', ''),
                ('Seq_lila', 'Lila sequential', ''),
                ('Seq_blueGreen', 'BlueGreen sequential', ''),
                ('Seq_red', 'Red sequential', ''),
                ('Seq_blue', 'Blue sequential', ''),
                ('Seq_blueYellow', 'BlueYellow sequential', ''),
                ('Seq_brown', 'Brown sequential', ''),
                ('Div_brownGreen', 'BrownGreen diverging', ''),
                ('Div_lilaGreen', 'LilaGreen diverging', ''),
                ('Div_violetGreen', 'VioletGreen diverging', ''),
                ('Div_brownViolet', 'BrownViolet diverging', ''),
                ('Div_french', 'French diverging', ''),
                ('Div_redBlue', 'RedBlue diverging', ''),
               ]
        )
    progress_bar: FloatProperty(
        name='Import',
        description='',
        precision=0,
        min=-1,
        soft_min=0,
        soft_max=100,
        max=100,
        subtype='PERCENTAGE',
        update=update_progress_bar
        )


# ------------------------------------------------------------------------
#    Operators
# ------------------------------------------------------------------------
class MORPHOBLEND_OT_Import(bpy.types.Operator):
    '''Import data from PLY files (single or batch)'''
    bl_idname = 'morphoblend.import'
    bl_label = 'Import'
    bl_descripton = 'Import data from PLY files (single or batch)'

    # Class properties
    import_path: bpy.props.StringProperty()
    finalize_smoothing: bpy.props.BoolProperty()
    color_upon_import: bpy.props.BoolProperty()
    chosen_palette: bpy.props.StringProperty()
    pixel_size: bpy.props.FloatProperty()
    magnification: bpy.props.IntProperty()
    vox_dim: bpy.props.FloatVectorProperty()
    rot_xyz: bpy.props.IntVectorProperty()
    progress_bar: bpy.props.FloatProperty()

    @classmethod
    def poll(cls, context):
        import_prop = context.scene.import_prop
        return import_prop.import_path != ''

    def number_of_file_to_import(self, inPath):
        '''Retrieve the total number of files to be imported'''
        _n_file = 0
        if Path(inPath).is_file:
            _n_file += 1
        else:
            for child in sorted(Path(inPath).iterdir()):
                if (child.is_dir() and re.match(g_tp_pattern, child.name)):
                    for grandchild in sorted(Path(child).iterdir()):
                        if grandchild.is_file() and grandchild.name.endswith('.ply'):
                            _n_file += 1
                elif child.is_file() and child.name.endswith('.ply'):
                    _n_file += 1
        return _n_file

    def import_process_sort(self, inColl=None, inFilePath=''):
        '''Import, process and assign all PLY files into collections'''
        # TODO Replace this by a low level function? hopefully faster!
        bpy.ops.import_mesh.ply(filepath=inFilePath)
        global n_files_imported
        n_files_imported += 1
        # Scale, move, smooth and colorize
        obj = bpy.context.active_object
        obj = self.scale_rotate(obj, inAngles=(radians(g_rot_val_x), radians(g_rot_val_y), radians(g_rot_val_z)), inScaling=(g_scaling_x, g_scaling_y, g_scaling_z))
        obj = self.smooth_color(obj)
        # Prefix the object name with the collection
        obj.name = f"{inColl.name}_{obj.name}"
        # Move the object to the collection
        if obj.name not in bpy.data.collections[inColl.name].objects:
            inColl.objects.link(obj)
            bpy.data.collections[g_import_coll_name].objects.unlink(obj)

    def smooth_color(self, inObj):
        '''Apply material and smoothing modifiers to an object'''
        # Degree of smoothing depends on the dimensions of the object: large objects --> higher octree_factor --> more details
        # this is arbitrary (and in internal Blender units - NO scaling applied)
        # TODO  come up with a smarter way
        dims = inObj.dimensions
        if max(dims) > 2.5:
            octree_factor = 7
        else:
            octree_factor = 6
        remesh = inObj.modifiers.new(name='Remesh', type='REMESH')
        remesh.octree_depth = octree_factor
        remesh.use_smooth_shade = True
        remesh.mode = 'SMOOTH'
        decim = inObj.modifiers.new(name='Decimate', type='DECIMATE')
        decim.ratio = 0.5
        if g_apply_mod:
            inObj = apply_modifiers(inObj)
        # Add a color at random from the palette
        assign_material(inObj, g_mat_palette, rand_color=g_random_color)
        return inObj

    def scale_rotate(self, inObj, inAngles, inScaling):
        '''Low level rotation & scaling of an object'''
        rot_x = Matrix.Rotation(inAngles[0], 4, 'X')
        rot_y = Matrix.Rotation(inAngles[1], 4, 'Y')
        rot_z = Matrix.Rotation(inAngles[2], 4, 'Z')
        rot_mat = rot_x @ rot_y @ rot_z
        scale_mat = (Matrix.Scale(inScaling[0], 4, (1, 0, 0)) @ Matrix.Scale(inScaling[1], 4, (0, 1, 0)) @ Matrix.Scale(inScaling[2], 4, (0, 0, 1)))
        # assemble the new matrix
        inObj.matrix_world @= rot_mat @  scale_mat
        # 'burn' the transformations by transforming the mesh using the matrix world & then reset it
        inObj.data.transform(inObj.matrix_world)
        inObj.matrix_world @= inObj.matrix_world.inverted()
        # Redefine the origin of each mesh to its center.
        bpy.ops.object.origin_set(type='ORIGIN_CENTER_OF_VOLUME', center='MEDIAN')
        # bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='MEDIAN')
        return inObj

    def initialise(self, in_mat_palette, in_voxel_xyz, in_rot_val_xyz):
        '''Initialise everything before import: create material palette, set units and scaling'''
        global g_mat_palette
        global g_scaling_x, g_scaling_y, g_scaling_z
        global g_rot_val_x, g_rot_val_y, g_rot_val_z
        global g_import_coll_name
        # Create materials palette
        g_mat_palette = create_materials_palette(in_mat_palette)
        # MAke sure that the collection 'Imported' exists and is selected that Collection as active one
        g_import_coll_name = 'Imported'
        if g_import_coll_name not in bpy.data.collections:
            imp_coll = bpy.data.collections.new(name=g_import_coll_name)
            bpy.context.scene.collection.children.link(imp_coll)
        bpy.context.view_layer.active_layer_collection = bpy.context.view_layer.layer_collection.children[g_import_coll_name]
        # Make sure nothing is selected
        bpy.ops.object.select_all(action='DESELECT')
        # Rotations (deg)
        g_rot_val_x = in_rot_val_xyz[0]
        g_rot_val_y = in_rot_val_xyz[1]
        g_rot_val_z = in_rot_val_xyz[2]
        # Units & scaling
        voxel_x = in_voxel_xyz[0]
        voxel_z = in_voxel_xyz[2]
        g_scaling_x = g_scaling_y = 0.01
        g_scaling_z = 0.01 * voxel_z / voxel_x
        # Set the Blender File unit setting to correct set of units
        # Although Blender accepts 'MICROMETERS', it can not accept 1e-5 as multiplicative factor (1e-5)
        # Solution: keep in meter and set .scale_length to 10
        # all measurements will be returned in meters but should be understood as µm.
        bpy.context.scene.unit_settings.length_unit = 'METERS'
        g_scaling_units_scene = voxel_x / g_scaling_x
        bpy.context.scene.unit_settings.scale_length = g_scaling_units_scene

    def execute(self, context):
        import_prop = context.scene.import_prop
        output_basename = 'Output'
        # WARN This implements a progress bar but in a hacky way. Forced to call bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
        # should find a way to use a modal operator for it. Issue: where to put the main call, in invoke() or in modal()?
        # see https://docs.blender.org/api/current/info_gotcha.html
        # TODO  Refactor & document!
        self.initialise(import_prop.chosen_palette, import_prop.vox_dim, import_prop.rot_xyz)
        import_prop.progress_bar = 0
        global g_random_color, g_apply_mod, n_files_imported, num_files_to_import
        g_random_color = import_prop.color_upon_import
        g_apply_mod = import_prop.finalize_smoothing
        num_files_to_import = self.number_of_file_to_import(bpy.path.abspath(import_prop.import_path))
        outfile_path = Path(bpy.path.abspath(import_prop.import_path), output_basename).with_suffix('.blend')
        n_files_imported = 0
        inPath = Path(bpy.path.abspath(import_prop.import_path))
        if inPath.is_dir():
            # Main loop: Parsing the content of the input path
            for child in sorted(inPath.iterdir()):
                # If this is a tXX folder
                if (child.is_dir() and re.match(g_tp_pattern, child.name)):
                    # Create tXX collection unless it already exist
                    if child.name not in bpy.data.collections:
                        tp_coll = bpy.data.collections.new(name=child.name)
                        bpy.context.scene.collection.children.link(tp_coll)
                    else:
                        tp_coll = bpy.data.collections[child.name]
                    # Process all PLY files in the folder
                    for ply_file in sorted(child.glob('*.ply')):
                        self.import_process_sort(inFilePath=ply_file.as_posix(), inColl=tp_coll)
                        self.progress_ratio = n_files_imported / num_files_to_import * 100
                        import_prop.progress_bar = self.progress_ratio
                        bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
                    # save project after each time point
                    bpy.ops.wm.save_as_mainfile(filepath=outfile_path.as_posix())
                elif (child.is_file() and child.name.endswith('.ply')):
                    # Create a Imported collection unless it exists
                    imp_coll = bpy.data.collections[g_import_coll_name]
                    self.import_process_sort(inFilePath=child.as_posix(), inColl=imp_coll)
                    self.progress_ratio = n_files_imported / num_files_to_import * 100
                    import_prop.progress_bar = self.progress_ratio
                    bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
        elif inPath.is_file() and inPath.name.endswith('.ply'):
            # Create a Imported collection unless it exists
            imp_coll = bpy.data.collections[g_import_coll_name]
            self.import_process_sort(inFilePath=inPath.as_posix(), inColl=imp_coll)
            self.progress_ratio = n_files_imported / num_files_to_import * 100
            import_prop.progress_bar = self.progress_ratio
            bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)

        return {'FINISHED'}


class MORPHOBLEND_OT_TranslateToCenter(bpy.types.Operator):
    '''Translate the group of objects to the center.'''
    bl_idname = 'morphoblend.translate_to_center'
    bl_label = 'To center'
    bl_descripton = 'Translate the group of objects to the center.'

    @classmethod
    def poll(cls, context):
        return True
        # return context.active_object is not None and context.object.select_get() and context.object.type == 'MESH'

    def execute(self, context):
        translate_to_origin()
        return {'FINISHED'}


# ------------------------------------------------------------------------
#    UI elements
# ------------------------------------------------------------------------
class MORPHOBLEND_PT_Import(bpy.types.Panel):
    bl_idname = 'MORPHOBLEND_PT_Import'
    bl_label = 'Import'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'MorphoBlend'
    bl_parent_id = 'VIEW3D_PT_MorphoBlend'
    bl_options = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        layout = self.layout
        layout.label(icon='IMPORT')

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        import_prop = scene.import_prop

        row = layout.row()
        row.prop(import_prop, 'import_path')

        box = layout.box()
        row = box.row()
        row.label(text='Microscope settings', icon='TOOL_SETTINGS')

        row = box.row()
        row.label(text='Magnification:')
        row.prop(import_prop, 'magnification')
        row.label(text='Camera pixel size (µm):')
        row.prop(import_prop, 'pixel_size')

        row = box.row()
        row.label(text='Voxel Size (µm):')
        row = box.row()
        row.prop(import_prop, 'vox_dim')

        box = layout.box()
        row = box.row()
        row.label(text='Post-processing', icon='SCENE_DATA')

        row = box.row()
        row.label(text='Apply rotation (deg):')
        row = box.row()
        row.prop(import_prop, 'rot_xyz')

        row = box.row()
        row.prop(import_prop, 'finalize_smoothing')
        row = box.row(align=True)
        row.prop(import_prop, 'color_upon_import')
        row.prop(import_prop, 'chosen_palette', text='Palette:')

        layout.row().separator()
        row = layout.row()
        # TODO  I wonder if I need all this mess below --> clean?
        op = row.operator(MORPHOBLEND_OT_Import.bl_idname, text='Import', icon='IMPORT')
        op.import_path = import_prop.import_path
        op.magnification = import_prop.magnification
        op.rot_xyz = import_prop.rot_xyz
        op.vox_dim = import_prop.vox_dim
        op.color_upon_import = import_prop.color_upon_import
        op.finalize_smoothing = import_prop.finalize_smoothing
        op.chosen_palette = import_prop.chosen_palette

        row = layout.row()
        row.prop(import_prop, 'progress_bar', slider=True)

        row = layout.row()
        row.operator(MORPHOBLEND_OT_TranslateToCenter.bl_idname, text='Translate to Center')


# ------------------------------------------------------------------------
#    Registrer/unregister calls
# ------------------------------------------------------------------------
classes = (ImportProperties, MORPHOBLEND_OT_Import, MORPHOBLEND_OT_TranslateToCenter)

register_classes, unregister_classes = bpy.utils.register_classes_factory(classes)


def register_import():
    register_classes()
    bpy.types.Scene.import_prop = PointerProperty(type=ImportProperties)


def unregister_import():
    unregister_classes()
    del bpy.types.Scene.import_prop
