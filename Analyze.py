import json
import re
import csv
from itertools import combinations
from math import acos, radians
from pathlib import Path
from random import randrange

from mathutils import Matrix

import bmesh
import bpy
import networkx as nx
from anytree import (AsciiStyle, Node, PreOrderIter, RenderTree, find_by_attr,
                     findall_by_attr)
from anytree.exporter import JsonExporter
from anytree.importer import JsonImporter
from bpy.props import (BoolProperty, BoolVectorProperty, EnumProperty,
                       FloatProperty, FloatVectorProperty, PointerProperty,
                       StringProperty, CollectionProperty)
from bpy_extras.view3d_utils import region_2d_to_location_3d
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
from networkx.readwrite import json_graph

from .Utilities import (assign_material, bmesh_copy_from_object, col_hierarchy,
                        create_materials_palette, distance2D, distance3D,
                        get_collection, get_global_coordinates, get_parent,
                        make_collection, move_obj_to_coll, move_obj_to_subcoll,
                        previous_and_next, collections_from_pattern)

# ------------------------------------------------------------------------
#    Global variable
# ------------------------------------------------------------------------
# The possible root layers
g_root_layers_names = ('Epidermis', 'Cortex', 'Endodermis', 'Stele')

global g_lineages  # The Dict containing all the lineages
g_lineages = {}

global g_networks  # Dict of the connectivity graphs for each time point. Nodes are objects IDs and edges are weighted by the area of contact between two cells
g_networks = {}

global g_nuclei  # Dict of nuclei position
g_nuclei = {}


# ------------------------------------------------------------------------
#    Properties
# ------------------------------------------------------------------------
class AnalyzeProperties(bpy.types.PropertyGroup):
    def dist_at_update(self, context):
        '''update the threshold values for the different layers'''
        if not self.dist_t0_at > self.dist_t1_at > self.dist_t2_at:
            self.dist_t1_at = self.dist_t2_at + 1
            self.dist_t0_at = self.dist_t1_at + 1

    def toggle_plane_def(self, context):
        ''' Ensures that only two checkboxes are selected '''
        plane_def = (self.plane_at_ref[0], self.plane_at_ref[1], self.plane_at_ref[2])
        if plane_def == (True, True, True):
            self.plane_at_ref = (False, False, False)

    def update_progress_bar(self, context):
        ''' update function to force redraw of the progress bar'''
        areas = context.window.screen.areas
        for area in areas:
            if area.type == 'INFO':
                area.tag_redraw()

    tp_pattern: StringProperty(
        name='Time point pattern',
        description='Regex pattern describing time points',  # Matches time point (t1, T42, t09, etc...)
        default='[Tt]\d{1,}'
    )
    root_layers_names: EnumProperty(  # This is not used yet
        name='Root layer names',
        description='Root layer names',
        items=[('Epidermis', 'Epidermis', ''),
                ('Cortex', 'Cortex', ''),
                ('Endodermis', 'Endodermis', ''),
                ('Stele', 'Stele', ''),
            ]
    )
    lineages: EnumProperty(  # This is not used yet
        name='Root layer names',
        description='Root layer names',
        items=[('Epidermis', 'Epidermis', ''),
                ('Cortex', 'Cortex', ''),
                ('Endodermis', 'Endodermis', ''),
                ('Stele', 'Stele', ''),
            ]
    )
    bool_at_color_cells: BoolProperty(
        name='Color cells',
        description="Color cells according to layer",
        default=True
    )
    plane_at_ref: BoolVectorProperty(
        name='',
        description="Radial plane definition",
        default=(True, False, True),
        size=3,
        subtype='EULER',
        update=toggle_plane_def
    )
    pos_at_ref: FloatVectorProperty(
        name='',
        description="Position of the root center reference",
        default=(0.0, 0.0, 0.0),
        precision=3,
        subtype='XYZ'
    )
    dist_t0_at: FloatProperty(
        name='',
        description=f"Distance from center for {g_root_layers_names[0]} (µm)",
        default=45,
        precision=2,
        min=1,
        step=100,
        update=dist_at_update
    )
    dist_t1_at: FloatProperty(
        name='',
        description=f"Distance from center for {g_root_layers_names[1]} (µm)",
        default=35,
        precision=2,
        min=1,
        step=100,
        update=dist_at_update
    )
    dist_t2_at: FloatProperty(
        name='',
        description=f"Distance from center for {g_root_layers_names[2]} (µm)",
        default=25,
        precision=2,
        min=1,
        step=100,
        update=dist_at_update
    )
    bool_at_all: BoolProperty(
        name='Assign to all',
        description='Assign tissue to all cells also the other time points or hidden ones',
        default=False
    )
    threshold_tracking: FloatProperty(
        name='',
        description='Below this cells are considered the same across time points',
        default=3.750,
        precision=3
    )
    bool_track_all: BoolProperty(
        name='Track all cells',
        description='Track all cells also the other time points or hidden ones',
        default=False
    )
    import_export_track_path: StringProperty(
        name='Path',
        description='Path to the tracking data',
        default='',
        subtype='FILE_PATH'
    )
    bool_3dconnect_all: BoolProperty(
        name='Analyze all cells',
        description='Extract 3D neigbours for all cells also the other time points or hidden ones',
        default=False
    )
    import_export_networks_path: StringProperty(
        name='Path',
        description='Path to the 3D connectivity graphs',
        default='',
        subtype='DIR_PATH'
    )
    progress_bar: FloatProperty(
        name='Progress',
        description='',
        precision=0,
        min=-1,
        soft_min=0,
        soft_max=100,
        max=100,
        subtype='PERCENTAGE',
        update=update_progress_bar
    )
    import_nuclei_path: StringProperty(
        name='Path',
        description='Path to the nuclei data',
        default='',
        subtype='FILE_PATH'
    )


class SceneAttribute(bpy.types.PropertyGroup):
    key: bpy.props.StringProperty(name="Scene attribute key")
    value: bpy.props.StringProperty(name="Scene attribute value")


