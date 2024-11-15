# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTIBILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

import importlib
import os
import subprocess
import sys

import bpy

from .Alter import MORPHOBLEND_PT_Alter, register_alter, unregister_alter
from .Import import MORPHOBLEND_PT_Import, register_import, unregister_import
from .Process import (MORPHOBLEND_PT_Process, register_process,
                      unregister_process)
from .Quantify import (MORPHOBLEND_PT_Quantify, register_quantify,
                       unregister_quantify)
from .Analyze import MORPHOBLEND_PT_Analyze, register_analyze, unregister_analyze
from .Render import MORPHOBLEND_PT_Render, register_render, unregister_render
from .Export import MORPHOBLEND_PT_Export, register_export, unregister_export

bl_info = {
    'name': 'morphoblend',
    'author': 'Alexis Maizel',
    'description': 'Addon for visualisation, processing and quantification of cell segmentation',
    'blender': (3, 6, 0),
    'version': (0, 6),
    'location': 'View3D',
    'warning': '',
    'category': 'Generic'
}
# This is the main MorphoBlend Module
# Creates the main Panel (MorphoBlend) and registers & attaches the different subpanels Operators


class VIEW3D_PT_MorphoBlend(bpy.types.Panel):
    bl_idname = 'VIEW3D_PT_MorphoBlend'
    bl_label = f"MorphoBlend v{'.'.join(map(str, bl_info.get('version')))}"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'MorphoBlend'

    def draw(self, context):
        layout = self.layout
        scene = context.scene


def install_pip():
    ''' Bootstrap pip and any dependencies into Blender's Python
    On Blender >2.83 pip should be activated by default and this check is useless'''
    try:
        import pip
    except ImportError:
        print("pip python package not found. Installing.")
        try:
            import ensurepip
            ensurepip.bootstrap(upgrade=True, default_pip=True)
            os.environ.pop("PIP_REQ_TRACKER", None)
        except ImportError:
            print("pip cannot be configured or installed. ")


def install_packages(package_names):
    ''' Bootstrap libraries dependencies into Blender's Python '''
    for pkg in package_names:
        try:
            importlib.import_module(pkg)
        except ImportError:
            print(f"Morphoblend - INFO: '{pkg}' python package not found. Installing... ")
            install_package(pkg)


def uninstall_packages(package_names):
    ''' Remove packages from Blender's Python '''
    for pkg in package_names:
        print(f"Morphoblend - INFO: Removing '{pkg}' python package.")
        uninstall_package(pkg)


def get_package_install_directory():
    for path in sys.path:
        if os.path.basename(path) in ("dist-packages", "site-packages"):
            return path


def install_package(name):
    pybin = sys.executable
    target = get_package_install_directory()
    subprocess.run([pybin, '-m', 'pip', 'install', name, '--target', target])


def uninstall_package(name):
    pybin = sys.executable
    subprocess.run([pybin, '-m', 'pip', 'uninstall', name, '-y'])


# List of third party packages that need to be installed
install_packages_list = ['anytree', 'networkx']

# List of third party packages that need to be UNinstalled
uninstall_packages_list = ['treelib']


morphoblend_classes = (VIEW3D_PT_MorphoBlend,
        MORPHOBLEND_PT_Import,
        MORPHOBLEND_PT_Process,
        MORPHOBLEND_PT_Alter,
        MORPHOBLEND_PT_Analyze,
        MORPHOBLEND_PT_Quantify,
        MORPHOBLEND_PT_Render,
        MORPHOBLEND_PT_Export,
        )

register_init, unregister_init = bpy.utils.register_classes_factory(morphoblend_classes)


def register():
    # uninstall_packages(uninstall_packages_list)
    install_packages(install_packages_list)
    register_init()
    register_import()
    register_process()
    register_alter()
    register_analyze()
    register_quantify()
    register_render()
    register_export()


def unregister():
    unregister_export()
    unregister_render()
    unregister_quantify()
    unregister_analyze()
    unregister_alter()
    unregister_process()
    unregister_import()
    unregister_init()
