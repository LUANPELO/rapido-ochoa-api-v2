"""
API REST para rastreo de encomiendas de Rápido Ochoa
Scraping HTTP directo (sin Selenium) - v3.0.0
"""

import re
import logging
import unicodedata
from datetime import datetime, timedelta
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

# ===== TIEMPOS DE VIAJE ENTRE CIUDADES (horas, referencia/aprox.) =====
# Tabla estática de duraciones típicas por ruta. Es la fuente PRINCIPAL para
# estimar la llegada de encomiendas: es instantánea (sin llamadas de red) y
# cubre muchas rutas entre poblaciones pequeñas que la API de horarios de
# pasajeros no necesariamente tiene indexadas como ciudad buscable.
TIEMPOS_VIAJE = {
    # ========== BOGOTÁ ==========
    ("BOGOTA", "MEDELLIN"): 10,
    ("MEDELLIN", "BOGOTA"): 10,
    ("BOGOTA", "CALI"): 10,
    ("CALI", "BOGOTA"): 10,
    ("BOGOTA", "BARRANQUILLA"): 18,
    ("BARRANQUILLA", "BOGOTA"): 18,
    ("BOGOTA", "BUCARAMANGA"): 8,
    ("BUCARAMANGA", "BOGOTA"): 8,
    ("BOGOTA", "TOLU"): 16,
    ("TOLU", "BOGOTA"): 16,
    ("BOGOTA", "SOLEDAD"): 18,
    ("SOLEDAD", "BOGOTA"): 18,
    ("BOGOTA", "CAUCASIA"): 13,
    ("CAUCASIA", "BOGOTA"): 13,
    ("BOGOTA", "CERETE"): 16,
    ("CERETE", "BOGOTA"): 16,
    ("BOGOTA", "CHINU"): 16,
    ("CHINU", "BOGOTA"): 16,
    ("BOGOTA", "COVENAS"): 17,
    ("COVENAS", "BOGOTA"): 17,
    ("BOGOTA", "LA APARTADA"): 14,
    ("LA APARTADA", "BOGOTA"): 14,
    ("BOGOTA", "LORICA"): 17,
    ("LORICA", "BOGOTA"): 17,
    ("BOGOTA", "MONTERIA"): 16,
    ("MONTERIA", "BOGOTA"): 16,
    ("BOGOTA", "PLANETA RICA"): 15,
    ("PLANETA RICA", "BOGOTA"): 15,
    ("BOGOTA", "RIONEGRO"): 7,
    ("RIONEGRO", "BOGOTA"): 7,
    ("BOGOTA", "SINCELEJO"): 17,
    ("SINCELEJO", "BOGOTA"): 17,
    ("BOGOTA", "SAHAGUN"): 16,
    ("SAHAGUN", "BOGOTA"): 16,
    ("BOGOTA", "SAN ANTERO"): 18,
    ("SAN ANTERO", "BOGOTA"): 18,

    # ========== MEDELLÍN ==========
    ("MEDELLIN", "BARRANQUILLA"): 16,
    ("BARRANQUILLA", "MEDELLIN"): 16,
    ("MEDELLIN", "CALI"): 8,
    ("CALI", "MEDELLIN"): 8,
    ("MEDELLIN", "PEREIRA"): 5,
    ("PEREIRA", "MEDELLIN"): 5,
    ("MEDELLIN", "SINCELEJO"): 12,
    ("SINCELEJO", "MEDELLIN"): 12,
    ("MEDELLIN", "CARTAGENA"): 14,
    ("CARTAGENA", "MEDELLIN"): 14,
    ("MEDELLIN", "CAUCASIA"): 8,
    ("CAUCASIA", "MEDELLIN"): 8,
    ("MEDELLIN", "PLANETA RICA"): 10,
    ("PLANETA RICA", "MEDELLIN"): 10,
    ("MEDELLIN", "MAICAO"): 22,
    ("MAICAO", "MEDELLIN"): 22,
    ("MEDELLIN", "SAHAGUN"): 9,
    ("SAHAGUN", "MEDELLIN"): 9,
    ("MEDELLIN", "TOLU"): 11,
    ("TOLU", "MEDELLIN"): 11,
    ("MEDELLIN", "QUIBDO"): 11,
    ("QUIBDO", "MEDELLIN"): 11,
    ("MEDELLIN", "RIOHACHA"): 21,
    ("RIOHACHA", "MEDELLIN"): 21,
    ("MEDELLIN", "SOLEDAD"): 16,
    ("SOLEDAD", "MEDELLIN"): 16,
    ("MEDELLIN", "MONTERIA"): 9,
    ("MONTERIA", "MEDELLIN"): 9,
    ("MEDELLIN", "SANTA MARTA"): 18,
    ("SANTA MARTA", "MEDELLIN"): 18,
    ("MEDELLIN", "ARBOLETES"): 8,
    ("ARBOLETES", "MEDELLIN"): 8,
    ("MEDELLIN", "BETULIA"): 3,
    ("BETULIA", "MEDELLIN"): 3,
    ("MEDELLIN", "BOLOMBOLO"): 3,
    ("BOLOMBOLO", "MEDELLIN"): 3,
    ("MEDELLIN", "CAICEDO"): 4,
    ("CAICEDO", "MEDELLIN"): 4,
    ("MEDELLIN", "CARMEN DE BOLIVAR"): 13,
    ("CARMEN DE BOLIVAR", "MEDELLIN"): 13,
    ("MEDELLIN", "CERETE"): 8,
    ("CERETE", "MEDELLIN"): 8,
    ("MEDELLIN", "CHINU"): 10,
    ("CHINU", "MEDELLIN"): 10,
    ("MEDELLIN", "CIENAGA"): 17,
    ("CIENAGA", "MEDELLIN"): 17,
    ("MEDELLIN", "CIUDAD BOLIVAR"): 3,
    ("CIUDAD BOLIVAR", "MEDELLIN"): 3,
    ("MEDELLIN", "CONCORDIA"): 3,
    ("CONCORDIA", "MEDELLIN"): 3,
    ("MEDELLIN", "CONDOTO"): 8,
    ("CONDOTO", "MEDELLIN"): 8,
    ("MEDELLIN", "COVENAS"): 10,
    ("COVENAS", "MEDELLIN"): 10,
    ("MEDELLIN", "GIRALDO"): 3,
    ("GIRALDO", "MEDELLIN"): 3,
    ("MEDELLIN", "ISTMINA"): 7,
    ("ISTMINA", "MEDELLIN"): 7,
    ("MEDELLIN", "JARDIN"): 3,
    ("JARDIN", "MEDELLIN"): 3,
    ("MEDELLIN", "LA APARTADA"): 5,
    ("LA APARTADA", "MEDELLIN"): 5,
    ("MEDELLIN", "LA DORADA"): 4,
    ("LA DORADA", "MEDELLIN"): 4,
    ("MEDELLIN", "LORICA"): 9,
    ("LORICA", "MEDELLIN"): 9,
    ("MEDELLIN", "MAGANGUE"): 11,
    ("MAGANGUE", "MEDELLIN"): 11,
    ("MEDELLIN", "MOMPOX"): 12,
    ("MOMPOX", "MEDELLIN"): 12,
    ("MEDELLIN", "PUERTO BERRIO"): 3,
    ("PUERTO BERRIO", "MEDELLIN"): 3,
    ("MEDELLIN", "SAN ANTERO"): 10,
    ("SAN ANTERO", "MEDELLIN"): 10,
    ("MEDELLIN", "SAN MARCOS"): 11,
    ("SAN MARCOS", "MEDELLIN"): 11,
    ("MEDELLIN", "SAN ONOFRE"): 12,
    ("SAN ONOFRE", "MEDELLIN"): 12,
    ("MEDELLIN", "TARAZA"): 6,
    ("TARAZA", "MEDELLIN"): 6,
    ("MEDELLIN", "TUTUNENDO"): 10,
    ("TUTUNENDO", "MEDELLIN"): 10,
    ("MEDELLIN", "URRAO"): 4,
    ("URRAO", "MEDELLIN"): 4,
    ("MEDELLIN", "ANDES"): 4,
    ("MEDELLIN", "RIONEGRO"): 1,

    # ========== BARRANQUILLA / SOLEDAD ==========
    ("BARRANQUILLA", "SINCELEJO"): 4,
    ("SINCELEJO", "BARRANQUILLA"): 4,
    ("BARRANQUILLA", "CALI"): 20,
    ("CALI", "BARRANQUILLA"): 20,
    ("BARRANQUILLA", "CAUCASIA"): 8,
    ("CAUCASIA", "BARRANQUILLA"): 8,
    ("BARRANQUILLA", "PLANETA RICA"): 6,
    ("PLANETA RICA", "BARRANQUILLA"): 6,
    ("BARRANQUILLA", "MAICAO"): 7,
    ("MAICAO", "BARRANQUILLA"): 7,
    ("BARRANQUILLA", "LA APARTADA"): 7,
    ("LA APARTADA", "BARRANQUILLA"): 7,
    ("BARRANQUILLA", "SANTA MARTA"): 3,
    ("SANTA MARTA", "BARRANQUILLA"): 3,
    ("BARRANQUILLA", "RIOHACHA"): 5,
    ("RIOHACHA", "BARRANQUILLA"): 5,
    ("BARRANQUILLA", "YARUMAL"): 13,
    ("YARUMAL", "BARRANQUILLA"): 13,
    ("BARRANQUILLA", "SAHAGUN"): 6,
    ("SAHAGUN", "BARRANQUILLA"): 6,
    ("BARRANQUILLA", "SOLEDAD"): 1,
    ("SOLEDAD", "BARRANQUILLA"): 1,
    ("BARRANQUILLA", "MONTERIA"): 7,
    ("MONTERIA", "BARRANQUILLA"): 7,
    ("BARRANQUILLA", "CARMEN DE BOLIVAR"): 5,
    ("CARMEN DE BOLIVAR", "BARRANQUILLA"): 5,
    ("BARRANQUILLA", "CHINU"): 5,
    ("CHINU", "BARRANQUILLA"): 5,
    ("BARRANQUILLA", "CIENAGA"): 2,
    ("CIENAGA", "BARRANQUILLA"): 2,
    ("BARRANQUILLA", "TARAZA"): 11,
    ("TARAZA", "BARRANQUILLA"): 11,
    ("SOLEDAD", "SINCELEJO"): 4,
    ("SINCELEJO", "SOLEDAD"): 4,
    ("SOLEDAD", "CALI"): 20,
    ("CALI", "SOLEDAD"): 20,
    ("SOLEDAD", "CAUCASIA"): 8,
    ("CAUCASIA", "SOLEDAD"): 8,
    ("SOLEDAD", "PLANETA RICA"): 6,
    ("PLANETA RICA", "SOLEDAD"): 6,
    ("SOLEDAD", "MAICAO"): 7,
    ("MAICAO", "SOLEDAD"): 7,
    ("SOLEDAD", "LA APARTADA"): 7,
    ("LA APARTADA", "SOLEDAD"): 7,
    ("SOLEDAD", "SANTA MARTA"): 3,
    ("SANTA MARTA", "SOLEDAD"): 3,
    ("SOLEDAD", "RIOHACHA"): 5,
    ("RIOHACHA", "SOLEDAD"): 5,
    ("SOLEDAD", "YARUMAL"): 13,
    ("YARUMAL", "SOLEDAD"): 13,
    ("SOLEDAD", "SAHAGUN"): 7,
    ("SAHAGUN", "SOLEDAD"): 7,
    ("SOLEDAD", "MONTERIA"): 7,
    ("MONTERIA", "SOLEDAD"): 7,

    # ========== MONTERÍA ==========
    ("MONTERIA", "SINCELEJO"): 3,
    ("SINCELEJO", "MONTERIA"): 3,
    ("MONTERIA", "PLANETA RICA"): 2,
    ("PLANETA RICA", "MONTERIA"): 2,
    ("MONTERIA", "LA APARTADA"): 2,
    ("LA APARTADA", "MONTERIA"): 2,
    ("MONTERIA", "RIOHACHA"): 12,
    ("RIOHACHA", "MONTERIA"): 12,
    ("MONTERIA", "MAICAO"): 14,
    ("MAICAO", "MONTERIA"): 14,
    ("MONTERIA", "SANTA MARTA"): 9,
    ("SANTA MARTA", "MONTERIA"): 9,
    ("MONTERIA", "TARAZA"): 4,
    ("TARAZA", "MONTERIA"): 4,
    ("MONTERIA", "SAHAGUN"): 3,
    ("SAHAGUN", "MONTERIA"): 3,
    ("MONTERIA", "CHINU"): 2,
    ("CHINU", "MONTERIA"): 2,
    ("MONTERIA", "TOLU"): 2,
    ("TOLU", "MONTERIA"): 2,
    ("MONTERIA", "ARBOLETES"): 3,
    ("ARBOLETES", "MONTERIA"): 3,
    ("MONTERIA", "CARTAGENA"): 5,
    ("CARTAGENA", "MONTERIA"): 5,
    ("MONTERIA", "CAUCASIA"): 3,
    ("CAUCASIA", "MONTERIA"): 3,
    ("MONTERIA", "COVENAS"): 2,
    ("COVENAS", "MONTERIA"): 2,
    ("MONTERIA", "LA DORADA"): 10,
    ("LA DORADA", "MONTERIA"): 10,
    ("MONTERIA", "LORICA"): 1,
    ("LORICA", "MONTERIA"): 1,
    ("MONTERIA", "SAN ANTERO"): 1,
    ("SAN ANTERO", "MONTERIA"): 1,
    ("MONTERIA", "YARUMAL"): 5,
    ("YARUMAL", "MONTERIA"): 5,

    # ========== SAHAGÚN ==========
    ("SAHAGUN", "SINCELEJO"): 2,
    ("SINCELEJO", "SAHAGUN"): 2,
    ("SAHAGUN", "PLANETA RICA"): 2,
    ("PLANETA RICA", "SAHAGUN"): 2,
    ("SAHAGUN", "LA APARTADA"): 2,
    ("LA APARTADA", "SAHAGUN"): 2,
    ("SAHAGUN", "MAICAO"): 13,
    ("MAICAO", "SAHAGUN"): 13,
    ("SAHAGUN", "SANTA MARTA"): 8,
    ("SANTA MARTA", "SAHAGUN"): 8,
    ("SAHAGUN", "RIOHACHA"): 12,
    ("RIOHACHA", "SAHAGUN"): 12,
    ("SAHAGUN", "CAUCASIA"): 4,
    ("CAUCASIA", "SAHAGUN"): 4,
    ("SAHAGUN", "YARUMAL"): 5,
    ("YARUMAL", "SAHAGUN"): 5,
    ("MAGANGUE", "SAHAGUN"): 2,
    ("SAHAGUN", "MAGANGUE"): 2,

    # ========== CAUCASIA ==========
    ("CAUCASIA", "SINCELEJO"): 4,
    ("SINCELEJO", "CAUCASIA"): 4,
    ("CAUCASIA", "SANTA MARTA"): 11,
    ("SANTA MARTA", "CAUCASIA"): 11,
    ("CAUCASIA", "MAICAO"): 15,
    ("MAICAO", "CAUCASIA"): 15,
    ("CAUCASIA", "PLANETA RICA"): 2,
    ("PLANETA RICA", "CAUCASIA"): 2,
    ("CAUCASIA", "TOLU"): 5,
    ("TOLU", "CAUCASIA"): 5,
    ("CAUCASIA", "ARBOLETES"): 3,
    ("ARBOLETES", "CAUCASIA"): 3,
    ("CAUCASIA", "CARTAGENA"): 8,
    ("CARTAGENA", "CAUCASIA"): 8,
    ("CAUCASIA", "CARMEN DE BOLIVAR"): 5,
    ("CARMEN DE BOLIVAR", "CAUCASIA"): 5,
    ("CAUCASIA", "CERETE"): 3,
    ("CERETE", "CAUCASIA"): 3,
    ("CAUCASIA", "CHINU"): 4,
    ("CHINU", "CAUCASIA"): 4,
    ("CAUCASIA", "COVENAS"): 5,
    ("COVENAS", "CAUCASIA"): 5,
    ("CAUCASIA", "MAGANGUE"): 6,
    ("MAGANGUE", "CAUCASIA"): 6,
    ("CAUCASIA", "PUERTO BERRIO"): 4,
    ("PUERTO BERRIO", "CAUCASIA"): 4,
    ("CAUCASIA", "SAN MARCOS"): 5,
    ("SAN MARCOS", "CAUCASIA"): 5,

    # ========== SANTA MARTA ==========
    ("SANTA MARTA", "SINCELEJO"): 7,
    ("SINCELEJO", "SANTA MARTA"): 7,
    ("SANTA MARTA", "PLANETA RICA"): 9,
    ("PLANETA RICA", "SANTA MARTA"): 9,
    ("SANTA MARTA", "MAICAO"): 4,
    ("MAICAO", "SANTA MARTA"): 4,
    ("SANTA MARTA", "LA APARTADA"): 9,
    ("LA APARTADA", "SANTA MARTA"): 9,
    ("SANTA MARTA", "CARMEN DE BOLIVAR"): 6,
    ("CARMEN DE BOLIVAR", "SANTA MARTA"): 6,
    ("SANTA MARTA", "CERETE"): 9,
    ("CERETE", "SANTA MARTA"): 9,
    ("SANTA MARTA", "CHINU"): 8,
    ("CHINU", "SANTA MARTA"): 8,
    ("SANTA MARTA", "TARAZA"): 13,
    ("TARAZA", "SANTA MARTA"): 13,
    ("SANTA MARTA", "YARUMAL"): 14,
    ("YARUMAL", "SANTA MARTA"): 14,

    # ========== PLANETA RICA ==========
    ("PLANETA RICA", "RIOHACHA"): 12,
    ("RIOHACHA", "PLANETA RICA"): 12,
    ("PLANETA RICA", "CARTAGENA"): 7,
    ("CARTAGENA", "PLANETA RICA"): 7,
    ("PLANETA RICA", "TOLU"): 3,
    ("TOLU", "PLANETA RICA"): 3,
    ("PLANETA RICA", "CERETE"): 1,
    ("CERETE", "PLANETA RICA"): 1,
    ("PLANETA RICA", "CHINU"): 2,
    ("CHINU", "PLANETA RICA"): 2,
    ("PLANETA RICA", "COVENAS"): 3,
    ("COVENAS", "PLANETA RICA"): 3,
    ("PLANETA RICA", "LA DORADA"): 7,
    ("LA DORADA", "PLANETA RICA"): 7,
    ("PLANETA RICA", "SAN MARCOS"): 2,
    ("SAN MARCOS", "PLANETA RICA"): 2,
    ("PLANETA RICA", "SAN ONOFRE"): 4,
    ("SAN ONOFRE", "PLANETA RICA"): 4,
    ("PLANETA RICA", "SINCELEJO"): 4,
    ("SINCELEJO", "PLANETA RICA"): 4,
    ("PLANETA RICA", "TARAZA"): 5,
    ("TARAZA", "PLANETA RICA"): 5,
    ("PLANETA RICA", "YARUMAL"): 7,
    ("YARUMAL", "PLANETA RICA"): 7,
    ("PLANETA RICA", "MAGANGUE"): 4,
    ("MAGANGUE", "PLANETA RICA"): 4,

    # ========== SINCELEJO ==========
    ("SINCELEJO", "CARTAGENA"): 5,
    ("CARTAGENA", "SINCELEJO"): 5,
    ("SINCELEJO", "YARUMAL"): 9,
    ("YARUMAL", "SINCELEJO"): 9,
    ("SINCELEJO", "CARMEN DE BOLIVAR"): 3,
    ("CARMEN DE BOLIVAR", "SINCELEJO"): 3,
    ("SINCELEJO", "LA APARTADA"): 3,
    ("LA APARTADA", "SINCELEJO"): 3,
    ("SINCELEJO", "LA DORADA"): 13,
    ("LA DORADA", "SINCELEJO"): 13,
    ("SINCELEJO", "MAGANGUE"): 2,
    ("MAGANGUE", "SINCELEJO"): 2,
    ("SINCELEJO", "RIOHACHA"): 9,
    ("RIOHACHA", "SINCELEJO"): 9,
    ("SINCELEJO", "TARAZA"): 7,
    ("TARAZA", "SINCELEJO"): 7,
    ("MAICAO", "SINCELEJO"): 9,
    ("SINCELEJO", "MAICAO"): 9,

    # ========== LA APARTADA ==========
    ("LA APARTADA", "RIOHACHA"): 12,
    ("RIOHACHA", "LA APARTADA"): 12,
    ("LA APARTADA", "MAICAO"): 13,
    ("MAICAO", "LA APARTADA"): 13,
    ("LA APARTADA", "LA DORADA"): 8,
    ("LA DORADA", "LA APARTADA"): 8,
    ("LA APARTADA", "PUERTO BERRIO"): 5,
    ("PUERTO BERRIO", "LA APARTADA"): 5,
    ("LA APARTADA", "SAN ONOFRE"): 4,
    ("SAN ONOFRE", "LA APARTADA"): 4,
    ("LA APARTADA", "TARAZA"): 2,
    ("TARAZA", "LA APARTADA"): 2,
    ("LA APARTADA", "YARUMAL"): 3,
    ("YARUMAL", "LA APARTADA"): 3,

    # ========== TOLÚ ==========
    ("TOLU", "PUERTO BERRIO"): 9,
    ("PUERTO BERRIO", "TOLU"): 9,
    ("TOLU", "CARTAGENA"): 4,
    ("CARTAGENA", "TOLU"): 4,
    ("TOLU", "LA APARTADA"): 3,
    ("LA APARTADA", "TOLU"): 3,
    ("CERETE", "TOLU"): 2,
    ("TOLU", "CERETE"): 2,

    # ========== CARTAGENA ==========
    ("CARTAGENA", "CARMEN DE BOLIVAR"): 2,
    ("CARMEN DE BOLIVAR", "CARTAGENA"): 2,
    ("CARTAGENA", "CHINU"): 4,
    ("CHINU", "CARTAGENA"): 4,
    ("CARTAGENA", "COVENAS"): 4,
    ("COVENAS", "CARTAGENA"): 4,
    ("CARTAGENA", "LA APARTADA"): 6,
    ("LA APARTADA", "CARTAGENA"): 6,
    ("CARTAGENA", "MAICAO"): 8,
    ("MAICAO", "CARTAGENA"): 8,
    ("CARTAGENA", "SAHAGUN"): 4,
    ("SAHAGUN", "CARTAGENA"): 4,

    # ========== RIOHACHA ==========
    ("RIOHACHA", "CARMEN DE BOLIVAR"): 8,
    ("CARMEN DE BOLIVAR", "RIOHACHA"): 8,
    ("RIOHACHA", "SANTA MARTA"): 3,
    ("SANTA MARTA", "RIOHACHA"): 3,
    ("RIOHACHA", "BARRANQUILLA"): 5,
    ("BARRANQUILLA", "RIOHACHA"): 5,
    ("RIOHACHA", "SINCELEJO"): 9,
    ("SINCELEJO", "RIOHACHA"): 9,
    ("RIOHACHA", "PALOMINO"): 1,
    ("PALOMINO", "RIOHACHA"): 1,
    ("RIOHACHA", "MAICAO"): 2,
    ("MAICAO", "RIOHACHA"): 2,
    ("RIOHACHA", "TARAZA"): 13,
    ("TARAZA", "RIOHACHA"): 13,
    ("RIOHACHA", "LA APARTADA"): 12,
    ("LA APARTADA", "RIOHACHA"): 12,
    ("RIOHACHA", "YARUMAL"): 16,
    ("YARUMAL", "RIOHACHA"): 16,
    ("RIOHACHA", "CAUCASIA"): 15,
    ("CAUCASIA", "RIOHACHA"): 15,
    ("RIOHACHA", "CHINU"): 10,
    ("CHINU", "RIOHACHA"): 10,
    ("RIOHACHA", "SAHAGUN"): 12,
    ("SAHAGUN", "RIOHACHA"): 12,

    # ========== LORICA ==========
    ("LORICA", "CARTAGENA"): 3,
    ("CARTAGENA", "LORICA"): 3,
    ("LORICA", "CAUCASIA"): 4,
    ("CAUCASIA", "LORICA"): 4,
    ("LORICA", "LA APARTADA"): 2,
    ("LA APARTADA", "LORICA"): 2,
    ("LORICA", "PLANETA RICA"): 2,
    ("PLANETA RICA", "LORICA"): 2,
    ("LORICA", "TARAZA"): 5,
    ("TARAZA", "LORICA"): 5,
    ("LORICA", "YARUMAL"): 6,
    ("YARUMAL", "LORICA"): 6,
    ("COVENAS", "LORICA"): 1,
    ("LORICA", "COVENAS"): 1,

    # ========== TARAZA ==========
    ("TARAZA", "ARBOLETES"): 3,
    ("ARBOLETES", "TARAZA"): 3,
    ("TARAZA", "CARTAGENA"): 8,
    ("CARTAGENA", "TARAZA"): 8,
    ("TARAZA", "CAUCASIA"): 2,
    ("CAUCASIA", "TARAZA"): 2,

    # ========== YARUMAL ==========
    ("YARUMAL", "CARMEN DE BOLIVAR"): 6,
    ("CARMEN DE BOLIVAR", "YARUMAL"): 6,
    ("YARUMAL", "CARTAGENA"): 10,
    ("CARTAGENA", "YARUMAL"): 10,
    ("YARUMAL", "CERETE"): 5,
    ("CERETE", "YARUMAL"): 5,
    ("YARUMAL", "SAN ANTERO"): 6,
    ("SAN ANTERO", "YARUMAL"): 6,
    ("SAN MARCOS", "YARUMAL"): 5,
    ("YARUMAL", "SAN MARCOS"): 5,

    # ========== CERETE ==========
    ("CERETE", "LA DORADA"): 10,
    ("LA DORADA", "CERETE"): 10,
    ("CERETE", "SAN ANTERO"): 1,
    ("SAN ANTERO", "CERETE"): 1,

    # ========== SAN ANTERO ==========
    ("SAN ANTERO", "CARTAGENA"): 4,
    ("CARTAGENA", "SAN ANTERO"): 4,
    ("SAN ANTERO", "CAUCASIA"): 4,
    ("CAUCASIA", "SAN ANTERO"): 4,

    # ========== CHINU ==========
    ("CHINU", "RIOHACHA"): 10,
    ("RIOHACHA", "CHINU"): 10,
    ("CHINU", "SAHAGUN"): 1,
    ("SAHAGUN", "CHINU"): 1,
    ("CHINU", "LA APARTADA"): 3,
    ("LA APARTADA", "CHINU"): 3,
    ("CHINU", "CERETE"): 1,
    ("CERETE", "CHINU"): 1,

    # ========== CARMEN DE BOLÍVAR ==========
    ("CARMEN DE BOLIVAR", "PLANETA RICA"): 3,

    # ========== QUIBDÓ / PACÍFICO ==========
    ("QUIBDO", "BOLOMBOLO"): 8,
    ("BOLOMBOLO", "QUIBDO"): 8,
    ("QUIBDO", "CIUDAD BOLIVAR"): 4,
    ("CIUDAD BOLIVAR", "QUIBDO"): 4,
    ("QUIBDO", "EL SIETE"): 2,
    ("EL SIETE", "QUIBDO"): 2,
    ("BOLOMBOLO", "CIUDAD BOLIVAR"): 3,
    ("CIUDAD BOLIVAR", "BOLOMBOLO"): 3,
    ("BOLOMBOLO", "ISTMINA"): 6,
    ("ISTMINA", "BOLOMBOLO"): 6,
    ("BOLOMBOLO", "JARDIN"): 2,
    ("JARDIN", "BOLOMBOLO"): 2,
    ("BOLOMBOLO", "URRAO"): 4,
    ("URRAO", "BOLOMBOLO"): 4,
    ("BOLOMBOLO", "BETULIA"): 2,
    ("BETULIA", "BOLOMBOLO"): 2,
    ("CIUDAD BOLIVAR", "ISTMINA"): 4,
    ("ISTMINA", "CIUDAD BOLIVAR"): 4,
    ("CAICEDO", "URRAO"): 2,
    ("URRAO", "CAICEDO"): 2,
    ("CONCORDIA", "URRAO"): 3,
    ("URRAO", "CONCORDIA"): 3,
    ("URRAO", "BETULIA"): 2,
    ("BETULIA", "URRAO"): 2,

    # ========== LA DORADA ==========
    ("LA DORADA", "CAUCASIA"): 8,
    ("CAUCASIA", "LA DORADA"): 8,
    ("LA DORADA", "FACATATIVA"): 3,
    ("FACATATIVA", "LA DORADA"): 3,
    ("RIONEGRO", "LA DORADA"): 3,
    ("LA DORADA", "RIONEGRO"): 3,

    # ========== MAGANGUÉ ==========
    ("MAGANGUE", "MEDELLIN"): 11,
    ("MAGANGUE", "SINCELEJO"): 2,
    ("SINCELEJO", "MAGANGUE"): 2,

    # ========== MOMPOX ==========
    ("MOMPOX", "MEDELLIN"): 12,
    ("MEDELLIN", "MOMPOX"): 12,

    # ========== SAN MARCOS / SAN ONOFRE ==========
    ("SAN MARCOS", "MEDELLIN"): 11,
    ("SAN MARCOS", "PLANETA RICA"): 2,
    ("PLANETA RICA", "SAN MARCOS"): 2,
    ("SAN ONOFRE", "MEDELLIN"): 12,
    ("MEDELLIN", "SAN ONOFRE"): 12,

    # ========== CIENAGA ==========
    ("CIENAGA", "CAUCASIA"): 10,
    ("CAUCASIA", "CIENAGA"): 10,
    ("CIENAGA", "BARRANQUILLA"): 2,
    ("BARRANQUILLA", "CIENAGA"): 2,
    ("CIENAGA", "MEDELLIN"): 17,
    ("MEDELLIN", "CIENAGA"): 17,
    ("SINCELEJO", "CIENAGA"): 7,
    ("CIENAGA", "SINCELEJO"): 7,

    # ========== TUTUNENDO / CONDOTO ==========
    ("TUTUNENDO", "MEDELLIN"): 10,
    ("MEDELLIN", "TUTUNENDO"): 10,
    ("CONDOTO", "MEDELLIN"): 10,
    ("MEDELLIN", "CONDOTO"): 10,

    # ========== LA APARTADA (adicionales) ==========
    ("LA APARTADA", "CARMEN DE BOLIVAR"): 4,
    ("CARMEN DE BOLIVAR", "LA APARTADA"): 4,
    ("LA APARTADA", "PALOMINO"): 10,
    ("PALOMINO", "LA APARTADA"): 10,

    # ========== SINCELEJO (adicionales) ==========
    ("SINCELEJO", "PALOMINO"): 7,
    ("PALOMINO", "SINCELEJO"): 7,

    # ========== PALOMINO ==========
    ("PALOMINO", "BARRANQUILLA"): 3,
    ("BARRANQUILLA", "PALOMINO"): 3,
    ("PALOMINO", "MAICAO"): 3,
    ("MAICAO", "PALOMINO"): 3,
    ("PALOMINO", "SANTA MARTA"): 1,
    ("SANTA MARTA", "PALOMINO"): 1,
    ("PALOMINO", "MEDELLIN"): 19,
    ("MEDELLIN", "PALOMINO"): 19,
    ("PALOMINO", "CARTAGENA"): 5,
    ("CARTAGENA", "PALOMINO"): 5,

    # ========== BUENAVISTA CÓRDOBA ==========
    ("BUENAVISTA", "MEDELLIN"): 5,
    ("MEDELLIN", "BUENAVISTA"): 5,
    ("BUENAVISTA", "BARRANQUILLA"): 7,
    ("BARRANQUILLA", "BUENAVISTA"): 7,
    ("BUENAVISTA", "MONTERIA"): 1,
    ("MONTERIA", "BUENAVISTA"): 1,
    ("BUENAVISTA", "PLANETA RICA"): 2,
    ("PLANETA RICA", "BUENAVISTA"): 2,
    ("BUENAVISTA", "CAUCASIA"): 3,
    ("CAUCASIA", "BUENAVISTA"): 3,
    ("BUENAVISTA", "SINCELEJO"): 4,
    ("SINCELEJO", "BUENAVISTA"): 4,
}

