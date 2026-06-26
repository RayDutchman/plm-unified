#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
STEP to GLB converter using OpenCASCADE (via cadquery-ocp).

Usage:
    python3 convert_step_glb.py -i input.stp -o output.glb [--deflection 0.05] [--angular 0.3]

Arguments:
    -i / --inputFile        Path to input STEP file
    -o / --outputFile       Path to output GLB file
    --deflection            Relative chord deflection for triangulation (default: 0.05)
    --angular               Angular deflection in radians (default: 0.3 ~ 17 deg)
    -l / --freeCadLibPath   Ignored (kept for backward compatibility with Java caller)

颜色读取策略
------------
1. XDE ColorTool（适用于 AP203 ed2 等颜色走 product 链路的文件）
2. STEP 文本解析 fallback（适用于 CATIA AP242 / AP214 等颜色走
   STYLED_ITEM presentation 链路的文件）
   支持 COLOUR_RGB 和 DRAUGHTING_PRE_DEFINED_COLOUR 两种颜色类型。
3. 默认灰色 (0.8, 0.8, 0.8)
"""

import sys
import os
import re
import argparse

import numpy as np
import pygltflib

from OCP.STEPCAFControl import STEPCAFControl_Reader
from OCP.XCAFDoc import (
    XCAFDoc_DocumentTool,
    XCAFDoc_ShapeTool,
    XCAFDoc_ColorType,
)
from OCP.TDocStd import TDocStd_Document
from OCP.XCAFApp import XCAFApp_Application
from OCP.TCollection import TCollection_ExtendedString
from OCP.TDF import TDF_LabelSequence
from OCP.Quantity import Quantity_Color
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.BRep import BRep_Tool
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_FACE, TopAbs_SOLID, TopAbs_COMPOUND, TopAbs_COMPSOLID
from OCP.TopoDS import TopoDS_Face
from OCP.gp import gp_Trsf


# ---------------------------------------------------------------------------
# 参数解析
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(description="Convert STEP to GLB")
    parser.add_argument("-i", "--inputFile",      required=True)
    parser.add_argument("-o", "--outputFile",     required=True)
    parser.add_argument("-l", "--freeCadLibPath", default="",
                        help="Ignored (kept for Java caller compatibility)")
    parser.add_argument("--deflection", type=float, default=0.05)
    parser.add_argument("--angular",    type=float, default=0.3)
    return parser.parse_args()


# ---------------------------------------------------------------------------
# 辅助：将 TopoDS_Shape 转型为 TopoDS_Face
# ---------------------------------------------------------------------------

def to_face(shape):
    f = TopoDS_Face()
    f.TShape(shape.TShape())
    f.Location(shape.Location())
    f.Orientation(shape.Orientation())
    return f


# ---------------------------------------------------------------------------
# 读取 STEP（使用 XDE CAF 框架）
# ---------------------------------------------------------------------------

DEFAULT_COLOR = (0.8, 0.8, 0.8)

def read_step(filepath):
    """
    读取 STEP 文件，返回 (doc, shape_tool, color_tool, free_labels)。
    调用方必须保持 doc 存活直到 build_glb 完成。
    """
    app = XCAFApp_Application.GetApplication_s()
    doc = TDocStd_Document(TCollection_ExtendedString("XmlOcaf"))
    app.NewDocument(TCollection_ExtendedString("XmlOcaf"), doc)

    reader = STEPCAFControl_Reader()
    reader.SetColorMode(True)
    reader.SetNameMode(True)
    status = reader.ReadFile(filepath)
    if status.value != 1:
        raise RuntimeError("STEP read failed, status=%s" % status)
    reader.Transfer(doc)

    st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    ct = XCAFDoc_DocumentTool.ColorTool_s(doc.Main())

    labels = TDF_LabelSequence()
    st.GetFreeShapes(labels)

    return doc, st, ct, labels


# ---------------------------------------------------------------------------
# XDE 颜色查询（对 shape 直接查，适用于 AP203 ed2 等标准文件）
# ---------------------------------------------------------------------------

def get_shape_color_xde(ct, shape):
    """
    通过 XDE ColorTool 对 shape 查询颜色。
    返回 (R, G, B) 或 None。
    """
    try:
        if shape.IsNull():
            return None
        col = Quantity_Color()
        if ct.GetColor(shape, XCAFDoc_ColorType.XCAFDoc_ColorSurf, col):
            return (col.Red(), col.Green(), col.Blue())
        if ct.GetColor(shape, XCAFDoc_ColorType.XCAFDoc_ColorGen, col):
            return (col.Red(), col.Green(), col.Blue())
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# STEP 文本解析颜色（fallback，支持 AP242 / AP214）
# ---------------------------------------------------------------------------

# ISO 10303-46 预定义颜色名 → RGB
_PREDEFINED_COLORS = {
    'white':        (1.000, 1.000, 1.000),
    'black':        (0.000, 0.000, 0.000),
    'red':          (1.000, 0.000, 0.000),
    'green':        (0.000, 0.502, 0.000),
    'blue':         (0.000, 0.000, 1.000),
    'yellow':       (1.000, 1.000, 0.000),
    'cyan':         (0.000, 1.000, 1.000),
    'magenta':      (1.000, 0.000, 1.000),
    'light_grey':   (0.800, 0.800, 0.800),
    'medium_grey':  (0.502, 0.502, 0.502),
    'dark_grey':    (0.204, 0.204, 0.204),
}


def parse_step_solid_colors(filepath):
    """
    直接解析 STEP 文本，提取 MANIFOLD_SOLID_BREP 的颜色。

    颜色链路（AP214 / AP242 通用）：
      STYLED_ITEM(item=MANIFOLD_SOLID_BREP)
        → PRESENTATION_STYLE_ASSIGNMENT
          → SURFACE_STYLE_USAGE
            → SURFACE_SIDE_STYLE
              → SURFACE_STYLE_FILL_AREA
                → FILL_AREA_STYLE
                  → FILL_AREA_STYLE_COLOUR
                    → COLOUR_RGB(r,g,b)           [AP214]
                    → DRAUGHTING_PRE_DEFINED_COLOUR('name') [AP242]

    返回按 ADVANCED_BREP_SHAPE_REPRESENTATION 中 solid 顺序排列的
    颜色列表 [(r,g,b) or None, ...]。
    返回 None 表示文件结构不支持或无颜色信息。
    """
    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            raw = f.read()
    except Exception:
        return None

    # 把跨行实体合并为单行，建立 #N -> body 字典
    content = re.sub(r'\s*\n\s*', ' ', raw)
    entity_map = {}
    for m in re.finditer(
            r'(#\d+)\s*=\s*([A-Z_][A-Z_0-9]*\s*\([^;]*\))\s*;',
            content):
        entity_map[m.group(1)] = m.group(2).strip()

    # ---- 1. 收集颜色定义 ----
    color_map = {}  # #N -> (r,g,b)

    for eid, body in entity_map.items():
        if body.startswith('COLOUR_RGB'):
            m = re.search(
                r"COLOUR_RGB\s*\(\s*'[^']*'\s*,"
                r"\s*([\d.Ee+-]+)\s*,\s*([\d.Ee+-]+)\s*,\s*([\d.Ee+-]+)",
                body)
            if m:
                color_map[eid] = (float(m.group(1)),
                                  float(m.group(2)),
                                  float(m.group(3)))
        elif 'PRE_DEFINED_COLOUR' in body:
            # DRAUGHTING_PRE_DEFINED_COLOUR('cyan') 或 PRE_DEFINED_COLOUR('white')
            m = re.search(r"PRE_DEFINED_COLOUR\s*\(\s*'([^']+)'\s*\)", body)
            if m:
                rgb = _PREDEFINED_COLORS.get(m.group(1).strip().lower())
                if rgb:
                    color_map[eid] = rgb

    if not color_map:
        return None  # 文件里没有任何颜色定义

    # ---- 2. 沿颜色链路向上传播 ----
    def propagate(src, prefix):
        """在 entity_map 中找以 prefix 开头、且引用了 src 中某个 key 的实体。"""
        result = {}
        for eid, body in entity_map.items():
            if not body.startswith(prefix):
                continue
            for ref in re.findall(r'#\d+', body):
                if ref in src:
                    result[eid] = src[ref]
                    break
        return result

    fasc = propagate(color_map, 'FILL_AREA_STYLE_COLOUR')
    fas  = propagate(fasc,      'FILL_AREA_STYLE')
    # 去掉被 FILL_AREA_STYLE_COLOUR 误匹配的条目
    fas  = {k: v for k, v in fas.items()
            if not entity_map.get(k, '').startswith('FILL_AREA_STYLE_COLOUR')}
    ssfa = propagate(fas,  'SURFACE_STYLE_FILL_AREA')
    sss  = propagate(ssfa, 'SURFACE_SIDE_STYLE')
    ssu  = propagate(sss,  'SURFACE_STYLE_USAGE')
    psa  = propagate(ssu,  'PRESENTATION_STYLE_ASSIGNMENT')

    if not psa:
        return None

    # ---- 3. STYLED_ITEM → solid 颜色映射 ----
    # STYLED_ITEM('name', (style_refs...), item_ref)
    # item_ref 是最后一个 #N，style_refs 是其余的
    solid_color = {}  # solid_eid -> (r,g,b)

    for eid, body in entity_map.items():
        if not body.startswith('STYLED_ITEM'):
            continue
        refs = re.findall(r'#\d+', body)
        if len(refs) < 2:
            continue
        item_ref   = refs[-1]
        style_refs = refs[:-1]
        if not entity_map.get(item_ref, '').startswith('MANIFOLD_SOLID_BREP'):
            continue
        for sr in style_refs:
            if sr in psa:
                solid_color[item_ref] = psa[sr]
                break

    # ---- 4. 按 ADVANCED_BREP_SHAPE_REPRESENTATION 中的 solid 顺序输出 ----
    ordered = []
    for eid, body in entity_map.items():
        if not body.startswith('ADVANCED_BREP_SHAPE_REPRESENTATION'):
            continue
        for ref in re.findall(r'#\d+', body):
            if entity_map.get(ref, '').startswith('MANIFOLD_SOLID_BREP'):
                ordered.append(solid_color.get(ref))  # None = 未找到颜色
        break  # 通常只有一个 ABSR

    return ordered if ordered else None


# ---------------------------------------------------------------------------
# 收集 (shape, color) 对
# ---------------------------------------------------------------------------

def collect_solid_colors(st, ct, labels, filepath=None):
    """
    遍历 XDE label 树，收集所有叶子 solid 的形状和颜色。

    颜色优先级：
      1. XDE ColorTool（对 shape 直接查）
      2. STEP 文本解析 fallback（filepath 不为 None 时启用）
      3. DEFAULT_COLOR
    """
    result = []  # list of (shape, color_or_None)

    def visit(label, parent_color=None):
        shape = XCAFDoc_ShapeTool.GetShape_s(label)
        color = (get_shape_color_xde(ct, shape)
                 if not shape.IsNull() else None) or parent_color

        referred = TDF_LabelSequence()
        if st.GetComponents_s(label, referred, False):
            for i in range(1, referred.Size() + 1):
                visit(referred.Value(i), color)
        else:
            if not shape.IsNull():
                result.append((shape, color))

    for i in range(1, labels.Size() + 1):
        visit(labels.Value(i))

    # fallback：label 树没找到叶子，直接用顶层 shape
    if not result:
        for i in range(1, labels.Size() + 1):
            shape = XCAFDoc_ShapeTool.GetShape_s(labels.Value(i))
            if not shape.IsNull():
                result.append((shape, get_shape_color_xde(ct, shape)))

    # 判断 XDE 是否成功取到颜色
    if any(c is not None for _, c in result):
        return [(s, c or DEFAULT_COLOR) for s, c in result]

    # ---- XDE 颜色全为 None：尝试 STEP 文本解析 ----
    if filepath:
        text_colors = parse_step_solid_colors(filepath)
        if text_colors is not None:
            # result 可能是单个 compound，需展开为独立 solid 列表
            solids = _expand_to_solids(result)
            if solids:
                pairs = []
                for idx, shape in enumerate(solids):
                    color = (text_colors[idx]
                             if idx < len(text_colors) else None)
                    pairs.append((shape, color or DEFAULT_COLOR))
                return pairs

    return [(s, DEFAULT_COLOR) for s, _ in result]


def _expand_to_solids(shape_color_list):
    """将 compound/compsolid 展开为独立 solid 形状列表。"""
    solids = []
    for shape, _ in shape_color_list:
        if shape.IsNull():
            continue
        stype = shape.ShapeType()
        if stype in (TopAbs_COMPOUND, TopAbs_COMPSOLID):
            exp = TopExp_Explorer(shape, TopAbs_SOLID)
            while exp.More():
                solids.append(exp.Current())
                exp.Next()
        else:
            solids.append(shape)
    return solids


# ---------------------------------------------------------------------------
# 三角化
# ---------------------------------------------------------------------------

def triangulate_shape(shape, deflection, angular):
    """
    三角化 TopoDS_Shape，返回 (vertices_np, indices_np)。
    vertices_np: float32 (N, 3)
    indices_np:  uint32  (M, 3)
    """
    mesh = BRepMesh_IncrementalMesh(shape, deflection, True, angular)
    mesh.Perform()

    all_verts = []
    all_idx   = []
    v_offset  = 0

    exp = TopExp_Explorer(shape, TopAbs_FACE)
    while exp.More():
        face = to_face(exp.Current())
        loc  = face.Location()
        poly = BRep_Tool.Triangulation_s(face, loc)
        if poly is not None:
            trsf = loc.IsIdentity()
            for j in range(1, poly.NbNodes() + 1):
                node = poly.Node(j)
                if not trsf:
                    node = node.Transformed(loc)
                all_verts.extend([float(node.X()),
                                   float(node.Y()),
                                   float(node.Z())])
            for j in range(1, poly.NbTriangles() + 1):
                n1, n2, n3 = poly.Triangle(j).Get()
                all_idx.extend([n1 - 1 + v_offset,
                                 n2 - 1 + v_offset,
                                 n3 - 1 + v_offset])
            v_offset += poly.NbNodes()
        exp.Next()

    if not all_verts:
        return None, None

    return (np.array(all_verts, dtype=np.float32).reshape(-1, 3),
            np.array(all_idx,   dtype=np.uint32).reshape(-1, 3))


# ---------------------------------------------------------------------------
# 构建 GLB
# ---------------------------------------------------------------------------

def build_glb(solid_colors, deflection, angular):
    """
    三角化每个 solid，按颜色分配独立材质，输出 GLTF2 对象。
    """
    meshes_primitives = []
    materials         = []
    accessors         = []
    buffer_views      = []
    byte_data         = bytearray()
    mat_index_map     = {}  # (r,g,b) rounded -> material index

    def get_or_create_material(color):
        key = (round(color[0], 4), round(color[1], 4), round(color[2], 4))
        if key in mat_index_map:
            return mat_index_map[key]
        idx = len(materials)
        materials.append(pygltflib.Material(
            pbrMetallicRoughness=pygltflib.PbrMetallicRoughness(
                baseColorFactor=[key[0], key[1], key[2], 1.0],
                metallicFactor=0.05,
                roughnessFactor=0.7,
            ),
            doubleSided=True,
        ))
        mat_index_map[key] = idx
        return idx

    node_indices = []

    for shape, color in solid_colors:
        verts, idxs = triangulate_shape(shape, deflection, angular)
        if verts is None or len(verts) == 0:
            continue

        mat_idx = get_or_create_material(color)
        verts_b = verts.tobytes()
        idxs_b  = idxs.flatten().tobytes()

        bv_pos = pygltflib.BufferView(
            buffer=0, byteOffset=len(byte_data),
            byteLength=len(verts_b), target=pygltflib.ARRAY_BUFFER)
        byte_data.extend(verts_b)

        bv_idx = pygltflib.BufferView(
            buffer=0, byteOffset=len(byte_data),
            byteLength=len(idxs_b), target=pygltflib.ELEMENT_ARRAY_BUFFER)
        byte_data.extend(idxs_b)

        bv_pos_i = len(buffer_views); buffer_views.append(bv_pos)
        bv_idx_i = len(buffer_views); buffer_views.append(bv_idx)

        acc_pos = pygltflib.Accessor(
            bufferView=bv_pos_i, componentType=pygltflib.FLOAT,
            count=len(verts), type=pygltflib.VEC3,
            max=verts.max(axis=0).tolist(), min=verts.min(axis=0).tolist())
        acc_idx = pygltflib.Accessor(
            bufferView=bv_idx_i, componentType=pygltflib.UNSIGNED_INT,
            count=idxs.size, type=pygltflib.SCALAR)

        acc_pos_i = len(accessors); accessors.append(acc_pos)
        acc_idx_i = len(accessors); accessors.append(acc_idx)

        prim = pygltflib.Primitive(
            attributes=pygltflib.Attributes(POSITION=acc_pos_i),
            indices=acc_idx_i, material=mat_idx, mode=4)
        mesh_i = len(meshes_primitives)
        meshes_primitives.append([prim])
        node_indices.append(pygltflib.Node(mesh=mesh_i))

    if not node_indices:
        return None

    gltf = pygltflib.GLTF2(
        asset=pygltflib.Asset(version="2.0",
                              generator="docdoku-plm-conversion-service"),
        scene=0,
        scenes=[pygltflib.Scene(nodes=list(range(len(node_indices))))],
        nodes=node_indices,
        meshes=[pygltflib.Mesh(primitives=p) for p in meshes_primitives],
        materials=materials,
        accessors=accessors,
        bufferViews=buffer_views,
        buffers=[pygltflib.Buffer(byteLength=len(byte_data))],
    )
    gltf.set_binary_blob(bytes(byte_data))
    return gltf


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

def main():
    args = parse_args()
    input_file  = args.inputFile
    output_file = args.outputFile
    deflection  = args.deflection
    angular     = args.angular

    if not os.path.exists(input_file):
        sys.exit("Error: input file not found: %s" % input_file)

    doc, st, ct, labels = read_step(input_file)
    solid_colors = collect_solid_colors(st, ct, labels, filepath=input_file)

    gltf = build_glb(solid_colors, deflection, angular)
    if gltf is None:
        sys.exit("Error: no geometry generated from %s" % input_file)

    gltf.save_binary(output_file)
    size_kb = os.path.getsize(output_file) / 1024
    print("Converted %s -> %s (%.1f KB, %d solid(s))" % (
        os.path.basename(input_file),
        os.path.basename(output_file),
        size_kb,
        len(solid_colors)))


if __name__ == "__main__":
    main()
