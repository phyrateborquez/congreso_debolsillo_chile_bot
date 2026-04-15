from playwright.sync_api import sync_playwright

def check_other_urls(urls):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        for url in urls:
            print(f"\n--- Checking {url} ---")
            page.goto(url)
            page.wait_for_timeout(5000)
            
            # Try the same article.proyecto selector
            articles = page.query_selector_all("article")
            print(f"Total articles found: {len(articles)}")
            if articles:
                for art in articles[:2]:
                    print(f"Article class: {art.get_attribute('class')}")
                    print(f"Content snippet: {art.inner_text().strip()[:100]}...")
            else:
                # If no articles, list all links to see what's there
                links = page.query_selector_all("a")
                for link in links[:10]:
                    print(f"Link: {link.inner_text().strip()} -> {link.get_attribute('href')}")

        browser.close()

urls = [
    "https://www.camara.cl/legislacion/resoluciones/proyectos_resolucion.aspx",
    "https://www.camara.cl/fiscalizacion/Acuerdos/proyectos_acuerdo.aspx"
]
check_other_urls(urls)
