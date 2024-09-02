import bpy
import bmesh
from mathutils import Vector, Matrix
# Function to create the segmented plane
def create_segmented_plane(bone_locations, width):
    mesh = bpy.data.meshes.new("Train_Path")
    plane = bpy.data.objects.new("Train_Path", mesh)
    bpy.context.collection.objects.link(plane)
    
    bm = bmesh.new()
    half_width = width / 2
    
    for i, location in enumerate(bone_locations):
        v1 = bm.verts.new(location + Vector((half_width, 0, 0)))
        v2 = bm.verts.new(location + Vector((-half_width, 0, 0)))
        bm.verts.ensure_lookup_table()
        
        bm.edges.new((v1, v2))
        
        if i > 0:
            bm.faces.new((bm.verts[-4], bm.verts[-3], bm.verts[-1], bm.verts[-2]))
    
    bm.to_mesh(mesh)
    bm.free()
    
    for i in range(len(bone_locations)):
        vg = plane.vertex_groups.new(name=f"Bone_{i+1}")
        vg.add([i*2, i*2+1], 1.0, 'REPLACE')
    
    return plane

# Function to set up the follow curve constraint using a control bone
def setup_follow_curve_constraint(armature, plane, curve):
    # Ensure the curve has a path
    curve.data.use_path = True
    curve.data.path_duration = 100  # Set an appropriate duration
    curve.data.use_stretch = True
    curve.data.use_deform_bounds = True

    # Create a control bone
    bpy.ops.object.mode_set(mode='EDIT')
    control_bone = armature.data.edit_bones.new("Control_Bone")
    control_bone.head = (0, 0, 0)
    control_bone.tail = (0, 1, 0)

    # Align control bone to curve's initial direction
    curve_start = curve.data.splines[0].points[0].co.xyz
    curve_end = curve.data.splines[0].points[-1].co.xyz
    curve_direction = (curve_end - curve_start).normalized()
    control_bone.align_roll(curve_direction)

    bpy.ops.object.mode_set(mode='OBJECT')

    # Add a FOLLOW_PATH constraint to the control bone
    control_bone_pose = armature.pose.bones["Control_Bone"]
    follow_path = control_bone_pose.constraints.new(type='FOLLOW_PATH')
    follow_path.target = curve
    follow_path.use_curve_follow = True
    follow_path.forward_axis = 'FORWARD_Y'
    follow_path.up_axis = 'UP_Z'

    # Add a custom property to the armature to control the progress
    armature["train_progress"] = 0.0
    armature.id_properties_ui("train_progress").update(min=0.0, max=100.0, soft_min=0.0, soft_max=100.0)

    # Add a driver to control the offset of the FOLLOW_PATH constraint
    fcurve = follow_path.driver_add("offset")
    driver = fcurve.driver
    var = driver.variables.new()
    var.name = "progress"
    var.type = 'SINGLE_PROP'
    var.targets[0].id = armature
    var.targets[0].data_path = '["train_progress"]'
    driver.expression = "progress / 100.0"

    # Add a CURVE modifier to the plane
    curve_mod = plane.modifiers.new(name="Follow_Curve", type='CURVE')
    curve_mod.object = curve
    curve_mod.deform_axis = 'POS_Y'

    # Parent the plane to the armature
    plane.parent = armature
    plane.parent_type = 'OBJECT'

    # Reset plane's rotation
    plane.rotation_euler = (0, 0, 0)

    return control_bone_pose

# Function to set up bone constraints
def setup_bone_constraints(armature, plane, loc_axis, loc_inverse, influence):
    sorted_bones = sorted(
        (bone for bone in armature.pose.bones if bone.bone.select),
        key=lambda b: (armature.matrix_world @ b.head).y
    )
    
    for i, bone in enumerate(sorted_bones):
        for constraint in bone.constraints:
            bone.constraints.remove(constraint)
        
        # Location constraint using vertex group
        loc_constraint = bone.constraints.new('COPY_LOCATION')
        loc_constraint.target = plane
        loc_constraint.subtarget = f"Bone_{i+1}"  # Assuming vertex groups are named "Bone_1", "Bone_2", etc.
        loc_constraint.use_offset = False
        loc_constraint.target_space = 'WORLD'
        loc_constraint.owner_space = 'WORLD'
        
        loc_constraint.use_x = 'X' in loc_axis
        loc_constraint.use_y = 'Y' in loc_axis
        loc_constraint.use_z = 'Z' in loc_axis
        loc_constraint.invert_x = 'X' in loc_inverse
        loc_constraint.invert_y = 'Y' in loc_inverse
        loc_constraint.invert_z = 'Z' in loc_inverse
        loc_constraint.influence = influence

        # Rotation constraint to align with the plane
        rot_constraint = bone.constraints.new('COPY_ROTATION')
        rot_constraint.target = plane
        rot_constraint.use_offset = True
        rot_constraint.target_space = 'WORLD'
        rot_constraint.owner_space = 'WORLD'
        rot_constraint.influence = influence

