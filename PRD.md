# Product Requirements Document (PRD)
# Web Scraping: Diagnostic Centers (Justdial + Google Maps)

## 1) Overview
This project scrapes publicly visible information about diagnostic centers, labs, scan centers, and hospitals from Justdial and Google Maps. The output is a clean CSV matching the provided schema, with optional JSON output. The system avoids authentication, follows ethical scraping practices, and handles missing data gracefully.

## 2) Goals
- Extract required business information from public profiles.
- Provide a reliable CSV output aligned with the `Scrapping.csv` header.
- Support keyword and city-based searches with pagination handling.
- Avoid aggressive request rates and prevent data loss on partial failures.

## 3) Non-Goals
- No login or authentication flows.
- No private or hidden data scraping.
- No bypass of anti-bot measures.
- No real-time dashboard or UI.

## 4) Target Users
- Data operations teams building a directory of diagnostic centers.
- Research teams collecting public business data.
- Internal reporting teams requiring structured business metadata.

## 5) Data Sources
- Justdial business listing pages.
- Google Maps public profiles (GMB).

## 6) Functional Requirements
### 6.1 Input
- Keyword-based searches (e.g., "diagnostic center", "lab").
- City-based scraping (e.g., "Mumbai").
- Optional GMB enrichment.

### 6.2 Output Fields (CSV)
- Center Name
- Center Type (Diagnostic Center / Scan Center / Lab / Hospital)
- Full Address
- Average Report Time
- Collection Charges
- Collection Radius (Kms)
- Opening & Closing Slots (Working hours)
- Image URL(s)
- Google Business Profile Link
- Google Maps Embed Link
- Local Landmark / Directions
- Reviews & Ratings
- Testimonials (if available)
- Photo Gallery URLs
- Staff / Doctors List

### 6.3 Output Format
- CSV file in `output/` using the same columns as `Scrapping.csv`.
- Optional JSON output (same schema).
- Multiple image URLs stored as comma-separated values.
- Reviews & ratings in readable format.

### 6.4 Logging
- Failed URLs logged in `output/failed_urls.log`.
- Missing fields logged in `output/missing_fields.log`.

## 7) Technical Requirements
- Language: Python
- Libraries: `requests`, `BeautifulSoup`, `selenium` (optional), `pandas`, `re`, `time`, `random`
- Handle:
  - JavaScript-rendered content where necessary (via Selenium)
  - Pagination or infinite scroll (basic pagination supported; extendable)
  - Missing fields without breaking
  - Duplicate listings
- Implement:
  - User-agent rotation
  - Rate limiting and random delays
  - try-except error handling

## 8) Ethical & Compliance Requirements
- Scrape only public data.
- Respect rate limits and avoid aggressive scraping.
- No authentication or bypassing access controls.

## 9) Project Structure
- `main.py` (entry point)
- `justdial_scraper.py`
- `gmb_scraper.py`
- `utils.py`
- `output/` for results and logs

## 10) Acceptance Criteria
- Produces a CSV that matches `Scrapping.csv` columns.
- Handles missing fields without crashing.
- Logs failures and missing data fields.
- Supports keyword and city-based scraping.
- Optional GMB enrichment works in headless mode.

## 11) Risks & Mitigations
- **Site HTML changes**: Keep selectors isolated per source for easy updates.
- **Anti-bot**: Maintain low request rates, rotate user agents.
- **Dynamic content**: Use Selenium only when required.
- **Data quality variance**: Log missing fields and keep output consistent.

## 12) Future Enhancements
- Config file for keywords/locations.
- Advanced scrolling for infinite results.
- Proxy support and request retries.
- Automated tests for core parsers.
