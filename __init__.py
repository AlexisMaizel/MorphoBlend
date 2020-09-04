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

bl_info = {
    "name" : "MorphoBlend",
    "author" : "Alexis Maizel",
    "description" : "Addon for visualisation, processing and quantification of cell segmentation",
    "blender" : (2, 83, 5),
    "version" : (0, 3, 5),
    "location" : "View3D",
    "warning" : "",
    "category" : "Generic"
}
# This is the main MorphoBlend Module
# Creates the main Panel (MorphoBlend) and registers & attaches the different subpanels
# Operators

import bpy
from . Import  import (MORPHOBLEND_PT_Import, register_import, unregister_import)
from . Process import (MORPHOBLEND_PT_Process, register_process, unregister_process)
from . Quantify import (MORPHOBLEND_PT_Quantify, register_quantify, unregister_quantify)
from . Edit import (MORPHOBLEND_PT_Edit, register_edit, unregister_edit)



class VIEW3D_PT_MorphoBlend(bpy.types.Panel):
    bl_idname = "VIEW3D_PT_MorphoBlend"
    bl_label = "MorphoBlend v" + '.'.join(map(str, bl_info.get('version')))
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "MorphoBlend"

    def draw(self, context):
        layout = self.layout
        scene = context.scene


classes = (VIEW3D_PT_MorphoBlend,
            MORPHOBLEND_PT_Import,
            MORPHOBLEND_PT_Process,
            MORPHOBLEND_PT_Edit,
            MORPHOBLEND_PT_Quantify,
            )

register_classes, unregister_classes = bpy.utils.register_classes_factory(classes)


def register():
    register_classes()
    register_import()
    register_process()
    register_edit()
    register_quantify()



def unregister():
    unregister_quantify()
    unregister_edit()
    unregister_process()
    unregister_import()
    unregister_classes()
