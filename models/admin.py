from sqlalchemy.orm import Session
from models.models import Base, engine, User

Base.metadata.create_all(engine)

def initialize_database():
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        admin = session.query(User).filter_by(role="admin").first()

        if admin:
            return

        admin = User(
            name="Administrator",
            email="admin@trek.com",
            phone="9999999999",
            role="admin",
            is_active=True
        )

        admin.set_password("admin123")

        session.add(admin)
        session.commit()