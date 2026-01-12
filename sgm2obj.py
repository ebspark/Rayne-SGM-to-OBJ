import struct, os, argparse

try:
    import bpy
    from bpy_extras.io_utils import ImportHelper
    IN_BLENDER = True
except ImportError:
    bpy = None
    IN_BLENDER = False

bl_info = {
    "name": "Import Rayne SGM model format",
    "author": ".index",
    "blender": (2, 80, 0),
    "category": "Import",
    "location": "File > Import > Rayne Model (.sgm)",
    "description": "Imports Rayne .sgm files to Blender by converting them to .obj",
    "version": (1, 0, 0),
    "wiki_url": "https://github.com/twhlynch/Rayne-SGM-To-OBJ"
}

if IN_BLENDER:
    class ImportSGM(bpy.types.Operator, ImportHelper):
        bl_idname = "import_scene.sgm"
        bl_label = "Import Rayne Model"

        filename_ext = ".sgm"
        filter_glob: bpy.props.StringProperty(default="*.sgm", options={"HIDDEN"})

        def execute(self, context):
            filepath = self.filepath
            output_file = f"{os.path.splitext(filepath)[0]}.obj"
            data = read_sgm(filepath)
            write_obj(data[0], data[1], output_file)
            if "import_scene.obj" in bpy.ops.__dir__():
                bpy.ops.import_scene.obj(filepath=output_file)
            else:
                bpy.ops.wm.obj_import(filepath=output_file)
            return {"FINISHED"}

def read_sgm(filename):
    with open(filename, "rb") as file:
        #magic number - uint32 - 352658064
        #version - uint8 - 3
        version = struct.unpack('<L B', file.read(5))
        print(version)

        #number of materials - uint8
        num_materials = struct.unpack('<B', file.read(1))[0]
        materials = []
        for _ in range(num_materials):
            #material id - uint8
            material_id = struct.unpack('<B', file.read(1))[0]
            #number of uv sets - uint8
            uv_count = struct.unpack('<B', file.read(1))[0]
            uv_data = []
            for _ in range(uv_count):
                #number of textures - uint8
                image_count = struct.unpack('<B', file.read(1))[0]
                images = []
                for _ in range(image_count):
                    #texture type hint - uint8
                    usage_hint = struct.unpack('<B', file.read(1))[0]
                    #filename length - uint16
                    texname_len = struct.unpack('<H', file.read(2))[0] - 1
                    #filename - char*filename length
                    texname = struct.unpack(f'<{texname_len}s', file.read(texname_len))[0].decode("utf_8")
                    file.seek(1, 1) # skip null terminator
                    images.append((texname, usage_hint))
                uv_data.append(images)
            #number of colors - uint8
            color_count = struct.unpack('<B', file.read(1))[0]
            colors = []
            for _ in range(color_count):
                #color type hint - uint8
                color_id = struct.unpack('<B', file.read(1))[0]
                #color rgba - float32*4
                color = struct.unpack('<ffff', file.read(16))
                colors.append((color, color_id))
            materials.append({
                'material_id': material_id,
                'uv_data': uv_data,
                'colors': colors
            })

        #number of meshes - uint8
        num_meshes = struct.unpack('<B', file.read(1))[0]
        meshes = [] 
        index_offset = 0 # for multiple meshes
        for _ in range(num_meshes):
            vertices = []
            indices = []
            #mesh id - uint8
            mesh_id = struct.unpack('<B', file.read(1))[0]
            #used materials id - uint8
            material_id = struct.unpack('<B', file.read(1))[0]
            #number of vertices - uint32
            vertex_count = struct.unpack('<I', file.read(4))[0]
            #texcoord count - uint8
            uv_count = struct.unpack('<B', file.read(1))[0]
            #color channel count - uint8 usually 0 or 4
            texdata_count = struct.unpack('<B', file.read(1))[0]
            #has tangents - uint8 0 if not, 1 otherwise
            has_tangents = struct.unpack('<B', file.read(1))[0]
            #has bones - uint8 0 if not, 1 otherwise
            has_bones = struct.unpack('<B', file.read(1))[0]
            #interleaved vertex data - float32
            #- position, normal, uvN, color, tangents, weights, bone indices
            for _ in range(vertex_count):
                position = struct.unpack('<fff', file.read(12))
                normal = struct.unpack('<fff', file.read(12))
                uvs = []
                for _ in range(uv_count):
                    uv = struct.unpack('<ff', file.read(8))
                    uvs.append(uv)
                color = None
                if texdata_count == 4:
                    color = struct.unpack('<ffff', file.read(16))
                tangent = None
                if has_tangents:
                    tangent = struct.unpack('<ffff', file.read(16))
                weights = None
                bones = None
                if has_bones:
                    weights = struct.unpack('<ffff', file.read(16))
                    bones = struct.unpack('<ffff', file.read(16))
                vertices.append((position, normal, uvs, color, tangent, weights, bones))
            
            #number of indices - uint32
            index_count = struct.unpack('<I', file.read(4))[0]
            #index size - uint8, usually 2 or 4 bytes
            index_size = struct.unpack('<B', file.read(1))[0]
            #indices - index size
            for _ in range(index_count):
                if index_size == 4:
                    index = struct.unpack('<I', file.read(4))[0]
                else:
                    index = struct.unpack('<H', file.read(2))[0]
                indices.append(index + index_offset)

            index_offset += len(vertices)
            meshes.append({"mesh_id": mesh_id, "material_id": material_id, "vertices": vertices, "indices": indices})
            
    return [meshes, materials]