# ===== NORMALIZACIÓN DE NOMBRES DE CIUDAD -> claves usadas en TIEMPOS_VIAJE =====
CIUDADES_NORMALIZE = {
    "medellin": "MEDELLIN", "medellín": "MEDELLIN",
    "barranquilla": "BARRANQUILLA",
    "bogota": "BOGOTA", "bogotá": "BOGOTA",
    "cali": "CALI",
    "sincelejo": "SINCELEJO",
    "bucaramanga": "BUCARAMANGA",
    "pereira": "PEREIRA",
    "cartagena": "CARTAGENA",
    "monteria": "MONTERIA", "montería": "MONTERIA",
    "maicao": "MAICAO",
    "caucasia": "CAUCASIA",
    "planeta rica": "PLANETA RICA", "planetarica": "PLANETA RICA",
    "la apartada": "LA APARTADA", "apartada": "LA APARTADA",
    "santa marta": "SANTA MARTA", "santamarta": "SANTA MARTA",
    "riohacha": "RIOHACHA",
    "yarumal": "YARUMAL",
    "sahagun": "SAHAGUN", "sahagún": "SAHAGUN",
    "soledad": "SOLEDAD", "soledao": "SOLEDAD",
    "puerto berrio": "PUERTO BERRIO", "puerto berrío": "PUERTO BERRIO", "puertoberrio": "PUERTO BERRIO",
    "taraza": "TARAZA", "tarazá": "TARAZA",
    "chinu": "CHINU", "chinú": "CHINU",
    "tolu": "TOLU", "tolú": "TOLU",
    "quibdo": "QUIBDO", "quibdó": "QUIBDO",
    "arboletes": "ARBOLETES",
    "betulia": "BETULIA",
    "bolombolo": "BOLOMBOLO",
    "caicedo": "CAICEDO",
    "carmen de bolivar": "CARMEN DE BOLIVAR", "carmen de bolívar": "CARMEN DE BOLIVAR",
    "cerete": "CERETE", "cereté": "CERETE",
    "cienaga": "CIENAGA", "ciénaga": "CIENAGA",
    "ciudad bolivar": "CIUDAD BOLIVAR", "ciudad bolívar": "CIUDAD BOLIVAR",
    "concordia": "CONCORDIA",
    "condoto": "CONDOTO",
    "covenas": "COVENAS", "coveñas": "COVENAS",
    "giraldo": "GIRALDO",
    "istmina": "ISTMINA",
    "jardin": "JARDIN", "jardín": "JARDIN",
    "la dorada": "LA DORADA",
    "lorica": "LORICA", "lórica": "LORICA",
    "magangue": "MAGANGUE", "magangué": "MAGANGUE",
    "mompox": "MOMPOX",
    "rionegro": "RIONEGRO",
    "san antero": "SAN ANTERO",
    "san marcos": "SAN MARCOS",
    "san onofre": "SAN ONOFRE",
    "tutunendo": "TUTUNENDO",
    "urrao": "URRAO",
    "el siete": "EL SIETE",
    "facatativa": "FACATATIVA", "facatativá": "FACATATIVA",
    "andes": "ANDES",
    "pueblo rico": "PUEBLO RICO",
    "palomino": "PALOMINO",
    "buenavista": "BUENAVISTA",
    "medellin terminal norte": "MEDELLIN",
    "medellin terminal sur": "MEDELLIN",
}

