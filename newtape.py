import bpy
import bmesh
import math
from mathutils import Vector, Matrix, Quaternion
# +z up +y fwd aligned train with bones and nurbs curve. 
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

def bake_curve(curve):
    # Store the original world matrix
    original_matrix = curve.matrix_world.copy()

    # Create a temporary copy of the curve
    temp_curve = curve.copy()
    temp_curve.data = temp_curve.data.copy()
    bpy.context.collection.objects.link(temp_curve)

    # Apply all transformations to the temporary curve
    temp_curve.data.transform(temp_curve.matrix_world)
    temp_curve.matrix_world = Matrix.Identity(4)

    # Calculate the tangent direction at the start of the curve
    spline = temp_curve.data.splines[0]
    if len(spline.points) >= 2:
        start_point = spline.points[0].co.xyz
        next_point = spline.points[1].co.xyz
        direction = (next_point - start_point).normalized()
    else:
        # Fallback if the curve has only one point
        direction = Vector((0, 1, 0))

    # Create a rotation matrix to align the curve's direction with the Y-axis, keeping Z up
    z_up = Vector((0, 0, 1))
    x_axis = z_up.cross(direction).normalized()
    y_axis = direction
    z_axis = x_axis.cross(y_axis)
    rotation_matrix = Matrix((x_axis, y_axis, z_axis)).to_4x4()

    # Apply the rotation to all points in the curve
    for spline in temp_curve.data.splines:
        for point in spline.points:
            point.co = rotation_matrix @ point.co

    # Transfer the baked data back to the original curve
    curve.data = temp_curve.data

    # Restore the original world matrix
    curve.matrix_world = original_matrix

    # Remove the temporary curve
    bpy.data.objects.remove(temp_curve, do_unlink=True)

def setup_train_rig(armature, plane, curve):
    # Bake the curve to ensure correct orientation
    bake_curve(curve)
    
    # Ensure the curve has a path
    curve.data.use_path = True
    curve.data.path_duration = 100
    curve.data.use_stretch = False
    curve.data.use_deform_bounds = True

    bpy.ops.object.mode_set(mode='EDIT')
    
    # Create control bone
    control_bone = armature.data.edit_bones.new("Train_Control")
    control_bone.head = (0, 0, 0)
    control_bone.tail = (0, 1, 0)  # Point along Y-axis
    
    bpy.ops.object.mode_set(mode='POSE')
    
    # Add follow path constraint to control bone
    control_bone_pose = armature.pose.bones["Train_Control"]
    follow_path = control_bone_pose.constraints.new(type='FOLLOW_PATH')
    follow_path.target = curve
    follow_path.use_curve_follow = True
    follow_path.forward_axis = 'FORWARD_Y'
    follow_path.up_axis = 'UP_Z'
    follow_path.use_fixed_location = True
    
    # Parent plane to armature
    plane.parent = armature
    plane.parent_type = 'BONE'
    plane.parent_bone = "Train_Control"
    
    # Reset plane transformations and align it with the curve
    plane.matrix_parent_inverse = control_bone_pose.matrix.inverted()
    plane.rotation_euler = (math.radians(90), 0, math.radians(90))  # Adjust rotation
    
    # Add curve modifier to plane
    curve_mod = plane.modifiers.new(name="Curve", type='CURVE')
    curve_mod.object = curve
    curve_mod.deform_axis = 'POS_Y'
    
    # Add custom property to control the offset
    armature["train_progress"] = 0.0
    armature.id_properties_ui("train_progress").update(min=0.0, max=100.0, soft_min=0.0, soft_max=100.0)
    
    # Add driver to control the offset
    fcurve = follow_path.driver_add("offset")
    driver = fcurve.driver
    var = driver.variables.new()
    var.name = "progress"
    var.type = 'SINGLE_PROP'
    var.targets[0].id = armature
    var.targets[0].data_path = '["train_progress"]'
    driver.expression = "progress / 100.0"
    
    return control_bone_pose

def setup_bone_constraints(armature, plane, loc_axis, loc_inverse, influence):
    sorted_bones = sorted(
        (bone for bone in armature.pose.bones if bone.bone.select),
        key=lambda b: (armature.matrix_world @ b.head).y
    )
    
    for i, bone in enumerate(sorted_bones):
        for constraint in bone.constraints:
            bone.constraints.remove(constraint)
        
        # Add a copy transforms constraint to the control bone
        copy_transforms = bone.constraints.new('COPY_TRANSFORMS')
        copy_transforms.target = armature
        copy_transforms.subtarget = "Train_Control"
        copy_transforms.influence = influence
        
        # Add a copy location constraint to the plane
        loc_constraint = bone.constraints.new('COPY_LOCATION')
        loc_constraint.target = plane
        loc_constraint.subtarget = f"Bone_{i+1}"
        loc_constraint.use_offset = True
        loc_constraint.target_space = 'LOCAL'
        loc_constraint.owner_space = 'LOCAL'
        
        loc_constraint.use_x = 'X' in loc_axis
        loc_constraint.use_y = 'Y' in loc_axis
        loc_constraint.use_z = 'Z' in loc_axis
        loc_constraint.invert_x = 'X' in loc_inverse
        loc_constraint.invert_y = 'Y' in loc_inverse
        loc_constraint.invert_z = 'Z' in loc_inverse
        loc_constraint.influence = influence
        
        if i < len(sorted_bones) - 1:
            track_constraint = bone.constraints.new('DAMPED_TRACK')
            track_constraint.target = armature
            track_constraint.subtarget = sorted_bones[i + 1].name
            track_constraint.track_axis = 'TRACK_Y'
            track_constraint.influence = influence

