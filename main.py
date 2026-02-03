import argparse
import re
from pathlib import Path
from typing import Dict, List

import pandas as pd

from gmb_scraper import scrape_gmb
from justdial_scraper import scrape_justdial, scrape_justdial_by_name
from utils import save_json


COLUMNS = [
    "Center Name",
    "Center Type",
    "Address",
    "Average Report Time",
    "Collection Charges",
    "Collection Radius (Kms)",
    "Opening & Closing Slots",
    "Image URL(s)",
    "Google Business Profile Link",
    "Google Maps Embed",
    "Local Landmark / Directions",
    "Reviews / Ratings",
    "Testimonials",
    "Photo Gallery",
    "Staff / Doctors List",
]


def _map_record(record: Dict[str, str]) -> Dict[str, str]:
    return {
        "Center Name": record.get("center_name"),
        "Center Type": record.get("center_type"),
        "Address": record.get("full_address"),
        "Average Report Time": record.get("average_report_time"),
        "Collection Charges": record.get("collection_charges"),
        "Collection Radius (Kms)": record.get("collection_radius"),
        "Opening & Closing Slots": record.get("working_hours"),
        "Image URL(s)": record.get("image_urls"),
        "Google Business Profile Link": record.get("google_business_profile_link"),
        "Google Maps Embed": record.get("google_maps_embed_link"),
        "Local Landmark / Directions": record.get("local_landmark"),
        "Reviews / Ratings": record.get("reviews_ratings"),
        "Testimonials": record.get("testimonials"),
        "Photo Gallery": record.get("photo_gallery"),
        "Staff / Doctors List": record.get("staff_doctors"),
    }


def _merge_gmb(data: Dict[str, str], gmb: Dict[str, str]) -> Dict[str, str]:
    for key, value in gmb.items():
        if key.startswith("_"):
            continue
        if value:
            data[key] = value
    return data


def _normalize_address_cell(value: str) -> str:
    cleaned = str(value or "").strip()
    if not cleaned:
        return ""
    lowered = cleaned.lower()
    if lowered in {"yes", "no", "yes in gmb"}:
        return ""
    if len(cleaned) < 5:
        return ""
    return cleaned


def _normalize_city_cell(value: str) -> str:
    cleaned = str(value or "").strip()
    if not cleaned:
        return ""
    lowered = cleaned.lower()
    if lowered in {"yes", "no", "yes in gmb"}:
        return ""
    return cleaned


def _normalize_pincode_cell(value: str) -> str:
    cleaned = str(value or "").strip()
    if not cleaned:
        return ""
    if cleaned.lower() in {"yes", "no", "yes in gmb"}:
        return ""
    if not re.match(r"^\d{5,6}$", cleaned):
        return ""
    return cleaned


def run_scrape(
    keywords: List[str],
    cities: List[str],
    max_pages: int,
    use_gmb: bool,
    headless: bool,
) -> List[Dict[str, str]]:
    all_rows: List[Dict[str, str]] = []
    seen = set()

    for city in cities:
        for keyword in keywords:
            rows = scrape_justdial(city=city, keyword=keyword, max_pages=max_pages)
            for row in rows:
                dedupe_key = (row.get("center_name"), row.get("full_address"))
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)

                if use_gmb and row.get("center_name"):
                    query = f"{row.get('center_name')} {row.get('full_address') or ''}".strip()
                    gmb_data = scrape_gmb(query=query, headless=headless)
                    row = _merge_gmb(row, gmb_data)

                all_rows.append(_map_record(row))

    return all_rows