# ------------------------------------------------------------------------
#    Operators
# ------------------------------------------------------------------------
class MORPHOBLEND_OT_AssignRootLayers(bpy.types.Operator):
    '''Assign layers based on radial distance from center'''
    bl_idname = 'morphoblend.assign_root_layers'
    bl_label = 'Assign root tissues'
    bl_descripton = 'Assign layers based on radial distance from center.'

    @classmethod
    def poll(cls, context):
        analyze_op = context.scene.analyze_tool
        if analyze_op.bool_at_all:
            return True
        else:
            return context.selected_objects is not None

    def assign_layer(self, ref_pos, obj_pos, plane, layers_thresh):
        ''' Return the layer the cell belongs to given: a reference (center of root), a definition of the radial plane and thresholds for the layers'''
        dist_to_ref = distance2D(ref_pos, obj_pos, plane)
        if dist_to_ref > layers_thresh[0]:
            layer = g_root_layers_names[0]
        elif layers_thresh[1] < dist_to_ref <= layers_thresh[0]:
            layer = g_root_layers_names[1]
        elif layers_thresh[2] < dist_to_ref <= layers_thresh[1]:
            layer = g_root_layers_names[2]
        else:
            layer = g_root_layers_names[3]
        return layer

    def assign_color_layer(self, obj, layer):
        ''' Assign a layer specific color to an object'''
        if layer == g_root_layers_names[0]:
            color = 'Col_1'
        elif layer == g_root_layers_names[1]:
            color = 'Col_3'
        elif layer == g_root_layers_names[2]:
            color = 'Col_5'
        else:
            color = 'Col_7'
        mat_palette = create_materials_palette(color)
        assign_material(obj, mat_palette)

    def execute(self, context):
        analyze_op = context.scene.analyze_tool
        _apply_to_all = analyze_op.bool_at_all
        # Definition of the radial plane
        rad_plane = analyze_op.plane_at_ref
        # Retrieve coordinates of the reference,  remove the scaling
        ref_pos = analyze_op.pos_at_ref / bpy.context.scene.unit_settings.scale_length
        # Thresholds for different layers
        layers_thresholds = (analyze_op.dist_t0_at, analyze_op.dist_t1_at, analyze_op.dist_t2_at)
        if _apply_to_all:
            # Parse all objects of the scene
            for obj in bpy.context.scene.objects:
                if obj.type == 'MESH':
                    layer = self.assign_layer(ref_pos, get_global_coordinates(obj), rad_plane, layers_thresholds)
                    col_obj = get_collection(obj)
                    if re.search(rf'{g_root_layers_names[0]}|{g_root_layers_names[1]}|{g_root_layers_names[2]}|{g_root_layers_names[3]}', col_obj.name):
                        # Check if the object already in a 'layer' collection?
                        move_obj_to_subcoll(obj, None)
                    else:
                        move_obj_to_subcoll(obj, layer)
                    if analyze_op.bool_at_color_cells:
                        self.assign_color_layer(obj, layer)
        else:
            # Parse selection
            for obj in bpy.context.selected_objects:
                if obj.type == 'MESH':
                    # get the world coordinates of the object, with scaling
                    layer = self.assign_layer(ref_pos, get_global_coordinates(obj), rad_plane, layers_thresholds)
                    col_obj = get_collection(obj)
                    if re.search(rf'{g_root_layers_names[0]}|{g_root_layers_names[1]}|{g_root_layers_names[2]}|{g_root_layers_names[3]}', col_obj.name):
                        # Check if the object already in a 'layer' collection?
                        move_obj_to_subcoll(obj, None)
                    else:
                        move_obj_to_subcoll(obj, layer)
                    if analyze_op.bool_at_color_cells:
                        self.assign_color_layer(obj, layer)
        return {'FINISHED'}


class MORPHOBLEND_OT_ClearRootLayers(bpy.types.Operator):
    '''Clear assignment to layers'''
    bl_idname = 'morphoblend.clear_rootlayers'
    bl_label = 'Clear assignment to layers'
    bl_descripton = 'Clear assignment to layers.'

    @classmethod
    def poll(cls, context):
        return True

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        max_levels = 9                          # Max Levels to parse
        scn_col = bpy.context.scene.collection  # Root collection
        analyze_op = context.scene.analyze_tool
        _apply_to_all = analyze_op.bool_at_all
        if _apply_to_all:
            # Retrieve hiearchy of all collections
            cols_tree = col_hierarchy(scn_col, levels=max_levels)
            # Create a dict of each collection and its parent
            cols_parents = {i: k for k, v in cols_tree.items() for i in v}
            for col, parent in cols_parents.items():
                # Is name matching any of the names used for the layers?
                if re.search(rf'{g_root_layers_names[0]}|{g_root_layers_names[1]}|{g_root_layers_names[2]}|{g_root_layers_names[3]}', col.name):
                    for obj in col.objects:
                        if obj.type == 'MESH':
                            if analyze_op.bool_at_color_cells:
                                mat_palette = create_materials_palette('Qual_bright')
                                assign_material(obj, mat_palette, rand_color=True)
                            parent.objects.link(obj)
                            col.objects.unlink(obj)
                    # unlink then delete the now empty collection
                    parent.children.unlink(col)
                    bpy.data.collections.remove(col)
        else:
            for obj in bpy.context.selected_objects:
                if obj.type == 'MESH':
                    obj_col = get_collection(obj)
                    obj_col_parent = get_parent(obj_col)
                    if re.search(rf'{g_root_layers_names[0]}|{g_root_layers_names[1]}|{g_root_layers_names[2]}|{g_root_layers_names[3]}', obj_col.name):
                        if analyze_op.bool_at_color_cells:
                            mat_palette = create_materials_palette('Qual_bright')
                            assign_material(obj, mat_palette, rand_color=True)
                        obj_col_parent.objects.link(obj)
                        obj_col.objects.unlink(obj)
                        # Unlink and delete the collection if empty
                        if len(obj_col.objects) == 0:
                            obj_col_parent.children.unlink(obj_col)
                            bpy.data.collections.remove(obj_col)
        return {'FINISHED'}