# Estado de trazabilidad que indica que la encomienda salió en bus hacia destino.
# La fecha de ESTE evento es la hora de "inicio de viaje" desde la cual se
# calcula la llegada estimada.
ESTADO_DESPACHO = "DESPACHO NACIONAL BUSES"

# API externa (mismo proyecto/ecosistema) que tiene los horarios reales de buses
# de Rápido Ochoa, incluida la duración del trayecto (duracion_minutos). La
# usamos como referencia para estimar cuánto tiempo tarda la encomienda en
# llegar — es la mejor aproximación disponible sin inventar tiempos de viaje,
# ya que la encomienda viaja físicamente en esos mismos buses.
RUTAS_API_BASE = "https://buscador-buses-colombia.onrender.com"

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

class EstimacionLlegada(BaseModel):
    salida_estimada: str
    llegada_estimada: str
    duracion_estimada_horas: float
    sede_origen_despacho: str
    nota: str

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
    estimacion_llegada: Optional[EstimacionLlegada] = None
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

# ── Estimación de llegada de encomiendas ─────────────────────────────────────
# Idea: cuando la guía llega al estado "DESPACHO NACIONAL BUSES", esa fecha es
# el momento en que la encomienda salió físicamente hacia su destino. A partir
# de ahí, le sumamos la duración TÍPICA del trayecto en bus entre el origen y
# el destino (consultando la API de horarios de Rápido Ochoa, que ya resuelve
# correctamente el tema de las dos terminales de Medellín) para darle al
# usuario una hora de llegada APROXIMADA — siempre como referencia, nunca como
# garantía, ya que depende del estado de la vía, clima, paradas, etc.

