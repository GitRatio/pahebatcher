"""Visual layout QA for the native Bunny Takeover HTML shell.

Run with: python -m pip install playwright && python -m playwright install chromium
          python scripts/ui_visual_check.py

Snapshots use explicit fixture data ONLY for screenshot QA, never in production.
"""
from __future__ import annotations

import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright

ASSETS = Path(__file__).resolve().parents[1] / 'src' / 'pahebatcher' / 'gui' / 'assets'
OUT = Path('ui-snapshots')


def main() -> None:
    OUT.mkdir(exist_ok=True)
    handler = partial(SimpleHTTPRequestHandler, directory=str(ASSETS))
    server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with sync_playwright() as driver:
            browser = driver.chromium.launch(headless=True, args=['--no-sandbox'])
            for width, height in ((1448, 1086), (1100, 820), (820, 950)):
                page = browser.new_page(viewport={'width': width, 'height': height}, device_scale_factor=1)
                errors: list[str] = []
                page.on('pageerror', lambda exc: errors.append(str(exc)))
                page.goto(f'http://127.0.0.1:{server.server_port}/desktop.html', wait_until='load')
                page.evaluate('''() => {
                  document.querySelectorAll('.page').forEach(p => p.classList.remove('current'));
                  document.querySelector('#page-episodes').classList.add('current');
                  document.querySelector('#series-title').textContent = 'Example Anime — UI Layout Test';
                  document.querySelector('#series-summary').textContent = '24 episodes · test data';
                  document.querySelector('#series-description').textContent =
                    'Synopsis panel: layout-only synthetic data to check responsive wrapping.';
                  document.querySelector('#episode-count').textContent = '(24)';
                  document.querySelector('#episode-list').innerHTML = Array.from({length:8}, (_,i)=>
                    `<label class="episode${i<3?' selected':''}"><input type="checkbox" ${i<3?'checked':''}><div class="ep-thumb">${String(i+1).padStart(2,'0')}</div><div class="episode-text"><strong>Ep ${i+1} — Example episode title for layout tests</strong><small>Source audio · Episode ${i+1}</small></div></label>`
                  ).join('');
                  document.querySelector('#download-selected').disabled = false;
                  document.querySelector('#mobile-download-selected').disabled = false;
                  document.querySelector('#download-selected').textContent = '↓ Download 3 episodes';
                  document.querySelector('#mobile-download-selected').textContent = '↓ Download 3 episodes';
                  document.querySelector('#selection-summary').textContent =
                     '3 episodes selected · size estimate';
                }''')
                page.screenshot(path=str(OUT / f'episodes-{width}x{height}.png'), full_page=True)
                cta = page.locator('#download-selected')
                assert cta.count() == 1 and cta.is_visible(), 'Download action must render'
                bounds = cta.bounding_box()
                assert bounds is not None and bounds['width'] >= 180
                assert bounds['x'] >= 0 and bounds['x'] + bounds['width'] <= width + 1
                action = page.locator('#mobile-download-selected') if width <= 1050 else cta
                visible = action.bounding_box()
                assert visible is not None and visible['y'] + visible['height'] <= height + 1, 'Download CTA clipped below viewport'
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), 'Horizontal overflow'
                assert not errors, f'Browser JavaScript errors: {errors}'
                print(f'PASS {width}x{height} — Download CTA bounds {bounds}')
                page.close()
            browser.close()
    finally:
        server.shutdown()


if __name__ == '__main__':
    main()