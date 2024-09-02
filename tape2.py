import bpy
import bmesh
from mathutils import Vector

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

def setup_train_rig(armature, plane, curve):
    bpy.ops.object.mode_set(mode='EDIT')
    
    # Create control bone
    control_bone = armature.data.edit_bones.new("Control_Bone")
    control_bone.head = (0, 0, 0)
    control_bone.tail = (0, 6, 0)
    
    bpy.ops.object.mode_set(mode='POSE')
    
    # Remove constraints from all bones
    for bone in armature.pose.bones:
        for constraint in bone.constraints:
            bone.constraints.remove(constraint)
    
    # Add follow path constraint to control bone
    control_bone_pose = armature.pose.bones["Control_Bone"]
    follow_path = control_bone_pose.constraints.new(type='FOLLOW_PATH')
    follow_path.target = curve
    follow_path.use_curve_follow = True
    follow_path.forward_axis = 'FORWARD_Y'
    follow_path.up_axis = 'UP_Z'
    
    # Parent plane to armature
    plane.parent = armature
    plane.parent_type = 'OBJECT'
    
    # Add curve modifier to plane
    curve_mod = plane.modifiers.new(name="Follow_Curve", type='CURVE')
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
        
        armature = context.active_object
        if armature and armature.type == 'ARMATURE' and "train_progress" in armature:
            layout.prop(armature, '["train_progress"]', text="Train Progress")

def register():
    bpy.utils.register_class(AddTrainPathOperator)
    bpy.utils.register_class(SetupTrainRigOperator)
    bpy.utils.register_class(TrainAnimationPanel)

def unregister():
    bpy.utils.unregister_class(AddTrainPathOperator)
    bpy.utils.unregister_class(SetupTrainRigOperator)
    bpy.utils.unregister_class(TrainAnimationPanel)

if __name__ == "__main__":
    register()
