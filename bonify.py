import bpy
import mathutils
from mathutils import Vector
import time
def calculate_bone_midpoint(bone):
    """Calculate the midpoint of a given bone."""
    head = bone.head
    tail = bone.tail
    midpoint = (head + tail) / 2
    return midpoint

def bone_length(bone):
    """Calculate the length of a given bone."""
    return (bone.head - bone.tail).length

def is_point_in_bone_bounds(point, bone):
    """Check if a point is within the bounds of a bone."""
    head = bone.head
    tail = bone.tail
    bone_direction = tail - head
    point_direction = point - head
    projection = point_direction.project(bone_direction)
    projected_point = head + projection
    return (projected_point - head).length <= bone_length(bone)

def go_to_pose_mode(context, armature):
    context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode='POSE')

def go_to_edit_mode(armature):
    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode='EDIT')

def safe_string(s):
    try:
        return s.encode('utf-8').decode('utf-8')
    except UnicodeDecodeError as e:
        print(f"Encoding error: {e}, in string: {repr(s)}")
        return ''.join([c if ord(c) < 128 else '?' for c in s])
def verify_bone_hierarchy(operator, armature):
    def report_hierarchy(bone, level=0):
        operator.report({'INFO'}, "|  " * level + "+- " + bone.name)
        for child in bone.children:
            report_hierarchy(child, level + 1)

    root_bones = [bone for bone in armature.data.bones if not bone.parent]
    for root in root_bones:
        report_hierarchy(root)
def sort_and_parent(operator,context, armature):
    
   
    safe_report(operator, {'INFO'}, "sort_and_parent")
    armature = bpy.context.active_object
    if armature.type != 'ARMATURE':
        return
    # Enter edit mode on the armature
    context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode='EDIT')
    
    sorted_bones = sorted(armature.data.edit_bones, key=lambda b: b.head.y)
    # Find the root bone (no parent)
    existing_root = next((bone for bone in armature.data.edit_bones if not bone.parent), None)
    
    
    for i, child_bone in enumerate(sorted_bones):
        if i == 0 and existing_root:
            child_bone.parent = existing_root
            #armature.data.edit_bones.link(child_bone)
        elif i > 0:
            child_bone.parent = sorted_bones[i-1]
            #armature.data.edit_bones.link(child_bone, parent=sorted_bones[i-1])
        child_bone.use_connect = False
    
    bpy.ops.object.mode_set(mode='OBJECT')
    
    
    
    
    
    
    
    def report_hierarchy(bone, level=0):
        operator.report({'INFO'}, "|  " * level + "-- " + bone.name)
        for child in bone.children:
            report_hierarchy(child, level + 1)

    root_bones = [bone for bone in armature.data.bones if not bone.parent]
    for root in root_bones:
        report_hierarchy(root)
def get_bone_parenting_chain(bone):
    """Get the parenting chain of a bone back to the root."""
    chain = []
    while bone:
        chain.append(bone.name)
        bone = bone.parent
    return " -> ".join(reversed(chain))

def find_potential_parent(armature, child_bone, bones):
    """Find a potential parent for a given bone."""
    child_midpoint = calculate_bone_midpoint(child_bone)
    potential_parents = [
        bone for bone in bones 
        if bone != child_bone and is_point_in_bone_bounds(child_midpoint, bone)
    ]
    if potential_parents:
        return max(potential_parents, key=bone_length)
    return None
def parent_bones_handler(sorted_bones):
    safe_report(operator, {'INFO'}, "handler")
    armature = bpy.context.active_object
    if armature.type != 'ARMATURE':
        return
    
    # Check if the armature is in edit mode
    if bpy.context.mode != 'EDIT_ARMATURE':
        bpy.ops.object.mode_set(mode='EDIT')
    
    # Find the root bone (no parent)
    existing_root = next((bone for bone in armature.data.edit_bones if not bone.parent), None)
    
    # Assume sorted_bones are globally available or passed via handler argument
    for i, child_bone in enumerate(sorted_bones):
        if i == 0 and existing_root:
            child_bone.parent = existing_root
        elif i > 0:
            child_bone.parent = sorted_bones[i-1]
        child_bone.use_connect = False
    
    bpy.ops.object.mode_set(mode='OBJECT')
    
    # Remove handler after execution
    #bpy.app.handlers.depsgraph_update_post.remove(parent_bones_handler)
    print("Bones parented successfully.")

