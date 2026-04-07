import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.deps import get_db
from app.services.access_code_service import AccessCodeService
from app.services.booking_service import BookingService, normalize_phone
from app.services.email_service import EmailService
from app.services.property_content_service import PropertyContentService
from app.services.security_service import EmailVerificationService
from app.services.telegram_service import TelegramService

router = APIRouter(prefix="/webhooks/telegram", tags=["telegram"])

settings = get_settings()
booking_service = BookingService()
telegram_service = TelegramService()
email_service = EmailService()
verification_service = EmailVerificationService()
property_content = PropertyContentService()
access_code_service = AccessCodeService()

CODE_RE = re.compile(r"^\d{6}$")


async def prompt_phone(chat_id: int | str) -> None:
    await telegram_service.send_message(
        chat_id,
        "Привет. Чтобы открыть бронь, отправьте номер телефона из бронирования в формате +79991234567.",
        reply_markup=telegram_service.main_menu(),
    )


async def send_booking_section(chat_id: int | str, booking) -> None:
    await telegram_service.send_message(
        chat_id,
        property_content.booking_summary(booking),
        reply_markup=telegram_service.booking_menu(),
    )


async def send_checkin_section(chat_id: int | str, booking) -> None:
    await telegram_service.send_message(
        chat_id,
        property_content.checkin_overview(booking),
        reply_markup=telegram_service.checkin_menu(),
    )


async def send_stay_section(chat_id: int | str, booking) -> None:
    await telegram_service.send_message(
        chat_id,
        property_content.stay_overview(booking),
        reply_markup=telegram_service.stay_menu(),
    )


async def send_support_section(chat_id: int | str, booking) -> None:
    await telegram_service.send_message(
        chat_id,
        property_content.support_text(booking),
        reply_markup=telegram_service.support_menu(),
    )


async def handle_callback(chat_id: int | str, message_id: int, callback_query_id: str, data: str, db: Session):
    booking = booking_service.get_booking_by_chat_id(db, chat_id)
    if booking is None and data not in {"back_main"}:
        await telegram_service.answer_callback_query(callback_query_id, "Сначала подтвердите доступ к брони")
        await prompt_phone(chat_id)
        return

    if data == "checkin_code" and booking is not None:
        await access_code_service.try_prepare_code_for_booking(db, booking)
        access_message = access_code_service.get_code_message(db, booking)
        await telegram_service.edit_message_text(
            chat_id,
            message_id,
            access_message.text,
            reply_markup=telegram_service.checkin_menu(),
        )
        await telegram_service.answer_callback_query(callback_query_id)
        return

    callback_map: dict[str, tuple[str, dict]] = {
        "back_main": ("Главное меню\n\nВыберите раздел в нижней клавиатуре.", {}),
        "booking_refresh": (property_content.booking_summary(booking), telegram_service.booking_menu()) if booking else ("", {}),
        "booking_details": (property_content.booking_details(booking), telegram_service.booking_menu()) if booking else ("", {}),
        "booking_dates": (property_content.booking_dates(booking), telegram_service.booking_menu()) if booking else ("", {}),
        "checkin_route": (property_content.checkin_route(booking), telegram_service.checkin_menu()) if booking else ("", {}),
        "checkin_instruction": (property_content.checkin_instruction(booking), telegram_service.checkin_menu()) if booking else ("", {}),
        "checkin_photo": (property_content.checkin_photo(booking), telegram_service.checkin_menu()) if booking else ("", {}),
        "checkin_address": (property_content.checkin_address(booking), telegram_service.checkin_menu()) if booking else ("", {}),
        "stay_wifi": (property_content.wifi_text(booking), telegram_service.stay_menu()) if booking else ("", {}),
        "stay_rules": (property_content.house_rules_text(booking), telegram_service.stay_menu()) if booking else ("", {}),
        "stay_problem": (property_content.problem_menu_text(booking), telegram_service.problem_menu()) if booking else ("", {}),
        "stay_extend": (property_content.extend_text(booking), telegram_service.stay_menu()) if booking else ("", {}),
        "support_call": (property_content.support_call_text(booking), telegram_service.support_menu()) if booking else ("", {}),
        "support_telegram": (property_content.support_telegram_text(booking), telegram_service.support_menu()) if booking else ("", {}),
        "support_whatsapp": (property_content.support_whatsapp_text(booking), telegram_service.support_menu()) if booking else ("", {}),
        "support_urgent": (property_content.support_urgent_text(booking), telegram_service.support_menu()) if booking else ("", {}),
        "problem_cant_enter": (property_content.problem_cant_enter_text(booking), telegram_service.problem_menu()) if booking else ("", {}),
        "problem_code": (property_content.problem_code_text(booking), telegram_service.problem_menu()) if booking else ("", {}),
        "problem_wifi": (property_content.problem_wifi_text(booking), telegram_service.problem_menu()) if booking else ("", {}),
        "problem_room": (property_content.problem_room_text(booking), telegram_service.problem_menu()) if booking else ("", {}),
        "problem_support": (property_content.support_text(booking), telegram_service.support_menu()) if booking else ("", {}),
        "back_stay": (property_content.stay_overview(booking), telegram_service.stay_menu()) if booking else ("", {}),
    }

    if data not in callback_map:
        await telegram_service.answer_callback_query(callback_query_id, "Неизвестное действие")
        return

    text, reply_markup = callback_map[data]
    await telegram_service.edit_message_text(chat_id, message_id, text, reply_markup=reply_markup or None)
    await telegram_service.answer_callback_query(callback_query_id)


