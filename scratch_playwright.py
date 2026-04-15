from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    response = page.goto("https://www.camara.cl/legislacion/ProyectosDeLey/proyectos_ley.aspx")
    print("Status:", response.status)
    page.wait_for_timeout(3000) # wait 3 seconds
    
    html = page.content()
    with open("page.html", "w", encoding="utf-8") as f:
        f.write(html)
    browser.close()
