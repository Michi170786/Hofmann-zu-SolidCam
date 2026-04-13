import streamlit as st
import xml.etree.ElementTree as ET
import math
import re
import zipfile
from io import BytesIO
from datetime import datetime

# --- KONFIGURATION & MAPPING ---
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
    if not value_str: return 0.0
    match = re.search(r"[-+]?\d*\.\d+|\d+", str(value_str).replace(',', '.'))
    return float(match.group()) if match else 0.0

def build_solidcam_xml(t, mat_name, vc, fz):
    now = datetime.now()
    d = clean_float(t.get('diameter', '10'))
    z = int(clean_float(t.get('teeth', '2')))
    if z < 1: z = 1
    
    n = int((vc * 1000) / (d * math.pi)) if d > 0 else 1000
    vf = int(n * z * fz)
    
    c_id = f"SC_Tool_{str(t['id']).replace(' ', '_').replace('/', '_')}"
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
    ET.SubElement(tool, "catalog_num").text = str(t['id'])
    ET.SubElement(tool, "description").text = str(t.get('desc', ''))
    ET.SubElement(tool, "ident").text = str(t['id'])
    ET.SubElement(tool, "number").text = "1"

    comps = ET.SubElement(tool, "Components")
    sc_subtype = "DRILL" if stype == "DRILL" else "END MILL"
    comp = ET.SubElement(comps, "Component", id=c_id, name="Werkzeug", type="Cutter", subType=sc_subtype)
    ET.SubElement(comp, "units").text = "Metric"
    ET.SubElement(comp, "manufacturer").text = "HOG"
    
    shape = ET.SubElement(comp, "Shape")
    tool_shape = ET.SubElement(shape, stype)
    ET.SubElement(tool_shape, "units").text = "Metric"
    ET.SubElement(tool_shape, "diameter", units="0").text = str(d)
    ET.SubElement(tool_shape, "cutting_edge_length", units="0").text = str(clean_float(t.get('cl', '20')))
    ET.SubElement(tool_shape, "total_length", units="0").text = str(clean_float(t.get('tl', '80')))
    ET.SubElement(tool_shape, "shoulder_length", units="0").text = str(clean_float(t.get('sl', '30')))
    
    if stype == "DRILL":
        p_angle = str(clean_float(t.get('point_angle', '140')))
        ET.SubElement(tool_shape, "point_angle").text = p_angle
    else:
        ET.SubElement(tool_shape, "number_of_teeth").text = str(z)
        ET.SubElement(tool_shape, "corner_chamfer", units="0").text = str(clean_float(t.get('cr', '0')))

    offsets = ET.SubElement(tool, "Offsets")
    off = ET.SubElement(offsets, "Offset", connectTo=c_id, name="Schneidenlage")
    ET.SubElement(off, "units").text = "Metric"
    ET.SubElement(off, "cutting").text = "1"
    ET.SubElement(off, "operation_type").text = "Milling"
    ET.SubElement(off, "offset_number", auto="1").text = "1"
    ET.SubElement(off, "radius", auto="1").text = str(d/2)

    fs_root = ET.SubElement(tool, "FeedsAndSpins")
    fs = ET.SubElement(fs_root, "FeedAndSpin", name=f"Auto_{mat_name}", connectTo=c_id, app_type="MillTurn")
    ET.SubElement(fs, "units").text = "Metric"
    mill = ET.SubElement(fs, "milling")
    ET.SubElement(mill, "FeedRate").text = str(vf)
    ET.SubElement(mill, "SpinRate").text = str(n)
    ET.SubElement(mill, "dir").text = "CW"

    return ET.tostring(results, encoding="UTF-8", xml_declaration=True)

# --- UI ---
st.set_page_config(page_title="DIN-SolidCAM Converter")
st.title("🛠 DIN 4000 to SolidCAM Converter")

st.sidebar.header("Schnittdaten-Setup")
selected_mat = st.sidebar.selectbox("Material", list(MATERIAL_DATA.keys()))
vc_in = st.sidebar.number_input("vc", value=MATERIAL_DATA[selected_mat]["vc"])
fz_in = st.sidebar.number_input("fz", value=MATERIAL_DATA[selected_mat]["fz"], format="%.3f")

uploaded_files = st.file_uploader("XML Dateien hochladen", type="xml", accept_multiple_files=True)

if uploaded_files:
    zip_buffer = BytesIO()
    count = 0
    with zipfile.ZipFile(zip_buffer, "w") as zf:
        for f in uploaded_files:
            try:
                f.seek(0)
                tree = ET.parse(f)
                root = tree.getroot()
                props = {}
                nsm_val = ""
                for prop in root.findall(".//Property-Data"):
                    n_e = prop.find("PropertyName"); v_e = prop.find("Value")
                    if n_e is not None and v_e is not None:
                        if n_e.text in DIN_MAP: props[DIN_MAP[n_e.text]] = v_e.text
                        if n_e.text == "NSM": nsm_val = v_e.text
                props['tool_type'] = "DRILL" if "4000-81" in nsm_val else "END_MILL"
                p_id = root.find(".//PrimaryId")
                props['id'] = p_id.text if p_id is not None else f.name.replace('.xml', '')
                xml_out = build_solidcam_xml(props, selected_mat, vc_in, fz_in)
                zf.writestr(f"{props['id'].replace(' ', '_')}.xml", xml_out)
                count += 1
            except Exception as e:
                st.error(f"Fehler bei {f.name}: {e}")
    if count > 0:
        st.success(f"{count} Werkzeuge bereit!")
        st.download_button("📦 Download ZIP", zip_buffer.getvalue(), "SolidCAM_Export.zip", "application/zip")
