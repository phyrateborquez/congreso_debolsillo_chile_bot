"""
Bot de Twitter para el Congreso de Chile.
Integra el scraper con Tweepy para publicación automática.
"""
import os
import sys
import time
import random
import tweepy
from datetime import datetime

# Importar funciones del scraper
sys.path.append(os.path.dirname(__file__))
from scraper import (
    init_db,
    get_unpublished_projects,
    mark_project_as_published,
    log_activity,
    generate_tweet,
    LegislativeScraper,
)


# ============================================================
# CONFIGURACIÓN DE TWITTER API
# ============================================================
def get_twitter_client():
    """
    Inicializa el cliente de Twitter API v2.
    Las credenciales se leen de variables de entorno (GitHub Secrets).
    """
    consumer_key = os.environ.get("TWITTER_API_KEY")
    consumer_secret = os.environ.get("TWITTER_API_SECRET")
    access_token = os.environ.get("TWITTER_ACCESS_TOKEN")
    access_token_secret = os.environ.get("TWITTER_ACCESS_TOKEN_SECRET")
    bearer_token = os.environ.get("TWITTER_BEARER_TOKEN")

    # Validar que existan todas las credenciales
    if not all([consumer_key, consumer_secret, access_token, access_token_secret, bearer_token]):
        raise ValueError("❌ Faltan credenciales de Twitter API. Configura las variables de entorno.")

    # Inicialización del cliente de Twitter API v2
    client = tweepy.Client(
        bearer_token=bearer_token,
        consumer_key=consumer_key,
        consumer_secret=consumer_secret,
        access_token=access_token,
        access_token_secret=access_token_secret
    )

    return client


# ============================================================
# PUBLICACIÓN DE TWEETS
# ============================================================
def publish_tweet(client, tweet_text):
    """
    Publica un tweet y retorna la respuesta.
    Manejo de errores incluido.
    """
    try:
        print(f"[*] Publicando tweet ({len(tweet_text)} chars)...")
        response = client.create_tweet(text=tweet_text)
        tweet_id = response.data["id"]
        print(f"[+] Tweet publicado exitosamente. ID: {tweet_id}")
        return tweet_id
    except tweepy.TooManyRequests:
        print("[!] Rate limit excedido. Esperando...")
        time.sleep(300)  # Esperar 5 minutos
        return None
    except tweepy.Unauthorized:
        print("[!] Error de autenticación. Verifica las credenciales.")
        return None
    except tweepy.Forbidden:
        print("[!] Acceso denegado. Posible suspensión o restricción.")
        return None
    except Exception as e:
        print(f"[!] Error al publicar: {e}")
        return None


# ============================================================
# FLUJO PRINCIPAL DEL BOT
# ============================================================
def main():
    """
    Flujo completo:
    1. Inicializar DB
    2. Scraping de las 3 secciones (con delays)
    3. Filtrar no publicados
    4. Publicar tweets con Tweepy (delay anti-spam de 2 min)
    5. Marcar como publicados
    """
    print("=" * 60)
    print("🏛️  BOT CONGRESO CHILE - INICIANDO")
    print(f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # Inicializar base de datos
    init_db()
    log_activity("bot_start", "Bot iniciado")

    # 1. Ejecutar scraping
    scraper = LegislativeScraper(headless=True)
    all_projects = scraper.scrape_all(delay_between=180)

    print(f"\n[+] Total proyectos encontrados: {len(all_projects)}")

    # 2. Filtrar no publicados
    unpublished = get_unpublished_projects(all_projects)
    print(f"[+] Proyectos nuevos (no publicados): {len(unpublished)}")

    if not unpublished:
        print("[*] No hay proyectos nuevos para publicar.")
        log_activity("no_new_projects", "Todos los proyectos ya fueron publicados")
        return

    # 3. Conectar con Twitter API
    try:
        client = get_twitter_client()
        print("[+] Conectado a Twitter API exitosamente.")
    except ValueError as e:
        print(f"[!] {e}")
        log_activity("error_auth", "Faltan credenciales de Twitter")
        sys.exit(1)
    except Exception as e:
        print(f"[!] Error al conectar con Twitter: {e}")
        log_activity("error_connection", str(e))
        sys.exit(1)

    # 4. Publicar tweets
    print("\n" + "=" * 60)
    print("📝 PUBLICANDO TWEETS:")
    print("=" * 60)

    published_count = 0
    failed_count = 0

    for i, project in enumerate(unpublished):
        tweet = generate_tweet(project)
        print(f"\n--- Tweet {i+1}/{len(unpublished)} ---")
        print(tweet)
        print(f"(Longitud: {len(tweet)}/280 chars)")

        # Publicar
        tweet_id = publish_tweet(client, tweet)

        if tweet_id:
            # Marcar como publicado
            mark_project_as_published(
                project["id"],
                project["tipo"],
                project["titulo"],
                project["link"],
                publicado_en=f"twitter:{tweet_id}"
            )
            published_count += 1
        else:
            failed_count += 1
            print(f"[!] No se pudo publicar el tweet {i+1}")
            log_activity("tweet_failed", f"Proyecto: {project['id']}")

        # Delay anti-spam entre tweets (2 minutos + variación)
        if i < len(unpublished) - 1:
            delay = 120 + random.uniform(-10, 10)
            print(f"\n[*] Esperando {delay:.0f}s antes del siguiente tweet (anti-spam)...")
            time.sleep(delay)

    # 5. Resumen final
    log_activity(
        "bot_finish",
        f"Publicados: {published_count}, Fallidos: {failed_count}"
    )
    print("\n" + "=" * 60)
    print("✅ BOT FINALIZADO")
    print(f"📊 Tweets publicados: {published_count}")
    print(f"❌ Tweets fallidos: {failed_count}")
    print("=" * 60)


if __name__ == "__main__":
    main()
