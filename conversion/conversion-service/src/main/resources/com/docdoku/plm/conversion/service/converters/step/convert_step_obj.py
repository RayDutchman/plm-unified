# -*- coding: utf-8 -*-
from optparse import OptionParser
import sys
import os
import re

parser = OptionParser()
parser.add_option("-l", "--freeCadLibPath", dest="l", help="")
parser.add_option("-i", "--inputFile",      dest="i", help="")
parser.add_option("-o", "--outputFile",     dest="o", help="")

(options, args) = parser.parse_args()

freeCadLibPath = options.l
inputFile      = options.i
outputFile     = options.o

sys.path.append(freeCadLibPath)

import FreeCAD
import Part, Mesh


# ---------------------------------------------------------------------------
# Parse STEP colors
# ---------------------------------------------------------------------------

def parse_step_colors(step_path):
    """
    Extract per-body colors from a STEP file.

    STEP color chain (CATIA AP214/AP242):
      STYLED_ITEM -> PRESENTATION_STYLE_ASSIGNMENT
        -> SURFACE_STYLE_USAGE -> SURFACE_STYLE_FILL_AREA
          -> FILL_AREA_STYLE -> FILL_AREA_STYLE_COLOUR -> COLOUR_RGB

    Returns:
      color_map : { brep_name_upper: (R, G, B) }
      fallback  : (R, G, B) or None
    """
    with open(step_path, 'r') as f:
        content = f.read()

    # Remove block comments
    content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)

    # Build entity dict  { '#123': ('TYPE', 'args_string') }
    entity_re = re.compile(
        r'(#\d+)\s*=\s*([A-Z_]+)\s*\(([^;]*)\)\s*;', re.DOTALL
    )
    entities = {}
    for m in entity_re.finditer(content):
        entities[m.group(1)] = (m.group(2), m.group(3).strip())

    def get(eid):
        return entities.get(eid, (None, None))

    def all_refs(args):
        return re.findall(r'(#\d+)', args)

    # Entity types that are known to contain color refs (not terminal, not geometry)
    # Using a broad approach: any entity that is not a geometry type gets traversed.
    GEOMETRY_TYPES = {
        'CARTESIAN_POINT', 'DIRECTION', 'VECTOR', 'AXIS2_PLACEMENT_3D',
        'PLANE', 'CYLINDRICAL_SURFACE', 'CONICAL_SURFACE', 'TOROIDAL_SURFACE',
        'SPHERICAL_SURFACE', 'B_SPLINE_SURFACE_WITH_KNOTS', 'RATIONAL_B_SPLINE_SURFACE',
        'ADVANCED_FACE', 'FACE_BOUND', 'FACE_OUTER_BOUND', 'EDGE_LOOP',
        'ORIENTED_EDGE', 'EDGE_CURVE', 'VERTEX_POINT', 'LINE', 'CIRCLE',
        'ELLIPSE', 'B_SPLINE_CURVE_WITH_KNOTS', 'MANIFOLD_SOLID_BREP',
        'SHELL_BASED_SURFACE_MODEL', 'BREP_WITH_VOIDS', 'OPEN_SHELL',
        'CLOSED_SHELL', 'SHAPE_REPRESENTATION', 'PRODUCT', 'PRODUCT_DEFINITION',
        'PRODUCT_DEFINITION_SHAPE', 'SHAPE_DEFINITION_REPRESENTATION',
        'NEXT_ASSEMBLY_USAGE_OCCURRENCE', 'PRODUCT_CATEGORY',
        'APPLICATION_CONTEXT', 'PRODUCT_CONTEXT', 'PRODUCT_DEFINITION_CONTEXT',
        'MECHANICAL_CONTEXT', 'DESIGN_CONTEXT',
    }

    _color_cache = {}

    def resolve_color(eid, depth=0):
        """
        Recursively walk entity refs to find COLOUR_RGB.
        Stops at geometry-type entities and at depth > 10 to avoid cycles.
        """
        if depth > 10:
            return None
        if eid in _color_cache:
            return _color_cache[eid]

        etype, eargs = get(eid)
        if etype is None:
            return None

        if etype == 'COLOUR_RGB':
            nums = re.findall(r'[\d.E+\-]+', eargs)
            floats = []
            for x in nums:
                try:
                    floats.append(float(x))
                except ValueError:
                    pass
            result = (floats[0], floats[1], floats[2]) if len(floats) >= 3 else None
            _color_cache[eid] = result
            return result

        # Skip geometry entities to avoid false positives
        if etype in GEOMETRY_TYPES:
            _color_cache[eid] = None
            return None

        # For all styling/presentation entities, follow all refs
        result = None
        for ref in all_refs(eargs):
            c = resolve_color(ref, depth + 1)
            if c:
                result = c
                break
        _color_cache[eid] = result
        return result

    # STYLED_ITEM('label', (style_list), item_ref)
    styled_re = re.compile(
        r'#\d+\s*=\s*STYLED_ITEM\s*\(\s*\'[^\']*\'\s*,\s*\(([^)]*)\)\s*,\s*(#\d+)\s*\)',
        re.DOTALL
    )

    # BREP-level entity types (whole-body granularity)
    BREP_TYPES = {
        'MANIFOLD_SOLID_BREP', 'BREP_WITH_VOIDS',
        'SHELL_BASED_SURFACE_MODEL', 'SURFACE_MODEL',
        'ADVANCED_BREP_SHAPE_REPRESENTATION',
    }

    color_map = {}  # brep_name.upper() -> (R,G,B)
    fallback  = None

    for sm in styled_re.finditer(content):
        style_list_str = sm.group(1)
        item_ref       = sm.group(2)

        # Resolve color from style references
        color = None
        for sref in re.findall(r'#\d+', style_list_str):
            color = resolve_color(sref)
            if color:
                break
        if color is None:
            continue

        if fallback is None:
            fallback = color

        itype, iargs = get(item_ref)
        if itype in BREP_TYPES:
            # Extract BREP label (first string argument)
            name_m = re.match(r"\s*'([^']*)'", iargs)
            if name_m:
                brep_name = name_m.group(1).strip()
                if brep_name:
                    color_map[brep_name.upper()] = color

    return color_map, fallback


