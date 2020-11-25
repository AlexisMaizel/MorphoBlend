from math import radians, sqrt
from pathlib import Path
from random import randrange

import re
import bgl
import blf
import bmesh
import bpy
import gpu
import numpy as np
from gpu_extras.batch import batch_for_shader
from mathutils import Matrix, Vector
from itertools import tee, islice, chain

# ------------------------------------------------------------------------
#    global variables
# ------------------------------------------------------------------------

# Cache for the volume and area measurements
g_cache_vol_area = {}


# ------------------------------------------------------------------------
#    Color & materials
# ------------------------------------------------------------------------
def rgb_to_rgbaf(_rgb):
    '''Convert a rgb color (123, 45, 234) to a rgbaf (0.123, 0.06, 0.12, 1)'''
    _rgbaf = tuple(ti / 255 for ti in _rgb) + (1,)
    return _rgbaf


def create_materials_palette(inPaletteName):
    '''Return an array of materials for the corresponding palette of color'''
    # Definition of all palettes that can be used
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
    _mat_palette = []
    # Create one materials for each color in the palette
    for color in palette:
        material_name = f"{inPaletteName}.{palette.index(color):02}"
        if material_name not in bpy.data.materials:
            new_mat = bpy.data.materials.new(material_name)
            new_mat.diffuse_color = rgb_to_rgbaf(color)
            _mat_palette.append(new_mat)
        else:
            _mat_palette.append(bpy.data.materials.get(material_name))
    return _mat_palette


def assign_material(inObj, inMatPalette, color_index=0, rand_color=False):
    '''Assign to an object a specific or random material from the palette.'''
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


# ------------------------------------------------------------------------
#    Collections
# ------------------------------------------------------------------------
def col_hierarchy(root_col, levels=1):
    '''Return hierarchy of the collections as dict. Starts from root. Levels specifies how deep to recurse.'''
    level_lookup = {}

    def recurse(root_col, parent, depth):
        if depth > levels:
            return
        if isinstance(parent, bpy.types.Collection):
            level_lookup.setdefault(parent, []).append(root_col)
        for child in root_col.children:
            recurse(child, root_col, depth + 1)
    recurse(root_col, root_col.children, 0)
    return level_lookup


def traverse_tree(t):
    '''Recursively traverse a tree'''
    yield t
    for child in t.children:
        yield from traverse_tree(child)


def parent_lookup(coll):
    '''Retrieve parents of a collection'''
    parent_lookup = {}
    for coll in traverse_tree(coll):
        for c in coll.children.keys():
            parent_lookup.setdefault(c, coll)
    return parent_lookup


def get_parent(coll):
    ''' Return the parent of a collection '''
    # Get parents of all collections in the scene
    coll_parents = parent_lookup(bpy.context.scene.collection)
    return coll_parents.get(coll.name)


def get_collection(obj):
    '''Return the 1st collection containing the object'''
    # TODO  Make this more versatile to return all collections containing the object (?)
    collections = obj.users_collection
    if len(collections) > 0:
        return collections[0]
    return bpy.context.scene.collection


def show_active_tp(context):
    '''Get the last active time point collection and make it the only one visible in viewport'''
    analyze_op = context.scene.analyze_tool
    all_tp_cols = collections_from_pattern(analyze_op.tp_pattern)
    current_col = context.collection
    if re.match(analyze_op.tp_pattern, current_col.name):
        currentTPcoll = current_col
    else:
        currentTPcoll = all_tp_cols[-1]
    # Only the current TP is visible on screen
    for col in all_tp_cols:
        if col == currentTPcoll:
            col.hide_viewport = False
        else:
            col.hide_viewport = True
    return currentTPcoll


def collection_navigator(inCollList, inCurrentColl, direction):
    '''Returns the next/previous time point collection  relative to the one passed in, return FALSE if error'''
    # Get index of the timepoint in the hierarchy
    tpcol_index = inCollList.index(inCurrentColl)
    if direction == 'next':
        dir = +1
    elif direction == 'previous':
        dir = -1
    else:
        return False
    # Return the next/previous object if  within bounds, or the last/first
    if 0 <= tpcol_index + dir < len(inCollList):
        return inCollList[tpcol_index + dir]
    elif tpcol_index + dir > len(inCollList) - 1:
        return inCollList[0]
    else:
        return inCollList[len(inCollList) - 1]


