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

# Configuración enfocada en dispositivos móviles y de escritorio
st.set_page_config(
    page_title="CGM Presupuestos",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Estilos CSS táctiles para móviles
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

# --- FUNCIONES DE CONTROL DE PERSISTENCIA SEGURA ---
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
    try:
        with open(FOLIO_FILE, "w", encoding="utf-8") as f:
            json.dump({"prefijo": prefijo, "numero": numero}, f, indent=4)
    except Exception:
        pass

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
    
    try:
        with open(HISTORIAL_FILE, "w", encoding="utf-8") as f:
            json.dump(historial, f, ensure_ascii=False, indent=4)
    except Exception:
        pass

# --- CATÁLOGO PERMANENTE DE CONCEPTOS ---
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
    titulo = concepto_obj.get("concepto", "").strip()
    if not titulo:
        return False, "La descripción del concepto no puede estar vacía."
    
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
    
    try:
        with open(CATALOGO_FILE, "w", encoding="utf-8") as f:
            json.dump(catalogo, f, ensure_ascii=False, indent=4)
        return True, "Concepto guardado en el catálogo general."
    except Exception as e:
        return False, f"Error al guardar en catálogo: {e}"

def parsear_folio(folio_str):
    match = re.match(r"^(.*?)(-?\d+)$", folio_str)
    if match:
        return match.group(1), int(match.group(2))
    return "GDL-", 763

# --- DETECCIÓN DE LOGO SENSIBLE A LINUX ---
def obtener_ruta_logo():
    try:
        if os.path.exists("."):
            archivos = os.listdir(".")
            for f in archivos:
                f_lower = f.lower()
                if ("cgm" in f_lower or "logo" in f_lower) and f_lower.endswith(('.jpeg', '.jpg', '.png')):
                    return f
    except Exception:
        pass
    return None

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

# --- FORMATOS ---
def formato_pesos(monto: float) -> str:
    return f"$ {monto:,.2f}"

def monto_en_letras_mxn(monto: float) -> str:
    try:
        total_centavos = int(round(monto * 100))
        entero = total_centavos // 100
        centavos = total_centavos % 100
        texto_letras = num2words(entero, lang='es').upper()
        unidad_peso = "PESO" if entero == 1 else "PESOS"
        return f"({texto_letras} {unidad_peso} {centavos:02d}/100 M.N.)"
    except Exception:
        return "(CERO PESOS 00/100 M.N.)"

folio = f"{st.session_state.prefijo_folio}{st.session_state.num_folio}"

if st.session_state.modo_edicion:
    st.warning(f"✏️ Editando Folio: **{st.session_state.folio_editando}**")

# --- INTERFAZ MÓVIL POR PESTAÑAS ---
tab_datos, tab_conceptos, tab_resumen, tab_exportar = st.tabs([
    "📋 Datos", 
    "🏗️ Conceptos", 
    "📊 Resumen", 
    "📤 Guardar / Enviar"
])

# === PESTAÑA 1: DATOS GENERALES ===
with tab_datos:
    st.subheader("Información del Cliente")
    
    col_f1, col_f2 = st.columns([1, 2])
    with col_f1:
        st.text_input("Prefijo", key="prefijo_folio")
    with col_f2:
        st.number_input("Folio Nº", step=1, key="num_folio")
        
    st.text_input("Propietario / Cliente", key="propietario")
    st.text_input("Proyecto", key="proyecto")
    st.text_area("Ubicación", key="ubicacion", height=80)
    
    col_d1, col_d2 = st.columns(2)
    with col_d1:
        st.text_input("WhatsApp Cliente", key="telefono_wa")
        st.text_input("Mi WhatsApp (Copia)", key="telefono_mi_wa")
    with col_d2:
        st.selectbox("Anticipo", ["50%", "35%"], key="anticipo")
        st.date_input("Fecha", key="fecha")
        
    st.number_input("Días Ejecución", step=1, key="dias_ejecucion")
        
    logo_path = obtener_ruta_logo()
    if not logo_path:
        uploaded_logo = st.file_uploader("Cargar Logo", type=["jpg", "png", "jpeg"])
        if uploaded_logo:
            logo_path = uploaded_logo

    with st.expander("📂 Cargar Presupuesto Anterior"):
        historial_guardado = obtener_historial()
        if historial_guardado:
            opciones = {f"{h['folio']} - {h['propietario']}": h for h in historial_guardado}
            seleccion = st.selectbox("Historial:", list(opciones.keys()))
            if st.button("✏️ Cargar para Editar", use_container_width=True):
                cargar_presupuesto_para_editar(opciones[seleccion])
            if st.session_state.modo_edicion:
                if st.button("➕ Crear Nuevo Presupuesto", use_container_width=True):
                    reiniciar_a_nuevo_presupuesto()
        else:
            st.info("No hay presupuestos previos.")

# === PESTAÑA 2: CONCEPTOS Y CATÁLOGO ===
with tab_conceptos:
    st.subheader("Conceptos de Obra")

    catalogo_items = obtener_catalogo()
    with st.expander("📚 **Cargar Concepto desde el Catálogo**"):
        if catalogo_items:
            opciones_cat = {item["concepto"]: item for item in catalogo_items}
            concepto_sel = st.selectbox("Seleccionar concepto predefinido:", list(opciones_cat.keys()))
            if st.button("📥 Insertar Concepto al Presupuesto", use_container_width=True):
                item_data = opciones_cat[concepto_sel]
                st.session_state.conceptos.append({
                    "id": str(uuid.uuid4()),
                    "num": len(st.session_state.conceptos) + 1,
                    "concepto": item_data["concepto"],
                    "unidad": item_data.get("unidad", "M2"),
                    "cantidad": 1.0,
                    "materiales_totales": item_data.get("materiales_totales", 0.0),
                    "materiales": 0.0,
                    "mano_obra": item_data.get("mano_obra", 0.0),
                    "equipo": item_data.get("equipo", 0.0),
                    "indirectos_pct": item_data.get("indirectos_pct", 10.0),
                    "utilidad_pct": item_data.get("utilidad_pct", 10.0),
                    "pu": 0.0
                })
                st.success("¡Concepto agregado!")
                st.rerun()
        else:
            st.info("Aún no tienes conceptos guardados en tu catálogo.")

    def agregar_concepto():
        st.session_state.conceptos.append({
            "id": str(uuid.uuid4()),
            "num": len(st.session_state.conceptos) + 1, 
            "concepto": "", 
            "unidad": "M2", 
            "cantidad": 0.0,
            "materiales_totales": 0.0,
            "materiales": 0.0, 
            "mano_obra": 0.0, 
            "equipo": 0.0,
            "indirectos_pct": 10.0, 
            "utilidad_pct": 10.0, 
            "pu": 0.0
        })

    def eliminar_concepto(idx):
        if len(st.session_state.conceptos) > 1:
            st.session_state.conceptos.pop(idx)

    for i, c in enumerate(st.session_state.conceptos):
        cid = c.get("id", str(i))
        
        st.markdown(f"**Concepto #{i+1}**")
        c["concepto"] = st.text_area(f"Descripción #{i+1}", value=c["concepto"], key=f"desc_{cid}", height=100)
        
        col_u1, col_u2 = st.columns(2)
        with col_u1:
            c["unidad"] = st.text_input(f"Unidad #{i+1}", value=c["unidad"], key=f"u_{cid}")
        with col_u2:
            c["cantidad"] = st.number_input(f"Cantidad #{i+1}", value=float(c["cantidad"]), key=f"cant_{cid}")

        with st.expander(f"📊 Desglose APU ($) - Concepto #{i+1}"):
            mat_tot_default = float(c.get("materiales_totales", float(c.get("materiales", 0.0)) * float(c["cantidad"])))
            
            col_m1, col_m2 = st.columns(2)
            with col_m1:
                c["materiales_totales"] = st.number_input(f"Mat. Totales ($)", value=mat_tot_default, key=f"mat_tot_{cid}")
                c["mano_obra"] = st.number_input(f"Mano Obra U. ($)", value=float(c["mano_obra"]), key=f"mo_{cid}")
                c["equipo"] = st.number_input(f"Equipo U. ($)", value=float(c["equipo"]), key=f"eq_{cid}")
            with col_m2:
                c["indirectos_pct"] = st.number_input(f"Indirectos (%)", value=float(c["indirectos_pct"]), key=f"ind_{cid}")
                c["utilidad_pct"] = st.number_input(f"Utilidad (%)", value=float(c["utilidad_pct"]), key=f"ut_{cid}")
            
            cant_val = float(c["cantidad"])
            mat_unitario = (c["materiales_totales"] / cant_val) if cant_val > 0 else 0.0
            c["materiales"] = mat_unitario
            
            costo_directo_unitario = mat_unitario + c["mano_obra"] + c["equipo"]
            factor_sobrecosto = 1 + ((c["indirectos_pct"] + c["utilidad_pct"]) / 100)
            
            if costo_directo_unitario > 0:
                c["pu"] = costo_directo_unitario * factor_sobrecosto
            else:
                c["pu"] = st.number_input(f"P.U. Venta ($)", value=float(c["pu"]), key=f"pu_manual_{cid}")
            
            importe_concepto = cant_val * c["pu"]
            
            st.markdown(f"""
            - **Mat. Unitario:** {formato_pesos(mat_unitario)}
            - **C.D. Unitario:** {formato_pesos(costo_directo_unitario)}
            - **P.U. Venta:** {formato_pesos(c['pu'])}
            - **Importe Total:** {formato_pesos(importe_concepto)}
            """)
            
            if st.button(f"⭐ Guardar Concepto #{i+1} en Catálogo", key=f"save_cat_{cid}", use_container_width=True):
                ok, msg = guardar_concepto_en_catalogo(c)
                if ok:
                    st.success(msg)
                else:
                    st.error(msg)

        if len(st.session_state.conceptos) > 1:
            st.button(f"🗑️ Eliminar Concepto #{i+1}", key=f"del_{cid}", on_click=eliminar_concepto, args=(i,), use_container_width=True)
        st.divider()

    st.button("➕ Agregar Nuevo Concepto", on_click=agregar_concepto, use_container_width=True)

# === PESTAÑA 3: RESUMEN FINANCIERO ===
costo_directo_total = sum([
    (c.get("materiales_totales", c["materiales"] * c["cantidad"]) + (c["mano_obra"] + c["equipo"]) * c["cantidad"]) 
    for c in st.session_state.conceptos
])
total_venta = sum([c["pu"] * c["cantidad"] for c in st.session_state.conceptos])
ganancia_total = total_venta - costo_directo_total
texto_total_letras = monto_en_letras_mxn(total_venta)

with tab_resumen:
    st.subheader("Resumen General")
    st.metric("Costo Directo Inversión", f"{formato_pesos(costo_directo_total)} M.N.")
    st.metric("Margen (Indirectos + Utilidad)", f"{formato_pesos(ganancia_total)} M.N.")
    st.metric("Total Presupuesto", f"{formato_pesos(total_venta)} M.N.")
    
    st.info(f"**Importe en Letras:**\n{texto_total_letras}")

# --- GENERACIÓN DE PDF SEGURA ---
def generar_pdf(logo_src):
    try:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
        story = []
        styles = getSampleStyleSheet()

        title_style = ParagraphStyle('TitleStyle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10, leading=12)
        body_style = ParagraphStyle('BodyStyle', parent=styles['Normal'], fontName='Helvetica', fontSize=8, leading=10)
        bold_body_style = ParagraphStyle('BoldBodyStyle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8, leading=10)
        center_bold_style = ParagraphStyle('CenterBoldStyle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8, leading=10, alignment=TA_CENTER)
        right_bold_style = ParagraphStyle('RightBoldStyle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8, leading=10, alignment=TA_RIGHT)
        right_body_style = ParagraphStyle('RightBodyStyle', parent=styles['Normal'], fontName='Helvetica', fontSize=8, leading=10, alignment=TA_RIGHT)
        center_body_style = ParagraphStyle('CenterBodyStyle', parent=styles['Normal'], fontName='Helvetica', fontSize=8, leading=10, alignment=TA_CENTER)

        logo_element = None
        if logo_src:
            try:
                if isinstance(logo_src, str) and os.path.exists(logo_src):
                    logo_element = Image(logo_src, width=140, height=60)
                elif hasattr(logo_src, "getvalue"):
                    logo_bytes = io.BytesIO(logo_src.getvalue())
                    logo_element = Image(logo_bytes, width=140, height=60)
            except Exception:
                logo_element = None

        if not logo_element:
            logo_element = Paragraph("<b>CGM</b><br/>GRUPO CONSTRUCTOR", title_style)

        header_left = [
            Paragraph(f"<b>PROPIETARIO:</b> {st.session_state.get('propietario', '')}", body_style),
            Spacer(1, 3),
            Paragraph(f"<b>PROYECTO:</b> {st.session_state.get('proyecto', '')}", body_style),
            Spacer(1, 3),
            Paragraph(f"<b>UBICACIÓN:</b> {st.session_state.get('ubicacion', '')}", body_style),
        ]

        fecha_val = st.session_state.get('fecha', datetime.today().date())
        fecha_str = fecha_val.strftime('%d/%m/%Y') if hasattr(fecha_val, 'strftime') else str(fecha_val)

        header_right = [
            logo_element,
            Spacer(1, 4),
            Paragraph(f"<b>PRESUPUESTO:</b> {folio}", right_bold_style),
            Paragraph(f"<b>FECHA:</b> {fecha_str}", right_body_style),
        ]

        t_header = Table([[header_left, header_right]], colWidths=[350, 202])
        t_header.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP'), ('ALIGN', (1,0), (1,0), 'RIGHT')]))
        story.append(t_header)
        story.append(Spacer(1, 12))

        header_cols = [
            Paragraph("<b>#</b>", center_bold_style),
            Paragraph("<b>CONCEPTO</b>", bold_body_style),
            Paragraph("<b>UNIDAD</b>", center_bold_style),
            Paragraph("<b>CANTIDAD</b>", right_bold_style),
            Paragraph("<b>PRECIO UNITARIO</b>", right_bold_style),
            Paragraph("<b>IMPORTE</b>", right_bold_style)
        ]
        
        table_data = [header_cols]
        for idx, c in enumerate(st.session_state.get("conceptos", [])):
            cant = float(c.get("cantidad", 0.0))
            pu = float(c.get("pu", 0.0))
            imp = cant * pu
            table_data.append([
                Paragraph(str(idx + 1), center_body_style),
                Paragraph(str(c.get("concepto", "")), body_style),
                Paragraph(str(c.get("unidad", "M2")), center_body_style),
                Paragraph(f"{cant:,.2f}", right_body_style),
                Paragraph(f"$ {pu:,.2f}", right_body_style),
                Paragraph(f"$ {imp:,.2f}", right_body_style)
            ])

        table_data.append([
            "", Paragraph("<b>TOTAL SUMA DE ESTE PRESUPUESTO</b>", bold_body_style), "", "", "", Paragraph(f"<b>$ {total_venta:,.2f}</b>", right_bold_style)
        ])

        t_budget = Table(table_data, colWidths=[20, 255, 45, 55, 85, 92])
        t_budget.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#E5E7EB')),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#9CA3AF')),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#F3F4F6')),
        ]))
        story.append(t_budget)
        story.append(Spacer(1, 8))

        story.append(Paragraph(f"<b>{texto_total_letras}</b>", bold_body_style))
        story.append(Spacer(1, 12))

        dias_ejec = st.session_state.get('dias_ejecucion', 5)
        anticipo_val = st.session_state.get('anticipo', '50%')

        notas = f"""<b>NOTAS:</b> EL IMPORTE DE ESTE PRESUPUESTO ES MÁS I.V.A. EN CASO DE REQUERIR FACTURA, ESTE PRESUPUESTO INCLUYE ÚNICAMENTE LO DESCRITO, SE DEBERÁN DE VERIFICAR LOS VOLÚMENES EN SITIO, EL TIEMPO DE EJECUCIÓN DE LOS TRABAJOS ES DE {dias_ejec} DÍAS HÁBILES O MENOS, SE DEPENDERÁ DE LA DISPONIBILIDAD DEL ÁREA, SE REQUIERE UN {anticipo_val} DE ANTICIPO Y EL SALDO CONTRA AVANCES DE OBRA Y/O ENTREGA DE LA MISMA, TODOS LOS TRABAJOS SOLICITADOS NO ENLISTADOS EN ESTE SERÁN COTIZADOS DE MANERA INDEPENDIENTE.<br/><br/>
        <b>INFORMACIÓN BANCARIA:</b><br/>
        A NOMBRE DE: ISRAEL CAMPOS CASTILLO<br/>
        BANCO: BANAMEX<br/>
        CUENTA: 70023399758<br/>
        CLABE INTERBANCARIA: 002691700233997587<br/><br/>
        <b>ATENTAMENTE</b><br/>
        CONSTRUCCIONES GENERALES ACABADOS Y MANTENIMIENTO<br/>
        www.cgmantenimiento.com<br/>
        M. 3316199571<br/>
        info@cgmantenimiento.com"""
        
        story.append(Paragraph(notas, body_style))
        doc.build(story)
        buffer.seek(0)
        return buffer
    except Exception as e:
        st.error(f"Error técnico al generar el archivo PDF: {e}")
        return None

def finalizar_y_guardar():
    registrar_en_historial(
        folio=folio,
        propietario=st.session_state.propietario,
        proyecto=st.session_state.proyecto,
        ubicacion=st.session_state.ubicacion,
        anticipo=st.session_state.anticipo,
        dias_ejecucion=st.session_state.dias_ejecucion,
        fecha=st.session_state.fecha,
        total=total_venta,
        conceptos=st.session_state.conceptos,
        telefono=st.session_state.telefono_wa
    )
    if not st.session_state.modo_edicion:
        siguiente_numero = st.session_state.num_folio + 1
        guardar_folio_siguiente(st.session_state.prefijo_folio, siguiente_numero)
        st.session_state.num_folio = siguiente_numero

def obtener_link_whatsapp(destino_tel, es_copia_personal=False):
    num_limpio = "".join(filter(str.isdigit, str(destino_tel)))
    if len(num_limpio) == 10:
        num_limpio = "52" + num_limpio
    
    encabezado = "📌 *RESPALDO DE PRESUPUESTO GENERADO (COPIA PERSONAL)*" if es_copia_personal else f"Hola *{st.session_state.propietario}*,"
    
    mensaje = (
        f"{encabezado}\n\n"
        f"Cotización de *CGM Grupo Constructor*:\n"
        f"📋 *Folio:* {folio}\n"
        f"🏗️ *Proyecto:* {st.session_state.proyecto}\n"
        f"💵 *Total:* {formato_pesos(total_venta)} M.N.\n\n"
        f"Adjunto encontrarás el archivo PDF detallado."
    )
    mensaje_encoded = urllib.parse.quote(mensaje)
    return f"https://wa.me/{num_limpio}?text={mensaje_encoded}"

# === PESTAÑA 4: FINALIZAR Y ENVIAR ===
with tab_exportar:
    st.subheader("Guardar y Enviar")
    
    pdf_data = generar_pdf(logo_path)
    
    if pdf_data:
        label_btn = f"💾 Guardar Cambios en PDF ({folio})" if st.session_state.modo_edicion else f"📄 Descargar PDF y Registrar ({folio})"
        st.download_button(
            label=label_btn,
            data=pdf_data,
            file_name=f"PRESUPUESTO_{folio}.pdf",
            mime="application/pdf",
            on_click=finalizar_y_guardar,
            use_container_width=True
        )
    else:
        st.warning("Aún no se puede generar el PDF. Verifica que la información de los conceptos esté completa.")
    
    st.divider()
    
    url_wa_cliente = obtener_link_whatsapp(st.session_state.telefono_wa, es_copia_personal=False)
    st.link_button(
        label="💬 1. Enviar por WhatsApp al Cliente",
        url=url_wa_cliente,
        use_container_width=True
    )
    
    st.markdown("<br/>", unsafe_allow_html=True)
    
    url_wa_propio = obtener_link_whatsapp(st.session_state.telefono_mi_wa, es_copia_personal=True)
    st.link_button(
        label="📱 2. Enviar COPIA a mi WhatsApp Personal",
        url=url_wa_propio,
        use_container_width=True
    )