"""
Job Scraper - Scrapes live job listings from South African job sites
Uses BeautifulSoup for parsing, httpx for requests
"""
import httpx
import logging
import hashlib
from datetime import datetime
from bs4 import BeautifulSoup
from app.core.supabase import save_jobs

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-ZA,en;q=0.5",
}


def make_source_id(source: str, url: str) -> str:
    """Create unique ID for a job from its URL"""
    return hashlib.md5(f"{source}:{url}".encode()).hexdigest()


def infer_field(title: str, description: str = "") -> str:
    """Infer job field from title and description"""
    text = f"{title} {description}".lower()
    
    fields = {
        "IT": ["software", "developer", "programmer", "it support", "network", "database",
               "devops", "cloud", "cyber", "data analyst", "systems", "helpdesk", "tech support"],
        "Engineering": ["engineer", "mechanical", "electrical", "civil", "chemical",
                       "structural", "industrial", "manufacturing"],
        "Finance": ["accountant", "finance", "financial", "bookkeeper", "auditor",
                   "tax", "payroll", "cost accounting", "cfo", "treasury"],
        "Healthcare": ["nurse", "doctor", "medical", "pharmacy", "health", "clinical",
                      "radiographer", "physiotherapy", "dentist", "paramedic"],
        "Sales": ["sales", "business development", "account manager", "representative",
                 "retail", "customer success"],
        "Marketing": ["marketing", "digital marketing", "brand", "social media",
                     "content", "seo", "advertising"],
        "Education": ["teacher", "lecturer", "tutor", "educator", "trainer", "facilitator"],
        "Admin": ["admin", "administrator", "receptionist", "office manager",
                 "secretary", "clerk", "coordinator"],
        "Legal": ["lawyer", "attorney", "legal", "paralegal", "compliance"],
        "Construction": ["construction", "building", "contractor", "foreman", "site manager"],
        "Logistics": ["logistics", "supply chain", "warehouse", "driver", "transport",
                     "fleet", "dispatch"],
    }
    
    for field, keywords in fields.items():
        if any(kw in text for kw in keywords):
            return field
    return "General"


def infer_experience_level(title: str, description: str = "") -> str:
    """Infer experience level from job text"""
    text = f"{title} {description}".lower()
    if any(w in text for w in ["senior", "lead", "principal", "head of", "manager", "director"]):
        return "Senior"
    if any(w in text for w in ["junior", "graduate", "entry", "trainee", "intern", "learner"]):
        return "Entry"
    return "Mid"


async def scrape_pnet(search_query: str, location: str = "South Africa", max_jobs: int = 20) -> list:
    """
    Scrape job listings from PNet.
    Returns list of job dicts.
    """
    jobs = []
    
    try:
        # PNet search URL
        query_encoded = search_query.replace(" ", "%20")
        location_encoded = location.replace(" ", "%20")
        url = f"https://www.pnet.co.za/jobs/{query_encoded}/{location_encoded}/"
        
        async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=15) as client:
            response = await client.get(url)
            
            if response.status_code != 200:
                logger.warning(f"PNet returned {response.status_code}")
                return []
            
            soup = BeautifulSoup(response.text, "lxml")
            
            # PNet job cards
            job_cards = soup.find_all("article", class_="job-card") or \
                       soup.find_all("div", class_="job-result") or \
                       soup.find_all("div", attrs={"data-job-id": True})
            
            for card in job_cards[:max_jobs]:
                try:
                    title_el = card.find(["h2", "h3", "a"], class_=lambda x: x and "title" in x.lower() if x else False) \
                              or card.find("a")
                    company_el = card.find(class_=lambda x: x and "company" in x.lower() if x else False)
                    location_el = card.find(class_=lambda x: x and "location" in x.lower() if x else False)
                    salary_el = card.find(class_=lambda x: x and "salary" in x.lower() if x else False)
                    
                    title = title_el.get_text(strip=True) if title_el else "Unknown Position"
                    company = company_el.get_text(strip=True) if company_el else "Unknown Company"
                    job_location = location_el.get_text(strip=True) if location_el else location
                    salary_text = salary_el.get_text(strip=True) if salary_el else "Market Related"
                    
                    # Get job URL
                    link = card.find("a", href=True)
                    job_url = f"https://www.pnet.co.za{link['href']}" if link else url
                    
                    source_id = make_source_id("pnet", job_url)
                    
                    jobs.append({
                        "title": title,
                        "company": company,
                        "location": job_location,
                        "province": extract_province(job_location),
                        "salary_text": salary_text,
                        "field": infer_field(title),
                        "experience_level": infer_experience_level(title),
                        "source": "pnet",
                        "source_url": job_url,
                        "source_id": source_id,
                        "posted_at": datetime.utcnow().isoformat(),
                        "is_active": True,
                    })
                    
                except Exception as e:
                    logger.warning(f"Error parsing PNet job card: {e}")
                    continue
                    
    except Exception as e:
        logger.error(f"PNet scraping failed: {e}")
    
    logger.info(f"PNet: found {len(jobs)} jobs for '{search_query}'")
    return jobs


