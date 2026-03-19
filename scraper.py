import time
import os
import pickle
import subprocess
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys

DEEPSEEK_URL = "https://chat.deepseek.com"
COOKIE_FILE = "deepseek_cookies.pkl"

# Edge binary + driver candidates (same folder)
EDGE_DIRS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application",
    r"C:\Program Files\Microsoft\Edge\Application",
]

_username = os.environ.get("USERNAME", "user")
CHROME_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.join("C:\\Users", _username, "AppData", "Local",
                 "Google", "Chrome", "Application", "chrome.exe"),
]


def _find_edge() -> tuple:
    """Return (msedge.exe path, msedgedriver.exe path) or (None, None)."""
    for d in EDGE_DIRS:
        edge_bin = os.path.join(d, "msedge.exe")
        if not os.path.exists(edge_bin):
            continue
        # msedgedriver lives in the same versioned sub-folder or alongside
        driver_path = os.path.join(d, "msedgedriver.exe")
        if os.path.exists(driver_path):
            return edge_bin, driver_path
        # search versioned sub-directories
        for item in os.listdir(d):
            candidate = os.path.join(d, item, "msedgedriver.exe")
            if os.path.exists(candidate):
                return edge_bin, candidate
        # driver not found in install dir; return binary only (will use PATH)
        return edge_bin, None
    return None, None


def find_browser() -> tuple:
    """
    Returns (browser_type, binary_path, driver_path).
    driver_path may be None (use PATH / webdriver-manager as fallback).
    """
    edge_bin, edge_drv = _find_edge()
    if edge_bin:
        return "edge", edge_bin, edge_drv
    for p in CHROME_PATHS:
        if os.path.exists(p):
            return "chrome", p, None
    return "chrome", None, None


def build_driver(headless: bool = True, user_data_dir: str = None):
    """Build Edge (preferred) or Chrome WebDriver using local binaries."""
    browser, binary, driver_exe = find_browser()
    print(f"[Browser] {browser} | binary={binary} | driver={driver_exe}")

    if browser == "edge":
        from selenium.webdriver.edge.options import Options as EdgeOptions
        from selenium.webdriver.edge.service import Service as EdgeService

        opts = EdgeOptions()
        if binary:
            opts.binary_location = binary
        if headless:
            opts.add_argument("--headless=new")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--window-size=1280,900")
        opts.add_argument("--lang=zh-TW")
        if user_data_dir:
            opts.add_argument(f"--user-data-dir={user_data_dir}")

        if driver_exe:
            service = EdgeService(executable_path=driver_exe)
        else:
            # Fallback: let Selenium find msedgedriver on PATH
            service = EdgeService()
        return webdriver.Edge(service=service, options=opts)

    else:
        from selenium.webdriver.chrome.options import Options as ChromeOptions
        from selenium.webdriver.chrome.service import Service as ChromeService

        opts = ChromeOptions()
        if binary:
            opts.binary_location = binary
        if headless:
            opts.add_argument("--headless=new")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--window-size=1280,900")
        opts.add_argument("--lang=zh-TW")
        if user_data_dir:
            opts.add_argument(f"--user-data-dir={user_data_dir}")

        # Try local chromedriver on PATH first
        try:
            service = ChromeService()
            return webdriver.Chrome(service=service, options=opts)
        except Exception:
            from webdriver_manager.chrome import ChromeDriverManager
            from selenium.webdriver.chrome.service import Service as CS2
            service = CS2(ChromeDriverManager().install())
            return webdriver.Chrome(service=service, options=opts)


def filter_bmp(text: str) -> str:
    """Strip non-BMP chars to avoid msedgedriver BMP-only crash."""
    return "".join(c for c in text if ord(c) < 0x10000)


def set_input_value_js(driver, element, text: str):
    """React-compatible JS text injection."""
    safe = filter_bmp(text)
    driver.execute_script("""
        var el = arguments[0];
        var text = arguments[1];
        var setter = Object.getOwnPropertyDescriptor(
            window.HTMLTextAreaElement.prototype, 'value') ||
            Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value');
        if (setter) { setter.set.call(el, text); } else { el.value = text; }
        el.dispatchEvent(new Event('input', { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));
    """, element, safe)