def _normalizar_nombre_ciudad(texto: str) -> str:
    """'BOGOTA (BOGOTA)' / 'Montería (Córdoba)' -> 'bogota' / 'monteria'

    La API de horarios espera el nombre de la ciudad en minúsculas y sin
    tildes (sus claves son del estilo 'medellin', 'monteria', 'bogota')."""
    if not texto:
        return ""
    nombre = texto.split("(", 1)[0].strip()
    nombre = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode("ascii")
    return nombre.lower().strip()

def _parsear_fecha_evento(fecha_str: str) -> Optional[datetime]:
    """Convierte la fecha de un evento de trazabilidad (ej. '2026/06/05 17:00')
    a datetime. Soporta también el formato con guiones por si cambia el sitio."""
    if not fecha_str:
        return None
    texto = fecha_str.strip()
    for fmt in ("%Y/%m/%d %H:%M", "%Y-%m-%d %H:%M", "%d/%m/%Y %H:%M"):
        try:
            return datetime.strptime(texto, fmt)
        except ValueError:
            continue
    return None

def _clave_tiempos_viaje(nombre_normalizado: str) -> str:
    """'medellin' -> 'MEDELLIN' usando CIUDADES_NORMALIZE; si la ciudad no está
    mapeada explícitamente, usamos el propio nombre en mayúsculas como
    fallback (cubre casos no listados sin reventar la búsqueda)."""
    return CIUDADES_NORMALIZE.get(nombre_normalizado, nombre_normalizado.upper())