def hide_display(currentTPcoll, next_tp):
    ''' Hide current collection, display the next one'''
    currentTPcoll.hide_viewport = True
    next_tp.hide_viewport = False
    layer_collection = bpy.context.view_layer.layer_collection.children[next_tp.name]
    bpy.context.view_layer.active_layer_collection = layer_collection
    info_mess = 'Visible: ' + next_tp.name
    return info_mess


def collections_from_pattern(in_pattern):
    ''' Returns a sorted list of all collections which name matches a pattern'''
    # list of all collections at 1st level
    scn_col = bpy.context.scene.collection  # Root collection
    root_cols = col_hierarchy(scn_col, levels=1)
    all_cols = [k for k in root_cols.values()][0]
    # Only keep collections that are time points
    all_tp_cols = {}
    for col in all_cols:
        if re.match(in_pattern, col.name) is not None:
            all_tp_cols[col.name] = col
    sorted_all_tp_cols = dict(sorted(all_tp_cols.items(), key=lambda i: i[0].lower()))
    return list(sorted_all_tp_cols.values())


def make_collection(collection_name, parent_collection):
    '''Create a collection if it does not already exist, attach it to the parent.
    Attach to the top most collection if no parent provided'''
    if parent_collection is None:
        parent_collection = bpy.context.scene.collection
        composite_name = collection_name
    else:
        composite_name = f"{parent_collection.name}_{collection_name}"
    if composite_name in bpy.data.collections:
        return bpy.data.collections[composite_name]
    else:
        new_collection = bpy.data.collections.new(composite_name)
        parent_collection.children.link(new_collection)
        return new_collection


def move_obj_to_subcoll(obj, destColl):
    ''' Moves an object to a sub-collection, child of the original one, creating the collection if it does not exist.'''
    if destColl is None:
        return
    else:
        orig_coll = get_collection(bpy.data.objects[obj.name])
        new_coll = make_collection(destColl, orig_coll)
        new_coll.objects.link(obj)
        orig_coll.objects.unlink(obj)


def move_obj_to_coll(obj, destColl):
    ''' Moves an object to a specific collection.'''
    orig_coll = get_collection(bpy.data.objects[obj.name])
    destColl.objects.link(obj)
    orig_coll.objects.unlink(obj)


def ObjectNavigator(inCollection, inObj, direction):
    '''Returns the next/previous object in the Collection relative to the object passed in.
    return FALSE if out of bound. '''
    # check that object is in the collection
    obj_in_coll = bpy.data.collections[inCollection].objects[:]
    # (!) The order of the objects in the navigtor and returned by the line above differ
    # TODO  sort this list the same way
    # obj_in_coll.sort(key = lambda o: o.name)
    if inCollection in bpy.data.collections and inObj in obj_in_coll:
        # Get index of the object in that collection
        obj_index = obj_in_coll.index(inObj)
        if direction == 'next':
            dir = +1
        elif direction == 'previous':
            dir = -1
        else:
            return False
        # Return the next/previous object if  within bounds, or the last/first
        if 0 <= obj_index + dir < len(obj_in_coll):
            return obj_in_coll[obj_index + dir]
        elif obj_index + dir > len(obj_in_coll) - 1:
            return obj_in_coll[0]
        else:
            return obj_in_coll[len(obj_in_coll) - 1]
    else:
        return False


def previous_and_next(some_iterable):
    ''' Return the previous and next element of any iteratable. Handle edge case graciously by returning 'None'.'''
    prevs, items, nexts = tee(some_iterable, 3)
    prevs = chain([None], prevs)
    nexts = chain(islice(nexts, 1, None), [None])
    return zip(prevs, items, nexts)


def unique_colls_names_list():
    ''' Return a list of unique collection names'''
    # Retrieve hiearchy of all collection and their parents
    cols_tree = col_hierarchy(bpy.context.scene.collection, levels=9)
    all_cols = {i: k for k, v in cols_tree.items() for i in v}

    # Parse all collections and process the ones matching the pattern
    names_elements = []
    for col in all_cols:
        name_element = re.split('\s+|_', col.name)
        names_elements.extend(name_element)
    # return a sorted list of unique names
    return sorted(list(set(names_elements)), key=lambda i: i[0].lower())


