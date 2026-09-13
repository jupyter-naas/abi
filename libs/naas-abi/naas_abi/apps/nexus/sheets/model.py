from __future__ import annotations

from pydantic import BaseModel, Field


class SheetTab(BaseModel):
    name: str = "Sheet1"
    rows: list[list[str | float | int | None]] = Field(default_factory=list)


class SheetWorkbook(BaseModel):
    title: str = "Untitled workbook"
    sheets: list[SheetTab] = Field(default_factory=lambda: [SheetTab()])
