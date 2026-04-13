import streamlit as st
import xml.etree.ElementTree as ET
import math
import re
import zipfile
from io import BytesIO
from datetime import datetime

# --- CONFIG ---
DIN_MAP = {
    "A1": "diameter", "B2": "cl", "B3": "sl", "B5": "tl", "C3": "sd",
    "F21": "teeth", "G2": "cr", "F4": "angle", "J22": "desc", "F1": "point_angle"
}

MATERIAL_DATA = {
    "Aluminium": {"vc": 400, "fz": 0.12},
    "Stahl": {"vc": 180, "fz": 0.06},
    "Edelstahl": {"vc": 90, "fz": 0.04}
}

def clean_float(value_str, fallback=0.0):
    if not value_str: return fallback
    match = re.search(r"[-+]?\d*\.\d+|\d+", str(value_str).replace(',', '.'))
    return float(match.group()) if match else fallback

def build_solidcam_xml(t, mat_name, vc, fz):
    now = datetime.now()
    # Falls Durchmesser 0 ist, versuche ihn aus der ID zu extrahieren (z.B. M3 -> 3.0)
    d = clean_float(t.get('diameter'))
    if d == 0: d = clean_float(t.get('id'), 10.0)
    
    z = int(clean_float(t.get('teeth'), 3))
    n = int((vc * 1000) / (d * math.pi)) if d > 0 else 1000
    vf = int(n * z * fz)
    c_id = f"SC_Tool_{str(t['id']).replace(' ', '_').replace('/', '_')}"
    
    # Typerkennung für Gewindebohrer
    stype = t.get('tool_type', 'END_MILL')
    desc_low = t.get('desc', '').lower()
    if "gewinde" in desc_low or "tap" in desc_low or " m" in str(t['id']).lower():
        stype = "TAP"

    results = ET.Element("Results")
    results.set("xmlns:xs", "http://www.w3.org/2001/XMLSchema")
    results.set("xmlns:ext", "http://exslt.org/common")
    
    proj = ET.SubElement(results, "projectData")
    ET.SubElement(proj, "programmer").text = "michael.schmaler"
    ET.SubElement(proj, "date").text = now.strftime("%m/%d/%y")
    ET.SubElement(proj, "time").text = now.strftime("%H:%M:%S")

    tools_node = ET.SubElement(results, "Tools", version="1")
    tool = ET.SubElement(tools_node, "Tool")
    ET.SubElement(tool, "units").text = "Metric"
    ET.SubElement(tool, "catalog_num").text = str(t['id'])
    ET.SubElement(tool, "description").text = str(t.get('desc', ''))
    ET.SubElement(tool, "ident").text = str(t['id'])
    ET.SubElement(tool, "number").text = "1"

    comps = ET.SubElement(tool, "Components")
    comp = ET.SubElement(comps, "Component", id=c_id, name="Werkzeug", type="Cutter", subType=stype.replace('_', ' '))
    ET.SubElement(comp, "units").text = "Metric"
    
    shape = ET.SubElement(comp, "Shape")
    tool_shape = ET.SubElement(shape, stype)
    ET.SubElement(tool_shape, "units").text = "Metric"
    ET.SubElement(tool_shape, "diameter", units="0").text = str(d)
    ET.SubElement(tool_shape, "cutting_edge_length", units="0").text = str(clean_float(t.get('cl', 20)))
    ET.SubElement(tool_shape, "total_length", units="0").text = str(clean_float(t.get('tl', 80)))
    
    if stype == "TAP":
        ET.SubElement(tool_shape, "pitch").text = "0.5" # Standard für M3, CAM passt das meist an
    elif stype == "DRILL":
        ET.SubElement(tool_shape, "point_angle").text = str(clean_float(t.get('point_angle', 140)))
    else:
        ET.SubElement(tool_shape, "number_of_teeth").text = str(z)

    offsets = ET.SubElement(tool, "Offsets")
    off = ET.SubElement(offsets, "Offset", connectTo=c_id, name="Schneidenlage")
    ET.SubElement(off, "units").text = "Metric"
    ET.SubElement(off, "radius", auto="1").text = str(d/2)

    fs_root = ET.SubElement(tool, "FeedsAndSpins")
    fs = ET.SubElement(fs_root, "FeedAndSpin", name=f"Auto_{mat_name}", connectTo=c_id)
    mill = ET.SubElement(fs, "milling")
    ET.SubElement(mill, "FeedRate").text = str(vf)
    ET.SubElement(mill, "SpinRate").text = str(n)

    return ET.tostring(results, encoding="UTF-8", xml_declaration=True)

# --- UI ---
st.title("🛠 DIN to SolidCAM (Tap & Drill Support)")
uploaded_files = st.file_uploader("XML hochladen", type="xml", accept_multiple_files=True)
selected_mat = st.sidebar.selectbox("Material", list(MATERIAL_DATA.keys()))

if uploaded_files:
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zf:
        for f in uploaded_files:
            try:
                tree = ET.parse(f)
                root = tree.getroot()
                props = {}
                nsm = ""
                for prop in root.findall(".//Property-Data"):
                    n_e = prop.find("PropertyName"); v_e = prop.find("Value")
                    if n_e is not None and v_e is not None:
                        if n_e.text in DIN_MAP: props[DIN_MAP[n_e.text]] = v_e.text
                        if n_e.text == "NSM": nsm = v_e.text
                props['tool_type'] = "DRILL" if "4000-81" in nsm else "END_MILL"
                p_id = root.find(".//PrimaryId")
                props['id'] = p_id.text if p_id is not None else f.name
                xml_out = build_solidcam_xml(props, selected_mat, MATERIAL_DATA[selected_mat]['vc'], MATERIAL_DATA[selected_mat]['fz'])
                zf.writestr(f"{props['id'].replace(' ', '_')}.xml", xml_out)
            except Exception as e: st.error(f"Error {f.name}: {e}")
    st.download_button("📦 Download ZIP", zip_buffer.getvalue(), "SolidCAM_Export.zip")
