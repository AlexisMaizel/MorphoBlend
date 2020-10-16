import json
import re
from random import randrange

import networkx as nx
from networkx.readwrite import json_graph

import bpy
import bmesh
from mathutils.bvhtree import BVHTree
from itertools import combinations
from anytree import AsciiStyle, Node, PreOrderIter, RenderTree, find_by_attr, findall_by_attr
from anytree.importer import JsonImporter
from anytree.exporter import JsonExporter
from bpy.props import (BoolProperty, BoolVectorProperty, FloatProperty,
                       FloatVectorProperty, PointerProperty, StringProperty, EnumProperty)
from bpy_extras.view3d_utils import region_2d_to_location_3d

from .Utilities import (assign_material, col_hierarchy,
                        create_materials_palette, distance2D, distance3D,
                        get_collection, get_global_coordinates, get_parent,
                        move_obj_to_coll, previous_and_next, bmesh_copy_from_object)

# ------------------------------------------------------------------------
#    Keymaps
# ------------------------------------------------------------------------
PT_Analyze_keymaps = []

# TODO Move everything related to keyboard navigation through timepoints to Render.py
# ------------------------------------------------------------------------
#    Global variable
# ------------------------------------------------------------------------
# TODO  Do *not* use global variables - use custom properties
# The possible root layers
g_root_layers_names = ('Epidermis', 'Cortex', 'Endodermis', 'Stele')
# The list containing all the lineages
global g_lineages
g_lineages = []
global g_networks  # Dict of the connectivity graphs for each time point. Nodes are objects IDs and edges are weighted by the area of contact between two cells
g_networks = {}


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

    tp_pattern: StringProperty(
        name='Time point pattern',
        description='Regex pattern describing time points', # Matches time point (t1, T42, t09, etc...)
        default='^[Tt]\d{1,}$'
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
        name='Extract 3D neigbours for all cells',
        description='Extract 3D neigbours for all cells also the other time points or hidden ones',
        default=False
    )
    import_export_networks_path: StringProperty(
        name='Path',
        description='Path to the 3D connectivity graphs',
        default='',
        subtype='DIR_PATH'
    )



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
        analyze_op = context.scene.analyze_tool
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
        analyze_op = context.scene.analyze_tool
        # Get all TP collections at the topmost level
        all_tp_cols = collections_from_pattern(analyze_op.tp_pattern)
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
                        move_obj_to_coll(obj, None)
                    else:
                        move_obj_to_coll(obj, layer)
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
                        move_obj_to_coll(obj, None)
                    else:
                        move_obj_to_coll(obj, layer)
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


class MORPHOBLEND_OT_TrackCells(bpy.types.Operator):
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
                            g_lineages.append(Node(name=obj.name, obj_name=obj.name))
                        if nxt is not None:  # Until the last time point is reached...
                            self.child_in_next_tp(nxt, pos_obj, _threshold_child, obj)
        else:
            # The selected objects are the roots of the lineages
            for obj in bpy.context.selected_objects:
                if obj.type == 'MESH':
                    g_lineages.append(Node(name=obj.name, obj_name=obj.name))
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
        for tree in g_lineages:
            if tree.height == len(all_tp_cols) - 1:
                k += 1
            # DEBUG print each tree
            print(RenderTree(tree, style=AsciiStyle()).by_attr())
        print(f"{k}/{len(g_lineages)} lineages cover all time points")
        # Store the lineages
        # store_lineages(g_lineages)
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
            for tree in g_lineages:
                Node(name=closest.name, obj_name=closest.name, parent=find_by_attr(tree, obj.name))


class MORPHOBLEND_OT_ClearLineages(bpy.types.Operator):
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
        g_lineages = []
        self.report({'INFO'}, "Lineages cleared!")
        return {'FINISHED'}


class MORPHOBLEND_OT_ExportTracking(bpy.types.Operator):
    ''' Export 3D lineages'''
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
            for tree in g_lineages:
                tree.parent = rooted_forest
            exporter.write(rooted_forest, f)
        info_mess = "Lineages exported!"
        self.report({'INFO'}, info_mess)
        return{'FINISHED'}


class MORPHOBLEND_OT_ImportTracking(bpy.types.Operator):
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
        info_mess = "Lineages imported!"
        self.report({'INFO'}, info_mess)
        k=0
        for tree in g_lineages:
            if tree.height == 20 - 1:
                k += 1
            # DEBUG print each tree
            print("---------------------------------------------")
            print(RenderTree(tree))
        print(f"{k}/{len(g_lineages)} lineages cover all time points")
        return{'FINISHED'}

    def parse_imported_trees(self, tree):
        ''' Parse Boyko's data ONLY - NOT VERSATILE. Format: AnyNode(name=30.0, t=10) with name= labelID'''
        # get all trees rooted at t=0
        roots = findall_by_attr(tree, name="t", value=0)
        _forest = []
        for root in roots:
            # detach
            root.parent = None
            # create a new obj_name attribute for each node to store the name of the object in the expected format: tXX_labelYYYY
            for node in PreOrderIter(root):
                node.new = 'obj_name'
                node.obj_name = f"t{node.t}_label{int(node.name)}"
            _forest.append(root)
        return _forest