def write_obj(meshes, materials, filename, texturename = None):
    mtl_filename = f"{os.path.splitext(filename)[0]}.mtl"

    with open(mtl_filename, 'w') as mtl_file:
        for i,m in enumerate(materials):
            material_id = m.get("material_id", f"mat_{i}")
            mtl_file.write(f"newmtl {material_id}\n")
            if m.get("colors"):
                color = m["colors"][0]
                r, g, b, a = color[0]
            else:
                r, g, b, a = 0.8, 0.8, 0.8, 1.0  # default grey
            uv_data = m.get("uv_data", [])
            mtl_file.write(f"Kd {r} {g} {b}\n")
            mtl_file.write(f"d {a}\n")
            if len(meshes[i]["vertices"][0][2]) > 0:
                if texturename is None:
                    for uv_images in uv_data:
                        for texname, _ in uv_images:
                            mtl_file.write(f"map_Kd {texname}\n")
                else:
                    mtl_file.write(f"map_Kd {texturename}\n")

    with open(filename, 'w') as f:
        f.write(f'mtllib {os.path.basename(mtl_filename)}\n')
        for (i,m) in enumerate(meshes):
            print(f"Working on mesh {i}")
            f.write(f"o {m['mesh_id']}\n")
            if m["material_id"] is not None and m["material_id"] < len(materials):
                f.write(f'usemtl {materials[m["material_id"]].get("material_id", "default")}\n')
            else:
                f.write('usemtl default\n')
            vertices = m["vertices"]
            indices = m["indices"]
            for v in vertices:
                f.write(f'v {v[0][0]} {v[0][1]} {v[0][2]}\n')
                f.write(f'vn {v[1][0]} {v[1][1]} {v[1][2]}\n')
                if v[2] is None or len(v[2]) == 0:
                    print(f"no uv: {v}")
                    f.write(f'vt 0 0\n')
                else:
                    f.write(f'vt {v[2][0][0]} {1-v[2][0][1]}\n')
            for i in range(0, len(indices), 3):
                if len(m["vertices"][0][2]) > 0:
                    f.write(f'f {indices[i] + 1}/{indices[i] + 1}/{indices[i] + 1} {indices[i + 1] + 1}/{indices[i + 1] + 1}/{indices[i + 1] + 1} {indices[i + 2] + 1}/{indices[i + 2] + 1}/{indices[i + 2] + 1}\n')
                else:
                    f.write(f'f {indices[i] + 1}//{indices[i] + 1} {indices[i + 1] + 1}//{indices[i + 1] + 1} {indices[i + 2] + 1}//{indices[i + 2] + 1}\n')

def menu_func_import(self, context):
    self.layout.operator(ImportSGM.bl_idname, text="Rayne Model (.sgm)")

def register():
    bpy.utils.register_class(ImportSGM)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)

def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    bpy.utils.unregister_class(ImportSGM)

def main():
    parser = argparse.ArgumentParser(description='Convert SGM to OBJ format')
    parser.add_argument('input_file', type=str, help='path to input file')
    parser.add_argument('output_file', nargs='?', type=str, help='path to output file')
    parser.add_argument('--texture', type=str, help='name of texture file if there is only one texture')
    args = parser.parse_args()

    input_file = args.input_file
    output_file = args.output_file
    if args.output_file is None:
        output_file = f'{os.path.splitext(args.input_file)[0]}.obj'
    else:
        output_file = args.output_file
    texture = args.texture

    data = read_sgm(input_file)
    write_obj(data[0], data[1], output_file, texture)

if __name__ == "__main__":
    if IN_BLENDER:
        register()
    else:
        main()
