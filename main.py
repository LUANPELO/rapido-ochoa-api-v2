"""
API REST para rastreo de encomiendas de Rápido Ochoa
Optimizada para respuesta rápida
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from typing import List, Optional
from datetime import datetime
import time
import logging
import re

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="API Rápido Ochoa Rastreo",
    description="API para consultar información de encomiendas de Rápido Ochoa",
    version="2.1.0"
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Modelos
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

class RapidoOchoaScraper:
    def __init__(self):
        self.url_base = "https://rapidoochoa.tmsolutions.com.co/tmland/faces/public/tmland-carga/cotizador_envios.xhtml?parametroInicial=cmFwaWRvb2Nob2E="
        self.driver = None
    
    def _inicializar_driver(self):
        """Inicializa el driver de Chrome en modo headless optimizado"""
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        
        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.set_page_load_timeout(20)
            logger.info("✅ Driver de Chrome inicializado")
        except Exception as e:
            logger.error(f"❌ Error al inicializar Chrome: {e}")
            raise HTTPException(
                status_code=500,
                detail="Error al inicializar navegador. Verifica que ChromeDriver esté instalado."
            )
    
    def _cerrar_driver(self):
        """Cierra el driver"""
        if self.driver:
            self.driver.quit()
            self.driver = None
    
    def consultar_guia(self, numero_guia: str) -> DatosEncomienda:
        """Consulta la información de una guía"""
        try:
            self._inicializar_driver()
            
            logger.info(f"🌐 Navegando a Rápido Ochoa...")
            self.driver.get(self.url_base)
            wait = WebDriverWait(self.driver, 20)
            
            time.sleep(2)
            
            # Click en la pestaña "Rastreo de envios"
            logger.info("🔍 Buscando pestaña de rastreo...")
            try:
                tab_rastreo = wait.until(
                    EC.element_to_be_clickable((By.XPATH, "//a[contains(text(), 'Rastreo de envios')]"))
                )
                self.driver.execute_script("arguments[0].click();", tab_rastreo)
                logger.info("✅ Click en pestaña Rastreo")
            except:
                logger.info("Método alternativo: buscando por índice...")
                tabs = self.driver.find_elements(By.CSS_SELECTOR, "li.ui-tabs-header")
                if len(tabs) > 1:
                    self.driver.execute_script("arguments[0].click();", tabs[1])
                else:
                    raise Exception("No se encontró la pestaña de rastreo")
            
            time.sleep(3)
            
            logger.info(f"📝 Ingresando número de guía: {numero_guia}")
            
            input_guia = wait.until(
                EC.presence_of_element_located((By.ID, "tabpane:form_entrega:codigoguia"))
            )
            
            input_guia.clear()
            time.sleep(0.5)
            input_guia.send_keys(numero_guia)
            time.sleep(0.5)
            input_guia.send_keys(Keys.RETURN)
            logger.info("✅ Guía ingresada, esperando resultados...")
            
            # Esperar resultados
            max_intentos = 20
            datos_encontrados = False
            for intento in range(max_intentos):
                time.sleep(0.5)
                try:
                    texto = self.driver.find_element(By.TAG_NAME, "body").text
                    
                    if ("Remitente" in texto and "Nombre:" in texto) or \
                       ("Destinatario" in texto and "Nombre:" in texto) or \
                       ("Trazabilidad" in texto and "GUIA ELABORADA" in texto):
                        logger.info(f"✅ Datos encontrados en ~{(intento + 1) * 0.5}s")
                        datos_encontrados = True
                        break
                except:
                    continue
            
            if not datos_encontrados:
                logger.warning("⚠️ No se detectaron datos, intentando extraer...")
            
            time.sleep(1)
            
            # Verificar si hay resultados
            try:
                texto_pagina = self.driver.find_element(By.TAG_NAME, "body").text
                if "No se encontr" in texto_pagina or "sin resultado" in texto_pagina.lower():
                    raise HTTPException(
                        status_code=404,
                        detail=f"No se encontró información para la guía {numero_guia}"
                    )
            except NoSuchElementException:
                pass
            
            datos = self._extraer_informacion(numero_guia, wait)
            
            return datos
            
        except TimeoutException as e:
            logger.error(f"⏱️ Timeout: {e}")
            raise HTTPException(
                status_code=408,
                detail="La consulta tardó demasiado. Intenta nuevamente."
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"❌ Error: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Error al consultar guía: {str(e)}"
            )
        finally:
            self._cerrar_driver()
    
    def _extraer_informacion(self, numero_guia: str, wait) -> DatosEncomienda:
        """Extrae toda la información de la página"""
        
        logger.info("📊 Extrayendo información...")
        
        try:
            wait.until(lambda driver: "Remitente" in driver.find_element(By.TAG_NAME, "body").text)
            logger.info("✅ Contenido confirmado")
        except:
            logger.warning("⚠️ No se pudo confirmar contenido")
        
        texto_pagina = self.driver.find_element(By.TAG_NAME, "body").text
        
        # Debug
        if "Remitente" in texto_pagina:
            inicio = texto_pagina.find("Remitente")
            fragmento = texto_pagina[inicio:inicio+200]
            logger.info(f"📝 Fragmento: {fragmento[:150]}")
        
        info_basica = self._extraer_info_basica(numero_guia, texto_pagina)
        remitente = self._extraer_remitente(texto_pagina)
        destinatario = self._extraer_destinatario(texto_pagina)
        productos = self._extraer_productos()
        trazabilidad = self._extraer_trazabilidad(texto_pagina)
        
        estado_actual = "Información disponible"
        if trazabilidad and len(trazabilidad) > 0:
            estado_actual = trazabilidad[-1].detalle
        
        datos = DatosEncomienda(
            numero_guia=numero_guia,
            documento_anexo=info_basica.get('documento_anexo'),
            fecha_admision=info_basica.get('fecha_admision', ''),
            origen=info_basica.get('origen', ''),
            destino=info_basica.get('destino', ''),
            remitente_nombre=remitente,
            destinatario_nombre=destinatario,
            productos=productos,
            total_unidades=info_basica.get('total_unidades'),
            trazabilidad=trazabilidad,
            estado_actual=estado_actual,
            fecha_consulta=datetime.now().isoformat()
        )
        
        logger.info(f"✅ Extracción completa: {len(trazabilidad)} eventos")
        
        return datos
    
    def _extraer_info_basica(self, numero_guia: str, texto_pagina: str) -> dict:
        """Extrae la información básica"""
        info = {'numero_guia': numero_guia}
        
        try:
            match = re.search(r'Documento anexo\s*(\S+)', texto_pagina)
            if match:
                info['documento_anexo'] = match.group(1)
            
            match = re.search(r'Fecha de admision\s*(\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2})', texto_pagina)
            if match:
                info['fecha_admision'] = match.group(1)
            
            match = re.search(r'Origen - Destino\s*([A-Z\s]+\([A-Z\s]+\))\s*-\s*([A-Z\s]+\([A-Z\s]+\))', texto_pagina)
            if match:
                info['origen'] = match.group(1).strip()
                info['destino'] = match.group(2).strip()
            
            match = re.search(r'Total\s*(\d+)', texto_pagina)
            if match:
                info['total_unidades'] = match.group(1)
                
        except Exception as e:
            logger.warning(f"⚠️ Error extrayendo info básica: {e}")
        
        return info
    
    def _extraer_remitente(self, texto_pagina: str) -> str:
        """Extrae el nombre del remitente"""
        try:
            # Método 1: Buscar entre "Remitente Nombre:" y salto de línea
            match = re.search(r'Remitente\s+Nombre:\s+([A-Z][A-Z\s]+?)(?=\n)', texto_pagina)
            if match:
                nombre = match.group(1).strip()
                nombre = re.sub(r'\s+[A-Z]$', '', nombre)  # Quitar letra suelta al final
                nombre = ' '.join(nombre.split())
                logger.info(f"✅ Remitente: {nombre}")
                return nombre
            
            # Método 2: Más flexible
            match = re.search(r'Remitente.*?Nombre:\s*([A-Z][A-Z\s]{3,50})', texto_pagina, re.DOTALL)
            if match:
                nombre = match.group(1).strip()
                # Limpiar hasta encontrar algo que no sea letra o espacio
                nombre = re.split(r'[^A-Z\s]', nombre)[0]
                nombre = ' '.join(nombre.split())
                logger.info(f"✅ Remitente (método 2): {nombre}")
                return nombre
                
        except Exception as e:
            logger.warning(f"⚠️ Error extrayendo remitente: {e}")
        
        logger.warning("⚠️ No se pudo extraer remitente")
        return "No disponible"
    
    def _extraer_destinatario(self, texto_pagina: str) -> str:
        """Extrae el nombre del destinatario"""
        try:
            # Método 1: Buscar entre "Destinatario Nombre:" y salto de línea
            match = re.search(r'Destinatario\s+Nombre:\s+([A-Z][A-Z\s]+?)(?=\n)', texto_pagina)
            if match:
                nombre = match.group(1).strip()
                nombre = re.sub(r'\s+[A-Z]$', '', nombre)  # Quitar letra suelta al final
                nombre = ' '.join(nombre.split())
                logger.info(f"✅ Destinatario: {nombre}")
                return nombre
            
            # Método 2: Más flexible
            match = re.search(r'Destinatario.*?Nombre:\s*([A-Z][A-Z\s]{3,50})', texto_pagina, re.DOTALL)
            if match:
                nombre = match.group(1).strip()
                nombre = re.split(r'[^A-Z\s]', nombre)[0]
                nombre = ' '.join(nombre.split())
                logger.info(f"✅ Destinatario (método 2): {nombre}")
                return nombre
                
        except Exception as e:
            logger.warning(f"⚠️ Error extrayendo destinatario: {e}")
        
        logger.warning("⚠️ No se pudo extraer destinatario")
        return "No disponible"
    
    def _extraer_productos(self) -> List[Producto]:
        """Extrae la lista de productos"""
        productos = []
        
        try:
            tablas = self.driver.find_elements(By.CSS_SELECTOR, "table.ui-datatable-data, table")
            
            for tabla in tablas:
                try:
                    filas = tabla.find_elements(By.TAG_NAME, "tr")
                    
                    for fila in filas:
                        celdas = fila.find_elements(By.TAG_NAME, "td")
                        
                        if len(celdas) >= 4:
                            texto = fila.text.strip()
                            if re.search(r'\d{5,}', texto):
                                producto = Producto(
                                    empaque=self._limpiar_texto(celdas[0].text),
                                    dice_contener=self._limpiar_texto(celdas[1].text),
                                    unidades=self._limpiar_texto(celdas[2].text),
                                    peso_cobrar=self._limpiar_texto(celdas[3].text)
                                )
                                productos.append(producto)
                except Exception:
                    continue
                    
        except Exception as e:
            logger.warning(f"⚠️ Error extrayendo productos: {e}")
        
        return productos
    
    def _extraer_trazabilidad(self, texto_pagina: str) -> List[EventoTrazabilidad]:
        """Extrae la trazabilidad completa"""
        eventos = []
        
        try:
            if "Trazabilidad" in texto_pagina:
                seccion_trazabilidad = texto_pagina.split("Trazabilidad")[1]
                
                patron = r'(\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2})([A-Z][A-Z\s]+?)([A-Z][A-Z\s]+\([^)]+\))'
                
                matches = re.finditer(patron, seccion_trazabilidad)
                
                for match in matches:
                    fecha = match.group(1).strip()
                    detalle = match.group(2).strip()
                    sede = match.group(3).strip()
                    
                    evento = EventoTrazabilidad(
                        fecha=fecha,
                        detalle=detalle,
                        sede=sede,
                        estado=detalle
                    )
                    eventos.append(evento)
            
            if not eventos:
                eventos = self._extraer_trazabilidad_tabla()
                
        except Exception as e:
            logger.warning(f"⚠️ Error extrayendo trazabilidad: {e}")
        
        return eventos
    
    def _extraer_trazabilidad_tabla(self) -> List[EventoTrazabilidad]:
        """Extrae trazabilidad de una tabla"""
        eventos = []
        
        try:
            tablas = self.driver.find_elements(By.CSS_SELECTOR, "table")
            
            for tabla in tablas:
                filas = tabla.find_elements(By.TAG_NAME, "tr")
                
                for fila in filas:
                    celdas = fila.find_elements(By.TAG_NAME, "td")
                    
                    if len(celdas) >= 3:
                        texto = celdas[0].text.strip()
                        if re.match(r'\d{4}/\d{2}/\d{2}', texto):
                            evento = EventoTrazabilidad(
                                fecha=self._limpiar_texto(celdas[0].text),
                                detalle=self._limpiar_texto(celdas[1].text),
                                sede=self._limpiar_texto(celdas[2].text),
                                estado=self._limpiar_texto(celdas[1].text)
                            )
                            eventos.append(evento)
        except Exception as e:
            logger.warning(f"⚠️ Error en tabla trazabilidad: {e}")
        
        return eventos
    
    def _limpiar_texto(self, texto: str) -> str:
        """Limpia y normaliza texto"""
        if not texto:
            return ""
        texto = ' '.join(texto.split())
        return texto.strip()

# Instancia del scraper
scraper = RapidoOchoaScraper()

# Endpoints
@app.get("/")
def root():
    return {
        "mensaje": "API de Rápido Ochoa - Rastreo de Encomiendas",
        "version": "2.1.0",
        "empresa": "Rápido Ochoa",
        "ejemplo_guia": "E121101188",
        "tiempo_respuesta": "~12-15 segundos",
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
    """Consulta una guía de Rápido Ochoa (GET)"""
    logger.info(f"📦 Nueva consulta: {numero_guia}")
    return scraper.consultar_guia(numero_guia)

@app.post("/api/rastreo", response_model=DatosEncomienda)
def consultar_guia_post(consulta: ConsultaRequest):
    """Consulta una guía de Rápido Ochoa (POST)"""
    logger.info(f"📦 Nueva consulta POST: {consulta.numero_guia}")
    return scraper.consultar_guia(consulta.numero_guia)

@app.get("/api/health")
def health_check():
    """Verifica el estado de la API"""
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "service": "Rápido Ochoa Rastreo API",
        "version": "2.1.0"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )