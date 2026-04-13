import streamlit as st
import xml.etree.ElementTree as ET
import math
import re
from io import BytesIO
import zipfile
from datetime import datetime

# --- ERWEITERTES MAPPING ---
DIN_MAP = {
    "A1": "diameter", "B2": "cl", "B3": "sl", "B5": "tl", "C3": "sd",
    "F21": "teeth", "G2": "cr", "F4": "angle", "J22": "desc",
    "F1": "point_angle"
}

MATERIAL_DATA = {
    "Aluminium": {"vc": 400, "fz": 0.12},
    "Stahl (St37/St52)": {"vc": 180, "fz": 0.06},
    "Edelstahl (V2A/V4A)": {"vc": 90, "fz": 0.04},
    "Guss (GG25)": {"vc": 140, "fz": 0.08}
}

def clean_float(value_str):
    """Extrahiert die erste Zahl aus einem String (z.B. 'M3' -> 3.0)"""
    if not value_str: return 0.0
    # Entfernt alles außer Zahlen und Punkt/Komma
    match = re.search(r"[-+]?\d*\.\d+|\d+", value_str.replace(',', '.'))
    return float(match.group()) if match else 0.0

def build_solidcam_xml(t, mat_name, vc, fz):
    now = datetime.now()
    d = clean_float(t.get('diameter', '10'))
    z = int(clean_float(t.get('teeth', '2')))
    n = int((vc * 1000) / (d * math.pi)) if d > 0 else 1000
    vf = int(n * z * fz)
    c_id = f"SC_Tool_{t['id'].replace(' ', '_')}"
    
    stype = t.get('tool_type', 'END_MILL')

    results = ET.Element("Results")
    results.set("xmlns:xs", "http://www.w3.org/2001/XMLSchema")
    results.set("xmlns:ext", "http://exslt.org/common")
    
    proj = ET.SubElement(results, "projectData")
    ET.SubElement(proj, "programmer").text = "michael.schmaler"
    ET.SubElement(proj, "date").text = now.strftime("%m/%d/%y")
    ET.SubElement(proj, "time").text = now.strftime("%H:%M:%S")

    tools_node = ET.SubElement(results, "Tools", version="1", machine="")
    tool = ET.SubElement(tools_node, "Tool")
    ET.SubElement(tool, "units").text = "Metric"
    ET.SubElement(tool, "ident").text = t['id']
    ET.SubElement(tool, "description").text = t.get('desc', '')
    ET.SubElement(tool, "number").text = "1"

    comps = ET.SubElement(tool, "Components")
    sc_subtype = "DRILL" if stype == "DRILL" else "END MILL"
    comp = ET.SubElement(comps, "Component", id=c_id, name="Werkzeug", type="Cutter", subType=sc_subtype)
    
    shape = ET.SubElement(comp, "Shape")
    tool_shape = ET.SubElement(shape, stype)
    ET.SubElement(tool_shape, "units").text = "Metric"
    ET.SubElement(tool_shape, "diameter", units="0").text = str(d)
    ET.SubElement(tool_shape, "cutting_edge_length", units="0").text = str(t.get('cl', '20'))
    ET.SubElement(tool_shape, "total_length", units="0").text = str(t.get('tl', '80'))
    
    if stype == "DRILL":
        p_angle = str(clean_float(t.get('point_angle', '140')))
        ET.SubElement(tool_shape, "point_angle").text = p_angle
    else:
        ET.SubElement(tool_shape, "number_of_teeth").text = str(z)
        ET.SubElement(tool_shape, "corner_chamfer", units="0").text = str(t.get('cr', '0'))

    offsets = ET.SubElement(tool, "Offsets")
    off = ET.SubElement(offsets, "Offset", connectTo=c_id, name="Schneidenlage")
    ET.SubElement(off, "units").text = "Metric"
    ET.SubElement(off, "radius", auto="1").text = str(d/2)

    fs_root = ET.SubElement(tool, "FeedsAndSpins")
    fs = ET.SubElement(fs_root, "FeedAndSpin", name=f"Auto_{mat_name}", connectTo=c_id)
    mill = ET.SubElement(fs, "milling")
    ET.SubElement(mill, "FeedRate").text = str(vf)
    ET.SubElement(mill, "SpinRate").text = str(n)
    ET.SubElement(mill, "dir").text = "CW"

    return ET.tostring(results, encoding="UTF-8", xml_declaration=True)

# --- UI & PARSER ---
st.title("🛠 DIN to SolidCAM (Robust Version)")
selected_mat = st.sidebar.selectbox("Material", list(MATERIAL_DATA.keys()))
vc = st.sidebar.nu