class MORPHOBLEND_OT_PositionRootLayersReference(bpy.types.Operator):
    '''Position center of root'''
    bl_idname = 'morphoblend.position_root_layers_reference'
    bl_label = 'Position center of root'
    bl_descripton = 'Position center of root.'

    def modal(self, context, event):
        analyze_op = context.scene.analyze_tool
        context.area.tag_redraw()
        if event.type == 'MOUSEMOVE':
            x, y = event.mouse_region_x, event.mouse_region_y
            # Moves empty with mouse
            loc = region_2d_to_location_3d(context.region, context.space_data.region_3d, (x, y), (0, 0, 0))
            bpy.data.objects[self.name_ref_empty].location = loc
            self.ref_loc = loc

        elif event.type == 'LEFTMOUSE':
            # copy coordinates of the references from the position of the empty
            analyze_op.pos_at_ref = self.ref_loc * bpy.context.scene.unit_settings.scale_length
            # Highlight the empty (cosmetic)
            context.view_layer.objects.active = bpy.data.objects[self.name_ref_empty]
            bpy.data.objects[self.name_ref_empty].select_set(False)
            return {'FINISHED'}

        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            # Delete the empty
            bpy.data.objects[self.name_ref_empty].select_set(True)
            bpy.ops.object.delete()
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}

    def invoke(self, context, event):
        analyze_op = context.scene.analyze_tool
        if context.area.type == 'VIEW_3D':
            self.ref_loc = []
            # set the viewport to display the radial plane
            plane_def = (analyze_op.plane_at_ref[0], analyze_op.plane_at_ref[1], analyze_op.plane_at_ref[2])
            if plane_def == (True, True, False):
                orient = 'TOP'
            elif plane_def == (False, True, True):
                orient = 'LEFT'
            else:
                orient = 'FRONT'
            bpy.ops.view3d.view_axis(type=orient)
            # Create an empty or select it if it already exists
            self.name_ref_empty = 'ref_empty'
            if not bpy.context.scene.objects.get(self.name_ref_empty):
                empty = bpy.data.objects.new(self.name_ref_empty, None)
                empty.empty_display_size = 0.5
                empty.empty_display_type = 'PLAIN_AXES'
                bpy.context.scene.collection.objects.link(empty)
            else:
                bpy.data.objects[self.name_ref_empty].select_set(True)
            context.window_manager.modal_handler_add(self)
            return {'RUNNING_MODAL'}
        else:
            self.report({'WARNING'}, 'View3D not found, cannot run operator')
            return {'CANCELLED'}


class MORPHOBLEND_OT_Lineages_Create(bpy.types.Operator):
    '''Track cells across time points based on position'''
    bl_idname = 'morphoblend.track_cells'
    bl_label = 'track cells'
    bl_descripton = 'Track cells across time points based on position'

    @classmethod
    def poll(cls, context):
        analyze_op = context.scene.analyze_tool
        if analyze_op.bool_track_all:
            return True
        else:
            return context.selected_objects is not None

    def execute(self, context):
        analyze_op = context.scene.analyze_tool
        _apply_to_all = analyze_op.bool_track_all
        _threshold_child = analyze_op.threshold_tracking
        if _apply_to_all:  # Process all objects starting from the first time point
            # Get all TP collections
            all_tp_cols = collections_from_pattern(analyze_op.tp_pattern)
            # Iterate over all time points
            for prev, item, nxt in previous_and_next(all_tp_cols):
                for obj in item.all_objects:  # Process all objects of the collection
                    if obj.type == 'MESH':
                        # get the coordinates of the object
                        pos_obj = get_global_coordinates(obj)
                        if prev is None:  # 1st time point objects have no parents --> they are the roots of each lineage tree
                            global g_lineages
                            g_lineages[obj.name] = Node(name=obj.name, obj_name=obj.name)
                        if nxt is not None:  # Until the last time point is reached...
                            self.child_in_next_tp(nxt, pos_obj, _threshold_child, obj)
        else:
            # The selected objects are the roots of the lineages
            for obj in bpy.context.selected_objects:
                if obj.type == 'MESH':
                    g_lineages[obj.name] = Node(name=obj.name, obj_name=obj.name)
            # Get all TP collections
            all_tp_cols = collections_from_pattern(analyze_op.tp_pattern)
            # Retrieve the currently active time point
            currentTP = show_active_tp(context)
            # Remove from the list all time points anterior to this one
            del all_tp_cols[:all_tp_cols.index(currentTP)]
            # Iterate over all remaining time points
            for prev, item, nxt in previous_and_next(all_tp_cols):
                for obj in item.all_objects:
                    pos_obj = get_global_coordinates(obj)  # get the coordinates of the object
                    if nxt is not None:  # Until the last time point is reached...
                        self.child_in_next_tp(nxt, pos_obj, _threshold_child, obj)
        # Report on the lineages found
        k = 0
        for root, tree in g_lineages.items():
            if tree.height == len(all_tp_cols) - 1:
                k += 1
            # DEBUG print each tree
            print(RenderTree(tree, style=AsciiStyle()).by_attr())
        print(f"{k}/{len(g_lineages)} lineages cover all time points")
        # Store the lineages
        store_lineages(g_lineages)
        self.report({'INFO'}, "Tracking complete!")
        return {'FINISHED'}

    def child_in_next_tp(self, nxt, pos_obj, _threshold_child, obj):
        ''' Identifies child of an object in the next collection and add it to the lineage tree.'''
        d_objn = {}  # Dict storing the name and distances between the reference object and each object in the next time point
        # compute distance between the object and *all* objects in the next time point
        for obj_n in nxt.all_objects:
            pos_obj_n = get_global_coordinates(obj_n)
            d_objn[obj_n] = distance3D(pos_obj, pos_obj_n)
        # Get the closest object
        closest = min(d_objn, key=d_objn.get)
        if d_objn[closest] < _threshold_child:
            # if distance to the closest is inf to the user defined threshold, define the object as a valid child
            for root, tree in g_lineages.items():
                Node(name=closest.name, obj_name=closest.name, parent=find_by_attr(tree, obj.name))