class MORPHOBLEND_OT_ColorLineages(bpy.types.Operator):
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
        for tree in g_lineages:
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


class MORPHOBLEND_OT_3DNeighborhood(bpy.types.Operator):
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

    def execute(self, context):
        # TODO  issue warning that processing may take a LONG time (implement progress or % in info mode??)
        analyze_op = context.scene.analyze_tool
        _apply_to_all = analyze_op.bool_3dconnect_all
        if _apply_to_all:
            # Get all TP collections
            all_tp_cols = collections_from_pattern(analyze_op.tp_pattern)
            # Iterate over all time points
            for tp in all_tp_cols:
                tp_G = nx.Graph()
                # Get all unique pairs of two objects and check if they are touching
                print(f"Extracting 3D connectivity for {tp.name}: processing {len(list(combinations(tp.all_objects, 2)))} pairs...")
                for objpair in combinations(tp.all_objects, 2):
                    area_intersection = self.intersection_area(objpair[0], objpair[1])
                    if area_intersection != 0:
                        tp_G.add_edge(objpair[0], objpair[1], weight=area_intersection)
                # add the Graph to the dict
                g_networks[tp.name] = tp_G
        else:
            # Get current time point
            currentTP = show_active_tp(context)
            G = nx.Graph()
            print(f"Processing {len(list(combinations(tp.all_objects, 2)))} pairs...")
            for objpair in combinations(bpy.context.selected_objects, 2):
                area_intersection = self.intersection_area(objpair[0], objpair[1])
                if area_intersection != 0:
                    G.add_edge(objpair[0], objpair[1], weight=area_intersection)
            g_networks[currentTP.name] = G

        # Display report in the console
        for tp, G in g_networks.items():
            print(f"{tp}: {G.number_of_nodes()} nodes and {G.number_of_edges()} edges in {len(list(nx.connected_components(G)))} graph(s)")
        self.report({'INFO'}, "Done!")
        return {'FINISHED'}

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


class MORPHOBLEND_OT_ClearNetworks(bpy.types.Operator):
    '''Erase all Networks'''
    bl_idname = 'morphoblend.clear_networks'
    bl_label = 'Clear networks'
    bl_descripton = 'Clear networks'

    @classmethod
    def poll(cls, context):
        # only if lineages data structure exist
        return g_networks is not None and len(g_networks) > 0
    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        global g_networks
        g_networks = {}
        self.report({'INFO'}, "Networks cleared!")
        return {'FINISHED'}


class MORPHOBLEND_OT_Draw3dConnectivity(bpy.types.Operator):
    '''Erase all Networks'''
    bl_idname = 'morphoblend.draw_networks'
    bl_label = 'Draw connectivity network'
    bl_descripton = 'Draw connectivity network'

    @classmethod
    def poll(cls, context):
        # only if lineages data structure exist
        return g_networks is not None and len(g_networks) > 0

    def execute(self, context):

        self.report({'INFO'}, "Done!")
        return {'FINISHED'}


class MORPHOBLEND_OT_Export3dConnectivity(bpy.types.Operator):
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
            # FIXME should export as JSON or YAML but does not work
            outfile_path = bpy.path.abspath(analyze_op.import_export_networks_path) + output_basename + tp + ".gexf"
            with open(outfile_path, 'w', encoding='utf-8') as f:
                nx.write_gexf(G, outfile_path)
        info_mess = "Networks exported!"
        self.report({'INFO'}, info_mess)
        return{'FINISHED'}


class MORPHOBLEND_OT_Import3dConnectivity(bpy.types.Operator):
    ''' Import 3D connectivity graph'''
    bl_idname = 'morphoblend.import_networks'
    bl_label = 'Import 3D connectivity graphs'
    bl_description = 'Import 3D connectivity graphse'
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        analyze_op = context.scene.analyze_tool
        # TODO To implement!
        with open(bpy.path.abspath(analyze_op.import_networks_path), 'w', newline='\n') as f:
            writer = csv.writer(f)
            for item in scn.results:
                writer.writerow(re.split('\s+', item.name))
        info_mess = "3D connectivity graphs imported!"
        self.report({'INFO'}, info_mess)
        return{'FINISHED'}


# ------------------------------------------------------------------------
#    Operator modules
# ------------------------------------------------------------------------
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


