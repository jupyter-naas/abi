# OpencodeBase

## What it is
- A minimal SQLAlchemy declarative base class used as the superclass for ORM model classes.

## Public API
- `class OpencodeBase(DeclarativeBase)`
  - Purpose: Provides the SQLAlchemy `DeclarativeBase` for defining mapped ORM models.

## Configuration/Dependencies
- Requires `sqlalchemy` with ORM support:
  - `from sqlalchemy.orm import DeclarativeBase`

## Usage
```python
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from naas_abi_core.models.opencode.Base import OpencodeBase

class User(OpencodeBase):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String)
```

## Caveats
- This class only defines the base; it does not configure an engine, session, or metadata handling beyond what `DeclarativeBase` provides.