class MORPHOBLEND_OT_Lineages_Clear(bpy.types.Operator):
    '''Color tracked cells based on lineages'''
    bl_idname = 'morphoblend.clear_lineages'
    bl_label = 'Clear lineages'
    bl_descripton = 'Clear lineages'

    @classmethod
    def poll(cls, context):
        # only if lineages data structure exist
        return g_lineages is not None and len(g_lineages) > 0

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        global g_lineages
        g_lineages = {}
        self.report({'INFO'}, "Lineages cleared!")
        return {'FINISHED'}


class MORPHOBLEND_OT_Lineages_Export(bpy.types.Operator):
    ''' Export lineages'''
    bl_idname = 'morphoblend.export_tracking'
    bl_label = 'Export tracking data'
    bl_description = 'Export tracking data'
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        # only if lineages data structure exist
        return g_lineages is not None and len(g_lineages) > 0

    def execute(self, context):
        analyze_op = context.scene.analyze_tool
        with open(bpy.path.abspath(analyze_op.import_export_track_path), 'w', encoding='utf-8') as f:
            exporter = JsonExporter(indent=2, sort_keys=False)
            rooted_forest = Node(name='root')
            for root, tree in g_lineages.items():
                tree.parent = rooted_forest
            exporter.write(rooted_forest, f)
        info_mess = "Lineages exported!"
        self.report({'INFO'}, info_mess)
        return{'FINISHED'}


class MORPHOBLEND_OT_Lineages_Import(bpy.types.Operator):
    ''' Import Tracking data'''
    bl_idname = 'morphoblend.import_tracking'
    bl_label = 'Import tracking data'
    bl_description = 'Import tracking data'
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        analyze_op = context.scene.analyze_tool
        return analyze_op.import_export_track_path != ''

    def execute(self, context):
        analyze_op = context.scene.analyze_tool
        with open(bpy.path.abspath(analyze_op.import_export_track_path), 'r+', encoding='utf-8') as f:
            importer = JsonImporter()
            imported_trees = importer.read(f)
            global g_lineages
            g_lineages = self.parse_imported_trees(imported_trees)
        for root, tree in g_lineages.items():
            # DEBUG print each tree
            print("---------------------------------------------")
            print(RenderTree(tree))
        info_mess = "Lineages imported!"
        self.report({'INFO'}, info_mess)
        return{'FINISHED'}

    def parse_imported_trees(self, tree):  # FIXME
        ''' Parse Boyko's data ONLY - NOT VERSATILE. Format: AnyNode(name=30.0, t=10) with name= labelID
        currrently this can NOT read back the format that export function is creating'''
        # get all trees rooted at t=0
        trees = findall_by_attr(tree, name="t", value=0)
        _forest = {}
        for tree in trees:
            # detach
            tree.parent = None
            # create a new obj_name attribute for each node to store the name of the object in the expected format: tXX_labelYYYY
            for node in PreOrderIter(tree):
                node.new = 'obj_name'
                node.obj_name = f"t{node.t}_label{int(node.name)}"
            _forest[tree.root.name] = tree
        return _forest


class MORPHOBLEND_OT_Lineages_Color(bpy.types.Operator):
    '''Color tracked cells based on lineages'''
    bl_idname = 'morphoblend.color_lineages'
    bl_label = 'Color lineages'
    bl_descripton = 'Color tracked cells based on lineages'

    palette = 'Qual_bright'

    @classmethod
    def poll(cls, context):
        # only if lineages data structure exist
        return g_lineages is not None and len(g_lineages) > 0

    def execute(self, context):
        # Get the materials corresponding to the palette
        materials = create_materials_palette(self.palette)
        for root, tree in g_lineages.items():
            # pick a color at random in the palette and use it to color all cells of a lineage
            col_index = randrange(0, len(materials))
            for node in PreOrderIter(tree):
                obj = bpy.context.scene.objects.get(node.obj_name)
                if obj:
                    assign_material(obj, materials, color_index=col_index)
        # WARN forcing  the redraw is not a good idea. If not done, one must click once.
        bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
        self.report({'INFO'}, "Coloring complete!")
        return {'FINISHED'}


class MORPHOBLEND_OT_Lineages_Load(bpy.types.Operator):
    '''Load existing lineages'''
    bl_idname = 'morphoblend.load_lineages'
    bl_label = 'Load lineages'
    bl_descripton = 'Load lineages'

    @classmethod
    def poll(cls, context):
        # only if lineages data structure exist
        return len(context.scene.g_lineages) > 0

    def execute(self, context):
        global g_lineages
        g_lineages = {}
        retrieve_lineages(context)
        self.report({'INFO'}, "Lineages loaded!")
        return {'FINISHED'}


