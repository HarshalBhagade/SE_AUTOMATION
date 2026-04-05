import os
import json
import time
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()

EMAIL = os.getenv("DELHIVERY_EMAIL")
PASSWORD = os.getenv("DELHIVERY_PASSWORD")

EMAIL_SELECTOR = (
    "#root > div > div > "
    "div.bg-delhivery-background-default.rounded-lg.shadow-delhivery-lg.w-full.max-w-md.relative.z-10 > "
    "div.w-full.max-w-sm.mx-auto.bg-delhivery-background-default.font-ibm.p-8 > "
    "form > div:nth-child(1) > div > div.flex.relative > section > input"
)
CONTINUE_BUTTON_SELECTOR = (
    "#root > div > div > "
    "div.bg-delhivery-background-default.rounded-lg.shadow-delhivery-lg.w-full.max-w-md.relative.z-10 > "
    "div.w-full.max-w-sm.mx-auto.bg-delhivery-background-default.font-ibm.p-8 > "
    "form > button"
)
PASSWORD_SELECTOR = "#password"
LOGIN_BUTTON_SELECTOR = "#kc-login"


def login():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        print("Navigating to login page...")
        page.goto("https://one.delhivery.com/v2/login")
        page.wait_for_load_state("networkidle")

        print("Entering email...")
        page.wait_for_selector(EMAIL_SELECTOR)
        page.fill(EMAIL_SELECTOR, EMAIL)

        print("Clicking Continue...")
        page.click(CONTINUE_BUTTON_SELECTOR)

        print("Waiting for password page...")
        page.wait_for_selector(PASSWORD_SELECTOR)

        print("Entering password...")
        page.fill(PASSWORD_SELECTOR, PASSWORD)

        print("Clicking Login...")
        page.click(LOGIN_BUTTON_SELECTOR)

        print("Waiting for post-login page...")
        page.wait_for_load_state("networkidle")

        print(f"Logged in! Current URL: {page.url}")

        # Close password reset popup if it appears
        reset_popup_selector = (
            "body > div.ap-modal.ap-modal--show.ap-modal--latest > "
            "div > div > section > button"
        )
        try:
            print("Checking for password reset popup...")
            page.wait_for_selector(reset_popup_selector, timeout=5000)
            page.click(reset_popup_selector)
            print("Closed password reset popup.")
        except Exception:
            print("No password reset popup found, continuing...")

        # Click the tenant selection dropdown
        tenant_dropdown_selector = (
            "#app > div > div > div.default-layout__header > div > "
            "div.ucp-headers__right > div.ucp__inputs--list-search.ucp-headers__tenant-selection.ml-2 > "
            "div.ap-meta-label > button > div > div"
        )
        print("Clicking tenant selection dropdown...")
        page.wait_for_selector(tenant_dropdown_selector)
        page.click(tenant_dropdown_selector)

        # Select "B2B Surface" from the dropdown
        print("Selecting B2B Surface...")
        page.wait_for_selector("div.item-title.utility-label.text-font-default-black.max-w-full.truncate")
        page.locator(
            "div.item-title.utility-label.text-font-default-black.max-w-full.truncate",
            has_text="B2B Surface"
        ).click()
        print("Selected B2B Surface.")

        page.wait_for_load_state("networkidle")
        print(f"Ready. Current URL: {page.url}")

        # Navigate to delivered orders page
        print("Navigating to delivered orders...")
        page.goto("https://one.delhivery.com/ltl/orders/delivered")
        page.wait_for_load_state("networkidle")

        # Close password reset popup again if it appears
        try:
            print("Checking for password reset popup...")
            page.wait_for_selector(reset_popup_selector, timeout=5000)
            page.click(reset_popup_selector)
            print("Closed password reset popup.")
        except Exception:
            print("No password reset popup, continuing...")

        # Open date picker dropdown
        datepicker_trigger_selector = (
            "#app > div > div > div.wide-layout__content.layout-content.scrollbar.py-4.pr-3.pl-1 > "
            "div > div.px-4\\.25.w-\\[calc\\(100\\%-15rem\\)\\] > div > div.search-n-filter > "
            "div.ap-datepicker.ap-datepicker--mobile > div > "
            "div.ap-dropdown-trigger-container.ap-drop__trigger > div > div > span:nth-child(1)"
        )
        print("Opening date picker dropdown...")
        page.wait_for_selector(datepicker_trigger_selector)
        page.click(datepicker_trigger_selector)

        # Select the 6th option from the dropdown
        datepicker_option_selector = (
            "#app > div > div > div.wide-layout__content.layout-content.scrollbar.py-4.pr-3.pl-1 > "
            "div > div.px-4\\.25.w-\\[calc\\(100\\%-15rem\\)\\] > div > div.search-n-filter > "
            "div.ap-datepicker.ap-datepicker--mobile > div > "
            "div.ap-drop__menu.ap-drop__menu--bottom-right.ap-drop__menu--active > "
            "div > div > div.flex.flex-col.min-w-48.py-2.text-left.-ml-4.-my-4 > div:nth-child(6)"
        )
        print("Selecting date range option...")
        page.wait_for_selector(datepicker_option_selector)
        page.click(datepicker_option_selector)
        print("Date range selected.")

        # Click Done button to apply date range
        done_button_selector = (
            "#app > div > div > div.wide-layout__content.layout-content.scrollbar.py-4.pr-3.pl-1 > "
            "div > div.px-4\\.25.w-\\[calc\\(100\\%-15rem\\)\\] > div > div.search-n-filter > "
            "div.ap-datepicker.ap-datepicker--mobile > div > "
            "div.ap-drop__menu.ap-drop__menu--bottom-right.ap-drop__menu--active > "
            "div > div > div:nth-child(2) > footer > div > button.ap-button.blue.base.rounded.filled"
        )
        print("Clicking Done...")
        page.wait_for_selector(done_button_selector)
        page.click(done_button_selector)

        print("Waiting 5 seconds for table to load...")
        time.sleep(5)

        # Wait for table to load
        table_selector = (
            "#app > div > div > div.wide-layout__content.layout-content.scrollbar.py-4.pr-3.pl-1 > "
            "div > div.px-4\\.25.w-\\[calc\\(100\\%-15rem\\)\\] > div > "
            "div.ucp__listing__list-container__table-container.flex.mb-4 > div > "
            "div.ap-table__wrapper.ap-table__wrapper--sticky-header > table"
        )
        print("Waiting for table...")
        page.wait_for_selector(table_selector)

        # Collect all order links across all pages
        all_links = []
        page_num = 1

        next_btn_active = "a.ap-pagination__next:not(.ap-pagination__link--disabled)"
        next_btn_any = "a.ap-pagination__next"

        while True:
            print(f"Scraping page {page_num}...")
            page.wait_for_selector(table_selector)

            # Grab all LR Number links on this page
            anchors = page.query_selector_all(
                "td.ap-table__td a.utility-label.text-cta-primary.cursor-pointer"
            )
            page_links = [a.get_attribute("href") for a in anchors if a.get_attribute("href")]
            all_links.extend(page_links)
            print(f"  Found {len(page_links)} links (total so far: {len(all_links)})")

            # Check if next page button exists and is NOT disabled
            next_btn = page.query_selector(next_btn_any)
            if not next_btn:
                print("No pagination found, done.")
                break

            classes = next_btn.get_attribute("class") or ""
            if "ap-pagination__link--disabled" in classes:
                print("Reached last page.")
                break

            # Go to next page
            next_btn.click()
            page_num += 1
            print(f"  Waiting for page {page_num} to load...")
            time.sleep(3)
            page.wait_for_load_state("networkidle")
            page.wait_for_selector(table_selector)
            time.sleep(2)

        print(f"\nCollected {len(all_links)} order links total.")

        # Save links to file
        base_url = "https://one.delhivery.com"
        full_links = [base_url + link for link in all_links]
        with open("order_links.json", "w") as f:
            json.dump(full_links, f, indent=2)
        print("Saved to order_links.json")

        # Download freight invoices for each order
        output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
        os.makedirs(output_dir, exist_ok=True)
        print(f"\nStarting invoice downloads to: {output_dir}")

        view_download_selector = (
            "#app > div > div > div.default-layout__content.scrollbar > "
            "div:nth-child(2) > main > section > section > div.flex.gap-x-4 > "
            "div:nth-child(1) > div.ap-dropdown-trigger-container.ap-drop__trigger > button"
        )
        freight_invoice_selector = (
            "#app > div > div > div.default-layout__content.scrollbar > "
            "div:nth-child(2) > main > section > section > div.flex.gap-x-4 > "
            "div:nth-child(1) > div.ap-drop__menu.ap-drop__menu--bottom-left.ap-drop__menu--active > "
            "div:nth-child(1)"
        )
        download_btn_selector = (
            "body > div.ap-modal.ap-modal--show.ap-modal--latest > "
            "div > div.modal__body > div > div > button"
        )

        for i, link in enumerate(full_links, 1):
            order_id = link.rstrip("/").split("/")[-1]
            print(f"\n[{i}/{len(full_links)}] Visiting order {order_id}...")

            try:
                page.goto(link)
                page.wait_for_load_state("networkidle")
                time.sleep(2)

                # Close password reset popup if it appears
                try:
                    page.wait_for_selector(reset_popup_selector, timeout=3000)
                    page.click(reset_popup_selector)
                    print("  Closed password reset popup.")
                except Exception:
                    pass

                # Click View & Download button
                page.wait_for_selector(view_download_selector, timeout=10000)
                page.click(view_download_selector)
                time.sleep(1)

                # Select Freight Invoice
                page.wait_for_selector(freight_invoice_selector, timeout=5000)
                page.click(freight_invoice_selector)
                time.sleep(1)

                # Wait for modal and trigger download
                page.wait_for_selector(download_btn_selector, timeout=10000)

                pdf_path = os.path.join(output_dir, f"{order_id}.pdf")
                with page.expect_download(timeout=30000) as download_info:
                    page.click(download_btn_selector)
                download = download_info.value
                download.save_as(pdf_path)
                print(f"  Saved: {pdf_path}")

            except Exception as e:
                print(f"  ERROR on order {order_id}: {e}")
                continue

        print(f"\nAll done! PDFs saved in: {output_dir}")
        browser.close()


if __name__ == "__main__":
    login()
