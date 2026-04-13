import streamlit as st
import xml.etree.ElementTree as ET
import math
from io import BytesIO
import zipfile
from datetime import datetime

# --- KONFIGURATION & MAPPING ---
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

def build_solidcam_xml(t, mat_name, vc, fz):
    now = datetime.now()
    d = float(t.get('diameter', 10))
    z = int(float(t.get('teeth', 2)))
    n = int((vc * 1000) / (d * math.pi))
    vf = int(n * z * fz)
    c_id = f"SC_Tool_{t['id'].replace(' ', '_')}"

    # XML Struktur aufbauen
    results = ET.Element("Results")
    proj = ET.SubElement(results, "projectData")
    ET.SubElement(proj, "programmer").text = "Converter_App"
    ET.SubElement(proj, "date").text = now.strftime("%m/%d/%y")
    ET.SubElement(proj, "time").text = now.strftime("%H:%M:%S")

    tools_node = ET.SubElement(results, "Tools", version="1")
    tool = ET.SubElement(tools_node, "Tool")
    ET.SubElement(tool, "units").text = "Metric"
    ET.SubElement(tool, "description").text = t.get('desc', '')
    ET.SubElement(tool, "ident").text = t['id']
    ET.SubElement(tool, "number").text = "1"

    # COMPONENTS
    comps = ET.SubElement(tool, "Components")
    comp = ET.SubElement(comps, "Component", id=c_id, name="Schaftfräser", type="Cutter", subType="END MILL")
    ET.SubElement(comp, "units").text = "Metric"
    
    shape = ET.SubElement(comp, "Shape")
    em = ET.SubElement(shape, "END_MILL")
    ET.SubElement(em, "units").text = "Metric"
    ET.SubElement(em, "diameter", units="0").text = str(d)
    ET.SubElement(em, "cutting_edge_length", units="0").text = str(t.get('cl', '20'))
    ET.SubElement(em, "shoulder_length", units="0").text = str(t.get('sl', '30'))
    ET.SubElement(em, "total_length", units="0").text = str(t.get('tl', '80'))
    ET.SubElement(em, "number_of_teeth").text = str(z)
    ET.SubElement(em, "corner_chamfer", units="0").text = str(t.get('cr', '0'))
    
    # OFFSETS (Wichtig für SolidCAM!)
    offsets = ET.SubElement(tool, "Offsets")
    off = ET.SubElement(offsets, "Offset", connectTo=c_id, name="Schneidenlage")
    ET.SubElement(off, "units").text = "Metric"
    ET.SubElement(off, "cutting").text = "1"
    ET.SubElement(off, "operation_type").text = "Milling"
    ET.SubElement(off, "offset_number", auto="1").text = "1"
    ET.SubElement(off, "radius", auto="1").text = str(d/2)

    # FEEDS AND SPINS
    fs_root = ET.SubElement(tool, "FeedsAndSpins")
    fs = ET.SubElement(fs_root, "FeedAndSpin", name=f"Auto_{mat_name}", connectTo=c_id)
    ET.SubElement(fs, "units").text = "Metric"
    mill = ET.SubElement(fs, "milling")
    ET.SubElement(mill, "FeedRate").text = str(vf)
    ET.SubElement(mill, "SpinRate").text = str(n)
    ET.SubElement(mill, "dir").text = "CW"

    return ET.tostring(results, encoding="UTF-8", xml_declaration=True)

# --- UI LOGIK ---
st.title("🛠 DIN to SolidCAM Converter (V2)")
selected_mat = st.sidebar.selectbox("Material", list(MATERIAL_DATA.keys()))
vc = st.sidebar.number_input("vc", value=MATERIAL_DATA[selected_mat]["vc"])
fz = st.sidebar.number_input("fz", value=MATERIAL_DATA[selected_mat]["fz"], format="%.3f")

uploaded_files = st.file_uploader("DIN XMLs hochladen", type="xml", accept_multiple_files=True)

if uploaded_files:
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zf:
        for f in uploaded_files:
            try:
                # Einfacher Parser für DIN-XML
                tree = ET.parse(f)
                root = tree.getroot()
                props = {}
                for prop in root.findall(".//Property-Data"):
                    n_elem = prop.find("PropertyName")
                    v_elem = prop.find("Value")
                    if n_elem is not None and v_elem is not None:
                        if n_elem.text in DIN_MAP:
                            props[DIN_MAP[n_elem.text]] = v_elem.text.replace(',', '.')
                props['id'] = root.find(".//PrimaryId").text if root.find(".//PrimaryId") is not None else "Unknown"
                
                # XML bauen und ins ZIP
                xml_out = build_solidcam_xml(props, selected_mat, vc, fz)
                zf.writestr(f"{props['id'].replace(' ', '_')}.xml", xml_out)
            except Exception as e:
                st.error(f"Fehler bei {f.name}: {e}")

    st.download_button("📦 Download ZIP", zip_buffer.getvalue(), "SolidCAM_Export.zip", "application/zip")
