import os
import asyncio
from datetime import datetime
from loguru import logger
from apify_client import ApifyClientAsync
from backend.modules.fetchers.base_fetcher import BaseFetcher, RawJob
from backend.config import get_settings

class BaseApifyFetcher(BaseFetcher):
    """
    Base class for fetchers that use Apify Actors via the apify-client SDK.
    """
    ACTOR_ID = ""
    
    def __init__(self):
        super().__init__()
        self.token = os.getenv("APIFY_TOKEN") or get_settings().apify_token
        if self.token:
            self.client = ApifyClientAsync(self.token)
        else:
            self.client = None
            
    async def _run_actor(self, run_input: dict, timeout_secs: int = 90) -> list[dict]:
        if not self.client:
            logger.warning(f"[{self.source_name}] APIFY_TOKEN missing, skipping fetch.")
            return []
            
        logger.info(f"[{self.source_name}] Calling Apify Actor {self.ACTOR_ID} with input: {run_input}")
        
        try:
                                                       
            run = await self.client.actor(self.ACTOR_ID).call(run_input=run_input, timeout_secs=timeout_secs)
            
                                                    
            if isinstance(run, dict):
                dataset_id = run.get("defaultDatasetId")
            else:
                dataset_id = getattr(run, "defaultDatasetId", None) or getattr(run, "default_dataset_id", None)
            
            if not dataset_id:
                logger.error(f"[{self.source_name}] Could not find dataset_id in run object.")
                return []
                
            dataset_client = self.client.dataset(dataset_id)
            
                                            
            list_page = await dataset_client.list_items()
            items = list_page.items
            
            logger.info(f"[{self.source_name}] Apify returned {len(items)} items from dataset {dataset_id}")
            return items
            
        except Exception as e:
            logger.error(f"[{self.source_name}] Apify Actor run failed: {e}")
            return []

class ApifyInternshalaFetcher(BaseApifyFetcher):
    source_name = "Internshala"
    ACTOR_ID = "unfenced-group/internshala-scraper"

    async def fetch(self, keywords: list[str], location: str = "", **kwargs) -> list[RawJob]:
        results: list[RawJob] = []
        
                                                                         
                                                                                                      
                                            
        for keyword in keywords[:2]:
            run_input = {
                "search": keyword,
                "maxItems": 15,
                "limit": 15,
                "max": 15,
            }
            if location and location.lower() != "india":
                                                                                                           
                                                                                        
                                                                                    
                if "remote" in location.lower() or "home" in location.lower():
                    run_input["search"] = f"work from home {keyword}"
                else:
                    run_input["search"] = f"{keyword} in {location}"

            items = await self._run_actor(run_input)
            
            for item in items:
                title = item.get("title") or item.get("internshipProfile", "Unknown")
                company = item.get("companyName", "Unknown")
                loc = item.get("locationNames", [])
                loc_str = ", ".join(loc) if isinstance(loc, list) else str(loc)
                
                                                    
                stipend = item.get("stipend", {}).get("salary") or item.get("stipend")
                duration = item.get("duration")
                
                desc_parts = []
                if stipend: desc_parts.append(f"Stipend: {stipend}")
                if duration: desc_parts.append(f"Duration: {duration}")
                
                skills = item.get("skills", [])
                if skills: desc_parts.append(f"Skills: {', '.join(skills)}")
                
                description = " | ".join(desc_parts) if desc_parts else None
                apply_link = item.get("url") or item.get("link")
                
                if not title or title == "Unknown": continue
                
                mode = None
                loc_lower = loc_str.lower()
                if "work from home" in loc_lower or "remote" in loc_lower:
                    mode = "remote"
                
                results.append(RawJob(
                    title=title,
                    company=company,
                    location=loc_str,
                    internship_type="Internship",
                    description=description,
                    apply_link=apply_link,
                    source=self.source_name,
                    extra={"mode": mode} if mode else {}
                ))
                
        return results

class ApifyLinkedInFetcher(BaseApifyFetcher):
    source_name = "LinkedIn"
    ACTOR_ID = "bebity/linkedin-jobs-scraper"

    async def fetch(self, keywords: list[str], location: str = "India", **kwargs) -> list[RawJob]:
        results: list[RawJob] = []
        
        query = " OR ".join(keywords[:2])
        run_input = {
            "keyword": query,
            "location": location or "India",
            "f_JT": "I",             
            "limit": 25,
            "saveDescription": True
        }
        
        items = await self._run_actor(run_input)
        
        for item in items:
            title = item.get("title")
            if not title: continue
            
            company = item.get("company", "Unknown")
            loc = item.get("location", "")
            description = item.get("description", "")
            apply_link = item.get("url")
            
            mode = None
            loc_lower = (loc or "").lower()
            if "remote" in loc_lower or "work from home" in loc_lower:
                mode = "remote"
            elif "hybrid" in loc_lower:
                mode = "hybrid"
                
            results.append(RawJob(
                title=title,
                company=company,
                location=loc,
                internship_type="Internship",
                description=description[:1000] if description else None,
                apply_link=apply_link,
                source=self.source_name,
                extra={"mode": mode} if mode else {}
            ))
            
        return results

