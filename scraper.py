import time
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service

DEEPSEEK_URL = "https://chat.deepseek.com"

def build_prompt(market_data: dict) -> str:
    """Convert market data dict into a prompt string."""
    json_str = json.dumps(market_data, ensure_ascii=False, indent=2)
    return (
        f"以下是目前市場資訊（JSON 格式），請根據這些數據給出分析與建議：\n\n"
        f"```json\n{json_str}\n```\n\n"
        f"請用繁體中文回答，包含：1) 市場趨勢判斷 2) 風險提示 3) 操作建議"
    )

def scrape_deepseek(market_data: dict, headless: bool = True, user_data_dir: str = None) -> str:
    """
    Open DeepSeek chat, inject market_data as JSON prompt, return AI response text.
    user_data_dir: path to Chrome profile dir that is already logged in to DeepSeek.
                   e.g. '/home/user/.config/google-chrome/Default'
    """
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1280,900")
    if user_data_dir:
        options.add_argument(f"--user-data-dir={user_data_dir}")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    wait = WebDriverWait(driver, 30)

    try:
        driver.get(DEEPSEEK_URL)
        time.sleep(3)

        # Try to find the textarea input box
        textarea = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "textarea"))
        )

        prompt = build_prompt(market_data)

        # Clear and inject via JS to handle large text reliably
        driver.execute_script(
            "arguments[0].value = arguments[1];"
            "arguments[0].dispatchEvent(new Event('input', {bubbles:true}));"
            "arguments[0].dispatchEvent(new Event('change', {bubbles:true}));",
            textarea,
            prompt
        )
        time.sleep(1)

        # Click send button
        send_btn = wait.until(
            EC.element_to_be_clickable(
                (By.CSS_SELECTOR, "button[aria-label='Send Message'], button[type='submit'], "
                 "div[role='button'][aria-label='Send']")
            )
        )
        send_btn.click()

        # Wait for response: wait until a new assistant message appears and stops streaming
        time.sleep(5)  # initial wait for response start
        last_text = ""
        stable_count = 0
        for _ in range(60):  # max 60s
            # DeepSeek response containers
            msgs = driver.find_elements(
                By.CSS_SELECTOR,
                "div[class*='message'][class*='assistant'], "
                "div[data-role='assistant'], "
                "div[class*='ds-markdown']"
            )
            if msgs:
                current_text = msgs[-1].text.strip()
                if current_text and current_text == last_text:
                    stable_count += 1
                    if stable_count >= 3:
                        return current_text
                else:
                    stable_count = 0
                    last_text = current_text
            time.sleep(1)

        return last_text or "No response captured."

    except Exception as e:
        return f"Scraper error: {str(e)}"
    finally:
        driver.quit()
