import bpy
import bmesh
import math
from mathutils import Vector

def create_segmented_plane(bone_locations, width):
    """Create a segmented plane with edges at bone head locations, aligned along the X-axis."""
    mesh = bpy.data.meshes.new("Train_Path")
    plane = bpy.data.objects.new("Train_Path", mesh)
    bpy.context.collection.objects.link(plane)
    
    bm = bmesh.new()
    half_width = width / 2
    
    for i, location in enumerate(bone_locations):
        # Calculate the vertices for the plane segment at each bone's head
        v1 = bm.verts.new(location + Vector((-half_width, 0, 0)))
        v2 = bm.verts.new(location + Vector((half_width, 0, 0)))
        bm.verts.ensure_lookup_table()
        
        bm.edges.new((v1, v2))
        
        if i > 0:
            bm.faces.new((bm.verts[-4], bm.verts[-3], bm.verts[-1], bm.verts[-2]))
    
    bm.to_mesh(mesh)
    bm.free()
    
    # Create vertex groups for each segment
    for i in range(len(bone_locations)):
        vg = plane.vertex_groups.new(name=f"Bone_{i+1}")
        vg.add([i*2, i*2+1], 1.0, 'REPLACE')
    
    return plane

def setup_follow_curve_constraint(plane, curve):
    """Apply the follow curve constraint to the segmented plane."""
    follow_curve = plane.constraints.new(type='FOLLOW_PATH')
    follow_curve.target = curve
    follow_curve.use_fixed_location = True
    follow_curve.forward_axis = 'FORWARD_Y'
    follow_curve.up_axis = 'UP_Z'

def setup_bone_constraints(armature, plane, loc_axis, loc_inverse, rot_axis, rot_inverse, influence):
    """Set up constraints to make bones follow the segmented plane."""
    sorted_bones = sorted(
        (bone for bone in armature.pose.bones if bone.bone.select),
        key=lambda b: (armature.matrix_world @ b.head).y
    )
    
    for i, bone in enumerate(sorted_bones):
        # Remove existing constraints
        for constraint in bone.constraints:
            bone.constraints.remove(constraint)
        
        # Copy Location constraint
        loc_constraint = bone.constraints.new('COPY_LOCATION')
        loc_constraint.target = plane
        loc_constraint.subtarget = f"Bone_{i + 1}"
        loc_constraint.use_offset = True
        loc_constraint.target_space = 'WORLD'
        loc_constraint.owner_space = 'WORLD'
        
        loc_constraint.use_x = 'X' in loc_axis
        loc_constraint.use_y = 'Y' in loc_axis
        loc_constraint.use_z = 'Z' in loc_axis
        loc_constraint.invert_x = 'X' in loc_inverse
        loc_constraint.invert_y = 'Y' in loc_inverse
        loc_constraint.invert_z = 'Z' in loc_inverse
        loc_constraint.influence = influence
        
        # Copy Rotation constraint
        rot_constraint = bone.constraints.new('COPY_ROTATION')
        rot_constraint.target = plane
        rot_constraint.subtarget = f"Bone_{i + 1}"
        rot_constraint.use_offset = True
        rot_constraint.target_space = 'WORLD'
        rot_constraint.owner_space = 'WORLD'
        
        rot_constraint.use_x = 'X' in rot_axis
        rot_constraint.use_y = 'Y' in rot_axis
        rot_constraint.use_z = 'Z' in rot_axis
        rot_constraint.invert_x = 'X' in rot_inverse
        rot_constraint.invert_y = 'Y' in rot_inverse
        rot_constraint.invert_z = 'Z' in rot_inverse
        rot_constraint.influence = influence

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
        setup_follow_curve_constraint(plane, curve)
        props = context.scene.train_anim_properties
        setup_bone_constraints(
            armature, 
            plane, 
            props.loc_axis, 
            props.loc_inverse, 
            props.rot_axis, 
            props.rot_inverse,
            props.influence
        )
        
        return {'FINISHED'}

class ClearConstraintsOperator(bpy.types.Operator):
    bl_idname = "object.clear_train_constraints"
    bl_label = "Clear Train Constraints"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        armature = context.active_object
        if armature.type != 'ARMATURE':
            self.report({'ERROR'}, "Active object must be an armature")
            return {'CANCELLED'}
        
        for bone in armature.pose.bones:
            for constraint in bone.constraints:
                bone.constraints.remove(constraint)
        
        return {'FINISHED'}

