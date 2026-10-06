from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field


class SheetTab(BaseModel):
    column_widths: dict[
        Annotated[int, Field(ge=0, le=16383)], Annotated[int, Field(ge=40, le=1000)]
    ] = Field(default_factory=dict)
    row_heights: dict[
        Annotated[int, Field(ge=0, le=1048575)], Annotated[int, Field(ge=20, le=400)]
    ] = Field(default_factory=dict)
    name: str = "Sheet1"
    rows: list[list[str | float | int | None]] = Field(default_factory=list)


class SheetWorkbook(BaseModel):
    title: str = "Untitled workbook"
    sheets: list[SheetTab] = Field(default_factory=lambda: [SheetTab()])