def try_load_cookies(driver) -> bool:
    if not os.path.exists(COOKIE_FILE):
        return False
    try:
        driver.get(DEEPSEEK_URL)
        time.sleep(2)
        with open(COOKIE_FILE, "rb") as f:
            cookies = pickle.load(f)
        for c in cookies:
            try:
                driver.add_cookie(c)
            except Exception:
                pass
        driver.refresh()
        time.sleep(3)
        return True
    except Exception:
        return False


def save_cookies(driver):
    try:
        with open(COOKIE_FILE, "wb") as f:
            pickle.dump(driver.get_cookies(), f)
    except Exception:
        pass


def login_with_password(driver, wait, email: str, password: str) -> bool:
    try:
        driver.get(DEEPSEEK_URL)
        time.sleep(3)
        try:
            btn = wait.until(EC.element_to_be_clickable((
                By.XPATH,
                "//*[contains(text(),'Log in') or contains(text(),'Sign in')"
                " or contains(text(),'login') or contains(text(),'sign in')]"
            )))
            btn.click()
            time.sleep(2)
        except Exception:
            pass

        email_el = wait.until(EC.presence_of_element_located((
            By.CSS_SELECTOR,
            "input[type='email'], input[name='email'], input[placeholder*='mail']"
        )))
        email_el.clear()
        email_el.send_keys(filter_bmp(email))
        time.sleep(0.5)

        pw_el = driver.find_element(
            By.CSS_SELECTOR, "input[type='password'], input[name='password']")
        pw_el.clear()
        pw_el.send_keys(filter_bmp(password))
        time.sleep(0.5)
        pw_el.send_keys(Keys.RETURN)
        time.sleep(5)

        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "textarea")))
        save_cookies(driver)
        print("[Login] Password login OK, cookies saved")
        return True
    except Exception as e:
        print(f"[Login] Password login failed: {e}")
        return False


def wait_for_response(driver, timeout: int = 90) -> str:
    time.sleep(4)
    last_text = ""
    stable_count = 0
    selectors = [
        "div[class*='ds-markdown']",
        "div[data-role='assistant']",
        "div[class*='message'][class*='assistant']",
        ".markdown",
    ]
    for _ in range(timeout):
        for sel in selectors:
            msgs = driver.find_elements(By.CSS_SELECTOR, sel)
            if msgs:
                current = msgs[-1].text.strip()
                if current and current == last_text:
                    stable_count += 1
                    if stable_count >= 3:
                        return current
                elif current:
                    stable_count = 0
                    last_text = current
                break
        time.sleep(1)
    return last_text or "No response captured."


def scrape_deepseek(
    prompt: str,
    email: str = "",
    password: str = "",
    headless: bool = True,
    user_data_dir: str = None
) -> str:
    driver = build_driver(headless=headless, user_data_dir=user_data_dir)
    wait = WebDriverWait(driver, 30)
    logged_in = False

    try:
        # 1. Cookie
        if not user_data_dir:
            if try_load_cookies(driver):
                try:
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "textarea")))
                    logged_in = True
                    print("[Login] Cookie OK")
                except Exception:
                    print("[Login] Cookie expired")

        # 2. Edge/Chrome profile
        if not logged_in and user_data_dir:
            driver.get(DEEPSEEK_URL)
            time.sleep(4)
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "textarea")))
                logged_in = True
                print("[Login] Profile OK")
            except Exception:
                print("[Login] Profile failed")

        # 3. Email + password
        if not logged_in and email and password:
            logged_in = login_with_password(driver, wait, email, password)
            if not logged_in:
                return "Login failed. Check email/password."

        if not logged_in:
            return "Not logged in. Provide email+password or Edge profile path."

        # Send prompt
        driver.get(DEEPSEEK_URL)
        time.sleep(3)
        textarea = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "textarea")))
        set_input_value_js(driver, textarea, prompt)
        time.sleep(1)

        try:
            send_btn = wait.until(EC.element_to_be_clickable((
                By.CSS_SELECTOR,
                "button[aria-label='Send Message'], "
                "button[type='submit'], "
                "div[role='button'][data-testid='send-button']"
            )))
            send_btn.click()
        except Exception:
            textarea.send_keys(Keys.CONTROL, Keys.RETURN)

        return wait_for_response(driver)

    except Exception as e:
        return f"Scraper error: {e}"
    finally:
        driver.quit()