class UpdateConstraintsOperator(bpy.types.Operator):
    """Update the constraints for the train animation."""
    bl_idname = "object.update_train_constraints"
    bl_label = "Update Train Constraints"
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
        
        # Get bone head locations and sort by Y axis
        armature_matrix = armature.matrix_world
        bone_locations = sorted(
            (armature_matrix @ bone.head for bone in armature.pose.bones if bone.bone.select),
            key=lambda v: v.y
        )
        
        # Update constraints with the panel properties
        props = context.scene.train_anim_properties
        setup_bone_constraints(
            armature, 
            plane, 
            props.loc_axis, 
            props.loc_inverse, 
            props.rot_axis, 
            props.rot_inverse,
            props.influence
        )
        
        return {'FINISHED'}

class TrainAnimationProperties(bpy.types.PropertyGroup):
    """Properties for train animation settings."""
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
    
    rot_axis: bpy.props.EnumProperty(
        items=[('X', 'X', 'X Axis'),
               ('Y', 'Y', 'Y Axis'),
               ('Z', 'Z', 'Z Axis'),
               ('XY', 'X Y', 'X and Y Axes'),
               ('XZ', 'X Z', 'X and Z Axes'),
               ('YZ', 'Y Z', 'Y and Z Axes'),
               ('XYZ', 'X Y Z', 'All Axes')],
        name="Rotation Axis",
        default='XYZ'
    )
    
    rot_inverse: bpy.props.EnumProperty(
        items=[('NONE', 'None', 'None'),
               ('X', 'X', 'Inverse X'),
               ('Y', 'Y', 'Inverse Y'),
               ('Z', 'Z', 'Inverse Z'),
               ('XY', 'X Y', 'Inverse X and Y'),
               ('XZ', 'X Z', 'Inverse X and Z'),
               ('YZ', 'Y Z', 'Inverse Y and Z'),
               ('XYZ', 'X Y Z', 'Inverse All')],
        name="Rotation Inverse",
        default='NONE'
    )
    
    influence: bpy.props.FloatProperty(
        name="Constraint Influence",
        default=1.0,
        min=0.0,
        max=1.0
    )

class TrainAnimationPanel(bpy.types.Panel):
    """Panel for train animation controls."""
    bl_label = "AAAAAAAAAAA"
    bl_idname = "VIEW3D_PT_train_animation"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Tool'

    def draw(self, context):
        layout = self.layout
        props = context.scene.train_anim_properties
        layout.prop(props, "loc_axis")
        layout.prop(props, "loc_inverse")
        layout.prop(props, "rot_axis")
        layout.prop(props, "rot_inverse")
        layout.prop(props, "loc_offset")
        layout.prop(props, "influence")
        layout.operator(AddTrainPathOperator.bl_idname)
        layout.operator(ClearConstraintsOperator.bl_idname)
        #layout.operator(RotateBonesOperator.bl_idname)
        
        if context.active_object and context.active_object.type == 'ARMATURE':
            layout.operator(UpdateConstraintsOperator.bl_idname)


def register():
    bpy.utils.register_class(AddTrainPathOperator)
    bpy.utils.register_class(ClearConstraintsOperator)
    bpy.utils.register_class(UpdateConstraintsOperator)
    #bpy.utils.register_class(RotateBonesOperator)
    bpy.utils.register_class(TrainAnimationPanel)
    bpy.utils.register_class(TrainAnimationProperties)
    
    bpy.types.Scene.train_anim_properties = bpy.props.PointerProperty(type=TrainAnimationProperties)

def unregister():
    bpy.utils.unregister_class(AddTrainPathOperator)
    bpy.utils.unregister_class(ClearConstraintsOperator)
    bpy.utils.unregister_class(UpdateConstraintsOperator)
    #bpy.utils.unregister_class(RotateBonesOperator)
    bpy.utils.unregister_class(TrainAnimationPanel)
    bpy.utils.unregister_class(TrainAnimationProperties)
    
    del bpy.types.Scene.train_anim_properties

if __name__ == "__main__":
    register()
