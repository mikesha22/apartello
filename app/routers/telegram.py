import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.deps import get_db
from app.services.booking_service import BookingService, normalize_phone
from app.services.email_service import EmailService
from app.services.security_service import EmailVerificationService
from app.services.telegram_service import TelegramService

router = APIRouter(prefix="/webhooks/telegram", tags=["telegram"])

settings = get_settings()
booking_service = BookingService()
telegram_service = TelegramService()
email_service = EmailService()
verification_service = EmailVerificationService()

CODE_RE = re.compile(r"^\d{6}$")


def format_booking_text(booking) -> str:
    return (
        f"Бронь: #{booking.external_booking_id}\n"
        f"Статус: {booking.status or 'не указан'}\n"
        f"Объект: {booking.property_name or 'не указан'}\n"
        f"Номер: {booking.room_name or 'не указан'}\n"
        f"Заезд: {booking.checkin_at or 'не указан'}\n"
        f"Выезд: {booking.checkout_at or 'не указан'}"
    )


async def prompt_phone(chat_id: int | str) -> None:
    await telegram_service.send_message(
        chat_id,
        "Привет. Чтобы открыть бронь, отправьте номер телефона из бронирования в формате +79991234567.",
    )


@router.post("/{secret}")
async def telegram_webhook(
    secret: str,
    update: dict,
    db: Session = Depends(get_db),
):
    if secret != settings.telegram_webhook_secret:
        raise HTTPException(status_code=403, detail="Invalid telegram webhook secret")

    message = update.get("message")
    if not message:
        return {"ok": True}

    chat_id = message["chat"]["id"]
    text = (message.get("text") or "").strip()

    if text.startswith("/start"):
        booking = booking_service.get_booking_by_chat_id(db, chat_id)
        if booking:
            await telegram_service.send_message(
                chat_id,
                "Добро пожаловать. Ваша бронь найдена.\n\n" + format_booking_text(booking),
                reply_markup=telegram_service.main_menu(),
            )
        else:
            await prompt_phone(chat_id)
        return {"ok": True}

    if text == "Моя бронь":
        booking = booking_service.get_booking_by_chat_id(db, chat_id)
        if booking:
            await telegram_service.send_message(
                chat_id,
                format_booking_text(booking),
                reply_markup=telegram_service.main_menu(),
            )
        else:
            await prompt_phone(chat_id)
        return {"ok": True}

    if text == "Как заселиться":
        booking = booking_service.get_booking_by_chat_id(db, chat_id)
        if not booking:
            await prompt_phone(chat_id)
            return {"ok": True}

        await telegram_service.send_message(
            chat_id,
            "Инструкция по заселению:\n"
            "1. Подойдите к зданию по адресу из брони.\n"
            "2. Используйте код доступа, когда он будет выдан.\n"
            "3. Если возникнут сложности — нажмите «Поддержка».",
            reply_markup=telegram_service.main_menu(),
        )
        return {"ok": True}

    if text == "Маршрут":
        booking = booking_service.get_booking_by_chat_id(db, chat_id)
        if not booking:
            await prompt_phone(chat_id)
            return {"ok": True}

        await telegram_service.send_message(
            chat_id,
            "Маршрут пока в тестовом режиме.\nПозже сюда добавим ссылку на карту и фото входа.",
            reply_markup=telegram_service.main_menu(),
        )
        return {"ok": True}

    if text == "Поддержка":
        booking = booking_service.get_booking_by_chat_id(db, chat_id)
        if not booking:
            await prompt_phone(chat_id)
            return {"ok": True}

        await telegram_service.send_message(
            chat_id,
            "Поддержка пока в тестовом режиме.\nПозже сюда добавим контакт администратора и быстрые сценарии помощи.",
            reply_markup=telegram_service.main_menu(),
        )
        return {"ok": True}

    if text == "Отправить код еще раз":
        verification = verification_service.get_latest_active_verification(db, chat_id)
        if verification is None:
            await prompt_phone(chat_id)
            return {"ok": True}

        if not verification_service.can_resend(verification):
            await telegram_service.send_message(
                chat_id,
                "Код уже был отправлен недавно. Подождите около минуты и попробуйте снова.",
                reply_markup=telegram_service.verification_menu(),
            )
            return {"ok": True}

        code = verification_service.resend_verification(db, verification)
        booking = verification.booking
        booking_label = f"#{booking.external_booking_id}" if booking else "без номера"
        try:
            await email_service.send_verification_code(verification.email, code, booking_label)
        except Exception:
            await telegram_service.send_message(
                chat_id,
                "Не удалось отправить письмо. Проверьте SMTP-настройки в .env и попробуйте еще раз.",
            )
            return {"ok": True}

        await telegram_service.send_message(
            chat_id,
            f"Новый код отправлен на {verification_service.mask_email(verification.email)}.\nВведите 6-значный код из письма.",
            reply_markup=telegram_service.verification_menu(),
        )
        return {"ok": True}

    if CODE_RE.fullmatch(text):
        verification = verification_service.verify_code(db, chat_id, text)
        if verification is None:
            await telegram_service.send_message(
                chat_id,
                "Код не подошел, истек или попытки закончились.\nПопробуйте запросить код еще раз.",
                reply_markup=telegram_service.verification_menu(),
            )
            return {"ok": True}

        booking = verification.booking
        booking_service.link_chat_to_booking_guest(db, chat_id, booking)
        await telegram_service.send_message(
            chat_id,
            "Готово, доступ подтвержден.\n\n" + format_booking_text(booking),
            reply_markup=telegram_service.main_menu(),
        )
        return {"ok": True}

    normalized_phone = normalize_phone(text)
    if normalized_phone and normalized_phone.startswith("+"):
        booking = booking_service.find_latest_booking_by_phone(db, normalized_phone)
        if booking is None or booking.guest is None:
            await telegram_service.send_message(chat_id, "Бронь по этому телефону не найдена.")
            return {"ok": True}

        if not booking.guest.email:
            await telegram_service.send_message(
                chat_id,
                "Мы нашли бронь, но у нее нет email для подтверждения.\nДобавьте email в бронь и попробуйте снова.",
            )
            return {"ok": True}

        verification, code = verification_service.create_or_replace_verification(
            db,
            booking=booking,
            chat_id=chat_id,
            email=booking.guest.email,
        )
        booking_label = f"#{booking.external_booking_id}"

        try:
            await email_service.send_verification_code(booking.guest.email, code, booking_label)
        except Exception:
            await telegram_service.send_message(
                chat_id,
                "Не удалось отправить письмо. Проверьте SMTP-настройки в .env и попробуйте еще раз.",
            )
            return {"ok": True}

        await telegram_service.send_message(
            chat_id,
            f"Нашли бронь и отправили код на {verification_service.mask_email(verification.email)}.\nВведите 6-значный код из письма.",
            reply_markup=telegram_service.verification_menu(),
        )
        return {"ok": True}

    await telegram_service.send_message(
        chat_id,
        "Используйте меню ниже или отправьте номер телефона из бронирования в формате +79991234567.",
        reply_markup=telegram_service.main_menu(),
    )
    return {"ok": True}
