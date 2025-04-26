from dotenv import load_dotenv
import os
import re

import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.utils import get_random_id
from vk_api.keyboard import VkKeyboard, VkKeyboardColor

load_dotenv()

from parser import rasp, prepods, rasp_prepod, get_pogoda, get_mnogo_pogoda, get_weather_by_day

TOKEN = os.getenv('TOKEN')
pattern=r'^[А-Яа-яЁё]+\s[А-Яа-яЁё]\.[А-Яа-яЁё]\.$'
user_groups = {}
current_week = 0
prepod_names = set(prepods())
days_list = ['понедельник', 'вторник', 'среда', 'четверг', 'пятница', 'суббота', 'воскресение', 'сегодня', 'завтра', 'вчера']

# Клавиатуры
main_keyboard = VkKeyboard(one_time=True)
main_keyboard.add_button('Сегодня', color=VkKeyboardColor.PRIMARY)
main_keyboard.add_button('Завтра', color=VkKeyboardColor.PRIMARY)
main_keyboard.add_line()
main_keyboard.add_button('На эту неделю', color=VkKeyboardColor.PRIMARY)
main_keyboard.add_button('На cледующую неделю', color=VkKeyboardColor.PRIMARY)
main_keyboard.add_line()
main_keyboard.add_button('ИКБО-72-23', color=VkKeyboardColor.SECONDARY)
main_keyboard.add_button('Установить номер группы', color=VkKeyboardColor.SECONDARY)
main_keyboard.add_line()
main_keyboard.add_button('Расписание преподавателя', color=VkKeyboardColor.SECONDARY)
main_keyboard.add_line()
main_keyboard.add_button('Погода', color=VkKeyboardColor.SECONDARY)

weather_keyboard = VkKeyboard(one_time=True)
weather_keyboard.add_button('На сегодня', color=VkKeyboardColor.PRIMARY)
weather_keyboard.add_button('На завтра', color=VkKeyboardColor.PRIMARY)
weather_keyboard.add_line()
weather_keyboard.add_button('На 5 дней', color=VkKeyboardColor.PRIMARY)
weather_keyboard.add_line()
weather_keyboard.add_button('Расписание', color=VkKeyboardColor.SECONDARY)

def main():
    vk_session = vk_api.VkApi(token=TOKEN)
    vk = vk_session.get_api()
    longpoll = VkLongPoll(vk_session)

    for event in longpoll.listen():
        if event.type != VkEventType.MESSAGE_NEW or not event.text:
            continue

        text = event.text.lower()
        user_id = event.user_id

        if text == 'начать' or text == 'расписание':
            send_message(vk, user_id, "Выберите опцию:", main_keyboard)

        elif text == 'погода':
            send_message(vk, user_id, "Выберите промежуток времени:", weather_keyboard)

        elif text == 'на 5 дней':
            weather_forecast(vk, user_id)

        elif text == 'на сегодня':
            weather_day(vk, user_id, 'сегодня')

        elif text == 'на завтра':
            weather_day(vk, user_id, 'завтра')

        elif text == 'расписание преподавателя':
            send_message(vk, user_id, "Введите ФИО преподавателя в формате Фамилия И.О.", main_keyboard)

        elif len(event.text) == 10 and event.text.count('-') == 2:
            user_groups[user_id] = event.text
            send_message(vk, user_id, f"Ваша группа установлена: {event.text}", main_keyboard)

        elif text == 'установить номер группы':
            if user_id in user_groups:
                send_message(vk, user_id, f"Текущая группа: {user_groups[user_id]}", main_keyboard)
            else:
                send_message(vk, user_id, "Введите номер группы в формате XXXX-XX-XX:", main_keyboard)

        elif text in days_list or text.endswith('неделю'):
            send_schedule(vk, user_id, text)

        elif any(prepod for prepod in prepod_names if prepod in text):
            send_prepod_schedule(vk, user_id, text)

        elif re.match(pattern, text):
            send_message(vk, user_id, "Преподаватель не найден", main_keyboard)


def send_message(vk, user_id, message, keyboard=None):
    vk.messages.send(
        user_id=user_id,
        random_id=get_random_id(),
        message=message,
        keyboard=keyboard.get_keyboard() if keyboard else None
    )

def weather_forecast(vk, user_id):
    weather = list(get_mnogo_pogoda())[5:]
    message = "\n".join(weather)
    send_message(vk, user_id, f"Погода на 5 дней в Москве:\n{message}", weather_keyboard)

def weather_day(vk, user_id, day):
    weather = get_weather_by_day(day)
    message = "\n".join(weather)
    send_message(vk, user_id, f"Погода {day} в Москве:\n{message}", weather_keyboard)

def send_schedule(vk, user_id, day):
    if user_id not in user_groups:
        send_message(vk, user_id, "Вы еще не установили группу", main_keyboard)
        return

    group = user_groups[user_id]
    message = ""

    if day.startswith('на эту'):
        message = build_week_schedule(group, current_week)
    elif day.startswith('на cледующую'):
        message = build_week_schedule(group, current_week + 1)
    else:
        schedule = list(rasp(day, group, current_week))
        if not schedule:
            send_message(vk, user_id, "Расписание не найдено", main_keyboard)
            return
        message = "\n".join(f"{idx + 1}) {pair or 'Нет пары'}" for idx, pair in enumerate(schedule))

    send_message(vk, user_id, f"Расписание:\n\n{message}", main_keyboard)

def build_week_schedule(group, week_offset):
    message = ""
    for day in days_list[:6]:  # Только будние дни
        schedule = list(rasp(day, group, week_offset))
        message += f"{day.capitalize()}:\n"
        for idx, pair in enumerate(schedule):
            message += f"{idx + 1}) {pair or 'Нет пары'}\n"
        message += "\n"
    return message

def send_prepod_schedule(vk, user_id, prepod_name):
    schedule = []
    for day in days_list[:6]:
        schedule.extend(rasp_prepod(day, prepod_name, 0))
    if not schedule:
        send_message(vk, user_id, "Расписание преподавателя не найдено", main_keyboard)
        return
    schedule.sort()
    message = ""
    for day_idx in range(6):
        day_schedule = [f"{pair[0]}) {pair[2]}" for pair in schedule if pair[1] == day_idx]
        if day_schedule:
            message += f"\n{days_list[day_idx].capitalize()}:\n" + "\n".join(day_schedule) + "\n"
    send_message(vk, user_id, f"Расписание преподавателя:\n{message}", main_keyboard)

if __name__ == '__main__':
    main()
