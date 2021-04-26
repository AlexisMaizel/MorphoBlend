import argparse
import logging
import re
from pathlib import Path
import json
from itertools import combinations


import bmesh
import bpy
import networkx as nx
from mathutils.bvhtree import BVHTree
from networkx.readwrite import json_graph


def args_parser():
    parser = argparse.ArgumentParser()
    # get all script args
    _, all_arguments = parser.parse_known_args()
    double_dash_index = all_arguments.index('--')
    script_args = all_arguments[double_dash_index + 1:]
    # Mandatory arguments
    parser.add_argument('--path', type=str, help='Path to the Blender file to process', required=True)
    parser.add_argument('--timepoints', nargs='+', type=int, help='list of time points to process. Example 00 15 62', required=False, default=None)
    parsed_script_args, _ = parser.parse_known_args(script_args)

    return parsed_script_args


def main():
    # Get the scripts arguments
    args = args_parser()
    # Configure logging
    base_dir = Path(bpy.path.abspath(args.path)).parent
    fname = Path(bpy.path.abspath(args.path)).stem
    log_path = Path(base_dir, 'RAG_'+fname).with_suffix('.log')
    logging.basicConfig(level=logging.INFO, filename=log_path, filemode='w', format='%(asctime)s - %(message)s')

    # Open  Blender file to process
    bpy.ops.wm.open_mainfile(filepath=args.path)
    logging.info('Open file %s', args.path)

    # Retrieve list of time points to process
    if args.timepoints is not None:
        all_tp_cols = collections_from_pattern('[Tt]\d{1,}') # Get all TP collections
        tp_list = list(args.timepoints) # Tp to process
        # only keep these ones
        tp_cols = [tp for tp in all_tp_cols if tp_from_col_name(tp.name) in tp_list]  # Python
    else:
        tp_cols = collections_from_pattern('[Tt]\d{1,}')  # Get all TP collections
    logging.info('To process: %s time points',  len(tp_cols))

    #Main Loop
    for tp in tp_cols:
        tp_G = nx.Graph()
        # Get all unique pairs of two objects and check if they are touching
        logging.info(f"Extracting 3D connectivity for {tp.name}: processing {len(list(combinations(tp.all_objects, 2)))} pairs...")
        for objpair in combinations(tp.all_objects, 2):
            area_intersection = intersection_area(objpair[0], objpair[1])
            if area_intersection != 0:
                # Add the pair of objects (referenced by name) as a weighted edge to the graph
                add_edge(tp_G, objpair, area_intersection)
        # add the Graph to the dict
        logging.info(f"Done!  {tp_G.number_of_nodes()} nodes and {tp_G.number_of_edges()} edges in {len(list(nx.connected_components(tp_G)))} RAG(s)")
        data = json_graph.node_link_data(tp_G)
        outfile_path = Path(base_dir, fname +"_" +tp.name).with_suffix('.json')
        with open(outfile_path, 'w', encoding='utf-8') as f:
            json.dump(data, f)
    logging.info('Finished!')


def tp_from_col_name(colname):
    re_match = re.search(r'[Tt](\d{1,})' , colname)
    if re_match:
        return int(re_match.group(1))


def add_edge(tp_G, objpair, area_intersection):
    # Add the pair of objects (referenced by name) as a weighted edge to the graph
    tp_G.add_edge(objpair[0].name, objpair[1].name, area=area_intersection)
    # Add to the nodes the collection/tissue of the cell
    tp_G.nodes[objpair[0].name]['collection'] = get_collection(objpair[0]).name
    tp_G.nodes[objpair[1].name]['collection'] = get_collection(objpair[1]).name


def get_number_of_pairs(inSet):
    total = 0
    try:
        for e in inSet:
            total += len(list(combinations(e.all_objects, 2)))
    except TypeError as te:
        total =  len(list(combinations(inSet.all_objects, 2)))
    return total


def intersection_area(obj1, obj2):
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
        return (area_faces(bm1, obj1_faces_idx) + area_faces(bm2, obj2_faces_idx)) / 2
    else:
        return 0


def area_faces(bm, idx_faces):
    ''' Return the scaled area of the a set of faces defined by their  indices'''
    bm.faces.ensure_lookup_table()
    area = sum(bm.faces[idx].calc_area() for idx in idx_faces)
    scaled_area = area * bpy.context.scene.unit_settings.scale_length ** 2
    return scaled_area


def store_3dConnectivity(connectivity):
    if connectivity is not None:
        for tp, G in connectivity.items():
            data = json_graph.node_link_data(G)
            item = bpy.context.scene.g_networks.add()
            item.key = tp
            item.value = json.dumps(data)


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


def get_collection(obj):
    '''Return the 1st collection containing the object'''
    # TODO  Make this more versatile to return all collections containing the object (?)
    collections = obj.users_collection
    if len(collections) > 0:
        return collections[0]
    return bpy.context.scene.collection

if __name__ == '__main__':
    main()
