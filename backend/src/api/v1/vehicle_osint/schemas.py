"""Pydantic schemas for the Vehicle OSINT module."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

QueryType = Literal["vin", "make_model"]


class VehicleOsintRequest(BaseModel):
    query: str
    query_type: QueryType = "vin"


class VehicleRecallSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    recall_id: str | None = None
    component: str | None = None
    summary: str | None = None
    consequence: str | None = None
    remedy: str | None = None
    report_date: str | None = None


class VehicleComplaintSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    odt_number: str | None = None
    component: str | None = None
    summary: str | None = None
    crash: bool = False
    fire: bool = False
    date_complaint_filed: str | None = None


class VehicleInfoSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    vin: str | None = None
    make: str | None = None
    model: str | None = None
    model_year: str | None = None
    vehicle_type: str | None = None
    body_class: str | None = None
    drive_type: str | None = None
    fuel_type: str | None = None
    engine_cylinders: str | None = None
    engine_displacement: str | None = None
    transmission: str | None = None
    plant_country: str | None = None
    manufacturer: str | None = None
    series: str | None = None
    trim: str | None = None
    doors: str | None = None
    error_code: str | None = None
    recalls: list[VehicleRecallSchema] = []
    complaints_count: int = 0
    recent_complaints: list[VehicleComplaintSchema] = []
    source: str = "nhtsa"


class VehicleOsintResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    query: str
    query_type: str
    total_results: int
    results: list[VehicleInfoSchema]
    created_at: datetime


class VehicleOsintListResponse(BaseModel):
    items: list[VehicleOsintResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