# Operator for creating the segmented plane
class AddTrainPathOperator(bpy.types.Operator):
    bl_idname = "object.add_train_path"
    bl_label = "Add Train Path"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        armature = context.active_object
        if armature.type != 'ARMATURE':
            self.report({'ERROR'}, "Active object must be an armature")
            return {'CANCELLED'}
        
        curve = next((obj for obj in bpy.data.objects if obj.type == 'CURVE'), None)
        if not curve:
            self.report({'ERROR'}, "No curve found in the scene")
            return {'CANCELLED'}
        
        selected_bones = [b for b in armature.data.bones if b.select]
        if len(selected_bones) < 2:
            self.report({'ERROR'}, "At least two bones must be selected")
            return {'CANCELLED'}
        
        armature_matrix = armature.matrix_world
        bone_locations = [armature_matrix @ bone.head_local for bone in selected_bones]
        plane = create_segmented_plane(bone_locations, 1)
        
        return {'FINISHED'}

# Operator for setting up the follow curve constraint
class SetupFollowCurveOperator(bpy.types.Operator):
    bl_idname = "object.setup_follow_curve"
    bl_label = "Setup Follow Curve"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        plane = bpy.data.objects.get("Train_Path")
        if not plane:
            self.report({'ERROR'}, "Train_Path object not found")
            return {'CANCELLED'}
        
        armature = context.active_object
        if armature.type != 'ARMATURE':
            self.report({'ERROR'}, "Active object must be an armature")
            return {'CANCELLED'}
        
        curve = next((obj for obj in bpy.data.objects if obj.type == 'CURVE'), None)
        if not curve:
            self.report({'ERROR'}, "No curve found in the scene")
            return {'CANCELLED'}
        
        setup_follow_curve_constraint(armature, plane, curve)
        
        return {'FINISHED'}

# Property group for animation properties
class TrainAnimationProperties(bpy.types.PropertyGroup):
    loc_axis: bpy.props.EnumProperty(
        items=[('X', 'X', 'X Axis'),
               ('Y', 'Y', 'Y Axis'),
               ('Z', 'Z', 'Z Axis'),
               ('XY', 'X Y', 'X and Y Axes'),
               ('XZ', 'X Z', 'X and Z Axes'),
               ('YZ', 'Y Z', 'Y and Z Axes'),
               ('XYZ', 'X Y Z', 'All Axes')],
        name="Location Axis",
        default='XYZ'
    )
    
    loc_inverse: bpy.props.EnumProperty(
        items=[('NONE', 'None', 'None'),
               ('X', 'X', 'Inverse X'),
               ('Y', 'Y', 'Inverse Y'),
               ('Z', 'Z', 'Inverse Z'),
               ('XY', 'X Y', 'Inverse X and Y'),
               ('XZ', 'X Z', 'Inverse X and Z'),
               ('YZ', 'Y Z', 'Inverse Y and Z'),
               ('XYZ', 'X Y Z', 'Inverse All')],
        name="Location Inverse",
        default='NONE'
    )
    
    influence: bpy.props.FloatProperty(
        name="Constraint Influence",
        default=1.0,
        min=0.0,
        max=1.0
    )

# UI Panel to house the buttons
class TrainAnimationPanel(bpy.types.Panel):
    bl_label = "Train Animation"
    bl_idname = "VIEW3D_PT_train_animation"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Tool'

    def draw(self, context):
        layout = self.layout
        layout.operator("object.add_train_path", text="Create Plane")
        layout.operator("object.setup_follow_curve", text="Setup Follow Curve")
        layout.operator("object.setup_bone_constraints", text="Setup Bone Constraints")
        
        armature = context.active_object
        if armature and armature.type == 'ARMATURE' and "train_progress" in armature:
            layout.prop(armature, '["train_progress"]', text="Progress Along Curve")

# Registering classes and properties
def register():
    bpy.utils.register_class(AddTrainPathOperator)
    bpy.utils.register_class(SetupFollowCurveOperator)
    bpy.utils.register_class(TrainAnimationProperties)
    bpy.utils.register_class(TrainAnimationPanel)
    bpy.types.Scene.train_anim_properties = bpy.props.PointerProperty(type=TrainAnimationProperties)

def unregister():
    bpy.utils.unregister_class(AddTrainPathOperator)
    bpy.utils.unregister_class(SetupFollowCurveOperator)
    bpy.utils.unregister_class(TrainAnimationPanel)
    bpy.utils.unregister_class(TrainAnimationProperties)
    
    del bpy.types.Scene.train_anim_properties

if __name__ == "__main__":
    register()
