import streamlit as st
import xml.etree.ElementTree as ET
import math
import zipfile
from io import BytesIO
from datetime import datetime

# --- KONFIGURATION ---
DIN_MAP = {
    "A1": "diameter", "B2": "cl", "B3": "sl", "B5": "tl", "C3": "sd",
    "F21": "teeth", "G2": "cr", "F4": "angle", "J22": "desc"
}

MATERIAL_DATA = {
    "Aluminium": {"vc": 400, "fz": 0.12},
    "Stahl": {"vc": 180, "fz": 0.06},
    "Edelstahl": {"vc": 90, "fz": 0.04}
}

def to_f(val, default=0.0):
    """Sicherer Umwandler für Zahlen"""
    try:
        return float(str(val).replace(',', '.'))
    except:
        return default

def build_xml(t, mat_name, vc, fz):
    d = to_f(t.get('diameter', 10.0))
    z = int(to_f(t.get('teeth', 2.0)))
    cr = to_f(t.get('cr', 0.0))
    n = int((vc * 1000) / (d * math.pi)) if d > 0 else 1000
    vf = int(n * z * fz)
    
    is_torus = cr > 0
    stype = "BULL_NOSE_MILL" if is_torus else "END_MILL"
    sname = "BULL NOSE MILL" if is_torus else "END MILL"
    c_id = f"SC_Tool_{str(t['id']).replace(' ', '_')}"

    results = ET.Element("Results")
    results.set("xmlns:xs", "http://www.w3.org/2001/XMLSchema")
    results.set("xmlns:ext", "http://exslt.org/common")
    
    proj = ET.SubElement(results, "projectData")
    ET.SubElement(proj, "programmer").text = "michael.schmaler"
    ET.SubElement(proj, "date").text = datetime.now().strftime("%m/%d/%y")
    
    tools_node = ET.SubElement(results, "Tools", version="1")
    tool = ET.SubElement(tools_node, "Tool")
    ET.SubElement(tool, "ident").text = str(t['id'])
    ET.SubElement(tool, "units").text = "Metric"
    ET.SubElement(tool, "number").text = "1"

    comps = ET.SubElement(tool, "Components")
    comp = ET.SubElement(comps, "Component", id=c_id, type="Cutter", subType=sname)
    shape = ET.SubElement(comp, "Shape")
    stype_node = ET.SubElement(shape, stype)
    ET.SubElement(stype_node, "diameter", units="0").text = str(d)
    if is_torus:
        ET.SubElement(stype_node, "corner_radius", units="0").text = str(cr)
    ET.SubElement(stype_node, "cutting_edge_length", units="0").text = str(to_f(t.get('cl', 20)))
    ET.SubElement(stype_node, "total_length", units="0").text = str(to_f(t.get('tl', 80)))
    ET.SubElement(stype_node, "number_of_teeth").text = str(z)

    offsets = ET.SubElement(tool, "Offsets")
    off = ET.SubElement(offsets, "Offset", connectTo=c_id)
    ET.SubElement(off, "radius", auto="1").text = str(d/2)

    fs_root = ET.SubElement(tool, "FeedsAndSpins")
    fs = ET.SubElement(fs_root, "FeedAndSpin", connectTo=c_id)
    mill = ET.SubElement(fs, "milling")
    ET.SubElement(mill, "FeedRate").text = str(vf)
    ET.SubElement(mill, "SpinRate").text = str(n)

    return ET.tostring(results, encoding="UTF-8", xml_declaration=True)

# --- APP UI ---
st.set_page_config(page_title="DIN to SolidCAM Converter", layout="centered")
st.title("🛠 DIN to SolidCAM (Final Stable)")

mat = st.sidebar.selectbox("Material", list(MATERIAL_DATA.keys()))
vc = st.sidebar.number_input("vc", value=MATERIAL_DATA[mat]["vc"])
fz = st.sidebar.number_input("fz", value=MATERIAL_DATA[mat]["fz"], format="%.3f")

files = st.file_uploader("XML Dateien hochladen", type="xml", accept_multiple_files=True)

if files:
    zip_buffer = BytesIO()
    count = 0
    
    with zipfile.ZipFile(zip_buffer, "w") as zf:
        for f in files:
            try:
                f.seek(0)
                tree = ET.parse(f)
                root = tree.getroot()
                props = {}
                for p in root.findall(".//Property-Data"):
                    n_tag = p.find("PropertyName")
                    v_tag = p.find("Value")
                    if n_tag is not None and v_tag is not None:
                        if n_tag.text in DIN_MAP:
                            props[DIN_MAP[n_tag.text]] = v_tag.text
                
                pid_elem = root.find(".//PrimaryId")
                props['id'] = pid_elem.text if pid_elem is not None else f.name.replace('.xml', '')
                
                xml_out = build_xml(props, mat, vc, fz)
                # Dateiname säubern
                filename = f"{str(props['id']).replace(' ', '_').replace('/', '_')}.xml"
                zf.writestr(filename, xml_out)
                count += 1
            except Exception as e:
                st.error(f"Fehler bei {f.name}: {str(e)}")

    # WICHTIG: Button nur zeigen, wenn mindestens eine Datei erfolgreich war
    if count > 0:
        st.success(f"Erfolgreich {count} Dateien konvertiert.")
        st.download_button(
            label="📦 SolidCAM ZIP herunterladen",
            data=zip_buffer.getvalue(),
            file_name="SolidCAM_Export.zip",
            mime="application/zip"
        )
    else:
    
