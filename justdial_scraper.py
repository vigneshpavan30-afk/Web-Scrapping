import re
from typing import Dict, List, Optional

from bs4 import BeautifulSoup

from utils import (
    fetch_html,
    log_missing_fields,
    looks_like_blocked,
    normalize_text,
    random_delay,
    unique_list,
)


def _extract_listing_cards(soup: BeautifulSoup) -> List:
    selectors = [
        "div.resultbox",
        "div.jcn",
        "li.cntanr",
        "div.store-details",
    ]
    for selector in selectors:
        cards = soup.select(selector)
        if cards:
            return cards
    return []


def _extract_profile_url(card) -> Optional[str]:
    for attr in ["data-href", "data-url"]:
        if card.has_attr(attr):
            return card.get(attr)
    link = card.select_one("a[href*='justdial.com']")
    if link:
        return link.get("href")
    return None


def _extract_name(card) -> Optional[str]:
    for selector in ["span.lng_cont_name", "span.jcn", "a.lng_cont_name", "h2"]:
        node = card.select_one(selector)
        if node:
            return normalize_text(node.get_text(" ", strip=True))
    return None


def _extract_address(card) -> Optional[str]:
    for selector in ["span.cont_fl_addr", "span.cont_fl_addr", "span.mrehover", "div.adrss"]:
        node = card.select_one(selector)
        if node:
            return normalize_text(node.get_text(" ", strip=True))
    return None


def _extract_rating_reviews(card) -> Optional[str]:
    for selector in ["span.green-box", "span.green-box span", "span.rating"]:
        node = card.select_one(selector)
        if node:
            rating = normalize_text(node.get_text(" ", strip=True))
            return rating
    return None


def _parse_details_page(url: str) -> Dict[str, Optional[str]]:
    data = {
        "hours": None,
        "images": [],
        "landmark": None,
        "testimonials": None,
        "staff": None,
        "collection_charges": None,
        "collection_radius": None,
        "average_report_time": None,
    }
    html = fetch_html(url)
    if not html:
        return data
    soup = BeautifulSoup(html, "html.parser")

    hours_node = soup.select_one("div.ophrs") or soup.select_one("span.timing")
    data["hours"] = normalize_text(hours_node.get_text(" ", strip=True)) if hours_node else None

    landmark_node = soup.find(text=lambda x: x and "Landmark" in x)
    if landmark_node and landmark_node.parent:
        data["landmark"] = normalize_text(landmark_node.parent.get_text(" ", strip=True))

    testimonial_nodes = soup.select("div.testi") or soup.select("div.testimonial")
    if testimonial_nodes:
        data["testimonials"] = normalize_text(
            " | ".join(node.get_text(" ", strip=True) for node in testimonial_nodes)
        )

    staff_nodes = soup.select("div.doctor") or soup.select("li.doctor") or soup.select("div.staff")
    if staff_nodes:
        data["staff"] = normalize_text(
            " | ".join(node.get_text(" ", strip=True) for node in staff_nodes)
        )

    images = []
    for img in soup.select("img"):
        src = img.get("data-src") or img.get("src")
        if src and "http" in src:
            images.append(src)
    data["images"] = unique_list(images)

    page_text = soup.get_text(" ", strip=True)
    if "Collection Charges" in page_text:
        match = re.search(r"Collection Charges\s*[:\-]?\s*([^\s]+)", page_text)
        if match:
            data["collection_charges"] = match.group(1)
    if "Collection Radius" in page_text:
        match = re.search(r"Collection Radius\s*[:\-]?\s*([0-9.]+)\s*Kms?", page_text)
        if match:
            data["collection_radius"] = match.group(1)
    if "Report Time" in page_text:
        match = re.search(r"Report Time\s*[:\-]?\s*([^\s]+)", page_text)
        if match:
            data["average_report_time"] = match.group(1)

    return data


