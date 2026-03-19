import time
import os
import pickle
import glob
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys

DEEPSEEK_URL = "https://chat.deepseek.com"
LOGIN_URL = "https://chat.deepseek.com/sign_in"
COOKIE_FILE = "deepseek_cookies.pkl"
DRIVER_PATH_FILE = "driver_path.txt"  # cached driver location

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


def _save_driver_path(path: str):
    try:
        with open(DRIVER_PATH_FILE, "w") as f:
            f.write(path)
        print(f"[Driver] Saved path to {DRIVER_PATH_FILE}")
    except Exception:
        pass


def _find_msedgedriver() -> str | None:
    # 0. Previously found and saved
    if os.path.exists(DRIVER_PATH_FILE):
        cached = open(DRIVER_PATH_FILE).read().strip()
        if os.path.exists(cached):
            print(f"[Driver] Using cached: {cached}")
            return cached

    # 1. Known Edge install dirs (root + versioned sub-folders)
    for d in EDGE_DIRS:
        if not os.path.isdir(d):
            continue
        p = os.path.join(d, "msedgedriver.exe")
        if os.path.exists(p):
            _save_driver_path(p)
            return p
        for item in sorted(os.listdir(d), reverse=True):
            p = os.path.join(d, item, "msedgedriver.exe")
            if os.path.exists(p):
                _save_driver_path(p)
                return p

    # 2. webdriver-manager cache
    wdm = os.path.join(os.path.expanduser("~"), ".wdm", "drivers", "msedgedriver")
    matches = glob.glob(os.path.join(wdm, "**", "msedgedriver.exe"), recursive=True)
    if matches:
        p = sorted(matches)[-1]
        _save_driver_path(p)
        return p

    # 3. Project root (user may have copied it here manually)
    local = os.path.join(os.path.dirname(__file__), "msedgedriver.exe")
    if os.path.exists(local):
        _save_driver_path(local)
        return local

    # 4. Full C:\ scan (auto, runs once, result cached)
    print("[Driver] msedgedriver.exe not found in known locations.")
    print("[Driver] Scanning C:\\ ... (one-time, may take ~60s)")
    skip = {"Windows", "$Recycle.Bin", "System Volume Information",
            "WinSxS", "Temp", "tmp", "ProgramData"}
    for root, dirs, files in os.walk("C:\\"):
        dirs[:] = [d for d in dirs if d not in skip]
        if "msedgedriver.exe" in files:
            p = os.path.join(root, "msedgedriver.exe")
            print(f"[Driver] Found by scan: {p}")
            _save_driver_path(p)
            return p

    print("[Driver] msedgedriver.exe NOT found on this machine.")
    print("[Driver] Download from https://developer.microsoft.com/en-us/microsoft-edge/tools/webdriver/")
    print("[Driver] Place msedgedriver.exe in this project folder and restart.")
    return None


def _find_edge_binary() -> str | None:
    for d in EDGE_DIRS:
        p = os.path.join(d, "msedge.exe")
        if os.path.exists(p):
            return p
    return None


def build_driver(headless: bool = True, user_data_dir: str = None):
    edge_bin = _find_edge_binary()
    edge_drv = _find_msedgedriver()
    print(f"[Browser] edge | binary={edge_bin} | driver={edge_drv}")

    if edge_bin:
        from selenium.webdriver.edge.options import Options as EdgeOptions
        from selenium.webdriver.edge.service import Service as EdgeService

        opts = EdgeOptions()
        opts.binary_location = edge_bin
        if headless:
            opts.add_argument("--headless=new")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--window-size=1280,900")
        opts.add_argument("--lang=zh-TW")
        opts.add_experimental_option("excludeSwitches", ["enable-logging"])
        if user_data_dir:
            opts.add_argument(f"--user-data-dir={user_data_dir}")

        if edge_drv:
            service = EdgeService(executable_path=edge_drv)
        else:
            service = EdgeService()  # hope selenium-manager finds it
        return webdriver.Edge(service=service, options=opts)

    # Fallback: Chrome
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    from selenium.webdriver.chrome.service import Service as ChromeService
    chrome_bin = next((p for p in CHROME_PATHS if os.path.exists(p)), None)
    opts = ChromeOptions()
    if chrome_bin:
        opts.binary_location = chrome_bin
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1280,900")
    opts.add_argument("--lang=zh-TW")
    if user_data_dir:
        opts.add_argument(f"--user-data-dir={user_data_dir}")
    return webdriver.Chrome(service=ChromeService(), options=opts)


def filter_bmp(text: str) -> str:
    return "".join(c for c in text if ord(c) < 0x10000)


def set_input_value_js(driver, element, text: str):
    safe = filter_bmp(text)
    driver.execute_script("""
        var el = arguments[0], val = arguments[1];
        var setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')
                  || Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value');
        if (setter && setter.set) setter.set.call(el, val);
        else el.value = val;
        el.dispatchEvent(new Event('input',  { bubbles: true }));
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
        driver.get(LOGIN_URL)
        time.sleep(3)

        email_el = wait.until(EC.presence_of_element_located((
            By.CSS_SELECTOR,
            "div.ds-sign-in-form__main input.ds-input__input[type='text']"
        )))
        email_el.click()
        time.sleep(0.3)
        set_input_value_js(driver, email_el, email)
        print(f"[Login] Email entered: {email}")
        time.sleep(0.5)

        pw_el = wait.until(EC.presence_of_element_located((
            By.CSS_SELECTOR,
            "div.ds-sign-in-form__main input.ds-input__input[type='password']"
        )))
        pw_el.click()
        time.sleep(0.3)
        set_input_value_js(driver, pw_el, password)
        print("[Login] Password entered")
        time.sleep(0.5)

        login_btn = wait.until(EC.element_to_be_clickable((
            By.CSS_SELECTOR, "button.ds-basic-button--primary"
        )))
        login_btn.click()
        print("[Login] Submit clicked")
        time.sleep(5)

        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "textarea")))
        save_cookies(driver)
        print("[Login] Login OK, cookies saved")
        return True

    except Exception as e:
        print(f"[Login] Failed: {e}")
        try:
            with open("login_debug.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            print("[Login] Saved login_debug.html")
        except Exception:
            pass
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
        if not user_data_dir:
            if try_load_cookies(driver):
                try:
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "textarea")))
                    logged_in = True
                    print("[Login] Cookie OK")
                except Exception:
                    print("[Login] Cookie expired")

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

        if not logged_in and email and password:
            logged_in = login_with_password(driver, wait, email, password)
            if not logged_in:
                return "Login failed. See login_debug.html for details."

        if not logged_in:
            return "Not logged in. Provide email+password or Edge profile path."

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
                "div[role='button'][data-testid='send-button']"
            )))
            send_btn.click()
        except Exception:
            textarea.send_keys(Keys.RETURN)

        return wait_for_response(driver)

    except Exception as e:
        return f"Scraper error: {e}"
    finally:
        driver.quit()