class MORPHOBLEND_OT_3DConnectivity_Create(bpy.types.Operator):
    ''' Derive graph of 3D cell connectivity'''
    bl_idname = 'morphoblend.3d_neighbours'
    bl_label = '3D Neighbours'
    bl_descripton = 'Derive graph of 3D cell connectivity'

    @classmethod
    def poll(cls, context):
        analyze_op = context.scene.analyze_tool
        if analyze_op.bool_3dconnect_all:
            return True
        else:
            return context.selected_objects is not None

    def invoke(self, context, event):
        analyze_op = context.scene.analyze_tool
        if analyze_op.bool_3dconnect_all | len(context.selected_objects) > 50:
            return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        row = self.layout
        row.label(text='This operation may take a long time')
        row = self.layout
        row.label(text='The bar will show progress')
        row = self.layout
        row.label(text='Press [Esc] to cancel')

    def execute(self, context):
        analyze_op = context.scene.analyze_tool
        _apply_to_all = analyze_op.bool_3dconnect_all
        analyze_op.progress_bar = 0
        total_n_pairs = 0
        pairs_processed = 0
        if _apply_to_all:
            # Get all TP collections
            all_tp_cols = collections_from_pattern(analyze_op.tp_pattern)
            # Get the total number of pairs to be analyzed
            total_n_pairs = self.get_number_of_pairs(all_tp_cols)
            # Iterate over all time points
            for tp in all_tp_cols:
                tp_G = nx.Graph()
                # Get all unique pairs of two objects and check if they are touching
                print(f"Extracting 3D connectivity for {tp.name}: processing {len(list(combinations(tp.all_objects, 2)))} pairs...")
                for objpair in combinations(tp.all_objects, 2):
                    area_intersection = self.intersection_area(objpair[0], objpair[1])
                    if area_intersection != 0:
                        # Add the pair of objects (referenced by name) as a weighted edge to the graph
                        self.add_edge(tp_G, objpair, area_intersection)
                    pairs_processed += 1
                # add the Graph to the dict
                self.update_progress(context, pairs_processed, total_n_pairs)
                g_networks[tp.name] = tp_G
        else:
            # Get current time point
            currentTP = show_active_tp(context)
            # Get the total number of pairs to be analyzed
            total_n_pairs = self.get_number_of_pairs(currentTP)
            G = nx.Graph()
            print(f"Processing {len(list(combinations(tp.all_objects, 2)))} pairs...")
            for objpair in combinations(bpy.context.selected_objects, 2):
                area_intersection = self.intersection_area(objpair[0], objpair[1])
                if area_intersection != 0:
                    # Add the pair of objects (referenced by name) as a weighted edge to the graph
                    self.add_edge(tp_G, objpair, area_intersection)
                pairs_processed += 1
                self.update_progress(context, pairs_processed, total_n_pairs)
            g_networks[currentTP.name] = G
        # Store data:
        store_3dConnectivity(g_networks)
        # Display report in the console
        for tp, G in g_networks.items():
            print(f"{tp}: {G.number_of_nodes()} nodes and {G.number_of_edges()} edges in {len(list(nx.connected_components(G)))} graph(s)")
        self.report({'INFO'}, 'Done!')
        return {'FINISHED'}

    def add_edge(self, tp_G, objpair, area_intersection):
        # Add the pair of objects (referenced by name) as a weighted edge to the graph
        tp_G.add_edge(objpair[0].name, objpair[1].name, area=area_intersection)
        # Add to the nodes the collection/tissue of the cell
        tp_G.nodes[objpair[0].name]['collection'] = get_collection(objpair[0]).name
        tp_G.nodes[objpair[1].name]['collection'] = get_collection(objpair[1]).name

    def get_number_of_pairs(self, inSet):
        total = 0
        for e in inSet:
            total += len(list(combinations(e.all_objects, 2)))
        return total

    def update_progress(self, context, n_file, total):
        analyze_op = context.scene.analyze_tool
        progress_ratio = n_file / total * 100
        analyze_op.progress_bar = progress_ratio
        bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)

    def intersection_area(self, obj1, obj2):
        '''If two objects intersect, return the scaled area of contact or 0 if no intersection. The area is the average of the areas for each object'''
        # Create two empty bmesh and fill with data from objects
        bm1 = bmesh.new()
        bm2 = bmesh.new()
        bm1 = bmesh_copy_from_object(obj1, apply_modifiers=True)
        bm2 = bmesh_copy_from_object(obj2, apply_modifiers=True)

        # make BVH tree from BMesh of objects
        obj1_BVHtree = BVHTree.FromBMesh(bm1)
        obj2_BVHtree = BVHTree.FromBMesh(bm2)

        # get intersecting pairs of faces indices
        inter = obj1_BVHtree.overlap(obj2_BVHtree)

        # if list is not empty,  objects are touching, compute the scaled area of contact as average of area on each object
        if inter != []:
            obj1_faces_idx = set([i[0] for i in inter])
            obj2_faces_idx = set([i[1] for i in inter])
            return (self.area_faces(bm1, obj1_faces_idx) + self.area_faces(bm2, obj2_faces_idx)) / 2
        else:
            return 0

    def area_faces(self, bm, idx_faces):
        ''' Return the scaled area of the a set of faces defined by their  indices'''
        bm.faces.ensure_lookup_table()
        area = sum(bm.faces[idx].calc_area() for idx in idx_faces)
        scaled_area = area * bpy.context.scene.unit_settings.scale_length ** 2
        return scaled_area


class MORPHOBLEND_OT_3DConnectivity_Load(bpy.types.Operator):
    '''Load existing Networks'''
    bl_idname = 'morphoblend.load_networks'
    bl_label = 'Load networks'
    bl_descripton = 'Load networks'

    @classmethod
    def poll(cls, context):
        # only if lineages data structure exist
        return len(context.scene.g_networks) > 0

    def execute(self, context):
        global g_networks
        g_networks = {}
        retrieve_3dConnectivity(context)
        self.report({'INFO'}, "Networks loaded!")
        return {'FINISHED'}


class MORPHOBLEND_OT_3DConnectivity_Clear(bpy.types.Operator):
    '''Erase all Networks'''
    bl_idname = 'morphoblend.clear_networks'
    bl_label = 'Clear networks'
    bl_descripton = 'Clear networks'

    @classmethod
    def poll(cls, context):
        # only if lineages data structure exist
        return len(g_networks) > 0 or len(context.scene.g_networks) > 0

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        global g_networks
        g_networks = {}
        context.scene.g_networks.clear()
        self.report({'INFO'}, "Networks cleared!")
        return {'FINISHED'}


