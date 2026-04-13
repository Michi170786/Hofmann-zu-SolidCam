import streamlit as st
import xml.etree.ElementTree as ET
import math
import re
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

def clean_float(value_str, fallback=0.0):
    """Extrahiert Zahlen aus Strings (hilft bei 'M3' oder '12,5')"""
    if not value_str: return fallback
    match = re.search(r"[-+]?\d*\.\d+|\d+", str(value_str).replace(',', '.'))
    return float(match.group()) if match else fallback

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
    ET.SubElement(mill, "FeedRate").text = str(int(vf))
    ET.SubElement(mill, "SpinRate").text = str(int(n))
    ET.SubElement(mill, "dir").text = "CW"

# --- TEMPLATES ---
def build_tool_xml(t, mat_name, vc, fz):
    d = clean_float(t.get('diameter', 10))
    z = int(clean_float(t.get('teeth', 2)))
    cr = clean_float(t.get('cr', 0))
    
    n = (vc * 1000) / (d * math.pi) if d > 0 else 1000
    vf = n * z * fz
    
    is_torus = cr > 0
    sub_type = "BULL NOSE MILL" if is_torus else "END MILL"
    shape_tag = "BULL_NOSE_MILL" if is_torus else "END_MILL"
    
    c_id = f"SC_Tool_{str(t['id']).replace(' ', '_')}"
    results = create_base_xml()
    tools_node = ET.SubElement(results, "Tools", version="1", machine="")
    tool = ET.SubElement(tools_node, "Tool")
    ET.SubElement(tool, "units").text = "Metric"
    ET.SubElement(tool, "ident").text = str(t['id'])
    ET.SubElement(tool, "number").text = "1"

    comps = ET.SubElement(tool, "Components")
    comp = ET.SubElement(comps, "Component", id=c_id, name=sub_type, type="Cutter", subType=sub_type)
    shape = ET.SubEleme
