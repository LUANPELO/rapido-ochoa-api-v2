"""
API REST para rastreo de encomiendas de Rápido Ochoa
Scraping HTTP directo (sin Selenium) - v3.0.0
"""

import re
import logging
from datetime import datetime
from typing import List, Optional

import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_URL = (
    "https://rapidoochoa.tmsolutions.com.co/tmland/faces/public/"
    "tmland-carga/cotizador_envios.xhtml?parametroInicial=cmFwaWRvb2Nob2E="
)
POST_URL = (
    "https://rapidoochoa.tmsolutions.com.co/tmland/faces/public/"
    "tmland-carga/cotizador_envios.xhtml"
)
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}

# ── Modelos ───────────────────────────────────────────────────────────────────

class EventoTrazabilidad(BaseModel):
    fecha: str
    detalle: str
    sede: str
    estado: Optional[str] = None

class Producto(BaseModel):
    empaque: str
    dice_contener: str
    unidades: str
    peso_cobrar: str

class DatosEncomienda(BaseModel):
    numero_guia: str
    documento_anexo: Optional[str] = None
    fecha_admision: str
    origen: str
    destino: str
    remitente_nombre: str
    destinatario_nombre: str
    productos: List[Producto] = []
    total_unidades: Optional[str] = None
    trazabilidad: List[EventoTrazabilidad] = []
    estado_actual: str
    fecha_consulta: str

class ConsultaRequest(BaseModel):
    numero_guia: str

# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_viewstate(html: str) -> Optional[str]:
    match = re.search(r'javax\.faces\.ViewState[^>]*value="([^"]+)"', html)
    return match.group(1) if match else None

def _get_viewstate_from_response(text: str) -> Optional[str]:
    match = re.search(
        r'id="j_id__v_0:javax\.faces\.ViewState:1"[^>]*>.*?<!\[CDATA\[([^\]]+)\]\]>',
        text, re.DOTALL,
    )
    return match.group(1) if match else None

def _label(soup: BeautifulSoup, id_: str) -> str:
    el = soup.find("label", id=id_)
    return el.get_text(strip=True) if el else ""

def _panel_nombre(soup: BeautifulSoup, *panel_ids) -> str:
    """Busca 'Nombre: X' dentro de cualquiera de los panel_ids dados."""
    for pid in panel_ids:
        panel = soup.find(id=pid)
        if not panel:
            continue
        for lbl in panel.find_all("label"):
            t = lbl.get_text(strip=True)
            if t.startswith("Nombre:"):
                return t.replace("Nombre:", "").strip()
    return ""

# ── Scraper ───────────────────────────────────────────────────────────────────

