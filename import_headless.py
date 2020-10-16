import argparse
import logging
import re
from math import radians
from pathlib import Path
from random import randrange

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector


g_tp_pattern = '^[Tt]\d{2,}'


def args_parser():
    parser = argparse.ArgumentParser()
    # get all script args
    _, all_arguments = parser.parse_known_args()
    double_dash_index = all_arguments.index('--')
    script_args = all_arguments[double_dash_index + 1:]
    # Mandatory arguments
    parser.add_argument('--path', type=str, help='Path to the folder containing the PLY files to import.', required=True)
    parser.add_argument('--voxel', nargs='+', type=float, help='Voxel dimensions in µm (x/y/z)', required=True)
    parser.add_argument('--rotation', nargs='+', type=int, help='Rotation to apply to each axis in deg (x/y/z)', required=True)
    parsed_script_args, _ = parser.parse_known_args(script_args)

    return parsed_script_args


def main():
    output_basename = 'Output'
    # Get the scripts arguments
    args = args_parser()
    # Configure logging
    log_path = Path(bpy.path.abspath(args.path), output_basename).with_suffix('.log')
    logging.basicConfig(level=logging.INFO, filename=log_path, filemode='w', format='%(asctime)s - %(message)s')
    # Remove everything from the project
    for o in bpy.context.scene.objects:
        o.select_set(True)
    bpy.ops.object.delete()
    initialise('Qual_bright', args.voxel, args.rotation)
    global g_random_color, g_apply_mod, n_files_imported, num_files_to_import
    g_random_color = True
    g_apply_mod = True
    num_files_to_import = number_of_file_to_import(bpy.path.abspath(args.path))
    n_files_imported = 0
    outfile_path = Path(bpy.path.abspath(args.path), output_basename).with_suffix('.blend')
    logging.info('Starting. Will import a total of %s files', num_files_to_import)
    # Main loop: Parsing the content of the input path
    for child in sorted(Path(bpy.path.abspath(args.path)).iterdir()):
        # If this is a tXX folder
        if (child.is_dir() and re.match(g_tp_pattern, child.name)):
            # Create tXX collection unless it already exist
            if child.name not in bpy.data.collections:
                tp_coll = bpy.data.collections.new(name=child.name)
                bpy.context.scene.collection.children.link(tp_coll)
            else:
                tp_coll = bpy.data.collections[child.name]
            logging.info('Processing: %s', tp_coll.name)
            # Process all PLY files in the folder
            k = 0
            for ply_file in sorted(child.glob('*.ply')):
                import_process_sort(inFilePath=ply_file.as_posix(), inColl=tp_coll)
                k += 1
            # save project when import of a time point is done
            logging.info('Imported %s files and saved after: %s', k, tp_coll.name)
            bpy.ops.wm.save_as_mainfile(filepath=outfile_path.as_posix())
        elif (child.is_file() and child.name.endswith('.ply')):
            # Create a Imported collection unless it exists
            imp_coll = bpy.data.collections[g_import_coll_name]
            import_process_sort(inFilePath=child.as_posix(), inColl=imp_coll)
            logging.info('Progress: %s / %s', n_files_imported, num_files_to_import)
    bpy.ops.wm.save_as_mainfile(filepath=outfile_path.as_posix())
    logging.info('Finished!')


def initialise(in_mat_palette, in_voxel_xyz, in_rot_val_xyz):
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


# Colorize and smooth mesh
def smooth_color(inObj):
    # Smooth
    # degree of smoothing depends on the dimensions of the object: large objects --> higher octree_factor --> more details
    dims = inObj.dimensions
    # this is arbitrary (and in internal Blender units - NO scaling applied)
    # TODO  come up with a smarter way
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
    assign_color(inObj, g_mat_palette, rand_color=g_random_color)
    return inObj


# Low level rotation & scaling of an object and application
def scale_rotate(inObj, inAngles, inScaling):
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


# Import, process and assign all PLY to collection
def import_process_sort(inColl=None, inFilePath=''):
    # TODO Replace this by a low level function? hopefully faster!
    bpy.ops.import_mesh.ply(filepath=inFilePath)
    global n_files_imported
    n_files_imported += 1
    # Scale, move, smooth and colorize
    obj = bpy.context.active_object
    obj = scale_rotate(obj, inAngles=(radians(g_rot_val_x), radians(g_rot_val_y), radians(g_rot_val_z)), inScaling=(g_scaling_x, g_scaling_y, g_scaling_z))
    obj = smooth_color(obj)
    # Prefix the object name with the collection
    obj.name = f"{inColl.name}_{obj.name}"
    # Move the object to the collection
    inColl.objects.link(obj)
    bpy.data.collections[g_import_coll_name].objects.unlink(obj)


