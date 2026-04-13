import streamlit as st
import xml.etree.ElementTree as ET
import math
from io import BytesIO
import zipfile
from datetime import datetime

# --- ERWEITERTES MAPPING ---
DIN_MAP = {
    "A1": "diameter", "B2": "cl", "B3": "sl", "B5": "tl", "C3": "sd",
    "F21": "teeth", "G2": "cr", "F4": "angle", "J22": "desc",
    "F1": "point_angle"  # Neu für Bohrer: Spitzenwinkel
}

MATERIAL_DATA = {
    "Aluminium": {"vc": 400, "fz": 0.12},
    "Stahl (St37/St52)": {"vc": 180, "fz": 0.06},
    "Edelstahl (V2A/V4A)": {"vc": 90, "fz": 0.04},
    "Guss (GG25)": {"vc": 140, "fz": 0.08}
}

def build_solidcam_xml(t, mat_name, vc, fz):
    now = datetime.now()
    d = float(t.get('diameter', 10))
    z = int(float(t.get('teeth', 2)))
    n = int((vc * 1000) / (d * math.pi))
    vf = int(n * z * fz)
    c_id = f"SC_Tool_{t['id'].replace(' ', '_')}"
    
    # Typerkennung: DRILL oder END MILL
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
    # subType Mapping für SolidCAM
    sc_subtype = "DRILL" if stype == "DRILL" else "END MILL"
    comp = ET.SubElement(comps, "Component", id=c_id, name="Werkzeug", type="Cutter", subType=sc_subtype)
    
    shape = ET.SubElement(comp, "Shape")
    tool_shape = ET.SubElement(shape, stype) # Erzeugt <END_MILL> oder <DRILL>
    ET.SubElement(tool_shape, "units").text = "Metric"
    ET.SubElement(tool_shape, "diameter", units="0").text = str(d)
    ET.SubElement(tool_shape, "cutting_edge_length", units="0").text = str(t.get('cl', '20'))
    ET.SubElement(tool_shape, "total_length", units="0").text = str(t.get('tl', '80'))
    
    if stype == "DRILL":
        # Spezifisch für Bohrer: Spitzenwinkel (Standard 118 oder 140)
        p_angle = t.get('point_angle', '140').replace('R', '').replace('L', '') # Falls 'R' für Rechtsdrall drinsteht
        ET.SubElement(tool_shape, "point_angle").text = p_angle
    else:
        # Spezifisch für Fräser
        ET.SubElement(tool_shape, "number_of_teeth").text = str(z)
        ET.SubElement(tool_shape, "corner_chamfer", units="0").text = str(t.get('cr', '0'))

    # OFFSETS & FEEDS (Bleiben gleich)
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
st.title("🛠 DIN to SolidCAM Converter (Fräser & Bohrer)")
selected_mat = st.sidebar.selectbox("Material", list(MATERIAL_DATA.keys()))
vc = st.sidebar.number_input("vc", value=MATERIAL_DATA[selected_mat]["vc"])
fz = st.sidebar.number_input("fz", value=MATERIAL_DATA[selected_mat]["fz"], format="%.3f")

uploaded_files = st.file_uploader("DIN XMLs hochladen", type="xml", accept_multiple_files=True)

if uploaded_files:
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zf:
        for f in uploaded_files:
            try:
                tree = ET.parse(f)
                root = tree.getroot()
                props = {}
                # DIN-Typ erkennen
                nsm_val = ""
                for prop in root.findall(".//Property-Data"):
                    n_e = prop.find("PropertyName")
                    v_e = prop.find("Value")
                    if n_e is not None and v_e is not None:
                        p_name = n_e.text
                        p_val = v_e.text.replace(',', '.')
                        if p_name in DIN_MAP: props[DIN_MAP[p_name]] = p_val
                        if p_name == "NSM": nsm_val = p_val
                
                # Zuweisung Typ
                props['tool_type'] = "DRILL" if "4000-81" in nsm_val else "END_MILL"
                props['id'] = root.find(".//PrimaryId").text if root.find(".//PrimaryId") is not None else "Unknown"
                
                xml_out = build_solidcam_xml(props, selected_mat, vc, fz)
                zf.writestr(f"{props['id'].replace(' ', '_')}.xml", xml_out)
            except Exception as e:
                st.error(f"Fehler bei {f.name}: {e}")

    st.download_button("📦 Download ZIP", zip_buffer.getvalue(), "SolidCAM_Tools.zip", "application/zip")
