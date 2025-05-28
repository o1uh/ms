# server/message_handler.py
import json
# Для работы с БД нам понадобятся функции из db_handler
from server import db_handler


# Функцию для отправки JSON-сообщения тоже можно было бы вынести
# в какой-нибудь protocol_utils.py или оставить в main_server.py.
# Пока предположим, что функция send_json_message будет доступна
# (например, передана как аргумент или импортирована из main_server, если мы ее там оставим).


def process_private_message(db_conn, payload, current_username, current_user_id, active_clients, clients_lock,
                            send_json_message_func, logger):
    """
    Обрабатывает запрос на отправку личного сообщения.
    Сохраняет сообщение в БД и пытается доставить онлайн-получателю.
    """
    recipient_username = payload.get("recipient")
    text = payload.get("text")

    if not recipient_username or not text:
        logger.warning(f"Некорректное личное сообщение от {current_username}: отсутствует получатель или текст.")
        send_json_message_func(active_clients[current_username]['conn'], {"type": "error_notification", "payload": {
            "message": "Некорректный формат личного сообщения."}})
        return

    # 1. Получаем ID получателя из БД
    recipient_user_data = db_handler.get_user_from_db(db_conn, recipient_username, logger)
    if not recipient_user_data:
        logger.warning(f"Получатель {recipient_username} не найден в БД (сообщение от {current_username}).")
        send_json_message_func(active_clients[current_username]['conn'], {"type": "error_notification", "payload": {
            "message": f"Пользователь '{recipient_username}' не существует."}})
        return

    recipient_user_id = recipient_user_data["user_id"]

    # Опционально: Проверка на отправку самому себе
    if recipient_user_id == current_user_id:
        logger.info(f"Пользователь {current_username} пытается отправить сообщение самому себе. (Сообщение: {text})")
        # Решите, как это обрабатывать. Можно разрешить, можно запретить.
        # Если разрешаем, то логика ниже сработает корректно.
        # Если запрещаем, то:
        # send_json_message_func(active_clients[current_username]['conn'], {"type": "error_notification", "payload": {"message": "Нельзя отправлять сообщения самому себе."}})
        # return

    # 2. Получаем или создаем ID чата
    chat_id = db_handler.get_or_create_direct_chat(db_conn, current_user_id, recipient_user_id, logger)
    if not chat_id:
        logger.error(f"Не удалось получить/создать chat_id для {current_username} и {recipient_username}.")
        send_json_message_func(active_clients[current_username]['conn'], {"type": "error_notification", "payload": {
            "message": "Ошибка сервера при обработке чата."}})
        return

    # 3. Сохраняем сообщение в БД
    saved_message_id = db_handler.save_message_to_db(db_conn, chat_id, current_user_id, 'text', text, logger)

    if not saved_message_id:
        logger.error(f"Сообщение от {current_username} к {recipient_username} не было сохранено в БД.")
        # Можно отправить ошибку отправителю
        send_json_message_func(active_clients[current_username]['conn'], {"type": "error_notification", "payload": {
            "message": "Ошибка сервера: сообщение не сохранено."}})
        # Пока просто логируем и не прерываем попытку онлайн-доставки
    else:
        logger.info(f"Сообщение (ID: {saved_message_id}) от {current_username} к {recipient_username} сохранено.")

    # 4. Пытаемся доставить онлайн-получателю
    recipient_info_for_delivery = None
    with clients_lock:  # Блокировка нужна при доступе к active_clients
        recipient_info_for_delivery = active_clients.get(recipient_username)

    if recipient_info_for_delivery and recipient_info_for_delivery['conn']:
        logger.info(f"Доставка онлайн-сообщения от {current_username} к {recipient_username}: {text}")
        send_json_message_func(recipient_info_for_delivery['conn'], {
            "type": "incoming_message",
            "payload": {
                "sender": current_username,
                "text": text,
                "chat_id": chat_id,
                "message_id": saved_message_id
            }
        })
    else:
        logger.info(
            f"Получатель {recipient_username} оффлайн. Сообщение от {current_username} (ID: {saved_message_id}) сохранено в БД для последующей доставки.")
        # Можно отправить уведомление отправителю, что сообщение сохранено (пока не делаем)
        # send_json_message_func(active_clients[current_username]['conn'],
        #    {"type": "notification", "payload": {"message": f"Сообщение для {recipient_username} сохранено и будет доставлено."}})

# Сюда в будущем можно будет добавить функции для обработки других типов сообщений
# например, запроса истории, групповых сообщений и т.д.
# def process_request_chat_history(db_conn, payload, current_user_id, send_json_message_func, logger):
#    pass