def _duracion_horas_tabla(origen_slug: str, destino_slug: str) -> Optional[float]:
    """Busca la duración (en horas) en la tabla estática TIEMPOS_VIAJE.

    Es la fuente PRINCIPAL: instantánea y con más cobertura que la API de
    horarios (incluye poblaciones pequeñas que esa API no indexa)."""
    clave_o = _clave_tiempos_viaje(origen_slug)
    clave_d = _clave_tiempos_viaje(destino_slug)
    return TIEMPOS_VIAJE.get((clave_o, clave_d))

def _duracion_horas_api_horarios(origen_slug: str, destino_slug: str, fecha_referencia) -> Optional[float]:
    """Respaldo: si el par origen/destino no está en TIEMPOS_VIAJE, consulta
    en vivo la API de horarios de Rápido Ochoa y promedia duracion_minutos.

    OJO: esa API solo devuelve viajes futuros/disponibles (si se le pide una
    fecha ya pasada, responde "0 buses" aunque la ruta exista). Como lo que
    necesitamos es la DURACIÓN típica del trayecto —que no cambia día a día—,
    si la fecha de referencia ya pasó usamos la fecha de HOY en su lugar."""
    fecha_consulta = max(fecha_referencia, datetime.now().date())
    try:
        resp = requests.get(
            f"{RUTAS_API_BASE}/buscar-rapido-ochoa",
            params={
                "origen": origen_slug,
                "destino": destino_slug,
                "fecha": fecha_consulta.strftime("%Y-%m-%d"),
            },
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
        duraciones = [
            h["duracion_minutos"] for h in (data.get("horarios") or [])
            if h.get("duracion_minutos")
        ]
    except Exception as e:
        logger.warning(
            f"No se pudo consultar duración de trayecto {origen_slug} -> {destino_slug}: {e}"
        )
        return None

    if not duraciones:
        return None
    return (sum(duraciones) / len(duraciones)) / 60.0

def estimar_llegada_encomienda(
    trazabilidad: List[EventoTrazabilidad], origen: str, destino: str
) -> Optional[EstimacionLlegada]:
    """Calcula una hora de llegada APROXIMADA para la encomienda.

    Busca el evento "DESPACHO NACIONAL BUSES" (la fecha de ese evento marca
    cuándo la encomienda salió hacia destino, y la 'sede' indica desde qué
    oficina/terminal salió), y le suma la duración típica del trayecto en bus
    entre el origen y el destino. Esa duración se obtiene en dos pasos:

      1. PRIMERO se busca en TIEMPOS_VIAJE (tabla de referencia local —
         instantánea y con cobertura de poblaciones pequeñas).
      2. Si el par origen/destino no está ahí, se consulta como respaldo la
         API de horarios reales de Rápido Ochoa (la encomienda viaja
         físicamente en esos mismos buses, así que su duración es una buena
         referencia).

    Devuelve None si no existe el evento de despacho, si no se puede leer su
    fecha, o si ninguna de las dos fuentes tiene una duración para esa ruta —
    en esos casos el endpoint simplemente no incluye la estimación (nunca se
    inventa un valor)."""
    if not trazabilidad:
        return None

    # Tomamos el evento de despacho más reciente (por si hay reintentos/escalas
    # con el mismo estado registrado más de una vez en la trazabilidad).
    evento_despacho = None
    for evento in trazabilidad:
        texto_estado = f"{evento.detalle or ''} {evento.estado or ''}".upper()
        if ESTADO_DESPACHO in texto_estado:
            evento_despacho = evento

    if not evento_despacho:
        return None

    fecha_salida = _parsear_fecha_evento(evento_despacho.fecha)
    if not fecha_salida:
        return None

    origen_slug = _normalizar_nombre_ciudad(origen)
    destino_slug = _normalizar_nombre_ciudad(destino)
    if not origen_slug or not destino_slug or origen_slug == destino_slug:
        return None

    duracion_horas = _duracion_horas_tabla(origen_slug, destino_slug)
    if duracion_horas is None:
        duracion_horas = _duracion_horas_api_horarios(origen_slug, destino_slug, fecha_salida.date())

    if duracion_horas is None:
        return None

    duracion_prom_min = duracion_horas * 60.0
    llegada_estimada = fecha_salida + timedelta(minutes=duracion_prom_min)

    return EstimacionLlegada(
        salida_estimada=fecha_salida.strftime("%Y-%m-%d %H:%M"),
        llegada_estimada=llegada_estimada.strftime("%Y-%m-%d %H:%M"),
        duracion_estimada_horas=round(duracion_prom_min / 60, 1),
        sede_origen_despacho=evento_despacho.sede,
        nota=(
            "Hora de llegada APROXIMADA (no garantizada): se calcula sumando "
            "la duración promedio del trayecto en bus entre origen y destino "
            "a la hora en que la encomienda salió de despacho. El tiempo real "
            "puede variar por estado de la vía, clima, paradas en ruta o "
            "trámites en la oficina de destino — comunícalo siempre al "
            "cliente como un estimado de referencia, nunca como una hora exacta."
        ),
    )

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

            origen_limpio = origen.strip()
            destino_limpio = destino.strip()

            # Estimación aproximada de hora de llegada (ver comentario junto a
            # estimar_llegada_encomienda). Si algo falla o no hay datos
            # suficientes, simplemente queda en None — no se inventa un valor.
            try:
                estimacion = estimar_llegada_encomienda(trazabilidad, origen_limpio, destino_limpio)
            except Exception as e:
                logger.warning(f"Fallo al estimar llegada de la guía {numero_guia}: {e}")
                estimacion = None

            return DatosEncomienda(
                numero_guia=numero,
                documento_anexo=None,
                fecha_admision=_label(soup, "tabpane:form_entrega:j_id_37"),
                origen=origen_limpio,
                destino=destino_limpio,
                remitente_nombre=remitente,
                destinatario_nombre=destinatario,
                productos=productos,
                total_unidades=total_unidades,
                trazabilidad=trazabilidad,
                estado_actual=estado_actual,
                estimacion_llegada=estimacion,
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
