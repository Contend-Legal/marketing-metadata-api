from typing import Optional, Any
from pydantic import BaseModel, Field


# --- GTM Models ---

class GtmTag(BaseModel):
    name: str
    tag_id: str = Field(..., alias="tagId")
    type: str
    parameters: Optional[list[dict[str, Any]]] = None

class GtmContainer(BaseModel):
    name: str
    public_id: str = Field(..., alias="publicId")
    container_id: str = Field(..., alias="containerId")
    tags: list[GtmTag] = Field(default_factory=list)

class GtmAccount(BaseModel):
    name: str
    account_id: str = Field(..., alias="accountId")
    containers: list[GtmContainer] = Field(default_factory=list)


# --- GA4 Models ---

class GaDataStream(BaseModel):
    display_name: str = Field(..., alias="displayName")
    type: str
    measurement_id: Optional[str] = None

class GaProperty(BaseModel):
    display_name: str = Field(..., alias="displayName")
    property_id: str
    time_zone: str = Field(..., alias="timeZone")
    currency_code: str = Field(..., alias="currencyCode")
    data_streams: list[GaDataStream] = Field(default_factory=list, alias="dataStreams")

class GaAccount(BaseModel):
    display_name: str = Field(..., alias="displayName")
    account_id: str
    properties: list[GaProperty] = Field(default_factory=list)


# --- Report Model ---

class AuditReport(BaseModel):
    gtm_accounts: list[GtmAccount]
    ga_accounts: list[GaAccount]