def retrieve_global_coordinates(inObj):
    v_co_world = inObj.matrix_world @ inObj.data.vertices[0].co
    return v_co_world


def number_of_file_to_import(inPath):
    _n_file = 0
    for child in sorted(Path(inPath).iterdir()):
        if (child.is_dir() and re.match(g_tp_pattern, child.name)):
            for grandchild in sorted(Path(child).iterdir()):
                if grandchild.is_file() and grandchild.name.endswith('.ply'):
                    _n_file += 1
        elif child.is_file() and child.name.endswith('.ply'):
            _n_file += 1
    return _n_file


def rgb_to_rgbaf(_rgb):
    # Convert a rgb color (123, 45, 234) to a rgbaf (0.123, 0.06, 0.12, 1)
    _rgbaf = tuple(ti / 255 for ti in _rgb) + (1, )
    return _rgbaf


def create_materials_palette(inPaletteName):
    # Generates Materials using palettes as source of colors
    # list of all palettes to use
    Seq_green = [(247, 252, 253), (229, 245, 249), (204, 236, 230), (153, 216, 201), (102, 194, 164), (65, 174, 118), (35, 139, 69), (0, 109, 44), (0, 68, 27)]
    Seq_lila = [(247, 252, 253), (224, 236, 244), (191, 211, 230), (158, 188, 218), (140, 150, 198), (140, 107, 177), (136, 65, 157), (129, 15, 124), (77, 0, 75)]
    Seq_blueGreen = [(247, 252, 240), (224, 243, 219), (204, 235, 197), (168, 221, 181), (123, 204, 196), (78, 179, 211), (43, 140, 190), (8, 104, 172), (8, 64, 129)]
    Seq_red = [(255, 247, 236), (254, 232, 200), (253, 212, 158), (253, 187, 132), (252, 141, 89), (239, 101, 72), (215, 48, 31), (179, 0, 0), (127, 0, 0)]
    Seq_blue = [(255, 247, 251), (236, 231, 242), (208, 209, 230), (166, 189, 219), (116, 169, 207), (54, 144, 192), (5, 112, 176), (4, 90, 141), (2, 56, 88)]
    Seq_blueYellow = [(255, 255, 217), (237, 248, 177), (199, 233, 180), (127, 205, 187), (65, 182, 196), (29, 145, 192), (34, 94, 168), (37, 52, 148), (8, 29, 88)]
    Seq_brown = [(255, 255, 229), (255, 247, 188), (254, 227, 145), (254, 196, 79), (254, 153, 41), (236, 112, 20), (204, 76, 2), (153, 52, 4), (102, 37, 6)]
    Div_brownGreen = [(84, 48, 5), (140, 81, 10), (191, 129, 45), (223, 194, 125), (246, 232, 195), (245, 245, 245), (199, 234, 229), (128, 205, 193), (53, 151, 143), (1, 102, 94), (0, 60, 48)]
    Div_lilaGreen = [(142, 1, 82), (197, 27, 125), (222, 119, 174), (241, 182, 218), (253, 224, 239), (247, 247, 247), (230, 245, 208), (184, 225, 134), (127, 188, 65), (77, 146, 33), (39, 100, 25)]
    Div_violetGreen = [(64, 0, 75), (118, 42, 131), (153, 112, 171), (194, 165, 207), (231, 212, 232), (247, 247, 247), (217, 240, 211), (166, 219, 160), (90, 174, 97), (27, 120, 55), (0, 68, 27)]
    Div_brownViolet = [(127, 59, 8), (179, 88, 6), (224, 130, 20), (253, 184, 99), (254, 224, 182), (247, 247, 247), (216, 218, 235), (178, 171, 210), (128, 115, 172), (84, 39, 136), (45, 0, 75)]
    Div_french = [(103, 0, 31), (178, 24, 43), (214, 96, 77), (244, 165, 130), (253, 219, 199), (247, 247, 247), (209, 229, 240), (146, 197, 222), (67, 147, 195), (33, 102, 172), (5, 48, 97)]
    Div_redBlue = [(165, 0, 38), (215, 48, 39), (244, 109, 67), (253, 174, 97), (254, 224, 144), (255, 255, 191), (224, 243, 248), (171, 217, 233), (116, 173, 209), (69, 117, 180), (49, 54, 149)]
    Qual_bright = [(166, 206, 227), (31, 120, 180), (178, 223, 138), (51, 160, 44), (251, 154, 153), (227, 26, 28), (253, 191, 111), (255, 127, 0), (202, 178, 214), (106, 61, 154), (255, 255, 153), (177, 89, 40)]
    Qual_pastel = [(141, 211, 199), (255, 255, 179), (190, 186, 218), (251, 128, 114), (128, 177, 211), (253, 180, 98), (179, 222, 105), (252, 205, 229), (217, 217, 217), (188, 128, 189), (204, 235, 197), (255, 237, 111)]
    Seq_viridis = [(68, 1, 84), (69, 16, 97), (70, 31, 110), (71, 44, 122), (67, 58, 128), (62, 71, 134), (58, 83, 139), (53, 94, 140), (47, 106, 141), (43, 116, 142), (39, 127, 142), (35, 139, 141), (34, 149, 139), (36, 159, 135), (38, 168, 131), (48, 178, 124), (69, 188, 112), (88, 198, 101), (112, 205, 87), (138, 212, 70), (165, 219, 53), (192, 223, 47), (223, 227, 42), (253, 231, 37)]
    Col_0 = [(211, 211, 211)]
    Col_1 = [(166, 206, 227)]
    Col_2 = [(31, 120, 180)]
    Col_3 = [(178, 223, 138)]
    Col_4 = [(51, 160, 44)]
    Col_5 = [(251, 154, 153)]
    Col_6 = [(227, 26, 28)]
    Col_7 = [(253, 191, 111)]
    Col_8 = [(255, 127, 0)]
    palettes = [Seq_green, Seq_lila, Seq_blueGreen, Seq_red, Seq_blue, Seq_blueYellow, Seq_brown, Div_brownGreen, Div_lilaGreen, Div_violetGreen, Div_brownViolet, Div_french, Div_redBlue, Qual_bright, Qual_pastel, Seq_viridis, Col_0, Col_1, Col_2, Col_3, Col_4, Col_5, Col_6, Col_7, Col_8]
    palettes_names = ['Seq_green', 'Seq_lila', 'Seq_blueGreen', 'Seq_red', 'Seq_blue', 'Seq_blueYellow', 'Seq_brown', 'Div_brownGreen', 'Div_lilaGreen', 'Div_violetGreen', 'Div_brownViolet', 'Div_french', 'Div_redBlue', 'Qual_bright', 'Qual_pastel', 'Seq_viridis', 'Col_0', 'Col_1', 'Col_2', 'Col_3', 'Col_4', 'Col_5', 'Col_6', 'Col_7', 'Col_8']

    palette = palettes[palettes_names.index(inPaletteName)]
    _palette_name = inPaletteName
    _mat_palette = []
    for color in palette:
        material_name = f'{_palette_name}.{palette.index(color):02}'
        if material_name not in bpy.data.materials:
            new_mat = bpy.data.materials.new(material_name)
            new_mat.diffuse_color = rgb_to_rgbaf(color)
            _mat_palette.append(new_mat)
        else:
            _mat_palette.append(bpy.data.materials.get(material_name))
    return _mat_palette


