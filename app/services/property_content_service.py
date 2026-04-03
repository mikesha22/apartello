from __future__ import annotations

from datetime import datetime


PROPERTY_SETTINGS = {
    "Apartello Tolstogo": {
        "address": "г. Томск, ул. Толстого, дом ...",
        "checkin_time": "14:00",
        "checkout_time": "12:00",
        "checkin_instructions": (
            "Подойдите к зданию по адресу из брони. Вход со стороны двора. "
            "Код доступа появится ближе ко времени заселения."
        ),
        "route_hint": "Вход со стороны двора, ориентир — черная калитка.",
        "entry_photo_caption": "Фото входа пока не добавлено. Позже сюда можно подставить фото или ссылку.",
        "yandex_maps_url": "https://yandex.ru/maps/",
        "two_gis_url": "https://2gis.ru/",
        "google_maps_url": "https://maps.google.com/",
        "wifi_name": "Apartello Guest",
        "wifi_password": "12345678",
        "house_rules": (
            "— не шуметь после 22:00\n"
            "— не курить в помещении\n"
            "— не передавать код доступа третьим лицам\n"
            "— бережно относиться к имуществу"
        ),
        "support_phone": "+7 999 123-45-67",
        "support_telegram": "@apartello_support",
        "support_whatsapp": "+7 999 123-45-67",
        "support_urgent": "+7 999 123-45-67",
    }
}

DEFAULT_SETTINGS = {
    "address": "Адрес объекта пока не заполнен.",
    "checkin_time": "14:00",
    "checkout_time": "12:00",
    "checkin_instructions": "Инструкция пока не добавлена.",
    "route_hint": "Ориентир пока не добавлен.",
    "entry_photo_caption": "Фото входа пока не добавлено.",
    "yandex_maps_url": "https://yandex.ru/maps/",
    "two_gis_url": "https://2gis.ru/",
    "google_maps_url": "https://maps.google.com/",
    "wifi_name": "Не заполнено",
    "wifi_password": "Не заполнено",
    "house_rules": "Правила проживания пока не добавлены.",
    "support_phone": "+7 ...",
    "support_telegram": "@support",
    "support_whatsapp": "+7 ...",
    "support_urgent": "+7 ...",
}


