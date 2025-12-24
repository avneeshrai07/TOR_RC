from typing import Optional, List
from datetime import date
from pydantic import BaseModel, Field, HttpUrl


class NewsResult(BaseModel):
    search_type: str = Field(..., description="GOOGLE / RSS / etc")
    search_term: Optional[str] = Field(None, description="Search keyword or phrase")
    engine_name: str = Field(..., description="Source engine name")

    title: str = Field(..., min_length=1)
    link: HttpUrl = Field(..., description="Canonical article URL")
    description: Optional[str] = None

    publish_date: Optional[date] = Field(
        None, description="Article publish date (YYYY-MM-DD)"
    )

    full_title: Optional[str] = Field(
        default="", description="Cleaned or expanded title after scraping"
    )
    full_news: Optional[str] = Field(
        default="", description="Full article content after scraping"
    )
