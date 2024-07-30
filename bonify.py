import bpy
from mathutils import Vector

def go_to_pose_mode(context, armature):
    context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode='POSE')

def safe_string(s):
    try:
        return s.encode('utf-8').decode('utf-8')
    except UnicodeDecodeError as e:
        # Log the error and the problematic string
        print(f"Encoding error: {e}, in string: {repr(s)}")
        # Replace invalid characters with a safe character
        return ''.join([c if ord(c) < 128 else '?' for c in s])

def get_bone_parenting_chain(bone):
    chain = []
    while bone:
        chain.append(bone.name)
        bone = bone.parent
    return " -> ".join(reversed(chain))

def safe_report(operator, level, message):
    try:
        operator.report(level, safe_string(message))
    except UnicodeDecodeError as e:
        print(f"Encoding error in report message: {e}, message: {repr(message)}")
        operator.report({'ERROR'}, f"Encoding error in report message: {str(e)}")

class OBJECT_OT_add_bone(bpy.types.Operator):
    bl_idname = "object.add_bone"
    bl_label = "Add Bone"
    bl_description = "Add a bone at the selected object's origin and set up weights"

    weight_method: bpy.props.EnumProperty(
        name="Weight Method",
        description="Choose the method for weight assignment",
        items=[
            ('ENVELOPE', "Envelope Weights", "Assign weights using envelope method"),
            ('AUTO', "Automatic Weights", "Assign weights automatically")
        ],
        default='AUTO'
    )

    def get_closest_bone_on_axes(self, context, armature, location_local, ignore_bone_name=None):
        closest_bone = None
        closest_distance = float('inf')

        safe_report(self, {'INFO'}, f"Searching for closest bone to location: {location_local}")
        safe_report(self, {'INFO'}, f"Selected axes: {context.scene.selected_axes}")

        # Create a direction vector based on selected axes
        direction = Vector((
            1 if 'X' in context.scene.selected_axes else (-1 if '-X' in context.scene.selected_axes else 0),
            1 if 'Y' in context.scene.selected_axes else (-1 if '-Y' in context.scene.selected_axes else 0),
            1 if 'Z' in context.scene.selected_axes else (-1 if '-Z' in context.scene.selected_axes else 0)
        ))

        if direction.length == 0:
            safe_report(self, {'WARNING'}, "No axes selected for search direction")
            return None

        direction.normalize()

        for bone in armature.data.edit_bones:
            if bone.name == ignore_bone_name:
                continue  # Skip the bone we want to ignore

            # Calculate the midpoint of the bone
            bone_midpoint = (bone.head + bone.tail) / 2

            # Calculate the vector from the location to the bone midpoint
            to_bone = bone_midpoint - location_local

            # Project the vector onto our search direction
            projection_length = to_bone.dot(direction)

            # Check if the projection is in the positive direction of our search
            if projection_length > 0:
                # Calculate the distance from the location to the projection point
                projection_point = location_local + direction * projection_length
                distance = (projection_point - bone_midpoint).length

                safe_report(self, {'INFO'}, f"Bone: {safe_string(bone.name)}, Distance: {distance}")

                if distance < closest_distance:
                    closest_distance = distance
                    closest_bone = bone

        if closest_bone:
            safe_report(self, {'INFO'}, f"Closest bone found: {safe_string(closest_bone.name)}")
        else:
            safe_report(self, {'WARNING'}, "No closest bone found")

        return closest_bone

    def execute(self, context):
        try:
            obj = context.object
            armature = context.scene.selected_armature
            go_to_pose_mode_flag = context.scene.go_to_pose_mode

            if obj and armature and obj != armature:
                if obj.name not in context.scene.objects:
                    safe_report(self, {'WARNING'}, "Selected object is no longer valid.")
                    return {'CANCELLED'}

                original_active = context.view_layer.objects.active
                original_selected = context.selected_objects.copy()
                original_mode = context.mode

                try:
                    safe_report(self, {'INFO'}, "Setting origin to geometry")
                    # Set origin to geometry
                    bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')

                    # Get the location of the object (geometry origin)
                    location_world = obj.matrix_world.translation
                    safe_report(self, {'INFO'}, f"Object location in world space: {location_world}")

                    context.view_layer.objects.active = armature

                    if armature.name not in context.scene.objects:
                        safe_report(self, {'WARNING'}, "Selected armature is no longer valid.")
                        return {'CANCELLED'}

                    # Convert the location to the armature's local space
                    location_local = armature.matrix_world.inverted() @ location_world
                    safe_report(self, {'INFO'}, f"Object location in local space: {location_local}")

                    # Enter edit mode on the armature
                    bpy.ops.object.mode_set(mode='EDIT')
                    
                    # Add a new bone at the object's location
                    new_bone_name = safe_string(obj.name)
                    safe_report(self, {'INFO'}, f"Creating new bone with name: {new_bone_name}")
                    new_bone = armature.data.edit_bones.new(new_bone_name)
                    new_bone.head = location_local

                    # Calculate bone size based on object dimensions
                    obj_size = max(obj.dimensions)
                    bone_length = max(obj_size * 0.5, 0.5)  # At least 0.5 units long

                    # Set bone tail to create a larger bone
                    new_bone.tail = location_local + Vector((0, 0, bone_length))

                    # Set envelope properties for the new bone
                    new_bone.envelope_distance = bone_length * 0.5
                    new_bone.envelope_weight = 1.0

                    if context.scene.selected_parent_bone:
                        parent_bone_name = safe_string(context.scene.selected_parent_bone)
                        safe_report(self, {'INFO'}, f"Finding parent bone: {parent_bone_name}")
                        parent_bone = armature.data.edit_bones.get(parent_bone_name)
                        if not parent_bone:
                            safe_report(self, {'WARNING'}, f"Selected parent bone '{parent_bone_name}' not found.")
                            bpy.ops.object.mode_set(mode='OBJECT')
                            return {'CANCELLED'}
                    else:
                        # Find the closest bone to parent the new bone to
                        parent_bone = self.get_closest_bone_on_axes(context, armature, location_local, ignore_bone_name=new_bone_name)
                        if not parent_bone:
                            safe_report(self, {'WARNING'}, "No suitable parent bone found.")
                            bpy.ops.object.mode_set(mode='OBJECT')
                            return {'CANCELLED'}
                    # Parent the new bone to the selected parent bone
                    new_bone.parent = parent_bone

                    safe_report(self, {'INFO'}, f"New bone added: {new_bone_name}")

                    # Exit edit mode
                    bpy.ops.object.mode_set(mode='OBJECT')

                    # Add armature modifier if it doesn't exist
                    found_existing_armature = False
                    for modifier in obj.modifiers:
                        modifier_name = safe_string(modifier.name)
                        safe_report(self, {'INFO'}, f"Existing modifier: {modifier_name}")
                        if modifier_name == "Armature":
                            found_existing_armature = True
                            if modifier.object != armature:
                                safe_report(self, {'WARNING'}, f"Existing armature modifier is linked to a different armature: {safe_string(modifier.object.name)}")
                            else:
                                safe_report(self, {'INFO'}, f"Using existing armature modifier linked to: {safe_string(modifier.object.name)}")
                            break

                    if not found_existing_armature:
                        safe_report(self, {'INFO'}, "Adding new armature modifier")
                        armature_modifier = obj.modifiers.new(name="Armature", type='ARMATURE')
                        armature_modifier.object = armature

                    safe_report(self, {'INFO'}, "aaaaa")
                    # Ensure the selected part is assigned to the new bone
                    vertex_group_name = safe_string(new_bone_name)
                    safe_report(self, {'INFO'}, "bbbbb")
                    safe_report(self, {'INFO'}, f"Vertex group name: {vertex_group_name}")

                    if obj.vertex_groups.get(vertex_group_name) is None:
                        safe_report(self, {'INFO'}, "Creating new vertex group")
                        vertex_group = obj.vertex_groups.new(name=vertex_group_name)
                    else:
                        safe_report(self, {'INFO'}, "Using existing vertex group")
                        vertex_group = obj.vertex_groups.get(vertex_group_name)

                    context.view_layer.objects.active = obj
                    bpy.ops.object.mode_set(mode='EDIT')
                    bpy.ops.mesh.select_all(action='SELECT')
                    obj.vertex_groups.active = vertex_group
                    bpy.ops.object.vertex_group_assign()
                    bpy.ops.mesh.select_all(action='DESELECT')
                    bpy.ops.object.mode_set(mode='OBJECT')

                    # Parent the object to the armature with the selected weight method
                    context.view_layer.objects.active = obj
                    armature.select_set(False)
                    obj.select_set(True)

                    if self.weight_method == 'ENVELOPE':
                        bpy.ops.object.parent_set(type='ARMATURE_ENVELOPE')
                    elif self.weight_method == 'AUTO':
                        bpy.ops.object.parent_set(type='ARMATURE_AUTO')

                    # Ensure the new bone is influencing the object
                    bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
                    bpy.ops.object.mode_set(mode='OBJECT')

                    # Optionally go to pose mode
                    if go_to_pose_mode_flag:
                        go_to_pose_mode(context, armature)
                    else:
                        # Restore original active object and selection
                        context.view_layer.objects.active = original_active
                        bpy.ops.object.select_all(action='DESELECT')
                        for ob in original_selected:
                            ob.select_set(True)

                        # Restore original mode
                        if original_mode != 'OBJECT':
                            bpy.ops.object.mode_set(mode=original_mode)

                    safe_report(self, {'INFO'}, f"Bone added, parented, and weights assigned using {self.weight_method} method.")
                    return {'FINISHED'}

                except UnicodeDecodeError as e:
                    safe_report(self, {'ERROR'}, f"Encoding error: {str(e)}")
                    return {'CANCELLED'}
                except Exception as e:
                    safe_report(self, {'ERROR'}, f"An error occurred: {str(e)}")
                    return {'CANCELLED'}

            else:
                safe_report(self, {'WARNING'}, "No object or armature selected, or object is the same as armature.")
                return {'CANCELLED'}

        except UnicodeDecodeError as e:
            safe_report(self, {'ERROR'}, f"Encoding error: {str(e)}")
            return {'CANCELLED'}

