from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Insured, Person, Profile, User, UserProfile


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def by_cpf(self, cpf: str) -> User | None:
        return self.db.scalar(select(User).where(User.cpf == cpf, User.deleted_at.is_(None)))

    def get(self, user_id: int) -> User | None:
        return self.db.get(User, user_id)

    def profiles(self, user_id: int) -> list[str]:
        statement = select(Profile.code).join(UserProfile).where(UserProfile.user_id == user_id)
        return list(self.db.scalars(statement))


class InsuredRepository:
    def __init__(self, db: Session):
        self.db = db

    def list(self, page: int, page_size: int, kind: str | None = None, status: str | None = None):
        statement = select(Insured, Person).join(Person, Person.id == Insured.person_id).where(Insured.deleted_at.is_(None))
        count_statement = select(func.count()).select_from(Insured).where(Insured.deleted_at.is_(None))
        if kind:
            statement = statement.where(Insured.tipo_vinculo == kind)
            count_statement = count_statement.where(Insured.tipo_vinculo == kind)
        if status:
            statement = statement.where(Insured.situacao == status)
            count_statement = count_statement.where(Insured.situacao == status)
        total = self.db.scalar(count_statement) or 0
        rows = self.db.execute(statement.order_by(Insured.created_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
        return rows, total
