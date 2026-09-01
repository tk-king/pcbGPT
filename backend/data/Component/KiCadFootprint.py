from typing import Set

from pydantic import BaseModel, Field


class KiCadFootprint(BaseModel):
    library: str
    name: str
    description: str = ""
    tags: str = ""
    keywords: str = ""
    pad_count: int = 0
    pad_types: Set[str] = Field(default_factory=set)
