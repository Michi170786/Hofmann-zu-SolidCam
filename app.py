import streamlit as st
import xml.etree.ElementTree as ET
import math
from io import BytesIO
import zipfile
from datetime import datetime

# --- KONFIGURATION ---
DIN_MAP = {
    "A1": "diameter", "B2": "cl", "B3": "sl", "B5": "tl", "C3": "sd",
    "F21": "teeth", "G2": "cr", "F4": "angle", "J22": "desc"
}

MATERIAL_DATA = {
    "Aluminium": {"vc": 400, "fz": 0.12},
    "Stahl (St37/St52)": {"vc": 180, "fz": 0.06},
    "Edelstahl (V2A/V4A)": {"vc": 90, "fz": 0.04},
    "Guss (GG25)": {"vc": 140, "fz": 0.08}
}

def create_base_xml():
    results = ET.Element("Results")
    results.set("xmlns:xs", "http://www.w3.org/2001/XMLSchema")
    results.set("xmlns:ext", "http://exslt.org/common")
    proj = ET.SubElement(results, "projectData")
    ET.SubElement(proj, "programmer").text = "michael.schmaler"
    ET.SubElement(proj, "date").text = datetime.now().strftime("%m/%d/%y")
    ET.SubElement(proj, "time").text = datetime.now().strftime("%H:%M:%S")
    ET.SubElement(proj, "vmid_name").text = ""
    return results

def add_feeds_and_spins(tool_node, c_id, mat_name, n, vf):
    fs_root = ET.SubElement(tool_node, "FeedsAndSpins")
    fs = ET.SubElement(fs_root, "FeedAndSpin", name=f"Auto_{mat_name}", connectTo=c_id, app_type="MillTurn")
    ET.SubElement(fs, "units").text = "Metric"
    mill = ET.SubElement(fs, "milling")
    ET.SubElement(mill, "FeedRate").text = str(vf)
    ET.SubElement(mill, "SpinRate").text = str(n)
    ET.SubElement(mill, "dir").text = "CW"

# --- TEMPLATE SCHAFTFRÄSER ---
def build_end_mill(t, mat_name, vc, fz):
    d = float(t.get('diameter', 10)); z = int(float(t.get('teeth', 2)))
    n = int((vc * 1000) / (d * math.pi)); vf = int(n * z * fz)
    c_id = f"SC_Schaftfräser_{t['id'].replace(' ', '_')}"
    
    results = create_base_xml()
    tools_node = ET.SubElement(results, "Tools", version="1", machine="")
    tool = ET.SubElement(tools_node, "Tool")
    ET.SubElement(tool, "units").text = "Metric"
    ET.SubElement(tool, "ident").text = t['id']
    ET.SubElement(tool, "number").text = "1"

    comps = ET.SubElement(tool, "Components")
    comp = ET.SubElement(comps, "Component", id=c_id, name="Schaftfräser", type="Cutter", subType="END MILL")
    shape = ET.SubElement(comp, "Shape")
    em = ET.SubElement(shape, "END_MILL")
    ET.SubElement(em, "units").text = "Metric"
    ET.SubElement(em, "diameter", units="0").text = str(d)
    ET.SubElement(em, "cutting_edge_length", units="0").text = str(t.get('cl', '20'))
    ET.SubElement(em, "total_length", units="0").text = str(t.get('tl', '80'))
    ET.SubElement(em, "number_of_teeth").text = str(z)
    
    offsets = ET.SubElement(tool, "Offsets")
    off = ET.SubElement(offsets, "Offset", connectTo=c_id, name="Schneidenlage")
    ET.SubElement(off, "radius", auto="1").text = str(d/2)
    
    add_feeds_and_spins(tool, c_id, mat_name, n, vf)
    return ET.tostring(results, encoding="UTF-8", xml_declaration=True)

# --- TEMPLATE TORUSFRÄSER ---
def build_bull_nose_mill(t, mat_name, vc, fz):
    d = float(t.get('diameter', 10)); z = int(float(t.get('teeth', 2))); cr = float(t.get('cr', 0))
    n = int((vc * 1000) / (d * math.pi)); vf = int(n * z * fz)
    c_id = f"SC_Torusfräser_{t['id'].replace(' ', '_')}"
    
    results = create_base_xml()
    tools_node = ET.SubElement(results, "Tools", version="1", machine="")
    tool = ET.SubElement(tools_node, "Tool")
    ET.SubElement(tool, "units").text = "Metric"
    ET.SubElement(tool, "ident").text = t['id']
    ET.SubElement(tool, "number").text = "1"

    comps = ET.SubElement(tool, "Components")
    comp = ET.SubElement(comps, "Component", id=c_id, name="Torusfräser", type="Cutter", subType="BULL NOSE MILL")
    shape = ET.SubElement(comp, "Shape")
    bnm = ET.SubElement(shape, "BULL_NOSE_MILL")
    ET.SubElement(bnm, "units").text = "Metric"
    ET.SubElement(bnm, "diameter", units="0").text = str(d)
    ET.SubElement(bnm, "corner_radius", units="0").text = str(cr)
    ET.SubElement(bnm, "cutting_edge_length", units="0").text = str(t.get('cl', '20'))
    ET.SubElement(bnm, "total_length", units="0").text = str(t.get('tl', '80'))
    ET.SubElement(bnm, "shoulder_length", units="0").text = str(t.get('sl', '30'))
    ET.SubElement(bnm, "number_of_teeth").text = str(z)

    offsets = ET.SubElement(tool, "Offsets")
    off = ET.SubElement(offsets, "Offset", connectTo=c_id, name="Schneidenlage")
    ET.SubElement(off, "radius", auto="1").text = str(d/2)

    add_feeds_and_spins(tool, c_id, mat_name, n, vf)
    return ET.tostring(results, encoding="UTF-8", xml_declaration=True)

# --- APP LOGIK ---
st.title("🛠 DIN to SolidCAM (Typ-Separiert)")
selected_mat = st.sidebar.selectbox("Material", list(MATERIAL_DATA.keys()))
vc = st.sidebar.number_input("vc", value=MATERIAL_DATA[selected_mat]["vc"])
fz = st.sidebar.number_input("fz", value=MATERIAL_DATA[selected_mat]["fz"], format="%.3f")

uploaded_files = st.file_uploader("DIN XMLs hochladen", type="xml", accept_multiple_files=True)

if uploaded_files:
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zf:
        for f in uploaded_files:
            try:
                tree = ET.parse(f); root = tree.getroot()
                props = {}
                for prop in root.findall(".//Property-Data"):
                    n_e = prop.find("PropertyName"); v_e = prop.find("Value")
                    if n_e and v_e:
                        if n_e.text in DIN_MAP: props[DIN_MAP[n_e.text]] = v_e.text.replace(',', '.')
                p_id = root.find(".//PrimaryId")
                props['id'] = p_id.text if p_id is not None else f.name.replace('.xml', '')
                
                # ENTSCHEIDUNG WELCHER TYP
                cr_val = float(props.get('cr', 0))
                if cr_val > 0:
                    xml_out
