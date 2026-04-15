from playwright.sync_api import sync_playwright

def inspect_page(url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        print(f"Navigating to {url}")
        page.goto(url)
        page.wait_for_timeout(5000) # Wait for dynamic content
        
        frames = page.frames
        print(f"Number of frames: {len(frames)}")
        for i, frame in enumerate(frames):
            print(f"Frame {i}: {frame.name} - {frame.url}")
            # Try to find tables or lists in each frame
            tables = frame.query_selector_all("table")
            print(f"  Tables found: {len(tables)}")
            if len(tables) > 0:
                # Print a snippet of the first table
                content = frame.evaluate("() => document.querySelector('table').innerText")
                print(f"  Table 1 Content Snippet: {content[:200]}...")

        browser.close()

inspect_page("https://www.camara.cl/legislacion/ProyectosDeLey/proyectos_ley.aspx")
