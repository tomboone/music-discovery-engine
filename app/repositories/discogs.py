import uuid

from sqlalchemy.orm import Session

from app.models.app import DiscogsProfile


class DiscogsRepository:
    def save_request_token(
        self,
        session: Session,
        user_id: uuid.UUID,
        request_token: str,
        request_token_secret: str,
    ) -> DiscogsProfile:
        profile = session.query(DiscogsProfile).filter_by(user_id=user_id).first()
        if profile is None:
            profile = DiscogsProfile(
                id=uuid.uuid4(),
                user_id=user_id,
                request_token=request_token,
                request_token_secret=request_token_secret,
            )
            session.add(profile)
        else:
            profile.request_token = request_token
            profile.request_token_secret = request_token_secret
        session.commit()
        return profile

    def save_access_token(
        self,
        session: Session,
        user_id: uuid.UUID,
        access_token: str,
        access_token_secret: str,
        username: str,
    ) -> DiscogsProfile:
        profile = session.query(DiscogsProfile).filter_by(user_id=user_id).one()
        profile.access_token = access_token
        profile.access_token_secret = access_token_secret
        profile.discogs_username = username
        profile.request_token = None
        profile.request_token_secret = None
        session.commit()
        return profile

    def clear_access_token(self, session: Session, user_id: uuid.UUID) -> None:
        profile = session.query(DiscogsProfile).filter_by(user_id=user_id).one()
        profile.access_token = None
        profile.access_token_secret = None

    def get_discogs_profile(
        self, session: Session, user_id: uuid.UUID
    ) -> DiscogsProfile | None:
        return session.query(DiscogsProfile).filter_by(user_id=user_id).first()

    def get_profile_by_request_token(
        self, session: Session, request_token: str
    ) -> DiscogsProfile | None:
        return (
            session.query(DiscogsProfile).filter_by(request_token=request_token).first()
        )