# ---------------------------------------------------------------------------
# Write OBJ + MTL
# ---------------------------------------------------------------------------

def write_obj_with_materials(doc_objects, obj_path, mtl_path, color_map, fallback):
    """
    Export each FreeCAD document object as a separate OBJ group with its own
    material referencing the parsed color.  Returns True on success.
    """
    mtl_name = os.path.basename(mtl_path)
    tmp_dir  = os.path.dirname(obj_path)

    def find_color(obj_name):
        """Match FreeCAD object name to a BREP color."""
        key = obj_name.upper()
        if key in color_map:
            return color_map[key]
        # Fuzzy: FreeCAD may replace spaces/special chars with underscores
        norm_key = re.sub(r'[^A-Z0-9]', '_', key)
        for brep_name, color in color_map.items():
            norm_brep = re.sub(r'[^A-Z0-9]', '_', brep_name)
            if norm_key == norm_brep or norm_key in norm_brep or norm_brep in norm_key:
                return color
        return fallback

    # Gather objects with shapes
    obj_list = [(o, find_color(o.Name)) for o in doc_objects if hasattr(o, 'Shape')]
    if not obj_list:
        return False

    # Deduplicate colors -> material names
    seen_colors = {}  # (R,G,B) -> mat_name
    mtl_lines   = []

    def get_mat(color):
        c = color if color else (0.8, 0.8, 0.8)
        if c not in seen_colors:
            mat_id = 'mat_%d' % len(seen_colors)
            seen_colors[c] = mat_id
            mtl_lines.append('newmtl ' + mat_id)
            # Ka = Kd for consistent color under all lighting conditions
            mtl_lines.append('Ka %.6f %.6f %.6f' % c)
            mtl_lines.append('Kd %.6f %.6f %.6f' % c)
            mtl_lines.append('Ks 0.050000 0.050000 0.050000')
            mtl_lines.append('Ns 10.0')
            mtl_lines.append('d 1.0')
            mtl_lines.append('')
        return seen_colors[c]

    # Export each object's mesh to a temp file, then merge
    all_vertices   = []
    all_normals    = []
    all_obj_blocks = []
    vertex_offset  = 0
    normal_offset  = 0

    for obj, color in obj_list:
        mat_name = get_mat(color)
        tmp_obj  = os.path.join(tmp_dir, '_tmp_' + obj.Name + '.obj')

        try:
            Mesh.export([obj], tmp_obj)
        except Exception:
            continue

        if not os.path.exists(tmp_obj):
            continue

        with open(tmp_obj, 'r') as f:
            lines = f.readlines()
        os.remove(tmp_obj)

        verts   = [l for l in lines if l.startswith('v ')]
        normals = [l for l in lines if l.startswith('vn ')]
        faces   = [l for l in lines if l.startswith('f ')]
        if not verts or not faces:
            continue

        all_vertices.extend(verts)
        all_normals.extend(normals)

        # Re-index face vertices and normals with global offsets
        adjusted = []
        for fl in faces:
            parts = fl.strip().split()
            new_parts = [parts[0]]
            for p in parts[1:]:
                segs = p.split('/')
                # vertex index (always present)
                segs[0] = str(int(segs[0]) + vertex_offset)
                # normal index: position 2 in v/vt/vn format, or position 1 in v//vn
                if len(segs) == 3 and segs[2]:
                    segs[2] = str(int(segs[2]) + normal_offset)
                new_parts.append('/'.join(segs))
            adjusted.append(' '.join(new_parts) + '\n')

        all_obj_blocks.append(
            ['g ' + obj.Name + '\n',
             'usemtl ' + mat_name + '\n']
            + adjusted
        )
        vertex_offset += len(verts)
        normal_offset += len(normals)

    if not all_vertices:
        return False

    # Write MTL
    with open(mtl_path, 'w') as f:
        f.write('\n'.join(mtl_lines))

    # Write merged OBJ (vertices, then normals, then grouped faces)
    with open(obj_path, 'w') as f:
        f.write('# Created by FreeCAD with color support\n')
        f.write('mtllib ' + mtl_name + '\n')
        f.writelines(all_vertices)
        f.writelines(all_normals)
        for block in all_obj_blocks:
            f.writelines(block)

    return True


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def explodeOBJS():
    if not inputFile or not outputFile:
        sys.exit(2)

    # Parse STEP colors
    color_map, fallback = parse_step_colors(inputFile)

    # Open STEP in FreeCAD
    Part.open(inputFile)
    doc = FreeCAD.ActiveDocument

    # No color info -> fall back to original single-mesh export
    if not color_map and fallback is None:
        Mesh.export(doc.Objects, outputFile)
        return

    base     = os.path.splitext(outputFile)[0]
    mtl_path = base + '.mtl'

    success = write_obj_with_materials(
        doc.Objects, outputFile, mtl_path, color_map, fallback
    )

    # Fall back to plain export if color export failed
    if not success:
        Mesh.export(doc.Objects, outputFile)


if __name__ == "__main__":
    explodeOBJS()
