"""Create every table on the configured database.

The application also does this on startup, so this script is only needed when
you want to prepare a database ahead of the first boot.

    python create_tables.py
"""

from app.database import engine
from app.models import Base  # importing the package registers every table


def main() -> None:
    Base.metadata.create_all(bind=engine)
    tables = ", ".join(sorted(Base.metadata.tables))
    print(f"Tables ready: {tables}")


if __name__ == "__main__":
    main()
