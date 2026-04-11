from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.deps import get_db
from app.services.booking_service import BookingService, normalize_phone
from app.services.property_content_service import PropertyContentService
from app.services.telegram_service import TelegramService

router = APIRouter(prefix="/webhooks/telegram", tags=["telegram"])

settings = get_settings()
booking_service = BookingService()
telegram_service = TelegramService()
property_content = PropertyContentService()


async def prompt_contact(chat_id: int | str) -> None:
    await telegram_service.send_message(
        chat_id,
        "Добро пожаловать в Apartello.\n\n"
        "Чтобы найти вашу бронь, нажмите кнопку ниже и отправьте ваш номер телефона.\n"
        "Важно: используйте именно кнопку Telegram «Поделиться моим номером».",
        reply_markup=telegram_service.contact_request_menu(),
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
        await telegram_service.answer_callback_query(callback_query_id, "Сначала подтвердите номер телефона")
        await prompt_contact(chat_id)
        return

    callback_map: dict[str, tuple[str, dict | None]] = {
        "back_main": (
            "Главное меню\n\nВыберите раздел в нижней клавиатуре.",
            None,
        ),
        "booking_refresh": (property_content.booking_summary(booking), telegram_service.booking_menu()) if booking else ("", None),
        "booking_details": (property_content.booking_details(booking), telegram_service.booking_menu()) if booking else ("", None),
        "booking_dates": (property_content.booking_dates(booking), telegram_service.booking_menu()) if booking else ("", None),
        "checkin_code": (property_content.access_code_text(booking), telegram_service.checkin_menu()) if booking else ("", None),
        "checkin_route": (property_content.checkin_route(booking), telegram_service.checkin_menu()) if booking else ("", None),
        "checkin_instruction": (property_content.checkin_instruction(booking), telegram_service.checkin_menu()) if booking else ("", None),
        "checkin_photo": (property_content.checkin_photo(booking), telegram_service.checkin_menu()) if booking else ("", None),
        "checkin_address": (property_content.checkin_address(booking), telegram_service.checkin_menu()) if booking else ("", None),
        "stay_wifi": (property_content.wifi_text(booking), telegram_service.stay_menu()) if booking else ("", None),
        "stay_rules": (property_content.house_rules_text(booking), telegram_service.stay_menu()) if booking else ("", None),
        "stay_problem": (property_content.problem_menu_text(booking), telegram_service.problem_menu()) if booking else ("", None),
        "stay_extend": (property_content.extend_text(booking), telegram_service.stay_menu()) if booking else ("", None),
        "support_call": (property_content.support_call_text(booking), telegram_service.support_menu()) if booking else ("", None),
        "support_telegram": (property_content.support_telegram_text(booking), telegram_service.support_menu()) if booking else ("", None),
        "support_whatsapp": (property_content.support_whatsapp_text(booking), telegram_service.support_menu()) if booking else ("", None),
        "support_urgent": (property_content.support_urgent_text(booking), telegram_service.support_menu()) if booking else ("", None),
        "problem_cant_enter": (property_content.problem_cant_enter_text(booking), telegram_service.problem_menu()) if booking else ("", None),
        "problem_code": (property_content.problem_code_text(booking), telegram_service.problem_menu()) if booking else ("", None),
        "problem_wifi": (property_content.problem_wifi_text(booking), telegram_service.problem_menu()) if booking else ("", None),
        "problem_room": (property_content.problem_room_text(booking), telegram_service.problem_menu()) if booking else ("", None),
        "problem_support": (property_content.support_text(booking), telegram_service.support_menu()) if booking else ("", None),
        "back_stay": (property_content.stay_overview(booking), telegram_service.stay_menu()) if booking else ("", None),
    }

    if data not in callback_map:
        await telegram_service.answer_callback_query(callback_query_id, "Неизвестное действие")
        return

    text, reply_markup = callback_map[data]
    await telegram_service.edit_message_text(chat_id, message_id, text, reply_markup=reply_markup)
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
    contact = message.get("contact")
    from_user = message.get("from") or {}

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
            await prompt_contact(chat_id)
        return {"ok": True}

    if contact:
        contact_user_id = contact.get("user_id")
        from_user_id = from_user.get("id")
        if contact_user_id is None or from_user_id is None or int(contact_user_id) != int(from_user_id):
            await telegram_service.send_message(
                chat_id,
                "Пожалуйста, используйте кнопку «Поделиться моим номером», чтобы отправить именно ваш контакт.",
                reply_markup=telegram_service.contact_request_menu(),
            )
            return {"ok": True}

        normalized_phone = normalize_phone(contact.get("phone_number"))
        booking = booking_service.find_latest_booking_by_phone(db, normalized_phone)
        if booking is None:
            await telegram_service.send_message(
                chat_id,
                "Активная бронь по этому номеру не найдена.\n"
                "Проверьте, что номер совпадает с номером в бронировании, или обратитесь в поддержку.",
                reply_markup=telegram_service.contact_request_menu(),
            )
            return {"ok": True}

        booking_service.link_chat_to_booking_guest(db, chat_id, booking)
        await telegram_service.send_message(
            chat_id,
            "Готово, бронь найдена и доступ открыт.\n\n"
            "Выберите нужный раздел в меню ниже.",
            reply_markup=telegram_service.main_menu(),
        )
        await send_booking_section(chat_id, booking)
        return {"ok": True}

    if text == "Моя бронь":
        booking = booking_service.get_booking_by_chat_id(db, chat_id)
        if booking:
            await send_booking_section(chat_id, booking)
        else:
            await prompt_contact(chat_id)
        return {"ok": True}

    if text == "Заселение":
        booking = booking_service.get_booking_by_chat_id(db, chat_id)
        if booking:
            await send_checkin_section(chat_id, booking)
        else:
            await prompt_contact(chat_id)
        return {"ok": True}

    if text == "Проживание":
        booking = booking_service.get_booking_by_chat_id(db, chat_id)
        if booking:
            await send_stay_section(chat_id, booking)
        else:
            await prompt_contact(chat_id)
        return {"ok": True}

    if text == "Поддержка":
        booking = booking_service.get_booking_by_chat_id(db, chat_id)
        if booking:
            await send_support_section(chat_id, booking)
        else:
            await prompt_contact(chat_id)
        return {"ok": True}

    await telegram_service.send_message(
        chat_id,
        "Используйте меню ниже. Если вы еще не идентифицированы, нажмите кнопку для отправки вашего номера телефона.",
        reply_markup=telegram_service.main_menu() if booking_service.get_booking_by_chat_id(db, chat_id) else telegram_service.contact_request_menu(),
    )
    return {"ok": True}
