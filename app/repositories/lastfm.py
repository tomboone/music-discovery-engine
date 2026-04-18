import uuid

from sqlalchemy.orm import Session

from app.models.app import LastfmProfile


class LastfmRepository:
    def save_lastfm_profile(
        self,
        session: Session,
        user_id: uuid.UUID,
        username: str,
        session_key: str,
    ) -> LastfmProfile:
        profile = session.query(LastfmProfile).filter_by(user_id=user_id).first()
        if profile:
            profile.lastfm_username = username
            profile.session_key = session_key
        else:
            profile = LastfmProfile(
                id=uuid.uuid4(),
                user_id=user_id,
                lastfm_username=username,
                session_key=session_key,
            )
            session.add(profile)
        session.commit()
        return profile

    def get_lastfm_profile(
        self, session: Session, user_id: uuid.UUID
    ) -> LastfmProfile | None:
        return session.query(LastfmProfile).filter_by(user_id=user_id).first()