def run_scrape_from_csv(
    input_csv: Path,
    city: str,
    use_gmb: bool,
    headless: bool,
) -> List[Dict[str, str]]:
    df = pd.read_csv(input_csv)
    name_column = None
    for candidate in ["Center Name", "partnerName", "centerName", "name"]:
        if candidate in df.columns:
            name_column = candidate
            break
    if not name_column:
        raise ValueError("Input CSV must include a center name column")

    address_column = None
    for candidate in ["Address", "address", "centerAddress"]:
        if candidate in df.columns:
            address_column = candidate
            break
    locality_column = None
    for candidate in ["locality", "Locality", "city", "City", "town", "Town"]:
        if candidate in df.columns:
            locality_column = candidate
            break
    pincode_column = None
    for candidate in ["pincode", "Pincode", "pin", "PIN"]:
        if candidate in df.columns:
            pincode_column = candidate
            break

    all_rows: List[Dict[str, str]] = []
    failed_rows: List[Dict[str, str]] = []
    seen = set()
    for _, row in df.iterrows():
        name = str(row.get(name_column, "")).strip()
        if not name:
            continue
        address = ""
        if address_column:
            address = _normalize_address_cell(row.get(address_column, ""))
        row_city = ""
        if locality_column:
            row_city = _normalize_city_cell(row.get(locality_column, ""))
        row_pincode = ""
        if pincode_column:
            row_pincode = _normalize_pincode_cell(row.get(pincode_column, ""))
        city_for_lookup = row_city or city
        address_hint = " ".join(part for part in [address, row_pincode, row_city] if part).strip()
        name = name.strip()
        if not name:
            continue
        if name in seen:
            continue
        seen.add(name)

        row = scrape_justdial_by_name(
            city=city_for_lookup,
            center_name=name,
            address=address_hint or row_city,
        ) or {
            "center_name": name,
            "center_type": None,
            "full_address": None,
            "average_report_time": None,
            "collection_charges": None,
            "collection_radius": None,
            "working_hours": None,
            "image_urls": None,
            "google_business_profile_link": None,
            "google_maps_embed_link": None,
            "local_landmark": None,
            "reviews_ratings": None,
            "testimonials": None,
            "photo_gallery": None,
            "staff_doctors": None,
            "source_url": None,
        }

        if row.get("_blocked"):
            failed_rows.append(
                {
                    "Center Name": name,
                    "Address": address,
                    "Reason": row.get("_blocked"),
                }
            )
            continue

        if use_gmb:
            base_address = row.get("full_address") or address_hint
            query = f"{row.get('center_name')} {base_address or ''}".strip()
            gmb_data = scrape_gmb(query=query, headless=headless)
            if gmb_data.get("_blocked"):
                failed_rows.append(
                    {
                        "Center Name": name,
                        "Address": address,
                        "Reason": gmb_data.get("_blocked"),
                    }
                )
                continue
            row = _merge_gmb(row, gmb_data)
            if not gmb_data.get("full_address"):
                row["full_address"] = None

        all_rows.append(_map_record(row))

    if failed_rows:
        failed_path = Path("output") / "Failed_Records.csv"
        pd.DataFrame(failed_rows).to_csv(failed_path, index=False)

    return all_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Justdial + GMB scraping")
    parser.add_argument("--keywords", nargs="+", default=["diagnostic center"])
    parser.add_argument("--cities", nargs="+", default=["Mumbai"])
    parser.add_argument("--city", default="Mumbai")
    parser.add_argument("--input-csv", default="Scrapping.csv")
    parser.add_argument("--max-pages", type=int, default=2)
    parser.add_argument("--no-gmb", action="store_true")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    input_csv = Path(args.input_csv)
    if input_csv.exists():
        results = run_scrape_from_csv(
            input_csv=input_csv,
            city=args.city,
            use_gmb=not args.no_gmb,
            headless=args.headless,
        )
    else:
        results = run_scrape(
            keywords=args.keywords,
            cities=args.cities,
            max_pages=args.max_pages,
            use_gmb=not args.no_gmb,
            headless=args.headless,
        )

    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    csv_path = output_dir / "Lab_Centers_Enriched.csv"

    df = pd.DataFrame(results, columns=COLUMNS)
    df.to_csv(csv_path, index=False)

    if args.json:
        save_json(output_dir / "scraped_centers.json", results)

    print(f"Saved {len(df)} rows to {csv_path}")


if __name__ == "__main__":
    main()