class AddTrainPathOperator(bpy.types.Operator):
    bl_idname = "object.add_train_path"
    bl_label = "Add Train Path"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        armature = context.active_object
        if armature.type != 'ARMATURE':
            self.report({'ERROR'}, "Active object must be an armature")
            return {'CANCELLED'}
        
        selected_bones = [b for b in armature.data.bones if b.select]
        if len(selected_bones) < 2:
            self.report({'ERROR'}, "At least two bones must be selected")
            return {'CANCELLED'}
        
        armature_matrix = armature.matrix_world
        bone_locations = [armature_matrix @ bone.head_local for bone in selected_bones]
        plane = create_segmented_plane(bone_locations, 1)
        
        return {'FINISHED'}

class SetupTrainRigOperator(bpy.types.Operator):
    bl_idname = "object.setup_train_rig"
    bl_label = "Setup Train Rig"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        armature = context.active_object
        if armature.type != 'ARMATURE':
            self.report({'ERROR'}, "Active object must be an armature")
            return {'CANCELLED'}
        
        plane = bpy.data.objects.get("Train_Path")
        if not plane:
            self.report({'ERROR'}, "Train_Path object not found")
            return {'CANCELLED'}
        
        curve = next((obj for obj in bpy.data.objects if obj.type == 'CURVE'), None)
        if not curve:
            self.report({'ERROR'}, "No curve found in the scene")
            return {'CANCELLED'}
        
        setup_train_rig(armature, plane, curve)
        
        return {'FINISHED'}

class SetupBoneConstraintsOperator(bpy.types.Operator):
    bl_idname = "object.setup_bone_constraints"
    bl_label = "Setup Bone Constraints"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        armature = context.active_object
        if armature.type != 'ARMATURE':
            self.report({'ERROR'}, "Active object must be an armature")
            return {'CANCELLED'}
        
        plane = bpy.data.objects.get("Train_Path")
        if not plane:
            self.report({'ERROR'}, "Train_Path object not found")
            return {'CANCELLED'}
        
        curve = next((obj for obj in bpy.data.objects if obj.type == 'CURVE'), None)
        if not curve:
            self.report({'ERROR'}, "No curve found in the scene")
            return {'CANCELLED'}
        
        props = context.scene.train_anim_properties
        setup_bone_constraints(
            armature, 
            plane, 
            props.loc_axis, 
            props.loc_inverse,
            props.influence
        )
        
        return {'FINISHED'}

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

class TrainAnimationPanel(bpy.types.Panel):
    bl_label = "Train Animation"
    bl_idname = "VIEW3D_PT_train_animation"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Tool'

    def draw(self, context):
        layout = self.layout
        layout.operator("object.add_train_path", text="Create Plane")
        layout.operator("object.setup_train_rig", text="Setup Train Rig")
        layout.operator("object.setup_bone_constraints", text="Setup Bone Constraints")
        
        props = context.scene.train_anim_properties
        layout.prop(props, "loc_axis")
        layout.prop(props, "loc_inverse")
        layout.prop(props, "influence")
        
        armature = context.active_object
        if armature and "train_progress" in armature:
            layout.prop(armature, '["train_progress"]', text="Train Progress")

def register():
    bpy.utils.register_class(AddTrainPathOperator)
    bpy.utils.register_class(SetupTrainRigOperator)
    bpy.utils.register_class(SetupBoneConstraintsOperator)
    bpy.utils.register_class(TrainAnimationProperties)
    bpy.utils.register_class(TrainAnimationPanel)
    bpy.types.Scene.train_anim_properties = bpy.props.PointerProperty(type=TrainAnimationProperties)

def unregister():
    bpy.utils.unregister_class(AddTrainPathOperator)
    bpy.utils.unregister_class(SetupTrainRigOperator)
    bpy.utils.unregister_class(SetupBoneConstraintsOperator)
    bpy.utils.unregister_class(TrainAnimationPanel)
    bpy.utils.unregister_class(TrainAnimationProperties)
    del bpy.types.Scene.train_anim_properties

if __name__ == "__main__":
    register()