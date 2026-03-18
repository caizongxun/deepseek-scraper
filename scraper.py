import time
import json
import os
import pickle
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.keys import Keys

DEEPSEEK_URL = "https://chat.deepseek.com"
COOKIE_FILE = "deepseek_cookies.pkl"


def filter_bmp(text: str) -> str:
    """Remove non-BMP characters (emoji etc) to avoid Edge/Chrome driver crash."""
    return "".join(c for c in text if ord(c) < 0x10000)


def set_input_value_js(driver, element, text: str):
    """Inject text via JS React-compatible setter (handles contenteditable & textarea)."""
    safe = filter_bmp(text)
    driver.execute_script("""
        var el = arguments[0];
        var text = arguments[1];
        var nativeInputValueSetter = Object.getOwnPropertyDescriptor(
            window.HTMLTextAreaElement.prototype, 'value') ||
            Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value');
        if (nativeInputValueSetter) {
            nativeInputValueSetter.set.call(el, text);
        } else {
            el.value = text;
        }
        el.dispatchEvent(new Event('input', { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));
    """, element, safe)


def build_options(headless: bool = True, user_data_dir: str = None) -> Options:
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1280,900")
    options.add_argument("--lang=zh-TW")
    if user_data_dir:
        options.add_argument(f"--user-data-dir={user_data_dir}")
    return options


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
    """Login via email+password. Returns True on success."""
    try:
        driver.get(DEEPSEEK_URL)
        time.sleep(3)
        # Look for login / sign in button or link
        try:
            login_btn = wait.until(EC.element_to_be_clickable(
                (By.XPATH, "//*[contains(text(),'Log in') or contains(text(),'Sign in') "
                            "or contains(text(),'login') or contains(text(),'sign in')]")))
            login_btn.click()
            time.sleep(2)
        except Exception:
            pass

        # Email input
        email_input = wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, "input[type='email'], input[name='email'], input[placeholder*='mail']")))
        email_input.clear()
        email_input.send_keys(filter_bmp(email))
        time.sleep(0.5)

        # Password input
        pw_input = driver.find_element(
            By.CSS_SELECTOR, "input[type='password'], input[name='password']")
        pw_input.clear()
        pw_input.send_keys(filter_bmp(password))
        time.sleep(0.5)

        # Submit
        pw_input.send_keys(Keys.RETURN)
        time.sleep(5)

        # Verify: look for textarea
        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "textarea")))
            save_cookies(driver)
            return True
        except Exception:
            return False
    except Exception as e:
        print(f"[Login] Error: {e}")
        return False


def find_textarea(driver, wait) -> object:
    return wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "textarea")))


def wait_for_response(driver, timeout: int = 90) -> str:
    """Poll for assistant response until stable."""
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
    """
    Main entry. Tries: 1) saved cookies 2) user_data_dir 3) email+password login.
    Then injects prompt and returns DeepSeek response.
    """
    options = build_options(headless=headless, user_data_dir=user_data_dir)
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    wait = WebDriverWait(driver, 30)

    logged_in = False
    try:
        # 1. Try cookies
        if not user_data_dir:
            if try_load_cookies(driver):
                try:
                    find_textarea(driver, WebDriverWait(driver, 10))
                    logged_in = True
                    print("[Login] Cookie login OK")
                except Exception:
                    print("[Login] Cookie expired, trying password...")

        # 2. Try user_data_dir (already handled via Chrome options)
        if not logged_in and user_data_dir:
            driver.get(DEEPSEEK_URL)
            time.sleep(4)
            try:
                find_textarea(driver, WebDriverWait(driver, 10))
                logged_in = True
                print("[Login] Profile login OK")
            except Exception:
                print("[Login] Profile failed, trying password...")

        # 3. Email + password
        if not logged_in and email and password:
            logged_in = login_with_password(driver, wait, email, password)
            if logged_in:
                print("[Login] Password login OK, cookies saved")
            else:
                return "Login failed. Check email/password or solve captcha manually."

        if not logged_in:
            return "Not logged in. Provide email+password or a valid Chrome profile."

        # --- Send prompt ---
        driver.get(DEEPSEEK_URL)
        time.sleep(3)
        textarea = find_textarea(driver, wait)
        set_input_value_js(driver, textarea, prompt)
        time.sleep(1)

        # Send button
        try:
            send_btn = wait.until(EC.element_to_be_clickable(
                (By.CSS_SELECTOR,
                 "button[aria-label='Send Message'], "
                 "button[type='submit'], "
                 "div[role='button'][data-testid='send-button']")))
            send_btn.click()
        except Exception:
            # Fallback: Ctrl+Enter
            textarea.send_keys(Keys.CONTROL, Keys.RETURN)

        return wait_for_response(driver)

    except Exception as e:
        return f"Scraper error: {e}"
    finally:
        driver.quit()
