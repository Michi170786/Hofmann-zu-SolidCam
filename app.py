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
    comp = ET.SubElement(comps, "Component", id=c_id, name="Schaftfräser", type="Cutter", subType="END MILL", c
