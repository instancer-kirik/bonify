import bpy
import bmesh
import math
from mathutils import Vector, Matrix

def create_segmented_plane(bone_count, bone_locations, width):
    # Create a new mesh for the plane
    mesh = bpy.data.meshes.new("Train_Path")
    plane = bpy.data.objects.new("Train_Path", mesh)
    bpy.context.collection.objects.link(plane)
    
    bm = bmesh.new()
    
    for location in bone_locations:
        half_width = width / 2
        # Create vertices on either side of the bone head location along the Y axis (since bones are vertical)
        v1 = bm.verts.new(location + Vector((-half_width, 0, 0)))  # Left vertex
        v2 = bm.verts.new(location + Vector((half_width, 0, 0)))   # Right vertex
        bm.verts.ensure_lookup_table()
        
        # Create an edge between the current pair of vertices
        bm.edges.new((v1, v2))
    
    # Create edges between the pairs of vertices to form a continuous path
    for i in range(bone_count - 1):
        bm.edges.new((bm.verts[i*2], bm.verts[(i+1)*2]))       # Connect left vertices
        bm.edges.new((bm.verts[i*2+1], bm.verts[(i+1)*2+1]))   # Connect right vertices
    
    # Create faces
    for i in range(bone_count - 1):
        bm.faces.new((bm.verts[i*2], bm.verts[i*2+1], bm.verts[(i+1)*2+1], bm.verts[(i+1)*2]))
    
    bm.to_mesh(mesh)
    bm.free()
    
    # Create vertex groups based on sorted bone locations
    for i, _ in enumerate(bone_locations):
        vg = plane.vertex_groups.new(name=f"Bone_{i+1}")
        vg.add([i*2, i*2+1], 1.0, 'REPLACE')
    
    return plane

def setup_bone_constraints(armature, plane, loc_axis, loc_inverse, rot_axis, rot_inverse, loc_offset, influence):
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
        loc_constraint.subtarget = f"Bone_{i+1}"
        loc_constraint.use_offset = loc_offset
        loc_constraint.target_space = 'WORLD'
        loc_constraint.owner_space = 'WORLD'
        
        loc_constraint.use_x = 'X' in loc_axis
        loc_constraint.use_y = 'Y' in loc_axis
        loc_constraint.use_z = 'Z' in loc_axis
        loc_constraint.invert_x = 'X' in loc_inverse
        loc_constraint.invert_y = 'Y' in loc_inverse
        loc_constraint.invert_z = 'Z' in loc_inverse
        loc_constraint.influence = influence
        loc_constraint.mute = False
        loc_constraint.show_expanded = True
        loc_constraint.name = f"Copy Loc {i+1}"
        
        # Copy Rotation constraint
        rot_constraint = bone.constraints.new('COPY_ROTATION')
        rot_constraint.target = plane
        rot_constraint.subtarget = f"Bone_{i+1}"
        rot_constraint.use_offset = loc_offset
        rot_constraint.target_space = 'WORLD'
        rot_constraint.owner_space = 'WORLD'
        
        rot_constraint.use_x = 'X' in rot_axis
        rot_constraint.use_y = 'Y' in rot_axis
        rot_constraint.use_z = 'Z' in rot_axis
        rot_constraint.invert_x = 'X' in rot_inverse
        rot_constraint.invert_y = 'Y' in rot_inverse
        rot_constraint.invert_z = 'Z' in rot_inverse
        rot_constraint.influence = influence
        rot_constraint.mute = False
        rot_constraint.show_expanded = True
        rot_constraint.name = f"Copy Rot {i+1}"