def bones_algorithm(operator, context, armature, objects, full_length=False):
    
    sorted_bones = []
    
    def create_and_sort_bones(objects, armature):
        new_bones = []
        for obj in objects:
            if obj.type != 'MESH':
                continue
            bone = add_bone_to_object(obj, armature, full_length)
            if bone:
                new_bones.append(bone)
        time.sleep(.02)
        # Print information about bones before sorting
        #safe_report(operator, {'INFO'}, "Bones before sorting:")
        #for i, bone in enumerate(new_bones):
        #    safe_report(operator, {'INFO'}, f"Bone {i}: Name: {bone.name}, Head Y: {bone.head.y:.4f}")
        bpy.context.view_layer.update()
        sorted_bones = sorted(new_bones, key=lambda b: b.head.y)
        
        # Print information about bones after sorting
        #safe_report(operator, {'INFO'}, "Bones after sorting:")
        #for i, bone in enumerate(sorted_bones):
            #safe_report(operator, {'INFO'}, f"Bone {i}: Name: {bone.name}, Head Y: {bone.head.y:.4f}")
        
        return sorted_bones

    try:
        bpy.context.view_layer.objects.active = armature
        sorted_bones = create_and_sort_bones(objects, armature)
        bpy.context.view_layer.update()
        
        if sorted_bones:#this doesn't work, but lets see if it works
            def delayed_parent_bones():
                safe_report(operator, {'INFO'}, "Parenting bones...")
                parent_bones_handler(sorted_bones, armature)  # Pass armature argument
                return None
            bpy.app.timers.register(delayed_parent_bones, first_interval=0.01)

        safe_report(operator, {'INFO'}, "Parenting operation initiated.")
    except Exception as e:
        safe_report(operator, {'ERROR'}, f"Error during bone creation and sorting: {str(e)}")
def create_bone(armature, name, head, tail, roll=0):
    """
    Create a new bone in the given armature.
    
    :param armature: The armature object
    :param name: Name of the new bone
    :param head: Head position of the bone
    :param tail: Tail position of the bone
    :param roll: Roll of the bone
    :return: The newly created bone
    """
    bone = armature.data.edit_bones.new(safe_string(name))
    bone.head = head
    bone.tail = tail
    bone.roll = roll
    return bone

def safe_report(operator, level, message):
    try:
        operator.report(level, safe_string(message))
    except UnicodeDecodeError as e:
        print(f"Encoding error in report message: {e}, message: {repr(message)}")
        operator.report({'ERROR'}, f"Encoding error in report message: {str(e)}")

def is_wheel(obj):
    if not bpy.context.scene.check_for_wheels:
        return False
    world_bbox = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    dimensions = Vector((
        max(v.x for v in world_bbox) - min(v.x for v in world_bbox),
        max(v.y for v in world_bbox) - min(v.y for v in world_bbox),
        max(v.z for v in world_bbox) - min(v.z for v in world_bbox)
    ))
    return abs(dimensions.x - dimensions.z) < 0.001 and dimensions.y < min(dimensions.x, dimensions.z)

def add_bone_to_object(obj, armature, full_length=False):
    try:
        if obj is None or armature is None:
            print("Invalid object or armature")
            return None

        bpy.context.view_layer.objects.active = armature
        bpy.ops.object.mode_set(mode='EDIT')

        world_bbox = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
        world_center = sum(world_bbox, Vector()) / 8
        world_dims = Vector((
            max(v.x for v in world_bbox) - min(v.x for v in world_bbox),
            max(v.y for v in world_bbox) - min(v.y for v in world_bbox),
            max(v.z for v in world_bbox) - min(v.z for v in world_bbox)
        ))

        obj_loc = armature.matrix_world.inverted() @ world_center

        if is_wheel(obj):
            bone_length = max(world_dims.x, world_dims.z)
            bone_dir = Vector((0, 0, 1))  # Use Z-axis for wheels
        else:
            bone_length = world_dims.y
            bone_dir = Vector((0, 1, 0))  # Use Y-axis for non-wheels

        if full_length:
            head = obj_loc - (bone_dir * bone_length / 2)
            tail = obj_loc + (bone_dir * bone_length / 2)
        else:
            head = obj_loc
            tail = obj_loc + (bone_dir * bone_length)

        bone_name = obj.name
        bone = create_bone(armature, bone_name, head, tail)

        bpy.ops.object.mode_set(mode='OBJECT')

        if not any(mod.type == 'ARMATURE' and mod.object == armature for mod in obj.modifiers):
            armature_modifier = obj.modifiers.new(name="Armature", type='ARMATURE')
            armature_modifier.object = armature

        vertex_group = obj.vertex_groups.new(name=bone_name)
        vertex_group.add(range(len(obj.data.vertices)), 1.0, 'REPLACE')

        return bone
    except Exception as e:
        print(f"Error in add_bone_to_object: {e}")
        if bpy.context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        return None