class PropertyContentService:
    def get_settings(self, property_name: str | None) -> dict:
        result = dict(DEFAULT_SETTINGS)
        if property_name:
            result.update(PROPERTY_SETTINGS.get(property_name, {}))
        return result

    def format_dt(self, value: datetime | None) -> str:
        if value is None:
            return "не указано"
        return value.strftime("%d.%m.%Y %H:%M")

    def booking_summary(self, booking) -> str:
        return (
            "Ваша бронь\n\n"
            f"Номер брони: {booking.external_booking_id}\n"
            f"Объект: {booking.property_name or 'не указан'}\n"
            f"Апартамент: {booking.room_name or 'не указан'}\n"
            f"Заезд: {self.format_dt(booking.checkin_at)}\n"
            f"Выезд: {self.format_dt(booking.checkout_at)}\n"
            f"Статус: {booking.status or 'не указан'}"
        )

    def booking_dates(self, booking) -> str:
        settings = self.get_settings(booking.property_name)
        return (
            "Даты проживания\n\n"
            f"Заезд: {self.format_dt(booking.checkin_at)}\n"
            f"Выезд: {self.format_dt(booking.checkout_at)}\n\n"
            f"Стандартное время заезда: {settings['checkin_time']}\n"
            f"Стандартное время выезда: {settings['checkout_time']}"
        )

    def booking_details(self, booking) -> str:
        return (
            "Детали брони\n\n"
            f"Номер брони: {booking.external_booking_id}\n"
            f"Объект: {booking.property_name or 'не указан'}\n"
            f"Апартамент: {booking.room_name or 'не указан'}\n"
            f"Статус: {booking.status or 'не указан'}"
        )

    def checkin_overview(self, booking) -> str:
        settings = self.get_settings(booking.property_name)
        return (
            "Заселение\n\n"
            f"Адрес:\n{settings['address']}\n\n"
            f"Заселение доступно с {settings['checkin_time']}.\n\n"
            f"Инструкция:\n{settings['checkin_instructions']}\n\n"
            "Если возникнут сложности со входом, откройте раздел «Поддержка»."
        )

    def checkin_route(self, booking) -> str:
        settings = self.get_settings(booking.property_name)
        return (
            "Как добраться\n\n"
            f"Адрес:\n{settings['address']}\n\n"
            f"Ориентир:\n{settings['route_hint']}\n\n"
            f"Яндекс Карты: {settings['yandex_maps_url']}\n"
            f"2ГИС: {settings['two_gis_url']}\n"
            f"Google Maps: {settings['google_maps_url']}"
        )

    def checkin_instruction(self, booking) -> str:
        settings = self.get_settings(booking.property_name)
        return (
            "Инструкция по входу\n\n"
            f"{settings['checkin_instructions']}\n\n"
            "Если уже наступило время заезда, а попасть внутрь не получается, нажмите «Поддержка»."
        )

    def checkin_address(self, booking) -> str:
        settings = self.get_settings(booking.property_name)
        return f"Адрес объекта\n\n{settings['address']}"

    def checkin_photo(self, booking) -> str:
        settings = self.get_settings(booking.property_name)
        return f"Фото входа\n\n{settings['entry_photo_caption']}"

    def access_code_text(self, booking) -> str:
        return (
            "Код доступа пока недоступен.\n\n"
            "Он появится ближе ко времени заселения. "
            "Если время заселения уже наступило, а код не отображается, обратитесь в поддержку."
        )

    def stay_overview(self, booking) -> str:
        return (
            "Во время проживания\n\n"
            "Здесь вы можете быстро открыть Wi-Fi, правила проживания, "
            "сообщить о проблеме или запросить продление."
        )

    def wifi_text(self, booking) -> str:
        settings = self.get_settings(booking.property_name)
        return (
            "Wi-Fi\n\n"
            f"Сеть: {settings['wifi_name']}\n"
            f"Пароль: {settings['wifi_password']}"
        )

    def house_rules_text(self, booking) -> str:
        settings = self.get_settings(booking.property_name)
        return f"Правила проживания\n\n{settings['house_rules']}"

    def extend_text(self, booking) -> str:
        return (
            "Продление проживания\n\n"
            "Если вы хотите продлить проживание, напишите в поддержку. "
            "Мы проверим доступность дат и подскажем дальнейшие шаги."
        )

    def support_text(self, booking) -> str:
        settings = self.get_settings(booking.property_name)
        return (
            "Поддержка Apartello\n\n"
            f"Телефон: {settings['support_phone']}\n"
            f"Telegram: {settings['support_telegram']}\n"
            f"WhatsApp: {settings['support_whatsapp']}\n\n"
            "Если вопрос срочный и вы не можете попасть внутрь, пожалуйста, звоните сразу."
        )

    def support_call_text(self, booking) -> str:
        settings = self.get_settings(booking.property_name)
        return f"Позвонить в поддержку\n\nТелефон: {settings['support_phone']}"

    def support_telegram_text(self, booking) -> str:
        settings = self.get_settings(booking.property_name)
        return f"Telegram поддержки\n\n{settings['support_telegram']}"

    def support_whatsapp_text(self, booking) -> str:
        settings = self.get_settings(booking.property_name)
        return f"WhatsApp поддержки\n\n{settings['support_whatsapp']}"

    def support_urgent_text(self, booking) -> str:
        settings = self.get_settings(booking.property_name)
        return (
            "Срочная помощь\n\n"
            f"Если вы не можете попасть внутрь или случилась срочная проблема, позвоните:\n{settings['support_urgent']}"
        )

    def problem_menu_text(self, booking) -> str:
        return "Сообщить о проблеме\n\nВыберите, что именно случилось."

    def problem_cant_enter_text(self, booking) -> str:
        settings = self.get_settings(booking.property_name)
        return (
            "Не могу войти\n\n"
            "Проверьте, что используете актуальный код и правильный вход. "
            f"Если проблема сохраняется, срочно звоните: {settings['support_phone']}"
        )

    def problem_code_text(self, booking) -> str:
        settings = self.get_settings(booking.property_name)
        return (
            "Не работает код\n\n"
            "Попробуйте ввести код еще раз без лишних символов. "
            f"Если не помогает, обратитесь в поддержку: {settings['support_phone']}"
        )

    def problem_wifi_text(self, booking) -> str:
        settings = self.get_settings(booking.property_name)
        return (
            "Проблема с Wi-Fi\n\n"
            f"Проверьте, что используете сеть {settings['wifi_name']}. "
            "Если интернета нет, напишите в поддержку."
        )

    def problem_room_text(self, booking) -> str:
        settings = self.get_settings(booking.property_name)
        return (
            "Проблема в апартаменте\n\n"
            f"Опишите проблему в поддержке или позвоните: {settings['support_phone']}"
        )
