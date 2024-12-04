import bpy

# Updater ops import, all setup in this file.
from . import addon_updater_ops

# ------------------------------------------------------------------------
#    UI elements
# ------------------------------------------------------------------------
class MORPHOBLEND_PT_Updater(bpy.types.Panel):
		"""Panel to demo popup notice and ignoring functionality"""
		bl_label = "Updates"
		bl_idname = "OBJECT_PT_UpdaterPanel"
		bl_space_type = 'VIEW_3D'
		bl_region_type = 'UI'
		bl_category = "MorphoBlend"
		bl_parent_id = 'VIEW3D_PT_MorphoBlend'

		def draw_header(self, context):
			layout = self.layout
			layout.label(icon='AUTO')

		def draw(self, context):
			layout = self.layout
			# Call to check for update in background.
			# Note: built-in checks ensure it runs at most once, and will run in
			# the background thread, not blocking or hanging blender.
			# Internally also checks to see if auto-check enabled and if the time
			# interval has passed.
			addon_updater_ops.check_for_update_background()

			# Could also use your own custom drawing based on shared variables.
			if addon_updater_ops.updater.update_ready:
				layout.label(text="An update for MorphoBlend is available!", icon="INFO")
			else:
				layout.label(text="You are running the latest version of MorphoBlend ", icon="INFO")

			# Call built-in function with draw code/checks.
			addon_updater_ops.update_notice_box_ui(self, context)

@addon_updater_ops.make_annotations
class MORPHOBLEND_PF_Updater(bpy.types.AddonPreferences):
	"""MorphoBlend  updater preferences"""
	bl_idname = __package__

	# Addon updater preferences.
	auto_check_update = bpy.props.BoolProperty(
		name="Auto-check for Update",
		description="If enabled, auto-check for updates using an interval",
		default=False)

	updater_interval_months = bpy.props.IntProperty(
		name='Months',
		description="Number of months between checking for updates",
		default=0,
		min=0)

	updater_interval_days = bpy.props.IntProperty(
		name='Days',
		description="Number of days between checking for updates",
		default=7,
		min=0,
		max=31)

	updater_interval_hours = bpy.props.IntProperty(
		name='Hours',
		description="Number of hours between checking for updates",
		default=0,
		min=0,
		max=23)

	updater_interval_minutes = bpy.props.IntProperty(
		name='Minutes',
		description="Number of minutes between checking for updates",
		default=0,
		min=0,
		max=59)

	def draw(self, context):
		layout = self.layout

		# Works best if a column, or even just self.layout.
		mainrow = layout.row()
		col = mainrow.column()

		# Updater draw function, could also pass in col as third arg.
		addon_updater_ops.update_settings_ui(self, context, col)

		# Alternate draw function, which is more condensed and can be
		# placed within an existing draw function. Only contains:
		#   1) check for update/update now buttons
		#   2) toggle for auto-check (interval will be equal to what is set above)
		#addon_updater_ops.update_settings_ui_condensed(self, context, col)

		# Adding another column to help show the above condensed ui as one column
		#col = mainrow.column()
		#col.scale_y = 2
		#ops = col.operator("wm.url_open",text="Open webpage ")
		#ops.url=addon_updater_ops.updater.website
