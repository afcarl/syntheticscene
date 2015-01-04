import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector
import numpy as np
from math import pi
from colorsys import hsv_to_rgb
from hashlib import sha256
import json
import os.path as op

rng = np.random.RandomState()
digest = sha256(rng.get_state()[1]).hexdigest()


n_objects = rng.randint(low=3, high=10)
LAMP_LOCATION = np.array([0, 0, 10])
BASE_CAMERA_LOCATION = np.array([-8, -8, 5])
BASE_CAMERA_ROTATION = np.array([0.4 * pi, 0, -0.25 * pi])

metadata = {}


def random_hsv(rng, hue_range=(0, 1)):
    h = rng.uniform(low=hue_range[0], high=hue_range[1])  # any color
    s = rng.uniform(low=.3, high=0.6)  # never saturate too much
    v = rng.uniform(low=0.6, high=1.)  # bright enough
    return (h, s, v)


def make_random_material(rng, name, hue_range=(0, 1)):
    material = bpy.data.materials.new(name)
    color_hsv = random_hsv(rng, hue_range=hue_range)
    color_rgb = hsv_to_rgb(*color_hsv)
    material.diffuse_color = color_rgb
    info = {
        'color': {
            'hsv': color_hsv,
            'rgb': color_rgb,
        },
    }
    return material, info


def add_random_material(ob, rng, hue_range=(0, 1)):
    material, info = make_random_material(rng, ob.name, hue_range=hue_range)
    ob.data.materials.append(material)
    return info


def random_deform(ob, rng, scale=0.1):
    max_dim = max(ob.dimensions)
    abs_scale = scale * max_dim
    for v in ob.data.vertices:
        v.co += Vector(rng.normal(scale=abs_scale, size=3))


def get_vertices_info(ob):
    vertices = []
    for v in ob.data.vertices:
        vertices.append(list(v.co))
    return vertices


def get_vertices_projections(scene, camera, ob):
    projections = []
    for v in ob.data.vertices:
        projections.append(list(world_to_camera_view(scene, camera, v.co)))
    return projections


# delete all objects from the scene to make it easier to generate the
# scene from scratch each time
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()


# Add a camera
camera_location = BASE_CAMERA_LOCATION + rng.normal(size=3, scale=0.2)
camera_rotation = BASE_CAMERA_ROTATION + rng.normal(size=3, scale=0.05)
bpy.ops.object.camera_add(location=camera_location,
                          rotation=camera_rotation)
camera = bpy.context.object
# TODO: store info in metadata

# Add a lamp
lamp_rotation = rng.uniform(low=-.4 * pi, high=.4 * pi, size=3)
lamp_rotation[2] = 0
bpy.ops.object.lamp_add(type='SUN',
                        location=LAMP_LOCATION,
                        rotation=lamp_rotation)
lamp = bpy.context.object
# TODO: store info in metadata

# Add a circular plane to get some shadows on the ground
ground_radius = rng.uniform(low=50, high=100)
bpy.ops.mesh.primitive_circle_add(location=(0, 0, 0),
                                  radius=ground_radius,
                                  fill_type='TRIFAN')
ground = bpy.context.object
add_random_material(ground, rng, hue_range=(0.1, 0.3))
ground_info = metadata.setdefault('ground', {})
ground_info['radius'] = ground_radius
# TODO: store material info for the ground in metadata

# Add some objects
collection_type = rng.choice(['cube', 'sphere', 'mixed'])


object_hue_center = rng.uniform(0, 1)
object_hue_min = max(0, object_hue_center - 0.1)
object_hue_max = min(1, object_hue_center + 0.1)
object_hue_range = (object_hue_min, object_hue_max)

collection_info = metadata.setdefault('object_collection', {})
collection_info['type'] = collection_type
objects_info = collection_info.setdefault('objects', [])
collection_info['hue_center'] = object_hue_center

for i in range(n_objects):
    object_info = {}
    objects_info.append(object_info)

    object_size = rng.uniform(0.5, 1.5)
    object_location = rng.normal(size=3, loc=(0, 0, 2), scale=1.0)
    object_rotation = rng.normal(size=3, loc=(0, 0, 0), scale=1.0)

    object_info['size'] = object_size
    object_info['location'] = object_location.tolist()
    object_info['rotation'] = object_rotation.tolist()

    if collection_type == 'mixed':
        object_type = rng.choice(['cube', 'sphere'])
    else:
        object_type = collection_type

    object_info['type'] = object_type

    if object_type == 'cube':
        bpy.ops.mesh.primitive_cube_add(
            radius=object_size,
            location=object_location,
            rotation=object_rotation,
        )
        bpy.ops.object.modifier_add(type='REMESH')
        bpy.context.object.modifiers["Remesh"].octree_depth = 2
        bpy.ops.object.modifier_apply(apply_as='DATA', modifier="Remesh")
        random_deform(bpy.context.object, rng, scale=0.1)
        bpy.ops.object.modifier_add(type='SUBSURF')
        bpy.context.object.modifiers["Subsurf"].levels = 4
        bpy.context.object.modifiers["Subsurf"].render_levels = 4
        # bpy.ops.object.modifier_apply(apply_as='DATA', modifier="Subsurf")
    elif object_type == 'sphere':
        bpy.ops.mesh.primitive_ico_sphere_add(
            size=object_size,
            location=object_location,
            rotation=object_rotation,
        )
        random_deform(bpy.context.object, rng, scale=0.03)
        bpy.ops.object.modifier_add(type='SUBSURF')
        bpy.context.object.modifiers["Subsurf"].levels = 4
        bpy.context.object.modifiers["Subsurf"].render_levels = 4
        # bpy.ops.object.modifier_apply(apply_as='DATA', modifier="Subsurf")

    ob = bpy.context.object
    scene = bpy.context.scene
    vertices = get_vertices_info(ob)
    object_info['vertices'] = vertices

    projections = get_vertices_projections(scene, camera, ob)
    object_info['projected_vertices'] = projections

    material_info = add_random_material(ob, rng, hue_range=object_hue_range)
    object_info['material'] = material_info


metadata_filename = 'scene_%s.json' % digest
print('saving scene to %s' % metadata_filename)
with open(metadata_filename, 'w') as f:
    json.dump(metadata, f, indent=2)

image_filename = 'scene_%s.png' % digest
print('rendering scene to %s' % image_filename)

bpy.context.scene.camera = camera
bpy.context.scene.render.filepath = op.abspath(image_filename)
bpy.context.scene.render.resolution_x = 256
bpy.context.scene.render.resolution_y = 256
bpy.ops.render.render(write_still=True)
