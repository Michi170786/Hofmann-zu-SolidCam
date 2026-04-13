import streamlit as st
import xml.etree.ElementTree as ET
import math
import pandas as pd
from io import BytesIO
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

# Schnittdaten-Vorgaben (Demo-Werte)
MATERIAL_DATA = {
    "Aluminium": {"vc": 400, "fz": 0.12},
    "Stahl (St37/St52)": {"vc": 180, "fz": 0.06},
    "Edelstahl (V2A/V4A)": {"vc": 90, "fz": 0.04},
    "Guss (GG25)": {"vc": 140, "fz": 0.08},
    "Werkzeugstahl (gehärtet)": {"vc": 60, "fz": 0.03}
}

def calculate_feeds(d, z, vc, fz):
    if d <= 0: return 0, 0
    n = round((vc * 1000) / (d * math.pi), 0)
    vf = round(n * z * fz, 0)
    return int(n), int(vf)

def parse_din_xml(file_content):
    tree = ET.parse(BytesIO(file_content))
    root = tree.getroot()
    props = {}
    
    # Extrahiere alle DIN Sachmerkmale
    for prop in root.findall(".//Property-Data"):
        name = prop.find("PropertyName").text
        val = prop.find("Value").text.replace(',', '.')
        if name in DIN_MAP:
            props[DIN_MAP[name]] = val
            
    # Metadaten
    props['id'] = root.find(".//PrimaryId").text if root.find(".//PrimaryId") is not None else "Unknown"
    props['manufacturer'] = root.find(".//Manufacturer").text if root.find(".//Manufacturer") is not None else "HOG"
    
    # Default Werte falls Felder fehlen
    props['teeth'] = int(float(props.get('teeth', 1)))
    props['diameter'] = float(props.get('diameter', 0))
    return props

def build_solidcam_xml(tools_list, material_name, material_params):
    now = datetime.now()
    results = ET.Element("Results")
    
    # Project Data Header
    proj = ET.SubElement(results, "projectData")
    ET.SubElement(proj, "programmer").text = "Converter_App"
    ET.SubElement(proj, "date").text = now.strftime("%m/%d/%y")
    ET.SubElement(proj, "time").text = now.strftime("%H:%M:%S")
    
    tools_node = ET.SubElement(results, "Tools", version="1")
    
    for i, t in enumerate(tools_list):
        n, vf = calculate_feeds(t['diameter'], t['teeth'], material_params['vc'], material_params['fz'])
        
        tool = ET.SubElement(tools_node, "Tool")
        ET.SubElement(tool, "number").text = str(i + 1)
        ET.SubElement(tool, "description").text = t.get('description', '')
        ET.SubElement(tool, "ident").text = t['id']
        
        # Components
        comps = ET.SubElement(tool, "Components")
        c_id = f"SC_Tool_{t['id']}"
        comp = ET.SubElement(comps, "Component", id=c_id, name="Schaftfräser", type="Cutter", subType="END MILL")
        ET.SubElement(comp, "manufacturer").text = t['manufacturer']
        
        # Shape
        shape = ET.SubElement(comp, "Shape")
        em = ET.SubElement(shape, "END_MILL")
        ET.SubElement(em, "diameter").text = str(t['diameter'])
        ET.SubElement(em, "cutting_edge_length").text = t.get('cutting_length', '10')
        ET.SubElement(em, "total_length").text = t.get('total_length', '50')
        ET.SubElement(em, "shoulder_length").text = t.get('shoulder_length', '20')
        ET.SubElement(em, "number_of_teeth").text = str(t['teeth'])
        ET.SubElement(em, "corner_chamfer").text = t.get('corner_radius', '0')
        
        # Feeds and Spins
        fs_root = ET.SubElement(tool, "FeedsAndSpins")
        fs = ET.SubElement(fs_root, "FeedAndSpin", name=f"Auto_{material_name}", connectTo=c_id)
        mill = ET.SubElement(fs, "milling")
        ET.SubElement(mill, "FeedRate").text = str(vf)
        ET.SubElement(mill, "SpinRate").text = str(n)
        ET.SubElement(mill, "dir").text = "CW"
        
    return ET.tostring(results, encoding="UTF-8", xml_declaration=True)

# --- STREAMLIT UI ---
st.set_page_config(page_title="SolidCAM DIN Converter", page_icon="⚙️")
st.title("⚙️ DIN 4000 to SolidCAM Converter")

# 1. Sidebar für Einstellungen
st.sidebar.header("Schnittdaten-Setup")
selected_mat = st.sidebar.selectbox("Werkstück-Material", list(MATERIAL_DATA.keys()))
custom_vc = st.sidebar.number_input("Schnittgeschwindigkeit (vc)", value=MATERIAL_DATA[selected_mat]["vc"])
custom_fz = st.sidebar.number_input("Vorschub pro Zahn (fz)", value=MATERIAL_DATA[selected_mat]["fz"], format="%.3f")

# 2. Upload
uploaded_files = st.file_uploader("DIN XML-Dateien hochladen", type="xml", accept_multiple_files=True)

if uploaded_files:
    parsed_tools = []
    for f in uploaded_files:
        try:
            tool_data = parse_din_xml(f.read())
            parsed_tools.append(tool_data)
        except Exception as e:
            st.error(f"Fehler in Datei {f.name}: {e}")

    if parsed_tools:
        st.subheader("Vorschau der erkannten Werkzeuge")
        df = pd.DataFrame(parsed_tools)
        st.dataframe(df[['id', 'diameter', 'teeth', 'description']])

        # 3. Download
        final_params = {"vc": custom_vc, "fz": custom_fz}
        output_xml = build_solidcam_xml(parsed_tools, selected_mat, final_params)
        
        st.download_button(
            label="💾 SolidCAM Bibliothek (.xml) herunterladen",
            data=output_xml,
            file_name=f"SolidCAM_Lib_{selected_mat}.xml",
            mime="application/xml"
        )
        st.success(f"{len(parsed_tools)} Werkzeuge konvertiert für {selected_mat}!")