class OBJECT_OT_select_parent_bone(bpy.types.Operator):
    bl_idname = "object.select_parent_bone"
    bl_label = "Select Parent Bone"
    bl_description = "Manually select the parent bone for the new bone"

    def execute(self, context):
        armature = context.scene.selected_armature
        if armature and armature.type == 'ARMATURE':
            if context.mode != 'EDIT_ARMATURE':
                bpy.ops.object.mode_set(mode='EDIT')
            active_bone = armature.data.edit_bones.active
            if active_bone:
                context.scene.selected_parent_bone = safe_string(active_bone.name)
                # Clear axes selection
                context.scene.selected_axes = set()
                safe_report(self, {'INFO'}, f"Selected parent bone: {safe_string(active_bone.name)}")
            else:
                safe_report(self, {'WARNING'}, "No active bone selected")
            if context.mode != 'OBJECT':
                bpy.ops.object.mode_set(mode='OBJECT')
        else:
            safe_report(self, {'WARNING'}, "No armature selected or invalid armature")
        return {'FINISHED'}

class OBJECT_OT_clear_selected_parent_bone(bpy.types.Operator):
    bl_idname = "object.clear_selected_parent_bone"
    bl_label = "Clear Parent Bone"
    bl_description = "Clear the manually selected parent bone"

    def execute(self, context):
        context.scene.selected_parent_bone = ""
        safe_report(self, {'INFO'}, "Cleared selected parent bone")
        return {'FINISHED'}