# ------------------------------------------------------------------------
#    Coordinates, positions, distance, volumes
# ------------------------------------------------------------------------
def get_global_coordinates(inObj):
    '''Retrieve the global coordinates of an object'''
    if inObj.type == 'MESH':
        v_co_world = inObj.matrix_world @ inObj.data.vertices[0].co
    else:
        v_co_world = inObj.matrix_world.translation
    return v_co_world


def scaled_dimensions(inObj):
    ''' Return an array of the scaled dimensions of an object'''
    dims = inObj.dimensions
    return dims * bpy.context.scene.unit_settings.scale_length


def translate_to_origin():
    '''Translates all meshes of the scene to the center of the scene'''
    obj_centers = []  # position of each imported object center
    for obj in bpy.context.scene.objects:
        bpy.context.view_layer.objects.active = obj
        if obj.type == 'MESH':
            # Get the coordinates of the object center
            obj_center = get_global_coordinates(obj)
            obj_centers.append(obj_center)
    # Compute the coordinates of the barycenter of all imported objects
    center = np.mean(np.asarray(obj_centers), axis=0)
    # Remove the center coordinate from each  object center to translate it
    for obj in bpy.context.scene.objects:
        bpy.context.view_layer.objects.active = obj
        if obj.type == 'MESH':
            obj.matrix_world @= Matrix.Translation(-Vector(center))


def distance3D(ref=(0, 0, 0), point=(0, 0, 0)):
    ''' Returns the scaled distance between two points. Input coordinates must NOT be scaled.'''
    dist = sqrt((ref[0] - point[0])**2 + (ref[1] - point[1])**2 + (ref[2] - point[2])**2)
    scaled_dist = bpy.context.scene.unit_settings.scale_length * dist
    return scaled_dist


def distance2D(ref=(0, 0, 0), point=(0, 0, 0), plane_def=(True, False, True)):
    ''' Returns the distance between two points in a plane defined by X/Y/Z = True. Input coordinates must NOT be scaled'''
    index_axes = [i for i, e in enumerate(plane_def) if e is True]
    i = index_axes[0]
    j = index_axes[1]
    dist = sqrt((ref[i] - point[i])**2 + (ref[j] - point[j])**2)
    scaled_dist = bpy.context.scene.unit_settings.scale_length * dist
    return scaled_dist


def volume_and_area_from_object(inObj):
    ''' Return the scaled volume & area for an object'''
    # If object is in the cache, retrieve the values
    global g_cache_vol_area
    if inObj in g_cache_vol_area.keys():
        return g_cache_vol_area[inObj][0], g_cache_vol_area[inObj][1]
    else:  # Not in the cache, compute.
        bm = bmesh.new()   # create an empty BMesh
        bm = bmesh_copy_from_object(inObj, apply_modifiers=True)
        volume = bm.calc_volume()
        area = sum(f.calc_area() for f in bm.faces)
        bm.free()
        scaled_volume = volume * bpy.context.scene.unit_settings.scale_length ** 3
        scaled_area = area * bpy.context.scene.unit_settings.scale_length ** 2
        # Cache the results
        g_cache_vol_area[inObj] = (abs(scaled_volume), abs(scaled_area))
        return abs(scaled_volume), abs(scaled_area)


# ------------------------------------------------------------------------
#    Meshes
# ------------------------------------------------------------------------
def bmesh_copy_from_object(obj, transform=True, triangulate=True, apply_modifiers=False):
    '''Return a copy of an Object mesh with optionally all modifiers, transformation and triangulation applied.
    The only way to get  reliable volume computation.'''
    assert(obj.type == 'MESH')

    if apply_modifiers and obj.modifiers:
        import bpy
        depsgraph = bpy.context.evaluated_depsgraph_get()
        obj_eval = obj.evaluated_get(depsgraph)
        me = obj_eval.to_mesh()
        bm = bmesh.new()
        bm.from_mesh(me)
        obj_eval.to_mesh_clear()
        del bpy
    else:
        me = obj.data
        if obj.mode == 'EDIT':
            bm_orig = bmesh.from_edit_mesh(me)
            bm = bm_orig.copy()
        else:
            bm = bmesh.new()
            bm.from_mesh(me)

    if transform:
        bm.transform(obj.matrix_world)

    if triangulate:
        bmesh.ops.triangulate(bm, faces=bm.faces)
    return bm


def apply_modifiers(inObj):
    '''Applies all modifiers of the selected object.'''
    dg = bpy.context.evaluated_depsgraph_get()
    bm = bmesh.new()
    bm.from_object(inObj, dg)
    bm.to_mesh(inObj.data)
    bm.free()
    for m in inObj.modifiers:
        inObj.modifiers.remove(m)
    return inObj