class MORPHOBLEND_OT_3DConnectivity_Draw(bpy.types.Operator):
    '''Draws Networks'''
    bl_idname = 'morphoblend.draw_networks'
    bl_label = 'Draw connectivity network'
    bl_descripton = 'Draw connectivity network'

    # class variables
    shapes = []

    @classmethod
    def poll(cls, context):
        # only if lineages data structure exist
        return g_networks is not None and len(g_networks) > 0

    def execute(self, context):
        # Parse the collection of networks
        for tp, G in g_networks.items():
            # Create sub-collection for Graph
            subcol = make_collection("3dConnectivity", bpy.data.collections[tp])
            # Draw each Nodes and edges
            self.draw_Nodes(G, subcol)
            self.draw_Edges(G, subcol)
        # Smooth and join them
        # FIXME: below --> only smooth the first set & returns an error after erasing
        # self.smooth_join(context)
        # Hide all collections that are not "3dconnectivity"
        showSubCol(context=context, pattern='3dConnectivity')
        self.report({'INFO'}, 'Done!')
        return {'FINISHED'}

    def draw_Nodes(self, G, DestColl):
        for node in G.nodes():
            # Create an empty mesh and the object.
            bpy.ops.object.select_all(action='DESELECT')
            bpy.ops.mesh.primitive_uv_sphere_add()
            node_sphere = bpy.context.object
            # Set  its properties from the ones referenced as node
            node_obj = bpy.data.objects[node]
            node_sphere.location = node_obj.location
            node_sphere.name = "node_" + node
            node_sphere.dimensions = [0.25, 0.25, 0.25]
            node_sphere.active_material = node_obj.active_material
            move_obj_to_coll(node_sphere, DestColl)
            self.shapes.append(node_sphere)

    def draw_Edges(self, G, DestColl):
        for source, target in G.edges():
            # Get references to the objects forming the edge
            source_obj = bpy.data.objects[source]
            target_obj = bpy.data.objects[target]
            # Get location of neighbour cells
            source_loc = source_obj.location
            target_loc = target_obj.location
            # compute difference, center and mag (??)
            diff = [c2 - c1 for c2, c1 in zip(source_loc, target_loc)]
            cent = [(c2 + c1) / 2 for c2, c1 in zip(source_loc, target_loc)]
            mag = sum([(c2 - c1) ** 2 for c1, c2 in zip(source_loc, target_loc)]) ** 0.5
            # Euler rotation calculation
            v_axis = Vector(diff).normalized()
            v_obj = Vector((0, 0, 1))
            v_rot = v_obj.cross(v_axis)
            angle = acos(v_obj.dot(v_axis))

            # Copy mesh primitive to create edge
            bpy.ops.object.select_all(action='DESELECT')
            bpy.ops.mesh.primitive_cylinder_add()
            edge_cylinder = bpy.context.object
            edge_cylinder.name = "edge_" + source + "-" + target
            edge_cylinder.dimensions = [0.05] * 2 + [mag]
            edge_cylinder.location = cent
            edge_cylinder.rotation_mode = 'AXIS_ANGLE'
            edge_cylinder.rotation_axis_angle = [angle] + list(v_rot)
            move_obj_to_coll(edge_cylinder, DestColl)
            self.shapes.append(edge_cylinder)

    def smooth_join(self, context):
        # Smooth & join shapes
        for shape in self.shapes:
            shape.select_set(True)
        context.view_layer.objects.active = self.shapes[0]
        bpy.ops.object.shade_smooth()

    def showSubCol(self, context, pattern):
        analyze_op = context.scene.analyze_tool
        # Retrieve hiearchy of all collection and their parents
        cols_tree = col_hierarchy(bpy.context.scene.collection, levels=9)
        all_cols = {i: k for k, v in cols_tree.items() for i in v}
        # Parse all collections and process the ones matching the pattern but not the one that are time points
        for col in all_cols:
            if not re.search(pattern, col.name) and not re.match(analyze_op.tp_pattern, col.name):
                col.hide_viewport = True
                col.hide_render = True
        return None


class MORPHOBLEND_OT_3DConnectivity_Erase(bpy.types.Operator):
    '''Erase Networks'''
    bl_idname = 'morphoblend.erase_networks'
    bl_label = 'Erase connectivity network'
    bl_descripton = 'Erase connectivity network'

    @classmethod
    def poll(cls, context):
        # only if lineages data structure exist
        return True

    def execute(self, context):
        # Parse all collections and process the ones matching the pattern but not the one that are time points
        # Erase collections containing 3DConnectivity and all objects therein
        # FIXME: this causes trouble as it removes too much data? --> 'ReferenceError: StructRNA of type Object has been removed' when drawing is called afterwards... Are the nodes removed??
        cols_tree = col_hierarchy(bpy.context.scene.collection, levels=9)
        all_cols = {i: k for k, v in cols_tree.items() for i in v}
        for col in all_cols:
            if re.search('3dConnectivity', col.name):
                coll = bpy.data.collections.get(col.name)
                if coll:
                    obs = [o for o in coll.objects if o.users == 1]
                    while obs:
                        bpy.data.objects.remove(obs.pop())
                    bpy.data.collections.remove(coll)
        # Make 1st time point visible only
        self.report({'INFO'}, 'Graph erased!')
        return {'FINISHED'}


class MORPHOBLEND_OT_3DConnectivity_Export(bpy.types.Operator):
    ''' Export 3D connectivity graph'''
    bl_idname = 'morphoblend.export_networks'
    bl_label = 'Export 3D connectivity graphs'
    bl_description = 'Export 3D connectivity graphse'
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        # only if networks data structure exist
        return g_networks is not None and len(g_networks) > 0

    def execute(self, context):
        analyze_op = context.scene.analyze_tool
        output_basename = "3dconnectivity_"
        for tp, G in g_networks.items():
            data = json_graph.node_link_data(G)
            outfile_path = bpy.path.abspath(analyze_op.import_export_networks_path) + output_basename + tp + '.json'
            with open(outfile_path, 'w', encoding='utf-8') as f:
                json.dump(data, f)
        info_mess = "Networks exported!"
        self.report({'INFO'}, info_mess)
        return{'FINISHED'}


class MORPHOBLEND_OT_3DConnectivity_Import(bpy.types.Operator):
    ''' Import 3D connectivity graph'''
    bl_idname = 'morphoblend.import_networks'
    bl_label = 'Import 3D connectivity graphs'
    bl_description = 'Import 3D connectivity graphs'
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        analyze_op = context.scene.analyze_tool
        _path = Path(bpy.path.abspath(analyze_op.import_export_networks_path))
        for child in sorted(_path.iterdir()):
            if child.is_file() and child.name.endswith('.json') and re.search(analyze_op.tp_pattern, child.name):
                tp = re.search(analyze_op.tp_pattern, child.name).group(0)
                self.import_json(child.as_posix(), tp)
            elif child.is_file() and child.name.endswith('.json'):
                tp = child.name
                self.import_json(child.as_posix(), tp)
        info_mess = "3D connectivity graphs imported!"
        self.report({'INFO'}, info_mess)
        return{'FINISHED'}

    def import_json(self, path, tp):
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            G = json_graph.node_link_graph(data)
            g_networks[tp] = G


