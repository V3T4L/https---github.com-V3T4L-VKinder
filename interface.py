# импорты
import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.utils import get_random_id

from config import comunity_token, access_token, db_url_object
from core import VkTools

from sqlalchemy import create_engine
from data_store import Base, add_user, check_user

# отправка сообщений
class BotInterface():
    def __init__(self, comunity_token, access_token, engine):
        self.vk = vk_api.VkApi(token=comunity_token)
        self.longpoll = VkLongPoll(self.vk)
        self.vk_tools = VkTools(access_token)
        self.params = {}
        self.worksheets = []
        self.offset = 0
        self.engine = engine

    def message_send(self, user_id, message, attachment=None):
        self.vk.method('messages.send',
                       {'user_id': user_id,
                        'message': message,
                        'attachment': attachment,
                        'random_id': get_random_id()}
                       )
        
    # обработка событий / получение сообщений
    def event_handler(self):
        for event in self.longpoll.listen():
            if event.type == VkEventType.MESSAGE_NEW:
                if event.to_me:
                    if event.text.lower() == 'привет':
                        self.params = self.vk_tools.get_profile_info(event.user_id)
                        self.message_send(
                            event.user_id, f'Приветствую, {self.params["name"]}')
                    elif event.text.lower() == 'поиск':
                        if self.params.get("city") is None:
                            self.message_send(
                                event.user_id,
                                'Введите город для поиска в формате: "город "Название города""')
                            continue

                        # логика для поиска анкет
                        self.message_send(
                            event.user_id, 'Начинаю поиск')
                        if self.worksheets:
                            worksheet = self.worksheets.pop()
                            photos = self.vk_tools.get_photos(worksheet['id'])
                            photo_string = ''
                            for photo in photos:
                                photo_string += f'photo{photo["owner_id"]}_{photo["id"]},'
                        else:
                            self.worksheets = self.vk_tools.search_worksheet(
                                self.params, self.offset)
                            worksheet = self.worksheets.pop()
                            photos = self.vk_tools.get_photos(worksheet['id'])
                            photo_string = ''
                            for photo in photos:
                                photo_string += f'photo{photo["owner_id"]}_{photo["id"]},'
                            self.offset += 10

                        self.message_send(
                            event.user_id,
                            f'имя: {worksheet["name"]} ссылка: vk.com/id{worksheet["id"]}',
                            attachment=photo_string
                            )

                        # проверка анкеты в БД в соотвествии с event.user_id
                        worksheet = None
                        new_worksheets = []
                        for worksheet in self.worksheets:
                            if not check_user(self.engine, event.user_id, worksheet['id']):
                                new_worksheets.append(worksheet)
                        self.worksheets = new_worksheets.copy()
                        worksheet = self.worksheets.pop(0)

                        # добавление анкеты в БД в соотвествии с event.user_id
                        add_user(self.engine, event.user_id, worksheet['id'])
                    elif event.text.lower().startswith("город "):
                        city_name = ' '.join(event.text.lower().split()[1:])
                        city = self.vk_tools.get_city(city_name)
                        if city is None:
                            self.message_send(
                                event.user_id, 'Такой город не найден')
                        else:
                            self.params['city'] = city['title']
                            self.message_send(
                                event.user_id, f'Будет выполнен поиск в городе {city["title"]}')

                    elif event.text.lower() == 'пока':
                        self.message_send(
                            event.user_id, 'До свидания')
                    else:
                        self.message_send(
                            event.user_id, 'Неизвестная команда')

if __name__ == '__main__':
    engine = create_engine(db_url_object)
    Base.metadata.create_all(engine)

    bot_interface = BotInterface(comunity_token, access_token, engine)
    bot_interface.event_handler()