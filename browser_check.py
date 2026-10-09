"""Optional UI check: pip install playwright; playwright install chromium."""
import argparse
import uuid
from playwright.sync_api import sync_playwright, expect


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-url', default='http://127.0.0.1:8082')
    args = parser.parse_args()
    title = 'Browser check '+uuid.uuid4().hex[:8]
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1280, 'height': 900})
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(args.base_url)
        expect(page.locator('#status')).to_have_text('Ready for your day')
        page.locator('#title').fill(title)
        page.locator('#priority').select_option('high')
        page.locator('#add').click()
        expect(page.get_by_text(title, exact=True)).to_be_visible()
        page.reload()
        expect(page.get_by_text(title, exact=True)).to_be_visible()
        page.get_by_role('button', name='Complete '+title, exact=True).click()
        expect(page.get_by_role('button', name='Reopen '+title, exact=True)).to_be_visible()
        page.get_by_role('button', name='Done', exact=True).click()
        expect(page.get_by_text(title, exact=True)).to_be_visible()
        page.get_by_role('button', name='Delete '+title, exact=True).click()
        expect(page.get_by_text(title, exact=True)).not_to_be_visible()
        page.get_by_role('button', name='All', exact=True).click()
        page.set_viewport_size({'width': 390, 'height': 844})
        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
        assert not errors, errors
        browser.close()
    print('PASS: UI add, reload, complete, filter, delete, JavaScript execution and mobile width')


if __name__ == '__main__':
    main()