class MORPHOBLEND_OT_Nuclei_Import(bpy.types.Operator):
    ''' Import nuclei position '''
    bl_idname = 'morphoblend.import_nuclei'
    bl_label = 'Import nuclei position '
    bl_description = 'Import nuclei position '
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        analyze_op = context.scene.analyze_tool
        _path = Path(bpy.path.abspath(analyze_op.import_nuclei_path))
        for child in sorted(_path.iterdir()):
            if child.is_file() and child.name.endswith('.csv') and re.search(analyze_op.tp_pattern, child.name):
                tp = re.search(analyze_op.tp_pattern, child.name).group(0)
                tp = re.sub('[0]{3}', '', tp, 1)
                self.import_csv(child.as_posix(), tp)
            elif child.is_file() and child.name.endswith('.csv'):
                tp = child.name
                self.import_csv(child.as_posix(), tp)
        info_mess = "Nuclei coordinates imported!"
        self.report({'INFO'}, info_mess)
        return{'FINISHED'}

    def import_csv(self, path, tp):
        with open(path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f, delimiter=',')
            data = []
            for line in reader:
                data.append(line)
            g_nuclei[tp] = data


class MORPHOBLEND_OT_Nuclei_Draw(bpy.types.Operator):
    ''' Import nuclei position '''
    bl_idname = 'morphoblend.draw_nuclei'
    bl_label = 'Draw nuclei position '
    bl_description = 'Draw nuclei position '
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return g_nuclei is not None and len(g_nuclei) > 0

    def execute(self, context):
        # Parse the collection of networks
        for tp, data in g_nuclei.items():
            # Create sub-collection for Graph
            subcol = make_collection("Nuclei", bpy.data.collections[tp])
            # Draw each Nodes and edges
            self.draw_Nuclei(data, subcol)
        # Smooth and join them
        # FIXME: below --> only smooth the first set & returns an error after erasing
        # self.smooth_join(context)
        # Hide all collections that are not "Nuclei"
        showSubCol(context=context, pattern='Nuclei')
        self.report({'INFO'}, 'Done!')
        return {'FINISHED'}

    def draw_Nuclei(self, data, DestColl):
        for line in data:
            if not re.search('\D', line[0]):  # skip header line (contains non numerical values)
                # Create a matrix  from the coordinates

                # Apply the same scaling and rotation as to the cells

                # Create an empty mesh and the object.
                bpy.ops.object.select_all(action='DESELECT')
                bpy.ops.mesh.primitive_uv_sphere_add()
                nucleus = bpy.context.object
                nucleus.location = (float(line[1])/100, float(line[3])/100, -1*float(line[2])/100)  # FIXME Scaling and orientation are HACKs --> rationalise
                nucleus.name = "nuc_" + line[0]
                nucleus.dimensions = [0.25, 0.25, 0.25]
                move_obj_to_coll(nucleus, DestColl)



# ------------------------------------------------------------------------
#    Operator modules
# ------------------------------------------------------------------------
def showSubCol(context, pattern):
    analyze_op = context.scene.analyze_tool
    # Retrieve hiearchy of all collection and their parents
    cols_tree = col_hierarchy(bpy.context.scene.collection, levels=9)
    all_cols = {i: k for k, v in cols_tree.items() for i in v}
    # Parse all collections and process the ones matching the pattern but not the one that are time points
    for col in all_cols:
        if not re.search(pattern, col.name) and not re.match(analyze_op.tp_pattern, col.name):
            col.hide_viewport = True
            col.hide_render = True
    return None


def store_3dConnectivity(connectivity):
    if connectivity is not None:
        for tp, G in connectivity.items():
            data = json_graph.node_link_data(G)
            item = bpy.context.scene.g_networks.add()
            item.key = tp
            item.value = json.dumps(data)


def retrieve_3dConnectivity(context):
    for i in range(len(context.scene.g_networks)):
        item = context.scene.g_networks[i]
        data = json.loads(item.value)
        G = json_graph.node_link_graph(data)
        g_networks[item.key] = G
    return None


def store_lineages(lineages):
    if lineages is not None:
        exporter = JsonExporter(indent=2, sort_keys=False)
        for root, tree in lineages.items():
            item = bpy.context.scene.g_lineages.add()
            item.key = root
            item.value = exporter.export(tree)


def retrieve_lineages(context):
    importer = JsonImporter()
    for i in range(len(context.scene.g_lineages)):
        item = context.scene.g_lineages[i]
        tree = importer.import_(item.value)
        g_lineages[item.key] = tree
    return None


"""
def lineages_from_parent_child_pairs(node, relationships):
    ''' Make lineages from (child, parent) pairs; value of node defines elements w/o parents. Returns a nested dict.
    Not used. Lifted from: https://stackoverflow.com/questions/444296/how-to-efficiently-build-a-tree-from-a-flat-structure'''
    return {
        v: lineages_from_parent_child_pairs(v, relationships)
        for v in [x[0] for x in relationships if x[1] == node]
    }
"""


