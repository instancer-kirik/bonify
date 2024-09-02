# bonify
add bones to objects in blender, with auto weighting and parent finding, also you can manually select parent
CURRENTLY ONLY PARENTS BY Y POSITION, AAAAAAAAA IM WORKING ON THE FOLLOW CURVE PART NOW
Instructions for now
1. Click on Scripting workspace tab (Top) > Text > New > paste bonify.py > press Play button |> bonify controls in Tool menu

2. have an armature, click on 'Armature' in controls to select armature

3. in object mode, select object,
choose axes for parent searching, or select one in armature edit mode. 
add bone with weights

![image](https://github.com/user-attachments/assets/07a7b4d8-12ee-4ac1-84ca-9d137b2d1d9d)
![image](https://github.com/user-attachments/assets/c41ee1a0-566d-4d28-b210-91ca1913ffbb)

### Hark-- Vertex Groups, Armature modifier, UNAPPLIED TRANSFORMS - I think this solves that for you, but if it is in wrong place try Ctrl+a > all transforms. 
#### If your object is not moving by the bone in pose mode, you probably duplicated to get it, renaming it might solve this


if you get a Encoding error: 'utf-8' codec can't decode byte 0x9f in position 2: invalid start byte
or a Encoding error: 'utf-8' codec can't decode byte 0xd0 in position 0: invalid continuation byte
buy me dinner first because I fixed it. Open an issue if this occurs.

TODO if you pay me $Instancer

prevent duplicate bones

hotkey and better direction selection

group selection actions

selection macros

custom bone naming strategy (currently it just takes object name)

decide bone direction

add utf-8 errors back in