class ApifyIndeedFetcher(BaseApifyFetcher):
    source_name = "Indeed"
    ACTOR_ID = "misceres/indeed-scraper"

    async def fetch(self, keywords: list[str], location: str = "", **kwargs) -> list[RawJob]:
        results: list[RawJob] = []
        
        for keyword in keywords[:2]:
            run_input = {
                "position": keyword,
                "country": "IN",
                "location": location or "India",
                "maxItems": 15,
                "limit": 15,
                "saveOnlyUniqueItems": True,
                "jobType": "internship"
            }
            
            items = await self._run_actor(run_input)
            
            for item in items:
                title = item.get("positionName") or item.get("title")
                if not title: continue
                
                company = item.get("company", "Unknown")
                loc = item.get("location", "")
                description = item.get("description", "")
                apply_link = item.get("url")
                
                mode = None
                loc_lower = (loc or "").lower()
                if "remote" in loc_lower or "work from home" in loc_lower:
                    mode = "remote"
                elif "hybrid" in loc_lower:
                    mode = "hybrid"
                    
                results.append(RawJob(
                    title=title,
                    company=company,
                    location=loc,
                    internship_type="Internship",
                    description=description[:1000] if description else None,
                    apply_link=apply_link,
                    source=self.source_name,
                    extra={"mode": mode} if mode else {}
                ))
                
        return results

class ApifyWellfoundFetcher(BaseApifyFetcher):
    source_name = "Wellfound"
    ACTOR_ID = "johnvc/wellfound-jobs-api"

    async def fetch(self, keywords: list[str], location: str = "", **kwargs) -> list[RawJob]:
        results: list[RawJob] = []
        
        for keyword in keywords[:2]:
            run_input = {
                "keyword": keyword,
                "locations": [location or "India"],
                "maxItems": 30,
            }
            
            items = await self._run_actor(run_input)
            
            for item in items:
                title = item.get("title") or item.get("jobTitle")
                if not title: continue
                
                company = item.get("companyName") or item.get("company", {}).get("name", "Unknown")
                if isinstance(company, dict):
                    company = company.get("name", "Unknown")
                    
                loc = ", ".join(item.get("locationNames") or [])
                description = item.get("description", "")
                apply_link = item.get("url") or item.get("jobUrl")
                
                mode = None
                loc_lower = (loc or "").lower()
                if item.get("remote") or "remote" in loc_lower or "work from home" in loc_lower:
                    mode = "remote"
                elif "hybrid" in loc_lower:
                    mode = "hybrid"
                    
                salary = item.get("compensationRaw", "")
                desc_parts = []
                if salary:
                    desc_parts.append(f"Salary: {salary}")
                if description:
                    desc_parts.append(description[:1000])
                
                results.append(RawJob(
                    title=title,
                    company=company,
                    location=loc,
                    internship_type="Internship",
                    description=" | ".join(desc_parts) if desc_parts else None,
                    apply_link=apply_link,
                    source=self.source_name,
                    extra={"mode": mode} if mode else {}
                ))
                
        return results

class ApifyNaukriFetcher(BaseApifyFetcher):
    source_name = "Naukri"
    ACTOR_ID = "parsebird/naukri-scraper"

    async def fetch(self, keywords: list[str], location: str = "", **kwargs) -> list[RawJob]:
        results: list[RawJob] = []
        
        for keyword in keywords[:2]:
            run_input = {
                "searchKeywords": keyword,
                "location": location or "India",
                "maxItems": 30,
            }
            
            items = await self._run_actor(run_input)
            
            for item in items:
                title = item.get("title") or item.get("jobTitle")
                if not title: continue
                
                company = item.get("companyName") or item.get("company", "Unknown")
                loc = item.get("location", "")
                description = item.get("jobDescription", "") or item.get("description", "")
                apply_link = item.get("jobUrl") or item.get("url")
                
                mode = None
                loc_lower = (loc or "").lower()
                if "remote" in loc_lower or "work from home" in loc_lower:
                    mode = "remote"
                elif "hybrid" in loc_lower:
                    mode = "hybrid"
                    
                salary = item.get("salary", "")
                experience = item.get("experience", "")
                
                desc_parts = []
                if salary: desc_parts.append(f"Salary: {salary}")
                if experience: desc_parts.append(f"Experience: {experience}")
                if description: desc_parts.append(description[:1000])
                    
                results.append(RawJob(
                    title=title,
                    company=company,
                    location=loc,
                    internship_type="Internship",
                    description=" | ".join(desc_parts) if desc_parts else None,
                    apply_link=apply_link,
                    source=self.source_name,
                    extra={"mode": mode} if mode else {}
                ))
                
        return results
