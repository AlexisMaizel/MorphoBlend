import re

import bpy
from bpy.props import (BoolProperty, BoolVectorProperty,
                       FloatProperty, FloatVectorProperty, PointerProperty, StringProperty)
from bpy_extras.view3d_utils import region_2d_to_location_3d
from .Utilities import (assign_material, col_hierarchy,
                        create_materials_palette, distance2D, get_collection,
                        get_parent, move_obj_to_coll,
                        retrieve_global_coordinates)


# ------------------------------------------------------------------------
#    Keymaps
# ------------------------------------------------------------------------
PT_Edit_keymaps = []

# ------------------------------------------------------------------------
#    Global variable
# ------------------------------------------------------------------------
# Matches time point (t1, T42, t09, etc...)
g_tp_pattern = '[tT]\d{1,}'
# The possible root layers
g_root_layers_names = ('Epidermis', 'Cortex', 'Endodermis', 'Stele')


# ------------------------------------------------------------------------
#    Properties
# ------------------------------------------------------------------------
class RenderProperties(bpy.types.PropertyGroup):
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
    pattern: StringProperty(
        name='Search pattern',
        description='Pattern to be searched',
        default="",
        subtype='NONE'
    )
    makeInvis: BoolProperty(
        name='Make collection visible',
        description='Make collection visible',
        default=False
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
        # Get all TP collections at the topmost level
        all_tp_cols = get_top_level_tp_collections(g_tp_pattern)
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
        # Get all TP collections at the topmost level
        all_tp_cols = get_top_level_tp_collections(g_tp_pattern)
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
        scene = context.scene
        render_op = scene.render_tool
        if render_op.bool_at_all:
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
        scene = context.scene
        render_op = scene.render_tool
        _apply_to_all = render_op.bool_at_all
        # Definition of the radial plane
        rad_plane = render_op.plane_at_ref
        # Retrieve coordinates of the reference,  remove the scaling
        ref_pos = render_op.pos_at_ref / bpy.context.scene.unit_settings.scale_length
        # Thresholds for different layers
        layers_thresholds = (render_op.dist_t0_at, render_op.dist_t1_at, render_op.dist_t2_at)
        if _apply_to_all:
            # Parse all objects of the scene
            for obj in bpy.context.scene.objects:
                if obj.type == 'MESH':
                    layer = self.assign_layer(ref_pos, retrieve_global_coordinates(obj), rad_plane, layers_thresholds)
                    col_obj = get_collection(obj)
                    if re.search(rf'{g_root_layers_names[0]}|{g_root_layers_names[1]}|{g_root_layers_names[2]}|{g_root_layers_names[3]}', col_obj.name):
                        # Check if the object already in a 'layer' collection?
                        move_obj_to_coll(obj, None)
                    else:
                        move_obj_to_coll(obj, layer)
                    if render_op.bool_at_color_cells:
                        self.assign_color_layer(obj, layer)
        else:
            # Parse selection
            for obj in bpy.context.selected_objects:
                if obj.type == 'MESH':
                    # get the world coordinates of the object, with scaling
                    layer = self.assign_layer(ref_pos, retrieve_global_coordinates(obj), rad_plane, layers_thresholds)
                    col_obj = get_collection(obj)
                    if re.search(rf'{g_root_layers_names[0]}|{g_root_layers_names[1]}|{g_root_layers_names[2]}|{g_root_layers_names[3]}', col_obj.name):
                        # Check if the object already in a 'layer' collection?
                        move_obj_to_coll(obj, None)
                    else:
                        move_obj_to_coll(obj, layer)
                    if render_op.bool_at_color_cells:
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

    def execute(self, context):
        max_levels = 9                          # Max Levels to parse
        scn_col = bpy.context.scene.collection  # Root collection
        scene = context.scene
        render_op = scene.render_tool
        _apply_to_all = render_op.bool_at_all
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
                            if render_op.bool_at_color_cells:
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
                        if render_op.bool_at_color_cells:
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
        scene = context.scene
        render_op = scene.render_tool
        context.area.tag_redraw()
        if event.type == 'MOUSEMOVE':
            x, y = event.mouse_region_x, event.mouse_region_y
            # Moves empty with mouse
            loc = region_2d_to_location_3d(context.region, context.space_data.region_3d, (x, y), (0, 0, 0))
            bpy.data.objects[self.name_ref_empty].location = loc
            self.ref_loc = loc

        elif event.type == 'LEFTMOUSE':
            # copy coordinates of the references from the position of the empty
            render_op.pos_at_ref = self.ref_loc * bpy.context.scene.unit_settings.scale_length
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
        scene = context.scene
        render_op = scene.render_tool
        if context.area.type == 'VIEW_3D':
            self.ref_loc = []
            # set the viewport to display the radial plane
            plane_def = (render_op.plane_at_ref[0], render_op.plane_at_ref[1], render_op.plane_at_ref[2])
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


class MORPHOBLEND_OT_ChangeVisibilityCollection(bpy.types.Operator):
    '''Set visibility of collections based on name pattern matching.'''
    bl_idname = 'morphoblend.toggle_visibility_collections'
    bl_label = 'Set'
    bl_descripton = 'Set visibility of collections based on name pattern matching.'

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        scene = context.scene
        render_op = scene.render_tool
        _pattern = render_op.pattern
        _makeinvis = render_op.makeInvis

        # Retrieve hiearchy of all collection and their parents
        cols_tree = col_hierarchy(bpy.context.scene.collection, levels=9)
        all_cols = {i: k for k, v in cols_tree.items() for i in v}

        # Parse all collections and process the ones matching the pattern
        n_coll = 0
        for col in all_cols:
            if re.search(_pattern, col.name):
                n_coll += 1
                col.hide_viewport = _makeinvis
        if n_coll > 0:
            info_mess = f"{str(n_coll)} collections matched!"
        else:
            info_mess = 'No match'
        self.report({'INFO'}, info_mess)
        return {'FINISHED'}


# ------------------------------------------------------------------------
#    Operator modules
# ------------------------------------------------------------------------
def get_top_level_tp_collections(in_tp_pattern):
    ''' Returns a list of all collections which name matches the time point pattern'''
    # The regex identifying TP
    pattern = re.compile(in_tp_pattern)
    # list of all collections at 1st level
    scn_col = bpy.context.scene.collection  # Root collection
    root_cols = col_hierarchy(scn_col, levels=1)
    all_tp_cols = [k for k in root_cols.values()][0]
    # Only keep collections that are time points
    for col in all_tp_cols:
        if not pattern.match(col.name):
            all_tp_cols.remove(col)
    return all_tp_cols


def show_active_tp(context):
    '''Get the last active time point collection and make it the only one visible in viewport'''
    all_tp_cols = get_top_level_tp_collections(g_tp_pattern)
    current_col = context.collection
    if re.match(g_tp_pattern, current_col.name):
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


# ------------------------------------------------------------------------
#    UI elements
# ------------------------------------------------------------------------
class MORPHOBLEND_PT_Render(bpy.types.Panel):
    bl_idname = 'MORPHOBLEND_PT_Render'
    bl_label = 'Render'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'MorphoBlend'
    bl_parent_id = 'VIEW3D_PT_MorphoBlend'

    def draw_header(self, context):
        layout = self.layout
        layout.label(icon='VIEW_PERSPECTIVE')

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        render_op = scene.render_tool

        box = layout.box()
        row = box.row()
        if len(bpy.context.selected_objects) > 1:
            text_box = f"Assign root layers [{str(len(bpy.context.selected_objects))} selected cells]"
        else:
            text_box = f"Assign root layers [{str(len(bpy.context.selected_objects))} selected cell]"
        row.label(text=text_box, icon='HAIR')

        row = box.row()
        row.label(text='Radial plane defined by:')
        row.prop(render_op, 'plane_at_ref')

        row = box.row()
        row.label(text='Center of root (µm):')
        row.prop(render_op, 'pos_at_ref')
        row.operator(MORPHOBLEND_OT_PositionRootLayersReference.bl_idname, text='Interactive')

        row = box.row()
        row.label(text=f"Threshold for {g_root_layers_names[0]} (µm):")
        row.prop(render_op, 'dist_t0_at')

        row = box.row()
        row.label(text=f"Threshold for {g_root_layers_names[1]} (µm):")
        row.prop(render_op, 'dist_t1_at')

        row = box.row()
        row.label(text=f"Threshold for {g_root_layers_names[2]} (µm):")
        row.prop(render_op, 'dist_t2_at')

        row = box.row()
        row.prop(render_op, 'bool_at_all')
        row.prop(render_op, 'bool_at_color_cells')
        row.operator(MORPHOBLEND_OT_AssignRootLayers.bl_idname, text='Assign layers')
        row.operator(MORPHOBLEND_OT_ClearRootLayers.bl_idname, text='Clear layers')

        box = layout.box()
        row = box.row()

        row.label(text="Show/hide collections", icon='RESTRICT_VIEW_ON')

        row = box.row()
        row.prop(render_op, "pattern")
        row.prop(render_op, "makeInvis", text="Hide")
        row.operator(MORPHOBLEND_OT_ChangeVisibilityCollection.bl_idname, text="Set")


# ------------------------------------------------------------------------
#    Registrer/unregister calls
# ------------------------------------------------------------------------
render_classes = (RenderProperties,
    MORPHOBLEND_OT_NextTimePoint,
    MORPHOBLEND_OT_PreviousTimePoint,
    MORPHOBLEND_OT_AssignRootLayers,
    MORPHOBLEND_OT_ClearRootLayers,
    MORPHOBLEND_OT_PositionRootLayersReference,
    MORPHOBLEND_OT_ChangeVisibilityCollection,)

register_classes, unregister_classes = bpy.utils.register_classes_factory(render_classes)


def register_render():
    register_classes()
    bpy.types.Scene.render_tool = PointerProperty(type=RenderProperties)
    # Define  keymaps
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    # MORPHOBLEND_OT_NextTimePoint --> Ctrl + Shift + down_arrow
    km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')
    kmi = km.keymap_items.new(MORPHOBLEND_OT_NextTimePoint.bl_idname, type='DOWN_ARROW', value='PRESS', ctrl=True, shift=True)
    PT_Edit_keymaps.append((km, kmi))

    # MORPHOBLEND_OT_PreviousTimePoint --> Ctrl + Shift + up_arrow
    km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')
    kmi = km.keymap_items.new(MORPHOBLEND_OT_PreviousTimePoint.bl_idname, type='UP_ARROW', value='PRESS', ctrl=True, shift=True)
    PT_Edit_keymaps.append((km, kmi))


def unregister_render():
    # handle the keymap
    for km, kmi in PT_Edit_keymaps:
        km.keymap_items.remove(kmi)
    PT_Edit_keymaps.clear()
    del bpy.types.Scene.render_tool
    unregister_classes()