def _infer_center_type(keyword: str, name: Optional[str]) -> Optional[str]:
    value = (keyword or "").lower()
    if "diagnostic" in value:
        return "Diagnostic Center"
    if "scan" in value:
        return "Scan Center"
    if "lab" in value or "laboratory" in value:
        return "Lab"
    if "hospital" in value:
        return "Hospital"
    if name:
        lowered = name.lower()
        if "diagnostic" in lowered:
            return "Diagnostic Center"
        if "scan" in lowered:
            return "Scan Center"
        if "lab" in lowered or "laboratory" in lowered:
            return "Lab"
        if "hospital" in lowered:
            return "Hospital"
    return None


def scrape_justdial(city: str, keyword: str, max_pages: int = 2) -> List[Dict[str, Optional[str]]]:
    results: List[Dict[str, Optional[str]]] = []
    for page in range(1, max_pages + 1):
        url = f"https://www.justdial.com/{city}/{keyword}/page-{page}"
        html = fetch_html(url)
        random_delay()
        if not html:
            continue
        if looks_like_blocked(html):
            log_missing_fields("justdial", url, ["justdial_blocked_or_captcha"])
            return [{"_blocked": "justdial_blocked_or_captcha"}]
        soup = BeautifulSoup(html, "html.parser")
        cards = _extract_listing_cards(soup)
        if not cards:
            break

        for card in cards:
            profile_url = _extract_profile_url(card)
            name = _extract_name(card)
            address = _extract_address(card)
            rating = _extract_rating_reviews(card)

            details = {}
            if profile_url:
                random_delay()
                details = _parse_details_page(profile_url)

            missing = []
            if not name:
                missing.append("Center Name")
            if not address:
                missing.append("Full Address")
            log_missing_fields("justdial", profile_url or url, missing)

            result = {
                "center_name": name,
                "center_type": _infer_center_type(keyword, name),
                "full_address": address,
                "average_report_time": details.get("average_report_time"),
                "collection_charges": details.get("collection_charges"),
                "collection_radius": details.get("collection_radius"),
                "working_hours": details.get("hours"),
                "image_urls": ", ".join(details.get("images", [])),
                "google_business_profile_link": None,
                "google_maps_embed_link": None,
                "local_landmark": details.get("landmark"),
                "reviews_ratings": rating,
                "testimonials": details.get("testimonials"),
                "photo_gallery": ", ".join(details.get("images", [])),
                "staff_doctors": details.get("staff"),
                "source_url": profile_url or url,
            }
            results.append(result)
    return results


def _tokenize_name(text: Optional[str]) -> List[str]:
    if not text:
        return []
    return [token for token in re.split(r"[^a-z0-9]+", text.lower()) if token]


def _match_score(
    candidate: Optional[str],
    target: str,
    candidate_address: Optional[str],
    target_address: Optional[str],
) -> int:
    candidate_tokens = set(_tokenize_name(candidate))
    target_tokens = set(_tokenize_name(target))
    if not candidate_tokens or not target_tokens:
        return 0
    score = len(candidate_tokens.intersection(target_tokens))
    if candidate_address and target_address:
        address_tokens = set(_tokenize_name(candidate_address))
        target_address_tokens = set(_tokenize_name(target_address))
        score += len(address_tokens.intersection(target_address_tokens))
    return score


def scrape_justdial_by_name(
    city: str,
    center_name: str,
    address: Optional[str] = None,
) -> Optional[Dict[str, Optional[str]]]:
    results = scrape_justdial(city=city, keyword=center_name, max_pages=1)
    if not results:
        return None
    if results and isinstance(results[0], dict) and results[0].get("_blocked"):
        return {"_blocked": results[0].get("_blocked")}

    best = None
    best_score = -1
    for result in results:
        score = _match_score(
            result.get("center_name"),
            center_name,
            result.get("full_address"),
            address,
        )
        if score > best_score:
            best_score = score
            best = result

    return best or results[0]