def store_lineages(lineages):
    if lineages is not None and len(lineages) > 0:
        bpy.context.Scene["lineages_list"] = lineages
    '''
    dump = json.dumps(lineages, indent=2)
    text_block = bpy.data.texts.new('lineages.json')
    text_block.from_string(dump)
    '''


def retrieve_lineages():
    if bpy.context.Scene["lineages_list"] is not None:
        return bpy.context.Scene["lineages_list"]

'''
def retrieve_lineages():
    text_obj = bpy.data.text['lineages.json']
    if text_obj is not None:
        text_str = text_obj.as_string()
        return json.loads(text_str)
    else:
        return None
'''


def lineages_from_parent_child_pairs(node, relationships):
    ''' Make lineages from (child, parent) pairs; value of node defines elements w/o parents. Returns a nested dict.
    Not used. Lifted from: https://stackoverflow.com/questions/444296/how-to-efficiently-build-a-tree-from-a-flat-structure'''
    return {
        v: lineages_from_parent_child_pairs(v, relationships)
        for v in [x[0] for x in relationships if x[1] == node]
    }


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
        row.operator(MORPHOBLEND_OT_AssignRootLayers.bl_idname, text='Assign layers')
        row.operator(MORPHOBLEND_OT_ClearRootLayers.bl_idname, text='Clear layers', icon='X')

        box = layout.box()
        row = box.row()
        row.label(text="Track cells", icon='TRACKING_REFINE_BACKWARDS')

        row = box.row()
        row.label(text="Threshold for tracking (µm):")
        row.prop(analyze_op, "threshold_tracking")

        row = box.row()
        row.prop(analyze_op, "bool_track_all")
        row.operator(MORPHOBLEND_OT_TrackCells.bl_idname, text="Track")
        row.operator(MORPHOBLEND_OT_ColorLineages.bl_idname, text="Color")
        row.operator(MORPHOBLEND_OT_ClearLineages.bl_idname, text="Clear", icon='X')

        row = box.row()
        row.prop(analyze_op, 'import_export_track_path')

        row = box.row()
        row.operator(MORPHOBLEND_OT_ExportTracking.bl_idname, text="Export", icon='EXPORT')
        row.operator(MORPHOBLEND_OT_ImportTracking.bl_idname, text="Import", icon='IMPORT')

        box = layout.box()
        row = box.row()
        row.label(text="3D connectivity graph", icon='OUTLINER_DATA_MESH')

        row = box.row()
        row.prop(analyze_op, "bool_3dconnect_all")
        row.operator(MORPHOBLEND_OT_3DNeighborhood.bl_idname, text="Generate")
        row.operator(MORPHOBLEND_OT_Draw3dConnectivity.bl_idname, text="Draw")

        row = box.row()
        row.prop(analyze_op, 'import_export_networks_path')

        row = box.row()
        row.operator(MORPHOBLEND_OT_ClearNetworks.bl_idname, text="Clear", icon='X')
        row.operator(MORPHOBLEND_OT_Export3dConnectivity.bl_idname, text="Export", icon='EXPORT')
        row.operator(MORPHOBLEND_OT_Import3dConnectivity.bl_idname, text="Import", icon='IMPORT')


# ------------------------------------------------------------------------
#    Registrer/unregister calls
# ------------------------------------------------------------------------
render_classes = (AnalyzeProperties,
    MORPHOBLEND_OT_NextTimePoint,
    MORPHOBLEND_OT_PreviousTimePoint,
    MORPHOBLEND_OT_AssignRootLayers,
    MORPHOBLEND_OT_ClearRootLayers,
    MORPHOBLEND_OT_PositionRootLayersReference,
    MORPHOBLEND_OT_TrackCells,
    MORPHOBLEND_OT_ColorLineages,
    MORPHOBLEND_OT_ClearLineages,
    MORPHOBLEND_OT_ImportTracking,
    MORPHOBLEND_OT_ExportTracking,
    MORPHOBLEND_OT_3DNeighborhood,
    MORPHOBLEND_OT_ClearNetworks,
    MORPHOBLEND_OT_Draw3dConnectivity,
    MORPHOBLEND_OT_Export3dConnectivity,
    MORPHOBLEND_OT_Import3dConnectivity)

register_classes, unregister_classes = bpy.utils.register_classes_factory(render_classes)


def register_analyze():
    register_classes()
    bpy.types.Scene.analyze_tool = PointerProperty(type=AnalyzeProperties)
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


def unregister_analyze():
    # handle the keymap
    for km, kmi in PT_Analyze_keymaps:
        km.keymap_items.remove(kmi)
    PT_Analyze_keymaps.clear()
    del bpy.types.Scene.analyze_tool
    unregister_classes()
