from typing import Dict, Optional

from utils import (
    build_embed_link,
    build_embed_link_from_place_url,
    log_missing_fields,
    looks_like_blocked,
    normalize_text,
    pick_user_agent,
    random_delay,
)

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
except Exception:  # pragma: no cover - handled at runtime
    webdriver = None


def _init_driver(headless: bool = True):
    if webdriver is None:
        return None
    options = webdriver.ChromeOptions()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1366,768")
    options.add_argument("--lang=en-US")
    options.add_argument(f"--user-agent={pick_user_agent()}")
    return webdriver.Chrome(options=options)


def scrape_gmb(query: str, headless: bool = True, timeout: int = 20) -> Dict[str, Optional[str]]:
    data: Dict[str, Optional[str]] = {
        "google_business_profile_link": None,
        "google_maps_embed_link": None,
        "reviews_ratings": None,
        "working_hours": None,
        "full_address": None,
        "image_urls": None,
        "photo_gallery": None,
        "testimonials": None,
        "_blocked": None,
    }

    driver = _init_driver(headless=headless)
    if driver is None:
        log_missing_fields("gmb", query, ["selenium_not_installed"])
        return data

    try:
        driver.get("https://www.google.com/maps")
        random_delay(2, 4)

        search_box = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.ID, "searchboxinput"))
        )
        search_box.clear()
        search_box.send_keys(query)
        search_box.send_keys(Keys.ENTER)

        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "h1"))
        )
        random_delay(2, 4)

        place_url = driver.current_url
        if looks_like_blocked(driver.page_source):
            data["_blocked"] = "gmb_blocked_or_captcha"
            log_missing_fields("gmb", query, ["gmb_blocked_or_captcha"])
            return data

        data["google_business_profile_link"] = place_url
        data["google_maps_embed_link"] = (
            build_embed_link_from_place_url(place_url) or build_embed_link(query)
        )

        rating_node = driver.find_elements(By.CSS_SELECTOR, "div.F7nice")
        if rating_node:
            data["reviews_ratings"] = normalize_text(rating_node[0].text)

        address_nodes = driver.find_elements(By.CSS_SELECTOR, "button[data-item-id='address']")
        if address_nodes:
            data["full_address"] = normalize_text(address_nodes[0].text)

        hours_button = driver.find_elements(By.CSS_SELECTOR, "button[data-item-id='oh']")
        if hours_button:
            data["working_hours"] = normalize_text(hours_button[0].text)

        image_nodes = driver.find_elements(By.CSS_SELECTOR, "img[decoding='async']")
        if image_nodes:
            images = [node.get_attribute("src") for node in image_nodes]
            images = [img for img in images if img and "googleusercontent" in img]
            if images:
                data["image_urls"] = ", ".join(images[:10])
                data["photo_gallery"] = ", ".join(images[:10])

        review_texts = []
        for node in driver.find_elements(By.CSS_SELECTOR, "span.wiI7pd"):
            text = normalize_text(node.text)
            if text:
                review_texts.append(text)
            if len(review_texts) >= 3:
                break
        if review_texts:
            data["testimonials"] = " | ".join(review_texts)

    except Exception:
        log_missing_fields("gmb", query, ["gmb_parse_failed"])
    finally:
        driver.quit()

    return data
