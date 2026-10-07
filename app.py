import streamlit as st
import os
import io
import json
import uuid
import re
import urllib.parse
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT
from num2words import num2words

# Configuración enfocado en dispositivos móviles y escritorio
st.set_page_config(
    page_title="CGM Presupuestos",
    layout="centered",
    initial_sidebar_state="collapsed"
)

st.markdown("""
    <style>
    .stButton>button, .stDownloadButton>button, .stLinkButton>a {
        min-height: 3rem;
        font-weight: bold;
        border-radius: 8px;
    }
    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
    }
    </style>
""", unsafe_allow_html=True)

st.title("🏗️ CGM Presupuestos ($ M.N.)")

# --- ARCHIVOS DE PERSISTENCIA ---
FOLIO_FILE = "ultimo_folio.json"
HISTORIAL_FILE = "historial_presupuestos.json"
CATALOGO_FILE = "catalogo_conceptos.json"

# --- FUNCIONES DE CONTROL DE PERSISTENCIA ---
def cargar_folio_guardado():
    if os.path.exists(FOLIO_FILE):
        try:
            with open(FOLIO_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("prefijo", "GDL-"), int(data.get("numero", 763))
        except Exception:
            pass
    return "GDL-", 763

def guardar_folio_siguiente(prefijo: str, numero: int):
    with open(FOLIO_FILE, "w", encoding="utf-8") as f:
        json.dump({"prefijo": prefijo, "numero": numero}, f, indent=4)

def obtener_historial():
    if os.path.exists(HISTORIAL_FILE):
        try:
            with open(HISTORIAL_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def registrar_en_historial(folio: str, propietario: str, proyecto: str, ubicacion: str, anticipo: str, dias_ejecucion: int, fecha, total: float, conceptos: list, telefono: str):
    historial = obtener_historial()
    registro = {
        "folio": folio,
        "propietario": propietario,
        "proyecto": proyecto,
        "ubicacion": ubicacion,
        "anticipo": anticipo,
        "dias_ejecucion": dias_ejecucion,
        "telefono": telefono,
        "fecha": str(fecha),
        "total": total,
        "conceptos": conceptos,
        "fecha_actualizacion": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    historial = [h for h in historial if h.get("folio") != folio]
    historial.append(registro)
    
    with open(HISTORIAL_FILE, "w", encoding="utf-8") as f:
        json.dump(historial, f, ensure_ascii=False, indent=4)

# --- FUNCIONES DE CATÁLOGO REUTILIZABLE DE CONCEPTOS ---
def obtener_catalogo():
    if os.path.exists(CATALOGO_FILE):
        try:
            with open(CATALOGO_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def guardar_concepto_en_catalogo(concepto_obj):
    catalogo = obtener_catalogo()
    # Buscar si ya existe uno con el mismo nombre descriptivo
    titulo = concepto_obj["concepto"].strip()
    if not titulo:
        return False, "La descripción del concepto no puede estar vacía."
    
    # Filtrar existentes para actualizar o agregar
    catalogo = [item for item in catalogo if item.get("concepto", "").strip() != titulo]
    catalogo.append({
        "concepto": titulo,
        "unidad": concepto_obj.get("unidad", "M2"),
        "materiales_totales": concepto_obj.get("materiales_totales", 0.0),
        "mano_obra": concepto_obj.get("mano_obra", 0.0),
        "equipo": concepto_obj.get("equipo", 0.0),
        "indirectos_pct": concepto_obj.get("indirectos_pct", 10.0),
        "utilidad_pct": concepto_obj.get("utilidad_pct", 10.0)
    })
    
    with open(CATALOGO_FILE, "w", encoding="utf-8") as f:
        json.dump(catalogo, f, ensure_ascii=False, indent=4)
    return True, "Concepto guardado en el catálogo con éxito."

def parsear_folio(folio_str):
    match = re.match(r"^(.*?)(-?\d+)$", folio_str)
    if match:
        return match.group(1), int(match.group(2))
    return "GDL-", 763

# --- INICIALIZACIÓN DE ESTADO ---
pref_init, num_init = cargar_folio_guardado()

defaults = {
    'prefijo_folio': pref_init,
    'num_folio': num_init,
    'propietario': "LIC. CARLOS PEREZ Y/O A QUIEN CORRESPONDA",
    'proyecto': "TRABAJOS DE REPARACIONES Y PINTURA CARPRO",
    'ubicacion': "EL SOL 2678, COL. JARDINES DEL BOSQUE, GUADALAJARA, JAL. C.P. 44520",
    'telefono_wa': "3312345678",
    'telefono_mi_wa': "3316199571",
    'anticipo': "50%",
    'dias_ejecucion': 5,
    'fecha': datetime.today().date(),
    'modo_edicion': False,
    'folio_editando': None,
    'conceptos': [{
        "id": str(uuid.uuid4()),
        "num": 1, 
        "concepto": "SUMINISTRO Y APLICACIÓN DE PINTURA VINILICA MCA. COMEX PRO 1000 O SIMILAR EN COLOR BLANCO EN LAS AREAS SELECCIONADAS, INCLUYE MATERIALES, HERRAMIENTA, EQUIPO Y TODO LO NECESARIO PARA SU CORRECTA EJECUCION.", 
        "unidad": "M2", 
        "cantidad": 613.78,
        "materiales_totales": 27620.10,
        "materiales": 45.00, 
        "mano_obra": 25.00, 
        "equipo": 5.00,
        "indirectos_pct": 10.0, 
        "utilidad_pct": 10.0, 
        "pu": 89.60
    }]
}

for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val

def cargar_presupuesto_para_editar(reg):
    pref, num = parsear_folio(reg.get("folio", ""))
    st.session_state["prefijo_folio"] = pref
    st.session_state["num_folio"] = int(num)
    st.session_state["propietario"] = reg.get("propietario", "")
    st.session_state["proyecto"] = reg.get("proyecto", "")
    st.session_state["ubicacion"] = reg.get("ubicacion", "")
    st.session_state["telefono_wa"] = reg.get("telefono", "")
    ant = reg.get("anticipo", "50%")
    st.session_state["anticipo"] = ant if ant in ["50%", "35%"] else "50%"
    st.session_state["dias_ejecucion"] = int(reg.get("dias_ejecucion", 5))
    
    try:
        st.session_state["fecha"] = datetime.strptime(reg.get("fecha"), "%Y-%m-%d").date()
    except Exception:
        st.session_state["fecha"] = datetime.today().date()
        
    conceptos_cargados = reg.get("conceptos", [])
    for c in conceptos_cargados:
        if "id" not in c:
            c["id"] = str(uuid.uuid4())
        if "materiales_totales" not in c:
            c["materiales_totales"] = float(c.get("materiales", 0.0)) * float(c.get("cantidad", 0.0))
            
    st.session_state["conceptos"] = conceptos_cargados
    st.session_state["modo_edicion"] = True
    st.session_state["folio_editando"] = reg.get("folio", "")
    st.rerun()

def reiniciar_a_nuevo_presupuesto():
    pref, num = cargar_folio_guardado()
    st.session_state["prefijo_folio"] = pref
    st.session_state["num_folio"] = int(num)
    st.session_state["propietario"] = "LIC. CARLOS PEREZ Y/O A QUIEN CORRESPONDA"
    st.session_state["proyecto"] = "TRABAJOS DE REPARACIONES Y PINTURA CARPRO"
    st.session_state["ubicacion"] = "EL SOL 2678, COL. JARDINES DEL BOSQUE, GUADALAJARA, JAL. C.P. 44520"
    st.session_state["telefono_wa"] = "3312345678"
    st.session_state["anticipo"] = "50%"
    st.session_state["dias_ejecucion"] = 5
    st.session_state["fecha"] = datetime.today().date()
    st.session_state["conceptos"] = [{
        "id": str(uuid.uuid4()),
        "num": 1, 
        "concepto": "SUMINISTRO Y APLICACIÓN DE PINTURA VINILICA MCA. COMEX PRO 1000 O SIMILAR EN COLOR BLANCO EN LAS AREAS SELECCIONADAS, INCLUYE MATERIALES, HERRAMIENTA, EQUIPO Y TODO LO NECESARIO PARA SU CORRECTA EJECUCION.", 
        "unidad": "M2", 
        "cantidad": 613.78,
        "materiales_totales": 27620.10,
        "materiales": 45.00, 
        "mano_obra": 25.00, 
        "equipo": 5.00,
        "indirectos_pct": 10.0, 
        "utilidad_pct": 10.0, 
        "pu": 89.60
    }]
    st.session_state["modo_edicion"] = False
    st.session_state["folio_editando"] = None
    st.rerun()

#