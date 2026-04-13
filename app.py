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
    if not val: return default
    try:
        return float(str(val).replace(',', '.'))
    except:
        return default

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

def add_feeds_spins(tool_node, c_id, mat_name, n, vf):
    fs_root = ET.SubElement(tool_node, "FeedsAndSpins")
    fs = ET.SubElement(fs_root, "FeedAndSpin", name=f"Auto_{mat_name}", connectTo=c_id, app_type="MillTurn")
    ET.SubElement(fs, "units").text = "Metric"
    mill = ET.SubElement(fs, "milling")
    ET.SubElement(mill, "FeedRate").text = str(int(vf))
    ET.SubElement(mill, "SpinRate").text = str(int(n))
    ET.SubElement(mill, "dir").text = "CW"

# --- TEMPLATE SCHAFTFRÄSER ---
def build_end_mill(t, mat_name, vc, fz):
    d = to_f(t.get('diameter', 10.0))
    z = int(to_f(t.get('teeth', 2.0)))
    n = (vc * 1000) / (d * math.pi) if d > 0 else 1000
    vf = n * z * fz
    c_id = f"SC_Tool_{str(t['id']).replace(' ', '_')}"
    
    results = create_base_xml()
    tools_node = ET.SubElement(results, "Tools", version="1", machine="")
    tool = ET.SubElement(tools_node, "Tool")
    ET.SubElement(tool, "units").text = "Metric"
    ET.SubElement(tool, "catalog_num").text = str(t['id'])
    ET.SubElement(tool, "ident").text = str(t['id'])
    ET.SubElement(tool, "number").text = "1"

    comps = ET.SubElement(tool, "Components")
    comp = ET.SubElement(comps, "Component", id=c_id, name="Schaftfräser", type="Cutter", subType="END MILL", connectedTo="", connectedJoint="")
    ET.SubElement(comp, "units").text = "Metric"
    
    shape = ET.SubElement(comp, "Shape")
    em = ET.SubElement(shape, "END_MILL")
    ET.SubElement(em, "units").text = "Metric"
    ET.SubElement(em, "arbor_diameter", units="0").text = str(to_f(t.get('sd', d)))
    ET.SubElement(em, "cutting_edge_length", units="0").text = str(to_f(t.get('cl', 20)))
    ET.SubElement(em, "diameter", units="0").text = str(d)
    ET.SubElement(em, "shoulder_diameter", units="0").text = str(to_f(t.get('sd', d)))
    ET.SubElement(em, "shoulder_length", units="0").text = str(to_f(t.get('sl', 30)))
    ET.SubElement(em, "total_length", units="0").text = str(to_f(t.get('tl', 80)))
    ET.SubElement(em, "number_of_teeth").text = str(z)

    offsets = ET.SubElement(tool, "Offsets")
    off = ET.SubElement(offsets, "Offset", connectTo=c_id, name="Schneidenlage")
    ET.SubElement(off, "units").text = "Metric"
    ET.SubElement(off, "radius", auto="1").text = str(d/2)

    add_feeds_spins(tool, c_id, mat_name, n, vf)
    return ET.tostring(results, encoding="UTF-8", xml_declaration=True)

# --- TEMPLATE TORUSFRÄSER ---
def build_bull_nose_mill(t, mat_name, vc, fz):
    d = to_f(t.get('diameter', 10.0))
    cr = to_f(t.get('cr', 0.0))
    z = int(to_f(t.get('teeth', 2.0)))
    n = (vc * 1000) / (d * math.pi) if d > 0 else 1000
    vf = n * z * fz
    c_id = f"SC_Tool_{str(t['id']).replace(' ', '_')}"
    
    results = create_base_xml()
    tools_node = ET.SubElement(results, "Tools", version="1", machine="")
    tool = ET.SubElement(tools_node, "Tool")
    ET.SubElement(tool, "units").text = "Metric"
    ET.SubElement(tool, "catalog_num").text = str(t['id'])
    ET.SubElement(tool, "ident").text = str(t['id'])
    ET.SubElement(tool, "number").text = "1"

    comps = ET.SubElement(tool, "Components")
    comp = ET.SubElement(comps, "Component", id=c_id, name="Torusfräser", type="Cutter", subType="BULL NOSE MILL", connectedTo="", connectedJoint="")
    ET.SubElement(comp, "units").text = "Metric"
    
    shape = ET.SubElement(comp, "Shape")
    bnm = ET.SubElement(shape, "BULL_NOSE_MILL")
    ET.SubElement(bnm, "units").text = "Metric"
    ET.SubElement(bnm, "arbor_diameter", units="0").text = str(to_f(t.get('sd', d)))
    ET.SubElement(bnm, "cutting_edge_length", units="0").text = str(to_f(t.get('cl', 20)))
    ET.SubElement(bnm, "diameter", units="0").text = str(d)
    ET.SubElement(bnm, "corner_radius", units="0").text = str(cr)
    ET.SubElement(bnm, "shoulder_diameter", units="0").text = str(to_f(t.get('sd', d)))
    ET.SubElement(bnm, "shoulder_length", units="0").text = str(to_f(t.get('sl', 30)))
    ET.SubElement(bnm, "total_length", units="0").text = str(to_f(t.get('tl', 80)))
    ET.SubElement(bnm, "number_of_teeth").text = str(z)

    offsets = ET.SubElement(tool, "Offsets")
    off = ET.SubElement(offsets, "Offset", connectTo=c_id, name="Schneidenlage")
    ET.SubElement(off, "units").text = "Metric"
    ET.SubElement(off, "radius", auto="1").text = str(d/2)

    add_feeds_spins(tool, c_id, mat_name, n, vf)
    return ET.tostring(results, encoding="UTF-8", xml_declaration=True)

# --- APP UI ---
st.title("🛠 DIN to SolidCAM (Logic Fix: Radius >= 0.3)")
mat = st.sidebar.selectbox("Material", list(MATERIAL_DATA.keys()))
vc = st.sidebar.number_input("vc", value=MATERIAL_DATA[mat]["vc"])
fz = st.sidebar.number_input("fz", value=MATERIAL_DATA[mat]["fz"], format="%.3f")

files = st.file_uploader("XML hochladen", type="xml", accept_multiple_files=True)

if files:
    zip_buffer = BytesIO()
    count = 0
    with zipfile.ZipFile(zip_buffer, "w") as zf:
        for f in files:
            try:
                tree = ET.parse(f); root = tree.getroot()
                props = {}
                for p in root.findall(".//Property-Data"):
                    n_tag = p.find("PropertyName"); v_tag = p.find("Value")
                    if n_tag is not None and v_tag is not None:
                        if n_tag.text in DIN_MAP: props[DIN_MAP[n_tag.text]] = v_tag.text
                pid_elem = root.find(".//PrimaryId")
                props['id'] = pid_elem.text if pid_elem is not None else f.name.replace('.xml', '')
                
                # ENTSCHEIDUNG LOGIK: Radius >= 0.3 mm -> Torus
                cr_val = to_f(props.get('cr', 0.0))
                
                if cr_val >= 0.3:
                    xml_out = build_bull_nose_mill(props, mat, vc, fz)
                else:
                    xml_out = build_end_mill(props, mat, vc, fz)
                
                zf.writestr(f"{str(props['id']).replace(' ', '_').replace('/', '_')}.xml", xml_out)
                count += 1
            except Exception as e:
                st.error(f"Fehler bei {f.name}: {e}")
    
    if count > 0:
        st.success(f"{count} Werkzeuge bereit.")
        st.download_button("📦 Download ZIP", zip_buffer.getvalue(), "SolidCAM_Export.zip", "application/zip")