@router.post("/{secret}")
async def telegram_webhook(
    secret: str,
    update: dict,
    db: Session = Depends(get_db),
):
    if secret != settings.telegram_webhook_secret:
        raise HTTPException(status_code=403, detail="Invalid telegram webhook secret")

    callback_query = update.get("callback_query")
    if callback_query:
        chat_id = callback_query["message"]["chat"]["id"]
        message_id = callback_query["message"]["message_id"]
        callback_query_id = callback_query["id"]
        data = callback_query.get("data", "")
        await handle_callback(chat_id, message_id, callback_query_id, data, db)
        return {"ok": True}

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
                "Добро пожаловать в Apartello.\n\n"
                "Ваша бронь найдена. Выберите нужный раздел в меню ниже.",
                reply_markup=telegram_service.main_menu(),
            )
            await send_booking_section(chat_id, booking)
        else:
            await prompt_phone(chat_id)
        return {"ok": True}

    if text == "Моя бронь":
        booking = booking_service.get_booking_by_chat_id(db, chat_id)
        if booking:
            await send_booking_section(chat_id, booking)
        else:
            await prompt_phone(chat_id)
        return {"ok": True}

    if text == "Заселение":
        booking = booking_service.get_booking_by_chat_id(db, chat_id)
        if booking:
            await send_checkin_section(chat_id, booking)
        else:
            await prompt_phone(chat_id)
        return {"ok": True}

    if text == "Проживание":
        booking = booking_service.get_booking_by_chat_id(db, chat_id)
        if booking:
            await send_stay_section(chat_id, booking)
        else:
            await prompt_phone(chat_id)
        return {"ok": True}

    if text == "Поддержка":
        booking = booking_service.get_booking_by_chat_id(db, chat_id)
        if booking:
            await send_support_section(chat_id, booking)
        else:
            await prompt_phone(chat_id)
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
            "Готово, доступ подтвержден.\n\nВыберите нужный раздел в меню ниже.",
            reply_markup=telegram_service.main_menu(),
        )
        await send_booking_section(chat_id, booking)
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
                "Не удалось отправить письмо. Проверьте SMTP-настройки в .env и попробуйте снова.",
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
