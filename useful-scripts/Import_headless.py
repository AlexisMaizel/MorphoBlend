import argparse
import logging
import re
import os
from math import radians
from pathlib import Path
from random import randrange

#import bmesh
import bpy
#import numpy as np
#from mathutils import Matrix, Vector

from morphoblend.Utilities import number_of_file_to_import
from morphoblend.Import import (initialise, import_process_assign)

g_import_coll_name = 'Imported' #TODO  Is this still needed?
g_allowed_extension = ('.obj', '.OBJ', '.ply', '.PLY')
g_output_basename = 'Output'


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
    # Get the scripts arguments
    args = args_parser()
    # Configure logging
    log_path = Path(bpy.path.abspath(args.path), g_output_basename).with_suffix('.log')
    logging.basicConfig(level=logging.INFO, filename=log_path, filemode='w', format='%(asctime)s - %(message)s')
    # Remove everything from the project and initialise scene
    cleanup()
    initialise('Qual_bright', args.voxel, args.rotation)
    process_input(args.path)
    # Save the file
    outfile_path = Path(bpy.path.abspath(args.path), g_output_basename).with_suffix('.blend')
    bpy.ops.wm.save_as_mainfile(filepath=outfile_path.as_posix())
    logging.info('Finished!')

def process_input(folder_path):
     # Get total number of files to process
    total_n_files_to_import = number_of_file_to_import(bpy.path.abspath(folder_path), g_allowed_extension)
    progress = 0
    # Initialise logging
    logging.info('Starting. Will import a total of %s files', total_n_files_to_import)
    # Convert folder_path to a Path object
    folder_path = Path(folder_path)
    # Set to store processed subfolders
    processed_subfolders = set()
    # Traverse through the folder and its subfolders
    for file_path in sorted(folder_path.glob('**/*')):
        # Check if the file extension is in the specified list of extensions
        folder_name = file_path.parent.name
        if file_path.suffix.upper() in g_allowed_extension:
            # Check if the parent folder name is already present in collection
            if folder_name not in bpy.data.collections:
                coll = bpy.data.collections.new(name=folder_name)
                bpy.context.scene.collection.children.link(coll)
            else:
                coll = bpy.data.collections[folder_name]
            import_process_assign(inFilePath=file_path.as_posix(), inColl=coll)
            # Add the parent folder to the set of processed subfolders if it hasn't been added yet (process new folder)
            if folder_name not in processed_subfolders:
                #Retrieve number of files to process in that subfolder
                local_n_files_to_import = number_of_file_to_import(bpy.path.abspath(file_path.parent.as_posix()), g_allowed_extension,  include_subfolders=False)
                progress = progress + local_n_files_to_import
                logging.info(f"Processing subfolder: {folder_name} - {local_n_files_to_import} files - Progress: {round(100*progress/total_n_files_to_import)}%")
                processed_subfolders.add(folder_name)



def cleanup():
    for c in bpy.context.scene.collection.children:
        if c.name != g_import_coll_name:
            coll = bpy.data.collections.get(c.name)
            if coll:
                obs = [o for o in coll.objects if o.users == 1]
                while obs:
                    bpy.data.objects.remove(obs.pop())
                bpy.data.collections.remove(coll)


def merge_data(list_files):
    j = 0
    for f in list_files:
        logging.info('Merging data from %s', f)
        with bpy.data.libraries.load(f) as (data_from, data_to):
            data_to.collections = [c for c in data_from.collections if c != g_import_coll_name]
        # link collection to scene collection
        for coll in data_to.collections:
            if coll is not None:
                bpy.context.scene.collection.children.link(coll)
        k = 0
        for ob in bpy.data.objects:
            if ob.type == 'MESH':
                k += 1
        i = k - j
        j = k
        logging.info('Added %s objects', i)
        os.remove(f)
        logging.info('Erased %s', f)


if __name__ == '__main__':
    main()