async def scrape_careerjunction(search_query: str, location: str = "", max_jobs: int = 20) -> list:
    """Scrape CareerJunction job listings"""
    jobs = []
    
    try:
        query_encoded = search_query.replace(" ", "+")
        url = f"https://www.careerjunction.co.za/jobs/results?Keywords={query_encoded}&Location={location}"
        
        async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=15) as client:
            response = await client.get(url)
            
            if response.status_code != 200:
                return []
            
            soup = BeautifulSoup(response.text, "lxml")
            job_cards = soup.find_all("article") or soup.find_all("div", class_="job-result")
            
            for card in job_cards[:max_jobs]:
                try:
                    title_el = card.find(["h2", "h3"])
                    company_el = card.find(class_=lambda x: x and "company" in str(x).lower())
                    location_el = card.find(class_=lambda x: x and "location" in str(x).lower())
                    
                    title = title_el.get_text(strip=True) if title_el else "Position Available"
                    company = company_el.get_text(strip=True) if company_el else "Company"
                    job_location = location_el.get_text(strip=True) if location_el else "South Africa"
                    
                    link = card.find("a", href=True)
                    job_url = f"https://www.careerjunction.co.za{link['href']}" if link and link['href'].startswith('/') else (link['href'] if link else url)
                    
                    source_id = make_source_id("careerjunction", job_url)
                    
                    jobs.append({
                        "title": title,
                        "company": company,
                        "location": job_location,
                        "province": extract_province(job_location),
                        "salary_text": "Market Related",
                        "field": infer_field(title),
                        "experience_level": infer_experience_level(title),
                        "source": "careerjunction",
                        "source_url": job_url,
                        "source_id": source_id,
                        "posted_at": datetime.utcnow().isoformat(),
                        "is_active": True,
                    })
                    
                except Exception as e:
                    continue
                    
    except Exception as e:
        logger.error(f"CareerJunction scraping failed: {e}")
    
    logger.info(f"CareerJunction: found {len(jobs)} jobs for '{search_query}'")
    return jobs


async def search_and_store_jobs(query: str, location: str = "South Africa") -> list:
    """
    Search multiple job sites and store results in Supabase.
    Returns combined list of jobs.
    """
    logger.info(f"Searching jobs: '{query}' in '{location}'")
    
    # Scrape multiple sources in parallel
    import asyncio
    pnet_jobs, cj_jobs = await asyncio.gather(
        scrape_pnet(query, location),
        scrape_careerjunction(query, location),
        return_exceptions=True
    )
    
    all_jobs = []
    if isinstance(pnet_jobs, list):
        all_jobs.extend(pnet_jobs)
    if isinstance(cj_jobs, list):
        all_jobs.extend(cj_jobs)
    
    # Save to Supabase
    if all_jobs:
        saved = await save_jobs(all_jobs)
        logger.info(f"Saved {saved} jobs to Supabase")
    
    return all_jobs


def extract_province(location_text: str) -> str:
    """Extract SA province from location string"""
    location_lower = location_text.lower()
    
    provinces = {
        "Gauteng": ["johannesburg", "pretoria", "sandton", "midrand", "centurion",
                   "soweto", "randburg", "roodepoort", "ekurhuleni", "gauteng"],
        "Western Cape": ["cape town", "stellenbosch", "george", "western cape", "paarl", "worcester"],
        "KwaZulu-Natal": ["durban", "pietermaritzburg", "kwazulu", "kzn", "umhlanga", "pinetown"],
        "Eastern Cape": ["port elizabeth", "east london", "eastern cape", "gqeberha"],
        "Limpopo": ["polokwane", "limpopo", "tzaneen"],
        "Mpumalanga": ["nelspruit", "mpumalanga", "witbank", "emalahleni"],
        "Free State": ["bloemfontein", "free state"],
        "North West": ["rustenburg", "north west", "potchefstroom"],
        "Northern Cape": ["kimberley", "northern cape", "upington"],
    }
    
    for province, cities in provinces.items():
        if any(city in location_lower for city in cities):
            return province
    
    return "National"
