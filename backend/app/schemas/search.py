from pydantic import BaseModel, model_validator

from app.schemas.filters import SearchFilters
from app.schemas.profile import ProfileIn


class SearchIn(BaseModel):
    profile_id: str | None = None
    profile: ProfileIn | None = None  # unsaved, ad-hoc profile
    filters: SearchFilters = SearchFilters()
    force_refresh: bool = False       # bypass the 6h search cache (costs quota)

    @model_validator(mode="after")
    def _one_profile(self):
        if not self.profile_id and not self.profile:
            raise ValueError("provide profile_id or profile")
        return self