def consultar_guia(numero_guia: str, timeout: int = 20) -> DatosEncomienda:
    try:
        session = requests.Session()
        session.headers.update(HEADERS)

        # Paso 1: GET inicial
        r1 = session.get(BASE_URL, timeout=timeout)
        r1.raise_for_status()
        view_state = _get_viewstate(r1.text)
        if not view_state:
            raise HTTPException(status_code=500, detail="No se encontró ViewState en el sitio")

        # Paso 2: Activar tab "Rastreo de envíos"
        # El form_entrega no existe en el HTML inicial; se carga al cambiar de tab.
        r2 = session.post(POST_URL, data={
            "javax.faces.partial.ajax": "true",
            "javax.faces.source": "tabpane",
            "javax.faces.partial.execute": "tabpane",
            "javax.faces.partial.render": "tabpane",
            "javax.faces.behavior.event": "tabChange",
            "javax.faces.partial.event": "tabChange",
            "tabpane_activeIndex": "1",
            "tabpane_newTab": "tabpane:j_id_1l",
            "tabpane": "tabpane",
            "tabpane:j_id_m_SUBMIT": "1",
            "javax.faces.ViewState": view_state,
        }, timeout=timeout)
        r2.raise_for_status()
        view_state2 = _get_viewstate_from_response(r2.text) or view_state

        # Paso 3: Consultar la guía (evento keyup)
        r3 = session.post(POST_URL, data={
            "javax.faces.partial.ajax": "true",
            "javax.faces.source": "tabpane:form_entrega:codigoguia",
            "javax.faces.partial.execute": "tabpane:form_entrega",
            "javax.faces.partial.render": "tabpane:form_entrega",
            "javax.faces.behavior.event": "keyup",
            "javax.faces.partial.event": "keyup",
            "tabpane": "tabpane",
            "tabpane:form_entrega:codigoguia": numero_guia,
            "tabpane:form_entrega:documento_anexo": "",
            "tabpane:form_entrega_SUBMIT": "1",
            "javax.faces.ViewState": view_state2,
        }, timeout=timeout)
        r3.raise_for_status()

        # Parsear respuesta
        for block in re.findall(r"<!\[CDATA\[(.*?)\]\]>", r3.text, re.DOTALL):
            if "form_entrega" not in block or len(block) < 500:
                continue

            soup = BeautifulSoup(block, "html.parser")

            numero = _label(soup, "tabpane:form_entrega:j_id_31")
            if not numero:
                raise HTTPException(
                    status_code=404,
                    detail=f"No se encontró información para la guía {numero_guia}"
                )

            # Origen / Destino
            od = _label(soup, "tabpane:form_entrega:j_id_3b")
            origen, destino = (od.split(" - ", 1) + [""])[:2] if " - " in od else (od, "")

            # Remitente — panel j_id_3e contiene j_id_3k internamente
            remitente = _panel_nombre(soup,
                "tabpane:form_entrega:j_id_3k",
                "tabpane:form_entrega:j_id_3e",
            )

            # Destinatario — panel j_id_3u contiene j_id_3w internamente
            destinatario = _panel_nombre(soup,
                "tabpane:form_entrega:j_id_3w",
                "tabpane:form_entrega:j_id_3u",
            )

            # Productos — [0] empaque, [1] dice_contener (colspan=2), [2] unidades, [3] peso
            productos = []
            tbody = soup.find("tbody", id=lambda x: x and "j_id_4d_data" in str(x))
            if tbody:
                for row in tbody.find_all("tr", attrs={"data-ri": True}):
                    cells = row.find_all("td")
                    if len(cells) >= 4:
                        productos.append(Producto(
                            empaque=cells[0].get_text(strip=True),
                            dice_contener=cells[1].get_text(strip=True),
                            unidades=cells[2].get_text(strip=True),
                            peso_cobrar=cells[3].get_text(strip=True),
                        ))

            # Total unidades desde tfoot
            total_unidades = None
            tfoot = soup.find("tfoot")
            if tfoot:
                cells = [td.get_text(strip=True) for td in tfoot.find_all("td")]
                total_unidades = cells[1] if len(cells) > 1 else None

            # Trazabilidad
            trazabilidad = []
            for row in soup.find_all("tr", attrs={"data-ri": True}):
                cells = [td.get_text(strip=True) for td in row.find_all("td")]
                if len(cells) >= 3 and "/" in cells[0]:
                    trazabilidad.append(EventoTrazabilidad(
                        fecha=cells[0],
                        detalle=cells[1],
                        sede=cells[2],
                        estado=cells[1],
                    ))

            estado_actual = trazabilidad[-1].detalle if trazabilidad else "Sin estado"

            return DatosEncomienda(
                numero_guia=numero,
                documento_anexo=None,
                fecha_admision=_label(soup, "tabpane:form_entrega:j_id_37"),
                origen=origen.strip(),
                destino=destino.strip(),
                remitente_nombre=remitente,
                destinatario_nombre=destinatario,
                productos=productos,
                total_unidades=total_unidades,
                trazabilidad=trazabilidad,
                estado_actual=estado_actual,
                fecha_consulta=datetime.now().isoformat(),
            )

        raise HTTPException(
            status_code=404,
            detail=f"No se encontró información para la guía {numero_guia}"
        )

    except HTTPException:
        raise
    except requests.exceptions.Timeout:
        raise HTTPException(status_code=408, detail="Timeout al conectar con el sitio de Rápido Ochoa")
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Error de red: {e}")
    except Exception as e:
        logger.error(f"Error inesperado: {e}")
        raise HTTPException(status_code=500, detail=f"Error inesperado: {e}")

# ── FastAPI ───────────────────────────────────────────────────────────────────

app = FastAPI(
    title="API Rápido Ochoa Rastreo",
    description="API para consultar información de encomiendas de Rápido Ochoa",
    version="3.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {
        "mensaje": "API de Rápido Ochoa - Rastreo de Encomiendas",
        "version": "3.0.0",
        "empresa": "Rápido Ochoa",
        "ejemplo_guia": "E121118705",
        "tiempo_respuesta": "~3-5 segundos",
        "endpoints": {
            "consultar_get": "/api/rastreo/{numero_guia}",
            "consultar_post": "/api/rastreo",
            "health": "/api/health",
            "docs": "/docs",
            "redoc": "/redoc"
        }
    }

@app.get("/api/rastreo/{numero_guia}", response_model=DatosEncomienda)
def consultar_guia_get(numero_guia: str):
    logger.info(f"📦 Consulta GET: {numero_guia}")
    return consultar_guia(numero_guia)

@app.post("/api/rastreo", response_model=DatosEncomienda)
def consultar_guia_post(consulta: ConsultaRequest):
    logger.info(f"📦 Consulta POST: {consulta.numero_guia}")
    return consultar_guia(consulta.numero_guia)

@app.get("/api/health")
def health_check():
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "service": "Rápido Ochoa Rastreo API",
        "version": "3.0.0"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
