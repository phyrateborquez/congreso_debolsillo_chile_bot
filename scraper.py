"""
Scraper modular para el Congreso de Chile.
Cubre: Proyectos de Ley, Resoluciones y Acuerdos.
Integra base de datos SQLite para tracking de publicaciones.
"""
import os
import time
import random
import sqlite3
import logging
from datetime import datetime
from urllib.parse import urlparse, parse_qs
from playwright.sync_api import sync_playwright


# ============================================================
# BASE DE DATOS SQLite
# ============================================================
DB_PATH = os.path.join(os.path.dirname(__file__), "bot_database.db")


def init_db():
    """Crea las tablas si no existen."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Tabla de proyectos ya publicados
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS published_projects (
            project_id TEXT PRIMARY KEY,
            tipo TEXT,
            titulo TEXT,
            link TEXT,
            publicado_en TEXT,
            fecha_publicacion TEXT
        )
    """)

    # Tabla de log de actividad
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT,
            evento TEXT,
            detalle TEXT
        )
    """)

    conn.commit()
    conn.close()


def is_project_published(project_id):
    """Verifica si un proyecto ya fue publicado."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM published_projects WHERE project_id = ?", (project_id,))
    result = cursor.fetchone()
    conn.close()
    return result is not None


def mark_project_as_published(project_id, tipo, titulo, link, publicado_en="twitter"):
    """Marca un proyecto como publicado."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR IGNORE INTO published_projects 
        (project_id, tipo, titulo, link, publicado_en, fecha_publicacion)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (project_id, tipo, titulo, link, publicado_en, datetime.now().isoformat()))
    conn.commit()
    conn.close()


def log_activity(evento, detalle=""):
    """Registra actividad del bot."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO activity_log (fecha, evento, detalle)
        VALUES (?, ?, ?)
    """, (datetime.now().isoformat(), evento, detalle))
    conn.commit()
    conn.close()


def get_unpublished_projects(new_projects):
    """Filtra solo proyectos que no han sido publicados."""
    unpublished = []
    for project in new_projects:
        if not is_project_published(project["id"]):
            unpublished.append(project)
    return unpublished


# ============================================================
# SCRAPER
# ============================================================
class LegislativeScraper:
    """
    Scraper para el Congreso de Chile.
    Maneja: Proyectos de Ley, Resoluciones y Acuerdos.
    """

    BASE_URL = "https://www.camara.cl"

    URLS = {
        "ley": "https://www.camara.cl/legislacion/ProyectosDeLey/proyectos_ley.aspx",
        "resolucion": "https://www.camara.cl/legislacion/resoluciones/proyectos_resolucion.aspx",
        "acuerdo": "https://www.camara.cl/fiscalizacion/Acuerdos/proyectos_acuerdo.aspx",
    }

    def __init__(self, headless=True):
        self.headless = headless
        self.logger = logging.getLogger(__name__)

    def _get_absolute_url(self, relative_url):
        """Convierte URLs relativas a absolutas."""
        if not relative_url:
            return None
        if relative_url.startswith("http"):
            return relative_url
        return f"{self.BASE_URL}{relative_url if relative_url.startswith('/') else '/' + relative_url}"

    def _extract_project_id(self, link):
        """
        Extrae un ID único del proyecto desde su URL.
        Usa parámetros de query o el path completo como identifier.
        """
        if not link:
            return None
        parsed = urlparse(link)
        params = parse_qs(parsed.query)
        
        # Intentar obtener 'id' de los query params
        if "id" in params:
            return f"id_{params['id'][0]}"
        
        # Si no, usar el path como identificador
        return f"path_{parsed.path.strip('/')}"

    def _scrape_page(self, url, tipo, limit=3):
        """
        Extrae proyectos de una página específica.
        Retorna lista de dicts con: id, tipo, titulo, link, boletin
        """
        proyectos = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
            page = context.new_page()

            try:
                print(f"[*] Accediendo a ({tipo}): {url}")
                page.goto(url, wait_until="networkidle", timeout=60000)

                # Esperar a que los artículos carguen
                page.wait_for_selector("article.proyecto", timeout=20000)

                items = page.query_selector_all("article.proyecto")
                print(f"[+] Se encontraron {len(items)} proyectos de {tipo}. Limitando a los primeros {limit}.")

                for item in items[:limit]:
                    title_elem = item.query_selector("h3 a")
                    boletin_elem = item.query_selector(".numero") or item.query_selector(".link-boletin")

                    if title_elem:
                        titulo = title_elem.inner_text().strip()
                        link_relativo = title_elem.get_attribute("href")
                        link_abs = self._get_absolute_url(link_relativo)
                        project_id = self._extract_project_id(link_abs)

                        boletin = ""
                        if boletin_elem:
                            boletin = boletin_elem.inner_text()
                            boletin = boletin.replace("Nº Boletín:", "").replace("N Boletn:", "").strip()

                        proyectos.append({
                            "id": project_id,
                            "tipo": tipo,
                            "titulo": titulo,
                            "link": link_abs,
                            "boletin": boletin
                        })

            except Exception as e:
                print(f"[!] Error durante el scraping de {tipo}: {e}")
                log_activity("error_scraping", f"{tipo}: {str(e)}")
            finally:
                browser.close()
                print(f"[*] Navegador cerrado ({tipo}).")

        return proyectos

    def scrape_all(self, delay_between=180, limit_per_type=3):
        """
        Scrapea las 3 secciones con delay entre cada una.
        delay_between: segundos entre cada página (default 3 min = 180s)
        limit_per_type: cuantos proyectos traer de cada sección
        """
        all_projects = []

        for tipo, url in self.URLS.items():
            projects = self._scrape_page(url, tipo, limit=limit_per_type)
            all_projects.extend(projects)

            # Delay anti-detección entre páginas (excepto después de la última)
            if tipo != "acuerdo":
                delay = delay_between + random.uniform(-30, 30)  # Variación de ±30s
                print(f"[*] Esperando {delay:.0f} segundos antes de la siguiente página...")
                time.sleep(delay)

        return all_projects


# ============================================================
# GENERADOR DE TWEETS
# ============================================================
def generate_tweet(project):
    """
    Genera un tweet atractivo a partir de un proyecto.
    Formato: emoji + tipo + boletín + título + link + hashtags
    Garantiza que no exceda 280 caracteres.
    """
    tipo = project["tipo"]
    titulo = project["titulo"]
    link = project["link"]
    boletin = project.get("boletin", "")

    # Mapeo de tipos a emojis y etiquetas
    tipo_config = {
        "ley": {"emoji": "📜", "label": "PROYECTO DE LEY", "hashtag": "#ProyectoDeLey"},
        "resolucion": {"emoji": "📢", "label": "RESOLUCIÓN", "hashtag": "#Resolucion"},
        "acuerdo": {"emoji": "🤝", "label": "ACUERDO", "hashtag": "#Acuerdo"},
    }

    config = tipo_config.get(tipo, {"emoji": "📄", "label": "PROYECTO", "hashtag": "#CongresoChile"})

    # Construir tweet sin título aún para calcular espacio disponible
    base_parts = [f"{config['emoji']} {config['label']}"]
    if boletin:
        base_parts.append(f"Boletín Nº {boletin}")
    base_parts.append(f"🔗 {link}")
    base_parts.append(f"{config['hashtag']} #CongresoChile #LegislacionChile")
    
    base_text = "\n".join(base_parts)
    
    # Espacio disponible para el título (280 - base - nueva línea extra)
    max_titulo_len = 280 - len(base_text) - 2
    
    # Recortar título si es necesario
    if len(titulo) > max_titulo_len:
        titulo = titulo[:max_titulo_len - 3] + "..."

    # Construir tweet final
    tweet_lines = [base_parts[0]]
    if boletin:
        tweet_lines.append(base_parts[1])
    tweet_lines.append(titulo)
    tweet_lines.append(base_parts[-2])
    tweet_lines.append(base_parts[-1])
    
    tweet = "\n".join(tweet_lines)

    # Verificación final de seguridad
    if len(tweet) > 280:
        excess = len(tweet) - 280
        titulo = titulo[:len(titulo) - excess - 3] + "..."
        tweet_lines[2] = titulo
        tweet = "\n".join(tweet_lines)

    return tweet


# ============================================================
# MAIN
# ============================================================
def main():
    """
    Flujo principal del bot:
    1. Inicializar DB
    2. Scraping de las 3 secciones
    3. Filtrar no publicados
    4. Publicar tweets con delay anti-spam
    5. Marcar como publicados
    """
    print("=" * 60)
    print("🏛️  BOT CONGRESO CHILE - INICIANDO")
    print("=" * 60)

    # Inicializar base de datos
    init_db()
    log_activity("bot_start", "Bot iniciado")

    # Ejecutar scraping
    scraper = LegislativeScraper(headless=True)
    all_projects = scraper.scrape_all(delay_between=180)

    print(f"\n[+] Total proyectos encontrados: {len(all_projects)}")

    # Filtrar no publicados
    unpublished = get_unpublished_projects(all_projects)
    print(f"[+] Proyectos nuevos (no publicados): {len(unpublished)}")

    if not unpublished:
        print("[*] No hay proyectos nuevos para publicar.")
        log_activity("no_new_projects", "Todos los proyectos ya fueron publicados")
        return

    # Publicar tweets
    # IMPORTANTE: En producción, aquí se integra con Tweepy
    # Por ahora, simulamos la publicación
    print("\n" + "=" * 60)
    print("📝 TWEETS A PUBLICAR:")
    print("=" * 60)

    for i, project in enumerate(unpublished):
        tweet = generate_tweet(project)
        print(f"\n--- Tweet {i+1}/{len(unpublished)} ---")
        print(tweet)
        print(f"(Longitud: {len(tweet)}/280 chars)")

        # Delay anti-spam entre tweets (2 minutos = 120s)
        # En producción, aquí se publicaría con Tweepy
        if i < len(unpublished) - 1:
            delay = 120 + random.uniform(-10, 10)
            print(f"\n[*] Esperando {delay:.0f}s antes del siguiente tweet (anti-spam)...")
            # time.sleep(delay)  # Descomentar en producción

        # Marcar como publicado
        mark_project_as_published(
            project["id"],
            project["tipo"],
            project["titulo"],
            project["link"]
        )

    log_activity("bot_finish", f"Se procesaron {len(unpublished)} proyectos nuevos")
    print("\n" + "=" * 60)
    print("✅ BOT FINALIZADO CORRECTAMENTE")
    print("=" * 60)


if __name__ == "__main__":
    main()