def assign_color(inObj, inMatPalette, color_index=0, rand_color=False):
    # Colorize an object using color from a palette optionally randomely
    if rand_color:
        material = inMatPalette[randrange(len(inMatPalette))]
    elif color_index < len(inMatPalette):
        material = inMatPalette[color_index]
    else:
        material = inMatPalette[len(inMatPalette)]

    if inObj.data.materials:
        inObj.data.materials[0] = material
    else:
        inObj.data.materials.append(material)


def apply_modifiers(inObj):
    # Applies all modifiers of the selected object
    dg = bpy.context.evaluated_depsgraph_get()
    bm = bmesh.new()
    bm.from_object(inObj, dg)
    bm.to_mesh(inObj.data)
    bm.free()
    for m in inObj.modifiers:
        inObj.modifiers.remove(m)
    return inObj


def translate_to_origin():
    obj_centers = []  # position of each imported object center
    for obj in bpy.context.scene.objects:
        bpy.context.view_layer.objects.active = obj
        if obj.type == 'MESH':
            # Get the coordinates of the object center
            obj_center = retrieve_global_coordinates(obj)
            obj_centers.append(obj_center)
    # Compute the coordinates of the barycenter of all imported objects
    center = np.mean(np.asarray(obj_centers), axis=0)
    # Remove the center coordinate from each  object center to translate it
    for obj in bpy.context.scene.objects:
        bpy.context.view_layer.objects.active = obj
        if obj.type == 'MESH':
            obj.matrix_world @= Matrix.Translation(-Vector(center))


if __name__ == '__main__':
    main()
