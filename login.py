import os
import json
import re
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
# After Continue, the Keycloak-hosted form re-renders with a disabled email field
# plus a password field, so target by type/autocomplete instead of Keycloak ids.
# ":visible" is required — the page keeps a hidden password input in the DOM too.
PASSWORD_SELECTOR = "form input[type='password'][autocomplete='current-password']:visible"
LOGIN_BUTTON_SELECTOR = "form button:has-text('Login'):visible"


# The pagination control was not part of the markup provided for the redesign,
# so try the known variants and fall back to treating the list as single-page.
NEXT_BUTTON_CANDIDATES = [
    '[data-testid="pagination-next"]',
    '[data-testid="pagination-next-page"]',
    'button[aria-label*="Next" i]',
    'a[aria-label*="Next" i]',
    "a.ap-pagination__next",
    'button:has-text("Next")',
]


# The order page now exposes the invoice directly: a "Freight invoice:"
# row with View / Download links, so no dropdown or modal is involved.
# The links are <a> without href, so match by text rather than by role.
FREIGHT_DOWNLOAD_SELECTOR = (
    'div:has(> span:text-is("Freight invoice:")) a:text-is("Download")'
)

# The download event occasionally never fires — the invoice is generated
# server-side and can take longer than one timeout window — so give each
# order several attempts with a progressively longer wait.
DOWNLOAD_TIMEOUTS_MS = [30000, 60000, 90000]


def download_invoice(page, link, order_id, output_dir):
    """Download one order's freight invoice. Returns True on success.

    Retries with a longer download timeout each attempt, and treats an
    already-downloaded PDF as done so a re-run resumes instead of restarting.
    """
    pdf_path = os.path.join(output_dir, f"{order_id}.pdf")
    if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0:
        print(f"  Skipped (already downloaded): {pdf_path}")
        return True

    for attempt, download_timeout in enumerate(DOWNLOAD_TIMEOUTS_MS, 1):
        if attempt > 1:
            print(f"  Retry {attempt}/{len(DOWNLOAD_TIMEOUTS_MS)} for order {order_id}...")
        try:
            page.goto(link)
            page.wait_for_load_state("networkidle")
            time.sleep(2)

            # Click the Freight invoice Download link and capture the file
            download_link = page.locator(FREIGHT_DOWNLOAD_SELECTOR).first
            download_link.wait_for(timeout=15000)

            with page.expect_download(timeout=download_timeout) as download_info:
                download_link.click()
            download = download_info.value
            download.save_as(pdf_path)
            print(f"  Saved: {pdf_path}")
            return True

        except Exception as e:
            print(f"  ERROR on order {order_id} (attempt {attempt}): {e}")
            # Back off before retrying; the invoice may still be generating.
            time.sleep(3 * attempt)

    print(f"  GIVING UP on order {order_id} after {len(DOWNLOAD_TIMEOUTS_MS)} attempts.")
    return False


def find_next_button(page):
    """Return a visible next-page control, or None if the list is single-page."""
    for selector in NEXT_BUTTON_CANDIDATES:
        candidate = page.locator(selector).first
        if candidate.count() > 0 and candidate.is_visible():
            return candidate
    return None