class OBJECT_OT_select_armature(bpy.types.Operator):
    bl_idname = "object.select_armature"
    bl_label = "Select Armature"
    bl_description = "Select an armature for adding bones"

    armature_name: bpy.props.StringProperty()

    def execute(self, context):
        armature = bpy.data.objects.get(self.armature_name)
        if armature and armature.type == 'ARMATURE':
            context.scene.selected_armature = armature
            safe_report(self, {'INFO'}, f"Selected armature: {safe_string(armature.name)}")
        else:
            safe_report(self, {'WARNING'}, "Armature not found or invalid")
        return {'FINISHED'}

class VIEW3D_PT_custom_panel(bpy.types.Panel):
    bl_label = "Custom Tools"
    bl_idname = "VIEW3D_PT_custom_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Tool'

    def draw(self, context):
        layout = self.layout
        layout.label(text="Select Armature:")
        for armature in bpy.data.objects:
            if armature.type == 'ARMATURE':
                layout.operator("object.select_armature", text=armature.name).armature_name = armature.name

        layout.label(text="Parent Bone:")
        row = layout.row(align=True)
        row.operator("object.select_parent_bone", text="Select Parent Bone")
        row.operator("object.clear_selected_parent_bone", text="", icon='X')

        if context.scene.selected_parent_bone:
            layout.label(text=f"Selected: {context.scene.selected_parent_bone}")
        else:
            layout.prop(context.scene, "selected_axes", text="Axes for Closest Bone")

        layout.prop(context.scene, "go_to_pose_mode", text="Go to Pose Mode After Adding Bone")

        layout.operator("object.add_bone", text="Add Bone with Envelope Weights", icon='BONE_DATA').weight_method = 'ENVELOPE'
        layout.operator("object.add_bone", text="Add Bone with Automatic Weights", icon='BONE_DATA').weight_method = 'AUTO'

        layout.label(text="Weight Painted Bones:")
        obj = context.object
        if obj and obj.type == 'MESH' and obj.vertex_groups:
            for vgroup in obj.vertex_groups:
                bone_name = vgroup.name
                if context.scene.selected_armature and bone_name in context.scene.selected_armature.data.bones:
                    bone = context.scene.selected_armature.data.bones[bone_name]
                    try:
                        layout.label(text=f"{safe_string(bone_name)}: {get_bone_parenting_chain(bone)}")
                    except UnicodeDecodeError as e:
                        print(f"Encoding error: {e}, in bone name: {repr(bone_name)}")
                        layout.label(text="Invalid character in bone name")
        else:
            layout.label(text="No weight painted bones found")

