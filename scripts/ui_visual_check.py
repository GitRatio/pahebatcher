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
            # High-DPI cases use reduced CSS viewports matching a 1100px window at
            # 125% and 150% OS scale. DPR alone would not expose layout clipping.
            cases = (
                (1448, 1086, 1),
                (1100, 820, 1),
                (820, 950, 1),
                (880, 820, 1.25),
                (733, 820, 1.5),
            )
            for width, height, scale in cases:
                page = browser.new_page(
                    viewport={'width': width, 'height': height}, device_scale_factor=scale
                )
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
                page.screenshot(
                    path=str(OUT / f'episodes-{width}x{height}-scale-{scale}.png'),
                    full_page=True,
                )
                cta = page.locator('#download-selected')
                assert cta.count() == 1 and cta.is_visible(), 'Download action must render'
                bounds = cta.bounding_box()
                assert bounds is not None and bounds['width'] >= 180
                assert bounds['x'] >= 0 and bounds['x'] + bounds['width'] <= width + 1
                action = page.locator('#mobile-download-selected') if width <= 1050 else cta
                visible = action.bounding_box()
                assert visible is not None and visible['y'] + visible['height'] <= height + 1, 'Download CTA clipped below viewport'
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), 'Horizontal overflow'
                # The mascot used to overlap the lower menu at short heights.
                # Check actual hit targets, not just visible CSS rectangles.
                if width > 760:
                    for item in page.locator('.nav button').all():
                        rect = item.bounding_box()
                        assert rect is not None
                        center_x = rect['x'] + rect['width'] / 2
                        center_y = rect['y'] + rect['height'] / 2
                        if 0 <= center_y <= height:
                            target = page.evaluate(
                                '({x,y}) => document.elementFromPoint(x,y)?.closest(".nav button")?.dataset.nav',
                                {'x': center_x, 'y': center_y},
                            )
                            assert target == item.get_attribute('data-nav'), 'Artwork covers navigation'
                assert not errors, f'Browser JavaScript errors: {errors}'
                print(f'PASS {width}x{height} — Download CTA bounds {bounds}')
                page.close()
            # Exercise the real frontend event handlers against a controlled mock
            # Python bridge. This catches inert controls and navigation regressions.
            screen = browser.new_page(viewport={'width': 1448, 'height': 1086})
            screen.add_init_script("""(() => {
              const episodes = Array.from({length:12}, (_,i)=>({
                ep_str:String(i+1),title:'Fixture Episode '+String(i+1),
                number:i+1,session:'ep'+String(i+1),audio:'jpn'}));
              window.pywebview = {api: {
                bootstrap: async()=>({solver_ok:true,settings:{quality:720,audio_lang:'jpn',
                  max_parallel:2,output_dir:'Test Downloads'}}),
                search: async()=>[{title:'Integration Test Anime',session:'fixture',
                  type:'TV',year:2026,episodes:12}],
                scan: async()=>({title:'Integration Test Anime',
                  description:'Real JavaScript event-handler fixture.',episodes}),
                save_settings: async()=>({ok:true}),
                download: async()=>({started:true}),
                status: async()=>({active:false,title:'Integration Test Anime',
                  fraction:0,items:[],message:'Download accepted in fixture'}),
                library: async()=>[],play:async()=>({ok:true})
              }};
            })();""")
            screen.goto(f'http://127.0.0.1:{server.server_port}/desktop.html', wait_until='load')
            screen.locator('#query').wait_for()
            screen.screenshot(path=str(OUT / 'home-1448x1086.png'), full_page=True)
            # Verify every visible navigation destination remains clickable with
            # the decorative bunny artwork enabled (including bottom menu items).
            for destination in ('downloads', 'library', 'settings', 'about', 'home'):
                screen.locator('.nav button[data-nav="' + destination + '"]').click()
                screen.locator('#page-' + destination + '.current').wait_for()
            screen.locator('#query').fill('Example')
            screen.locator('#search-button').click()
            screen.locator('.result-card').first.wait_for()
            screen.locator('.result-card').first.click()
            screen.locator('#page-episodes.current').wait_for()
            inputs = screen.locator('#episode-list input[type=checkbox]')
            assert inputs.count() == 12, 'Source episodes must be rendered by JS'
            for i in range(3):
                inputs.nth(i).check()
            cta = screen.locator('#download-selected')
            assert cta.is_enabled() and '3 episodes' in cta.inner_text()
            screen.screenshot(path=str(OUT / 'interactive-episodes-1448x1086.png'), full_page=True)
            cta.click()
            screen.locator('#page-downloads.current').wait_for()
            print('PASS real frontend search → scan → select → Download navigation')
            screen.close()
            browser.close()
    finally:
        server.shutdown()


if __name__ == '__main__':
    main()