# ------------------------------------------------------------------------
#    GUI - 2D display
# ------------------------------------------------------------------------
def Display2D_LUT_image(inPaletteName, inPosDim=(100, 100, 50, 300), inMinMax=(0, 100), inLabel=""):
    '''Display in the viewport the image of a palette and the range of values covered.'''
    # get the name of the LUT PNG
    PaletteImage = f"{inPaletteName}.png"
    # get the absolute path to where the script is executed and create the path to the LUT.png file
    exec_path = Path(__file__).parent.absolute()
    abs_lut_path = exec_path.joinpath('resources', PaletteImage)
    # Open & store the image
    bpy.ops.image.open(filepath=abs_lut_path.as_posix())
    bpy.data.images[PaletteImage].pack()  # Pack an image as embedded data into the .blend file
    image = bpy.data.images[PaletteImage]

    # Dimensions of the LUT
    pos_x = inPosDim[0]
    pos_y = inPosDim[1]
    w = inPosDim[2]
    h = inPosDim[3]

    # Display the LUT image
    shader = gpu.shader.from_builtin('2D_IMAGE')
    batch = batch_for_shader(
        shader, 'TRI_FAN',
        {
            # bottom left, top left, top right, bottom right
            "pos": ((pos_x, pos_y), (pos_x, pos_y + h), (pos_x + w, pos_y + h), (pos_x + w, pos_y)),
            "texCoord": ((1, 0), (0, 1), (1, 1), (0, 0),),
        },
    )
    if image.gl_load():
        raise Exception()

    def draw():
        bgl.glActiveTexture(bgl.GL_TEXTURE0)
        bgl.glBindTexture(bgl.GL_TEXTURE_2D, image.bindcode)

        shader.bind()
        shader.uniform_int("image", 0)
        batch.draw(shader)

    bpy.types.SpaceView3D.draw_handler_add(draw, (), 'WINDOW', 'POST_PIXEL')

    # Display the min and max values
    # Min & Max values to use for labels
    min_val = "{:.2e}".format(inMinMax[0])
    max_val = "{:.2e}".format(inMinMax[1])
    x_offset = 10
    y_offset = 25
    font_size = 25

    def draw_callback_text(self, context):
        '''Draw on the viewports'''
        # BLF drawing routine
        font_id = 0
        blf.position(font_id, pos_x + w + x_offset, pos_y, 0)
        blf.size(font_id, font_size, 72)
        blf.draw(font_id, min_val)

        blf.position(font_id, pos_x + w + x_offset, pos_y + h - y_offset, 0)
        blf.size(font_id, font_size, 72)
        blf.draw(font_id, max_val)

        blf.enable(font_id, blf.ROTATION)
        blf.rotation(font_id, radians(90))
        blf.position(font_id, pos_x - x_offset, pos_x + h / 2 - y_offset, 0)
        blf.size(font_id, font_size, 72)
        blf.draw(font_id, inLabel)
        blf.disable(font_id, blf.ROTATION)
    bpy.types.SpaceView3D.draw_handler_add(draw_callback_text, (None, None), 'WINDOW', 'POST_PIXEL')


def Display2D_LUT(inPaletteName, pos_dim=(100, 100, 10)):
    ''' Experimental... '''
    # Get Palette
    LUT = create_materials_palette(inPaletteName)
    n_elements = len(LUT)

    # Origin and aspect of the LUT
    x_orig = pos_dim[0]
    y_orig = pos_dim[1]
    size = pos_dim[2]

    for k in range(0, n_elements):
        vertices = (
            (x_orig, y_orig + k * size), (x_orig + size, y_orig + k * size),
            (x_orig, y_orig + size + k * size), (x_orig + size, y_orig + size + k * size))

        indices = ((0, 1, 2), (2, 1, 3))

        shader = gpu.shader.from_builtin('2D_UNIFORM_COLOR')
        batch = batch_for_shader(shader, 'TRIS', {"pos": vertices}, indices=indices)

        def draw():
            shader.bind()
            shader.uniform_float("color", LUT[k].diffuse_color)
            batch.draw(shader)
        draw_handler = bpy.types.SpaceView3D.draw_handler_add(draw, (), 'WINDOW', 'POST_VIEW')
    return draw_handler