def is_clickable(locator):
    """A next button can be greyed out via disabled, aria-disabled or a class."""
    if not locator.is_enabled():
        return False
    if (locator.get_attribute("aria-disabled") or "").lower() == "true":
        return False
    classes = locator.get_attribute("class") or ""
    return "disabled" not in classes


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
        # Continue redirects through the Keycloak auth endpoint before the
        # password form renders, so let the navigation settle first.
        page.wait_for_load_state("networkidle")
        password_field = page.locator(PASSWORD_SELECTOR).first
        password_field.wait_for()

        print("Entering password...")
        password_field.fill(PASSWORD)

        print("Clicking Login...")
        page.locator(LOGIN_BUTTON_SELECTOR).first.click()

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

        # Open the "Delivered date" filter dropdown. Several filters share the
        # same testid, so pick the one showing the delivered-date label.
        print("Opening date picker dropdown...")
        datepicker_trigger = page.get_by_test_id("filter-dropdown-trigger").filter(
            has_text="Delivered date"
        ).first
        datepicker_trigger.wait_for()
        datepicker_trigger.click()

        # Select the "Last Month" preset by its label
        print("Selecting Last Month...")
        last_month_option = page.get_by_role("button", name="Last Month", exact=True).first
        last_month_option.wait_for()
        last_month_option.click()
        print("Date range selected.")

        # Some layouts still need an explicit apply; others filter immediately.
        try:
            done_button = page.get_by_role(
                "button", name=re.compile(r"^(Done|Apply)$", re.I)
            ).first
            done_button.wait_for(timeout=3000)
            print("Clicking Done...")
            done_button.click()
        except Exception:
            print("No Done button, filter applied directly.")

        print("Waiting 5 seconds for table to load...")
        time.sleep(5)

        # Wait for table to load. The redesigned table only has emotion-hashed
        # class names, so match on structure instead.
        row_selector = "table tbody tr"
        # First cell holds the LR number as a button (no href) plus the waybill.
        lr_button_selector = "table tbody tr td:first-child button"
        print("Waiting for table...")
        page.wait_for_selector(row_selector)

        # Collect all order LR numbers across all pages
        all_lr_numbers = []
        page_num = 1

        while True:
            print(f"Scraping page {page_num}...")
            page.wait_for_selector(row_selector)

            # Grab all LR numbers on this page
            buttons = page.query_selector_all(lr_button_selector)
            page_lrs = []
            for b in buttons:
                lr = (b.inner_text() or "").strip()
                if lr.isdigit():
                    page_lrs.append(lr)
            first_lr_before = page_lrs[0] if page_lrs else None
            all_lr_numbers.extend(page_lrs)
            print(f"  Found {len(page_lrs)} orders (total so far: {len(all_lr_numbers)})")

            next_btn = find_next_button(page)
            if next_btn is None:
                print("No pagination control found, assuming single page.")
                break

            if not is_clickable(next_btn):
                print("Reached last page.")
                break

            # Go to next page and wait for the first row to actually change
            next_btn.click()
            page_num += 1
            print(f"  Waiting for page {page_num} to load...")
            for _ in range(30):
                time.sleep(1)
                current = page.query_selector(lr_button_selector)
                if current and (current.inner_text() or "").strip() != first_lr_before:
                    break
            else:
                print("  Warning: page content did not change, stopping.")
                break
            time.sleep(2)

        print(f"\nCollected {len(all_lr_numbers)} orders total.")

        # Build order-details URLs from the LR numbers and save them
        base_url = "https://one.delhivery.com/ltl/order-details/"
        full_links = [base_url + lr for lr in all_lr_numbers]
        with open("order_links.json", "w") as f:
            json.dump(full_links, f, indent=2)
        print("Saved to order_links.json")

        # Download freight invoices for each order
        output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
        os.makedirs(output_dir, exist_ok=True)
        print(f"\nStarting invoice downloads to: {output_dir}")

        failed_orders = []

        for i, link in enumerate(full_links, 1):
            order_id = link.rstrip("/").split("/")[-1]
            print(f"\n[{i}/{len(full_links)}] Visiting order {order_id}...")
            if not download_invoice(page, link, order_id, output_dir):
                failed_orders.append((order_id, link))

        # Final sweep: orders that failed early may just have been slow to have
        # their invoice generated, so give them one more pass at the end.
        if failed_orders:
            print(f"\nRetrying {len(failed_orders)} failed orders...")
            still_failed = []
            for i, (order_id, link) in enumerate(failed_orders, 1):
                print(f"\n[retry {i}/{len(failed_orders)}] Order {order_id}...")
                if not download_invoice(page, link, order_id, output_dir):
                    still_failed.append(order_id)
            failed_orders = still_failed
        else:
            failed_orders = []

        downloaded = len(full_links) - len(failed_orders)
        print(f"\nAll done! {downloaded}/{len(full_links)} PDFs saved in: {output_dir}")

        if failed_orders:
            # Record the LR numbers so they can be chased up or re-run later.
            with open("failed_orders.json", "w") as f:
                json.dump(failed_orders, f, indent=2)
            print(f"FAILED ({len(failed_orders)}) — saved to failed_orders.json:")
            for order_id in failed_orders:
                print(f"  {order_id}")
        else:
            print("No failures.")

        browser.close()


if __name__ == "__main__":
    login()
