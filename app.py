import streamlit as st
import xml.etree.ElementTree as ET
import math
import re
import zipfile
from io import BytesIO
from datetime import datetime

# --- KONFIGURATION & MAPPING ---
# Zuordnung der DIN 4000 Sachmerkmale zu internen Bezeichnungen
DIN_MAP = {
    "A1": "diameter", 
    "B2": "cl", 
    "B3": "sl", 
    "B5": "tl", 
    "C3": "sd",
    "F21": "teeth", 
    "G2": "cr", 
    "F4": "angle", 
    "J22": "desc",
    "F1": "point_angle"
}

# Standard-Schnittdaten für die Materialauswahl
MATERIAL_DATA = {
    "Aluminium": {"vc": 400, "fz": 0.12},
    "Stahl (St37/St52)": {"vc": 180, "fz": 0.06},
    "Edelstahl (V2A/V4A)": {"vc": 90, "fz": 0.04},
    "Guss (GG25)": {"vc": 140, "fz": 0.08}
}

def clean_float(value_str):
    """Extrahiert Zahlen aus Strings, auch wenn Buchstaben wie 'M3' enthalten sind."""
    if not value_str: return 0.0
    # Sucht nach der ersten Zahl im String (unterstützt Punkt und Komma)
    match = re.search(r"[-+]?\d*\.\d+|\d+", str(value_str).replace(',', '.'))
    return float(match.group()) if match else 0.0

def build_solidcam_xml(t, mat_name, vc, fz):
    """Erzeugt die SolidCAM XML-Struktur für ein einzelnes Werkzeug."""
    now = datetime.now()
    
    # Werte bereinigen
    d = clean_float(t.get('diameter', '10'))
    z = int(clean_float(t.get('teeth', '2')))
    if z < 1: z = 1
    
    # Schnittdaten berechnen
    n = int((vc * 1000) / (d * math.pi)) if d > 0 else 1000
    vf = int(n * z * fz)
    
    c_id = f"SC_Tool_{str(t['id']).replace(' ', '_').replace('/', '_')}"
    stype = t.get('tool_type', 'END_MILL')

    # XML Root mit Namespaces
    results = ET.Element("Results")
    results.set("xmlns:xs", "http://www.w3.org/2001/XMLSchema")
    results.set("xmlns:ext", "http://exslt.org/common")
    
    proj = ET.SubElement(results, "projectData")
    ET.SubElement(proj, "programmer").text = "michael.schmaler"
    ET.SubElement(proj, "date").text = now.strftime("%m/%d/%y")
    ET.SubElement(proj, "time").text = now.strftime("%H:%M:%S")
    ET.SubElement(proj, "vmid_name").text = ""

    tools_node = ET.SubElement(results, "Tools", version="1", machine="")
    tool = ET.SubElement(tools_node, "Tool")
    
    # Basis Werkzeugdaten
    ET.SubElement(tool, "units").text = "Metric"
    ET.SubElement(tool, "catalog_num").text = str(t['id'])
    ET.SubElement(tool, "description").text = str(t.get('desc', ''))
    ET.SubElement(tool, "ident").text = str(t['id'])
    ET.SubElement(tool, "number").text = "1"

    # Komponenten (Geometrie)
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
        ET.SubElement(tool_shape, "corner_chamfer
