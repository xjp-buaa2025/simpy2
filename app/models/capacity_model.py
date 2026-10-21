"""Opt-in work-area resource model; inventory quantities remain global totals."""
from typing import Dict, Literal, Optional
from pydantic import BaseModel, Field, ConfigDict, model_validator


class AreaResources(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str = ""
    efficiency_multiplier: float = Field(default=1.0, ge=1, le=2, allow_inf_nan=False)
    resource_sets: int = Field(default=1, ge=1, le=4, strict=True)
    dedicated_workers: int = Field(default=0, exclude=True, json_schema_extra={"deprecated": True}, description="已停用：人员按需供给")

    @model_validator(mode="before")
    @classmethod
    def ignore_obsolete_workers(cls, value):
        if isinstance(value, dict):
            value = dict(value)
            value.pop("dedicated_workers", None)
        return value
    equipment: Dict[str, int] = Field(default_factory=dict)


class Workstation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    area_id: str
    label: str = ""
    capacity: int = Field(default=1, ge=1, le=1000)


class CapacityModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool = False
    areas: Dict[str, AreaResources] = Field(default_factory=dict)
    workstations: Dict[str, Workstation] = Field(default_factory=dict)


class EvaluationSettings(BaseModel):
    mode: Literal["plan", "capacity"] = "plan"
    sampling_scheme: Literal["legacy", "paired_v1"] = "legacy"
    max_wip: Optional[int] = Field(default=None, ge=2, le=10000)