def register():
    bpy.utils.register_class(OBJECT_OT_add_bone)
    bpy.utils.register_class(OBJECT_OT_select_armature)
    bpy.utils.register_class(OBJECT_OT_select_parent_bone)
    bpy.utils.register_class(OBJECT_OT_clear_selected_parent_bone)
    bpy.utils.register_class(VIEW3D_PT_custom_panel)
    bpy.types.Scene.selected_armature = bpy.props.PointerProperty(type=bpy.types.Object)
    bpy.types.Scene.selected_axes = bpy.props.EnumProperty(
        name="Axes",
        description="Axes to find the closest bone",
        items=[
            ('X', "X Axis", "Find the closest bone on the X axis"),
            ('-X', "-X Axis", "Find the closest bone on the negative X axis"),
            ('Y', "Y Axis", "Find the closest bone on the Y axis"),
            ('-Y', "-Y Axis", "Find the closest bone on the negative Y axis"),
            ('Z', "Z Axis", "Find the closest bone on the Z axis"),
            ('-Z', "-Z Axis", "Find the closest bone on the negative Z axis")
        ],
        options={'ENUM_FLAG'},
        default={'Z'}
    )
    bpy.types.Scene.go_to_pose_mode = bpy.props.BoolProperty(
        name="Go to Pose Mode",
        description="Toggle to go to Pose Mode after adding the bone",
        default=False
    )
    bpy.types.Scene.selected_parent_bone = bpy.props.StringProperty(
        name="Selected Parent Bone",
        description="Name of the manually selected parent bone"
    )

def unregister():
    bpy.utils.unregister_class(OBJECT_OT_add_bone)
    bpy.utils.unregister_class(OBJECT_OT_select_armature)
    bpy.utils.unregister_class(OBJECT_OT_select_parent_bone)
    bpy.utils.unregister_class(OBJECT_OT_clear_selected_parent_bone)
    bpy.utils.unregister_class(VIEW3D_PT_custom_panel)
    del bpy.types.Scene.selected_armature
    del bpy.types.Scene.selected_axes
    del bpy.types.Scene.go_to_pose_mode
    del bpy.types.Scene.selected_parent_bone

if __name__ == "__main__":
    register()