class OBJECT_OT_add_bone(bpy.types.Operator):
    bl_idname = "object.add_bone"
    bl_label = "Add Bone"
    bl_description = "Add a bone at the selected object's origin and set up weights"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        try:
            obj = context.object
            armature = context.scene.selected_armature
            go_to_pose_mode_flag = context.scene.go_to_pose_mode
            full_length = context.scene.full_length_bone
            weight_method = context.scene.weight_method

            if obj and armature and obj != armature:
                if obj.name not in context.scene.objects:
                    self.report({'WARNING'}, "Selected object is no longer valid.")
                    return {'CANCELLED'}

                add_bone_to_object(obj, armature, full_length)

                if weight_method == 'ENVELOPE':
                    bpy.ops.object.parent_set(type='ARMATURE_ENVELOPE')
                elif weight_method == 'AUTO':
                    bpy.ops.object.parent_set(type='ARMATURE_AUTO')

                if go_to_pose_mode_flag:
                    bpy.ops.object.mode_set(mode='POSE')

                self.report({'INFO'}, f"Bone added, parented, and weights assigned using {weight_method} method.")
                return {'FINISHED'}

            else:
                self.report({'WARNING'}, "No object or armature selected, or object is the same as armature.")
                return {'CANCELLED'}

        except Exception as e:
            self.report({'ERROR'}, f"Error in add_bone_to_object: {str(e)}")
            return {'CANCELLED'}

class OBJECT_OT_generate_rig(bpy.types.Operator):
    bl_idname = "object.generate_rig"
    bl_label = "Generate Rig"
    bl_description = "Generate rig with custom parenting algorithm"

    def execute(self, context):
        armature = context.scene.selected_armature
        full_length = context.scene.full_length_bone
        if not armature:
            self.report({'WARNING'}, "No armature selected")
            return {'CANCELLED'}

        objects = context.selected_objects
        if not objects:
            self.report({'WARNING'}, "No objects selected")
            return {'CANCELLED'}

        try:
            # Ensure we're in Object Mode before starting
            bpy.ops.object.mode_set(mode='OBJECT')
            
            # Select the armature and enter Edit Mode
            bpy.context.view_layer.objects.active = armature
            bpy.ops.object.mode_set(mode='EDIT')
            
            bones_algorithm(self, context, armature, objects, full_length)
            bpy.context.view_layer.objects.active = armature
            bpy.ops.object.mode_set(mode='EDIT')
            # Crucial: Apply the changes before exiting Edit Mode
            #bpy.ops.armature.select_all(action='SELECT')
            #bpy.ops.armature.parent_set(type='OFFSET')
            
            # Return to Object Mode
            bpy.ops.object.mode_set(mode='OBJECT')
            sort_and_parent(self,context, armature)
            # Return to Object Mode
            bpy.ops.object.mode_set(mode='OBJECT')
            # Verify the bone hierarchy
            verify_bone_hierarchy(self, armature)
        except Exception as e:
            self.report({'ERROR'}, f"Error during rig generation: {str(e)}")
            if bpy.context.mode != 'OBJECT':
                bpy.ops.object.mode_set(mode='OBJECT')
            return {'CANCELLED'}

        self.report({'INFO'}, "Rig generated successfully")
        return {'FINISHED'}


class VIEW3D_PT_custom_panel(bpy.types.Panel):
    bl_label = "Bonify"
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
        layout.prop(context.scene, "full_length_bone", text="Full Length Bone")
        layout.prop(context.scene, "check_for_wheels", text="Check for Wheels")
        layout.prop(context.scene, "weight_method", text="Weight Method")
        layout.prop(context.scene, "main_chain_cutoff", text="Main Chain Cutoff (%)")
        layout.operator("object.add_bone", text="Add Bone", icon='BONE_DATA')
        layout.operator("object.generate_rig", text="Generate Rig")
        layout.operator("object.clear_all_bones_except_root", text="Clear All Bones Except Root", icon='BONE_DATA')

        layout.label(text="Bone Chain:")
        obj = context.object
        if obj and obj.type == 'MESH' and obj.vertex_groups:
            armature = context.scene.selected_armature
            if armature:
                for vgroup in obj.vertex_groups:
                    bone_name = vgroup.name
                    if bone_name in armature.data.bones:
                        bone = armature.data.bones[bone_name]
                        chain = get_bone_parenting_chain(bone)
                        layout.label(text=f"{bone_name}: {chain}")
        else:
            layout.label(text="No weight painted bones found")

class OBJECT_OT_select_armature(bpy.types.Operator):
    bl_idname = "object.select_armature"
    bl_label = "Select Armature"
    bl_description = "Select an armature for adding bones"

    armature_name: bpy.props.StringProperty()

    def execute(self, context):
        armature = bpy.data.objects.get(self.armature_name)
        if armature and armature.type == 'ARMATURE':
            context.scene.selected_armature = armature
            self.report({'INFO'}, f"Selected armature: {armature.name}")
        else:
            self.report({'WARNING'}, "Armature not found or invalid")
        return {'FINISHED'}

