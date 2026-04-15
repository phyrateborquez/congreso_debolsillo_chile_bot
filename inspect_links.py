from playwright.sync_api import sync_playwright

def inspect_links(url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url)
        page.wait_for_timeout(5000)
        
        links = page.query_selector_all("a")
        print(f"Total links found: {len(links)}")
        for link in links:
            href = link.get_attribute("href")
            text = link.inner_text().strip()
            if href and ("boletin" in href.lower() or "id=" in href.lower()):
                print(f"Link: {text} -> {href}")

        browser.close()

print("--- LEYES ---")
inspect_links("https://www.camara.cl/legislacion/ProyectosDeLey/proyectos_ley.aspx")
