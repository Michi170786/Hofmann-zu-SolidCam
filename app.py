import streamlit as st
import xml.etree.ElementTree as ET
import math
import pandas as pd
from io import BytesIO
import zipfile
from datetime import datetime

# --- KONFIGURATION & MAPPING ---
DIN_MAP = {
    "A1": "diameter",
    "B2": "cutting_length",
    "B3": "shoulder_length",
    "B5": "total_length",
    "C3": "shank_diameter",
    "F21": "teeth",
    "G2": "corner_radius",
    "F4": "helical_angle",
    "J22": "description"
}

MATERIAL_DATA = {
    "Aluminium": {"vc": 400, "fz": 0.12},
    "Stahl (St37/St52)": {"vc": 180, "fz": 0.06},
    "Edelstahl (V2A/V4A)": {"vc": 90, "fz": 0.04},
    "Guss (GG25)": {"vc": 140, "fz": 0.08}
}

def calculate_feeds(d, z, vc, fz):
    if d <= 0: return 0, 0
    n = int((vc * 1000) / (d * math.pi))
    vf = int(n * z * fz)
    return n, vf

def parse_din_xml(file_content):
    tree = ET.parse(BytesIO(file_content))
    root = tree.getroot()
    props = {}
    for prop in root.findall(".//Property-Data"):
        name = prop.find("PropertyName").text
        val = prop.find("Value").text.replace(',', '.')
        if name in DIN_MAP:
            props[DIN_MAP[name]] = val
    props['id'] = root.find(".//PrimaryId").text if root.find(".//PrimaryId") is not None else "Unknown"
    props['manufacturer'] = root.find(".//Manufacturer").text if root.find(".//Manufacturer") is not None else "HOG"
    props['teeth'] = int(float(props.get('teeth', 1)))
    props['diameter'] = float(props.get('diameter', 0))
    
    # Typerkennung anhand NSM (Bohrer vs Fräser)
    nsm = root.find(".//Property-Data[PropertyName='NSM']/Value")
    props['subType'] = "DRILL" if nsm is not None and "4000-81" in nsm.text else "END MILL"
    return props

def build_single_solidcam_xml(t, material_name, material_params):
    now = datetime.now()
    results = ET.Element("Results")
    proj = ET.SubElement(results, "projectData")
    ET.SubElement(proj, "date").text = now.strftime("%m/%d/%y")
    
    tools_node = ET.SubElement(results, "Tools", version="1")
    n, vf = calculate_feeds(t['diameter'], t['teeth'], material_params['vc'], material_params['fz'])
    
    tool = ET.SubElement(tools_node, "Tool")
    ET.SubElement(tool, "number").text = "1"
    ET.SubElement(tool, "description").text = t.get('description', '')
    ET.SubElement(tool, "ident").text = t['id']
    
    comps = ET.SubElement(tool, "Components")
    c_id = f"SC_Tool_{t['id'].replace(' ', '_')}"
    comp = ET.SubElement(comps, "Component", id=c_id, name=t['subType'], type="Cutter", subType=t['subType'])
    
    shape = ET.SubElement(comp, "Shape")
    stype = ET.SubElement(shape, t['subType'])
    ET.SubElement(stype, "diameter").text = str(t['diameter'])
    ET.SubElement(stype, "cutting_edge_length").text = t.get('cutting_length', '10')
    ET.SubElement(stype, "total_length").text = t.get('total_length', '50')
    ET.SubElement(stype, "number_of_teeth").text = str(t['teeth'])
    
    fs_root = ET.SubElement(tool, "FeedsAndSpins")
    fs = ET.SubElement(fs_root, "FeedAndSpin", name=f"Auto_{material_name}", connectTo=c_id)
    mill = ET.SubElement(fs, "milling")
    ET.SubElement(mill, "FeedRate").text = str(vf)
    ET.SubElement(mill, "SpinRate").text = str(n)
    
    return ET.tostring(results, encoding="UTF-8", xml_declaration=True)

# --- UI ---
st.title("🛠 DIN to SolidCAM (Einzel-Dateien)")

st.sidebar.header("Schnittdaten")
selected_mat = st.sidebar.selectbox("Material", list(MATERIAL_DATA.keys()))
vc = st.sidebar.number_input("vc", value=MATERIAL_DATA[selected_mat]["vc"])
fz = st.sidebar.number_input("fz", value=MATERIAL_DATA[selected_mat]["fz"], format="%.3f")

uploaded_files = st.file_uploader("DIN XMLs hochladen", type="xml", accept_multiple_files=True)

if uploaded_files:
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
        for f in uploaded_files:
            try:
                data = parse_din_xml(f.read())
                sc_xml = build_single_solidcam_xml(data, selected_mat, {"vc": 
