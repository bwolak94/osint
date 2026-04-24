from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import uuid
from datetime import datetime

router = APIRouter(prefix="/api/v1/knowledge-base", tags=["knowledge-base"])

_articles: dict[str, dict] = {}

def _seed():
    if _articles: return
    samples = [
        ("Bypassing WAF with Encoding Techniques", "web", "A comprehensive guide to WAF bypass techniques using URL encoding, Unicode normalization...", ["waf", "bypass", "web"], "high"),
        ("Active Directory Privilege Escalation Paths", "active-directory", "Common privilege escalation paths in Active Directory environments including Kerberoasting, AS-REP Roasting...", ["active-directory", "privilege-escalation", "kerberos"], "critical"),
        ("SSRF to Internal Network Access", "web", "Server-Side Request Forgery exploitation techniques for accessing internal resources...", ["ssrf", "web", "network"], "high"),
        ("Password Spraying without Lockout", "authentication", "Techniques for safe password spraying while avoiding account lockouts...", ["password", "authentication", "active-directory"], "medium"),
        ("Post-Exploitation Data Collection", "post-exploitation", "Systematic approach to collecting valuable data after achieving initial foothold...", ["post-exploitation", "data-collection", "lateral-movement"], "high"),
    ]
    for title, category, content, tags, sev in samples:
        aid = str(uuid.uuid4())
        _articles[aid] = {
            "id": aid, "title": title, "category": category, "content": content,
            "tags": tags, "severity_context": sev, "views": 0,
            "created_at": datetime.utcnow().isoformat(), "updated_at": datetime.utcnow().isoformat()
        }

_seed()

class KbArticle(BaseModel):
    id: str
    title: str
    category: str
    content: str
    tags: list[str]
    severity_context: str
    views: int
    created_at: str
    updated_at: str

class CreateArticleInput(BaseModel):
    title: str
    category: str
    content: str
    tags: list[str] = []
    severity_context: str = "medium"

@router.get("/articles", response_model=list[KbArticle])
async def list_articles(search: Optional[str] = None, category: Optional[str] = None):
    articles = list(_articles.values())
    if search:
        search_l = search.lower()
        articles = [a for a in articles if search_l in a["title"].lower() or search_l in a["content"].lower() or any(search_l in t for t in a["tags"])]
    if category:
        articles = [a for a in articles if a["category"] == category]
    return [KbArticle(**a) for a in articles]

@router.post("/articles", response_model=KbArticle)
async def create_article(data: CreateArticleInput):
    aid = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    article = {"id": aid, "views": 0, "created_at": now, "updated_at": now, **data.model_dump()}
    _articles[aid] = article
    return KbArticle(**article)
