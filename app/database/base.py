from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """The declarative base every model inherits from.

    Loading strategy: this project runs on asyncio, where a lazy load raises
    MissingGreenlet instead of quietly fetching. Scalar relationships therefore
    use lazy="selectin". Collections are left lazy on purpose -- load them per
    query with selectinload(), rather than dragging them in everywhere.
    """