def rotate_bones_to_path(armature):
    bones = [bone for bone in armature.pose.bones if bone.bone.select]
    
    if len(bones) < 2:
        return  # Need at least two bones to determine direction

    for i in range(len(bones) - 1):
        current_bone = bones[i]
        next_bone = bones[i + 1]
        
        # Calculate direction vector between current and next bone
        direction = next_bone.head - current_bone.head
        direction.normalize()
        
        # Calculate rotation from vertical (Z-axis) to new direction
        axis = Vector((0, 0, 1)).cross(direction)
        angle = math.acos(Vector((0, 0, 1)).dot(direction))
        
        # Create rotation matrix
        rotation_matrix = Matrix.Rotation(angle, 4, axis)
        
        # Apply rotation to the bone
        current_bone.matrix_basis = rotation_matrix @ current_bone.matrix_basis

    # Rotate the last bone to match the direction of the previous bone
    if len(bones) > 1:
        last_bone = bones[-1]
        last_direction = last_bone.head - bones[-2].head
        last_direction.normalize()
        
        axis = Vector((0, 0, 1)).cross(last_direction)
        angle = math.acos(Vector((0, 0, 1)).dot(last_direction))
        
        rotation_matrix = Matrix.Rotation(angle, 4, axis)
        last_bone.matrix_basis = rotation_matrix @ last_bone.matrix_basis

    # Update the armature
    armature.data.update_tag()
    bpy.context.view_layer.update()

class RotateBonesOperator(bpy.types.Operator):
    bl_idname = "object.rotate_bones"
    bl_label = "Rotate Bones"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        armature = context.active_object
        if armature.type != 'ARMATURE':
            self.report({'ERROR'}, "Active object must be an armature")
            return {'CANCELLED'}
        
        # Rotate bones to proper orientation
        rotate_bones_to_path(armature)
        
        return {'FINISHED'}

class AddTrainPathOperator(bpy.types.Operator):
    bl_idname = "object.add_train_path"
    bl_label = "Add Train Path"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        armature = context.active_object
        if armature.type != 'ARMATURE':
            self.report({'ERROR'}, "Active object must be an armature")
            return {'CANCELLED'}
        
        bone_count = len([b for b in armature.data.bones if b.select])
        if bone_count < 2:
            self.report({'ERROR'}, "At least two bones must be selected")
            return {'CANCELLED'}
        
        # Rotate bones to proper orientation
        rotate_bones_to_path(armature)
        
        # Get bone head locations and sort by Y axis
        bone_locations = sorted((bone.head for bone in armature.pose.bones if bone.bone.select), key=lambda v: v.y)
        
        plane = create_segmented_plane(bone_count, bone_locations, 1)
        props = context.scene.train_anim_properties
        setup_bone_constraints(armature, plane, props.loc_axis, props.loc_inverse, props.rot_axis, props.rot_inverse, props.loc_offset, props.influence)
        
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

    loc_offset: bpy.props.BoolProperty(
        name="Location Offset",
        description="Use offset for location constraints",
        default=False
    )

    influence: bpy.props.FloatProperty(
        name="Influence",
        description="Influence of the constraint",
        default=1.0,
        min=0.0,
        max=1.0
    )

class TrainAnimationPanel(bpy.types.Panel):
    bl_label = "Train Animation"
    bl_idname = "OBJECT_PT_train_animation"
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
        layout.operator(RotateBonesOperator.bl_idname)
        
        if context.active_object and context.active_object.type == 'ARMATURE':
            layout.operator(UpdateConstraintsOperator.bl_idname)

class UpdateConstraintsOperator(bpy.types.Operator):
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
            props.loc_offset,
            props.influence
        )
        
        return {'FINISHED'}

def register():
    bpy.utils.register_class(AddTrainPathOperator)
    bpy.utils.register_class(ClearConstraintsOperator)
    bpy.utils.register_class(UpdateConstraintsOperator)
    bpy.utils.register_class(RotateBonesOperator)
    bpy.utils.register_class(TrainAnimationPanel)
    bpy.utils.register_class(TrainAnimationProperties)
    bpy.types.Scene.train_anim_properties = bpy.props.PointerProperty(type=TrainAnimationProperties)

def unregister():
    bpy.utils.unregister_class(AddTrainPathOperator)
    bpy.utils.unregister_class(ClearConstraintsOperator)
    bpy.utils.unregister_class(UpdateConstraintsOperator)
    bpy.utils.unregister_class(RotateBonesOperator)
    bpy.utils.unregister_class(TrainAnimationPanel)
    bpy.utils.unregister_class(TrainAnimationProperties)
    del bpy.types.Scene.train_anim_properties

if __name__ == "__main__":
    register()
