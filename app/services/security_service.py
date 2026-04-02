import hashlib
import secrets
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Booking, EmailVerification

settings = get_settings()


class EmailVerificationService:
    def generate_code(self) -> str:
        return f"{secrets.randbelow(1_000_000):06d}"

    def hash_code(self, chat_id: int | str, email: str, code: str) -> str:
        payload = f"{settings.email_otp_secret}:{chat_id}:{email.lower()}:{code}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def mask_email(self, email: str) -> str:
        local, _, domain = email.partition("@")
        if len(local) <= 2:
            masked_local = local[:1] + "***"
        else:
            masked_local = local[:1] + "***" + local[-1:]
        return f"{masked_local}@{domain}"

    def create_or_replace_verification(
        self,
        db: Session,
        booking: Booking,
        chat_id: int | str,
        email: str,
    ) -> tuple[EmailVerification, str]:
        active_items = db.scalars(
            select(EmailVerification).where(
                EmailVerification.chat_id == str(chat_id),
                EmailVerification.is_used.is_(False),
            )
        ).all()
        for item in active_items:
            item.is_used = True

        code = self.generate_code()
        now = datetime.utcnow()
        verification = EmailVerification(
            booking_id=booking.id,
            chat_id=str(chat_id),
            email=email,
            code_hash=self.hash_code(chat_id, email, code),
            attempts_left=settings.email_otp_attempts,
            is_used=False,
            expires_at=now + timedelta(minutes=settings.email_otp_ttl_minutes),
            resend_available_at=now + timedelta(seconds=settings.email_otp_resend_cooldown_seconds),
        )
        db.add(verification)
        db.commit()
        db.refresh(verification)
        return verification, code

    def get_latest_active_verification(self, db: Session, chat_id: int | str) -> EmailVerification | None:
        stmt = (
            select(EmailVerification)
            .where(
                EmailVerification.chat_id == str(chat_id),
                EmailVerification.is_used.is_(False),
            )
            .order_by(EmailVerification.created_at.desc())
        )
        return db.scalars(stmt).first()

    def can_resend(self, verification: EmailVerification) -> bool:
        return datetime.utcnow() >= verification.resend_available_at and not verification.is_used

    def resend_verification(
        self,
        db: Session,
        verification: EmailVerification,
    ) -> str:
        code = self.generate_code()
        now = datetime.utcnow()
        verification.code_hash = self.hash_code(verification.chat_id, verification.email, code)
        verification.expires_at = now + timedelta(minutes=settings.email_otp_ttl_minutes)
        verification.resend_available_at = now + timedelta(seconds=settings.email_otp_resend_cooldown_seconds)
        verification.attempts_left = settings.email_otp_attempts
        db.commit()
        return code

    def verify_code(self, db: Session, chat_id: int | str, code: str) -> EmailVerification | None:
        verification = self.get_latest_active_verification(db, chat_id)
        if verification is None:
            return None

        now = datetime.utcnow()
        if verification.is_used or verification.expires_at < now or verification.attempts_left <= 0:
            return None

        expected_hash = self.hash_code(chat_id, verification.email, code)
        if expected_hash != verification.code_hash:
            verification.attempts_left -= 1
            db.commit()
            return None

        verification.is_used = True
        db.commit()
        db.refresh(verification)
        return verification