# ------------------------------------------------------------------------
#    UI elements
# ------------------------------------------------------------------------
class MORPHOBLEND_PT_Analyze(bpy.types.Panel):
    bl_idname = 'MORPHOBLEND_PT_Analyze'
    bl_label = 'Analyze'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'MorphoBlend'
    bl_parent_id = 'VIEW3D_PT_MorphoBlend'

    def draw_header(self, context):
        layout = self.layout
        layout.label(icon='IPO_ELASTIC')

    def draw(self, context):
        layout = self.layout
        analyze_op = context.scene.analyze_tool

        box = layout.box()
        row = box.row()
        if len(bpy.context.selected_objects) > 1:
            text_box = f"Assign root layers [{str(len(bpy.context.selected_objects))} selected cells]"
        else:
            text_box = f"Assign root layers [{str(len(bpy.context.selected_objects))} selected cell]"
        row.label(text=text_box, icon='HAIR')

        row = box.row()
        row.label(text='Radial plane defined by:')
        row.prop(analyze_op, 'plane_at_ref')

        row = box.row()
        row.label(text='Center of root (µm):')
        row.prop(analyze_op, 'pos_at_ref')
        row.operator(MORPHOBLEND_OT_PositionRootLayersReference.bl_idname, text='Interactive')

        row = box.row()
        row.label(text=f"Threshold for {g_root_layers_names[0]} (µm):")
        row.prop(analyze_op, 'dist_t0_at')

        row = box.row()
        row.label(text=f"Threshold for {g_root_layers_names[1]} (µm):")
        row.prop(analyze_op, 'dist_t1_at')

        row = box.row()
        row.label(text=f"Threshold for {g_root_layers_names[2]} (µm):")
        row.prop(analyze_op, 'dist_t2_at')

        row = box.row()
        row.prop(analyze_op, 'bool_at_all')
        row.prop(analyze_op, 'bool_at_color_cells')
        row.operator(MORPHOBLEND_OT_AssignRootLayers.bl_idname, text='Assign layers', icon='HAIR')
        row.operator(MORPHOBLEND_OT_ClearRootLayers.bl_idname, text='Clear layers', icon='X')

        box = layout.box()
        row = box.row()
        row.label(text="Track cells", icon='TRACKING_REFINE_BACKWARDS')

        row = box.row()
        row.label(text="Threshold for tracking (µm):")
        row.prop(analyze_op, "threshold_tracking")

        row = box.row()
        row.prop(analyze_op, "bool_track_all")
        row.operator(MORPHOBLEND_OT_Lineages_Create.bl_idname, text="Track", icon='TRACKING_REFINE_BACKWARDS')
        row.operator(MORPHOBLEND_OT_Lineages_Load.bl_idname, text='Load', icon='ADD')
        row.operator(MORPHOBLEND_OT_Lineages_Color.bl_idname, text="Color", icon='RESTRICT_COLOR_ON')
        row.operator(MORPHOBLEND_OT_Lineages_Clear.bl_idname, text="Clear", icon='X')

        row = box.row()
        row.prop(analyze_op, 'import_export_track_path')

        row = box.row()
        row.operator(MORPHOBLEND_OT_Lineages_Export.bl_idname, text="Export", icon='EXPORT')
        row.operator(MORPHOBLEND_OT_Lineages_Import.bl_idname, text="Import", icon='IMPORT')

        box = layout.box()
        row = box.row()
        row.label(text="3D connectivity graph", icon='OUTLINER_DATA_MESH')

        row = box.row()
        row.prop(analyze_op, "bool_3dconnect_all")
        row.operator(MORPHOBLEND_OT_3DConnectivity_Create.bl_idname, text='Generate', icon='OUTLINER_DATA_MESH')
        row.operator(MORPHOBLEND_OT_3DConnectivity_Load.bl_idname, text='Load', icon='ADD')
        row.operator(MORPHOBLEND_OT_3DConnectivity_Clear.bl_idname, text='Clear', icon='X')

        row = box.row()
        row.prop(analyze_op, 'progress_bar', slider=True)

        row = box.row()
        row.operator(MORPHOBLEND_OT_3DConnectivity_Draw.bl_idname, text='Draw', icon='OUTLINER_DATA_MESH')
        row.operator(MORPHOBLEND_OT_3DConnectivity_Erase.bl_idname, text='Erase', icon='REMOVE')

        row = box.row()
        row.prop(analyze_op, 'import_export_networks_path')

        row = box.row()
        row.operator(MORPHOBLEND_OT_3DConnectivity_Export.bl_idname, text="Export", icon='EXPORT')
        row.operator(MORPHOBLEND_OT_3DConnectivity_Import.bl_idname, text="Import", icon='IMPORT')

        box = layout.box()
        row = box.row()
        row.label(text="Nuclei", icon='PARTICLES')

        row = box.row()
        row.prop(analyze_op, 'import_nuclei_path')
        row.operator(MORPHOBLEND_OT_Nuclei_Import.bl_idname, text='Import', icon='IMPORT')
        row = box.row()
        row.operator(MORPHOBLEND_OT_Nuclei_Draw.bl_idname, text='Draw', icon='BRUSH_TEXDRAW')


# ------------------------------------------------------------------------
#    Registrer/unregister calls
# ------------------------------------------------------------------------
render_classes = (AnalyzeProperties,
    SceneAttribute,
    MORPHOBLEND_OT_AssignRootLayers,
    MORPHOBLEND_OT_ClearRootLayers,
    MORPHOBLEND_OT_PositionRootLayersReference,
    MORPHOBLEND_OT_Lineages_Create,
    MORPHOBLEND_OT_Lineages_Color,
    MORPHOBLEND_OT_Lineages_Clear,
    MORPHOBLEND_OT_Lineages_Import,
    MORPHOBLEND_OT_Lineages_Export,
    MORPHOBLEND_OT_Lineages_Load,
    MORPHOBLEND_OT_3DConnectivity_Create,
    MORPHOBLEND_OT_3DConnectivity_Load,
    MORPHOBLEND_OT_3DConnectivity_Clear,
    MORPHOBLEND_OT_3DConnectivity_Draw,
    MORPHOBLEND_OT_3DConnectivity_Erase,
    MORPHOBLEND_OT_3DConnectivity_Export,
    MORPHOBLEND_OT_3DConnectivity_Import,
    MORPHOBLEND_OT_Nuclei_Import,
    MORPHOBLEND_OT_Nuclei_Draw)

register_classes, unregister_classes = bpy.utils.register_classes_factory(render_classes)


def register_analyze():
    register_classes()
    bpy.types.Scene.analyze_tool = PointerProperty(type=AnalyzeProperties)
    bpy.types.Scene.g_networks = CollectionProperty(type=SceneAttribute)
    bpy.types.Scene.g_lineages = CollectionProperty(type=SceneAttribute)


def unregister_analyze():
    del bpy.types.Scene.g_lineages
    del bpy.types.Scene.g_networks
    del bpy.types.Scene.analyze_tool
    unregister_classes()
