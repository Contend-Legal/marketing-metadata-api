from typing import Optional, Any
from pydantic import BaseModel, Field, ConfigDict, computed_field


class ModelBase(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        validate_by_name=True,
        validate_by_alias=True,
        validation_error_cause=True,
    )


# --- GTM Models ---


class GtmVariable(ModelBase):
    name: str
    variable_id: str = Field(..., alias="variableId")
    type: str


class GtmTrigger(ModelBase):
    name: str
    trigger_id: str = Field(..., alias="triggerId")
    type: str


class GtmTag(ModelBase):
    name: str
    tag_id: str = Field(..., alias="tagId")
    type: str
    firing_trigger_ids: list[str] = Field(default_factory=list, alias="firingTriggerId")
    parameters: Optional[list[dict[str, Any]]] = None


class GtmContainer(ModelBase):
    name: str
    public_id: str = Field(..., alias="publicId")
    container_id: str = Field(..., alias="containerId")
    tags: list[GtmTag] = Field(default_factory=list)
    triggers: list[GtmTrigger] = Field(default_factory=list)
    variables: list[GtmVariable] = Field(default_factory=list)
    live_version_id: Optional[str] = None
    error: Optional[str] = None  # Captures errors for this container


class GtmAccount(ModelBase):
    name: str
    account_id: str = Field(..., alias="accountId")
    containers: list[GtmContainer] = Field(default_factory=list)


# --- GA4 Models ---


class GaDataStream(ModelBase):
    display_name: str = Field(..., alias="displayName")
    type: str
    measurement_id: Optional[str] = None


class GaProperty(ModelBase):
    display_name: str = Field(..., alias="displayName")
    property_id: str
    time_zone: str = Field(..., alias="timeZone")
    currency_code: str = Field(..., alias="currencyCode")
    data_streams: list[GaDataStream] = Field(default_factory=list, alias="dataStreams")


class GaAccount(ModelBase):
    display_name: str = Field(..., alias="displayName")
    account_id: str
    properties: list[GaProperty] = Field(default_factory=list)


# --- Report Models ---


class AuditSummary(ModelBase):
    gtm_accounts: int = 0
    gtm_containers: int = 0
    gtm_tags: int = 0
    gtm_triggers: int = 0
    gtm_variables: int = 0
    ga_accounts: int = 0
    ga_properties: int = 0
    ga_streams: int = 0


class AuditReport(ModelBase):
    gtm_accounts: list[GtmAccount]
    ga_accounts: list[GaAccount]

    @computed_field
    @property
    def summary(self) -> AuditSummary:
        summary = AuditSummary()
        summary.gtm_accounts = len(self.gtm_accounts)
        for acc in self.gtm_accounts:
            summary.gtm_containers += len(acc.containers)
            for cont in acc.containers:
                summary.gtm_tags += len(cont.tags)
                summary.gtm_triggers += len(cont.triggers)
                summary.gtm_variables += len(cont.variables)
        summary.ga_accounts = len(self.ga_accounts)
        for acc in self.ga_accounts:
            summary.ga_properties += len(acc.properties)
            for prop in acc.properties:
                summary.ga_streams += len(prop.data_streams)
        return summary
