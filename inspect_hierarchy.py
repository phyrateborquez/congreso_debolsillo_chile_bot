from playwright.sync_api import sync_playwright

def inspect_structure(url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url)
        page.wait_for_timeout(5000)
        
        # Look for the links and trace up to find the common container
        first_boletin = page.query_selector("a:has-text('Boletín')")
        if first_boletin:
            print("Found a boletin link.")
            parent = first_boletin.evaluate_handle("el => el.parentElement")
            grandparent = parent.evaluate_handle("el => el.parentElement")
            print(f"Parent tag: {parent.evaluate('el => el.tagName')}, Class: {parent.evaluate('el => el.className')}")
            print(f"Grandparent tag: {grandparent.evaluate('el => el.tagName')}, Class: {grandparent.evaluate('el => el.className')}")
            
            # Show the HTML of the grandparent to see the sibling structure
            print("--- Container HTML ---")
            print(grandparent.evaluate("el => el.outerHTML")[:1000])
        else:
            print("No boletin link found.")

        browser.close()

inspect_structure("https://www.camara.cl/legislacion/ProyectosDeLey/proyectos_ley.aspx")