class OBJECT_OT_select_parent_bone(bpy.types.Operator):
    bl_idname = "object.select_parent_bone"
    bl_label = "Select Parent Bone"
    bl_description = "Manually select the parent bone for the new bone"

    def execute(self, context):
        armature = context.scene.selected_armature
        if armature and armature.type == 'ARMATURE':
            if bpy.context.mode != 'EDIT_ARMATURE':
                bpy.ops.object.mode_set(mode='EDIT')
            active_bone = armature.data.edit_bones.active
            if active_bone:
                context.scene.selected_parent_bone = safe_string(active_bone.name)
                context.scene.selected_axes = set()
                safe_report(self, {'INFO'}, f"Selected parent bone: {safe_string(active_bone.name)}")
            else:
                safe_report(self, {'WARNING'}, "No active bone selected")
            if bpy.context.mode != 'OBJECT':
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
        self.report({'INFO'}, "Cleared selected parent bone")
        return {'FINISHED'}

class OBJECT_OT_clear_all_bones_except_root(bpy.types.Operator):
    bl_idname = "object.clear_all_bones_except_root"
    bl_label = "Clear All Bones Except Root"
    bl_description = "Clear all bones from the selected armature except the root bone"

    def execute(self, context):
        armature = context.scene.selected_armature
        if armature and armature.type == 'ARMATURE':
            bpy.context.view_layer.objects.active = armature
            if bpy.context.mode != 'EDIT_ARMATURE':
                bpy.ops.object.mode_set(mode='EDIT')
            root_bone = next((bone for bone in armature.data.edit_bones if not bone.parent), None)
            if root_bone:
                bones_to_remove = [bone for bone in armature.data.edit_bones if bone != root_bone]
                for bone in bones_to_remove:
                    armature.data.edit_bones.remove(bone)
            if bpy.context.mode != 'OBJECT':
                bpy.ops.object.mode_set(mode='OBJECT')
            self.report({'INFO'}, "All bones except the root have been cleared.")
            return {'FINISHED'}
        else:
            self.report({'WARNING'}, "No valid armature selected.")
            return {'CANCELLED'}

def register():
    bpy.utils.register_class(OBJECT_OT_add_bone)
    bpy.utils.register_class(OBJECT_OT_generate_rig)
    bpy.utils.register_class(OBJECT_OT_select_armature)
    bpy.utils.register_class(OBJECT_OT_select_parent_bone)
    bpy.utils.register_class(OBJECT_OT_clear_selected_parent_bone)
    bpy.utils.register_class(OBJECT_OT_clear_all_bones_except_root)
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
    bpy.types.Scene.full_length_bone = bpy.props.BoolProperty(
        name="Full Length Bone",
        description="Toggle to create full-length bones from bottom to top of object",
        default=False
    )
    bpy.types.Scene.check_for_wheels = bpy.props.BoolProperty(
        name="Check for Wheels",
        description="Toggle to check if objects are wheels based on their dimensions",
        default=True
    )
    bpy.types.Scene.weight_method = bpy.props.EnumProperty(
        name="Weight Method",
        description="Choose the method for weight assignment",
        items=[
            ('ENVELOPE', "Envelope Weights", "Assign weights using envelope method"),
            ('AUTO', "Automatic Weights", "Assign weights automatically")
        ],
        default='AUTO'
    )
    bpy.types.Scene.main_chain_cutoff = bpy.props.FloatProperty(
        name="Main Chain Cutoff",
        description="Percentage of the largest bone's length to be considered as main chain",
        default=36.0,
        min=0.0,
        max=100.0,
        subtype='PERCENTAGE'
    )

def unregister():
    bpy.utils.unregister_class(OBJECT_OT_add_bone)
    bpy.utils.unregister_class(OBJECT_OT_generate_rig)
    bpy.utils.unregister_class(OBJECT_OT_select_armature)
    bpy.utils.unregister_class(OBJECT_OT_select_parent_bone)
    bpy.utils.unregister_class(OBJECT_OT_clear_selected_parent_bone)
    bpy.utils.unregister_class(OBJECT_OT_clear_all_bones_except_root)
    bpy.utils.unregister_class(VIEW3D_PT_custom_panel)
    del bpy.types.Scene.selected_armature
    del bpy.types.Scene.selected_axes
    del bpy.types.Scene.go_to_pose_mode
    del bpy.types.Scene.selected_parent_bone
    del bpy.types.Scene.full_length_bone
    del bpy.types.Scene.check_for_wheels
    del bpy.types.Scene.weight_method
    del bpy.types.Scene.main_chain_cutoff

if __name__ == "__main__":
    register()