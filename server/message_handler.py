# server/message_handler.py
import json
import psycopg2
from server import db_handler


# --- Новая функция для запроса списка чатов ---
def process_request_chat_list(db_conn, current_user_id, active_clients, send_json_message_func, logger):
    """Обрабатывает запрос на получение списка чатов пользователя."""
    logger.info(f"Пользователь ID {current_user_id} запросил список чатов.")

    user_chats = db_handler.get_user_chats(db_conn, current_user_id, logger)

    current_user_conn = None
    # Мы не используем clients_lock здесь, так как предполагаем, что current_user_id
    # соответствует активному пользователю, чье соединение мы ищем.
    # active_clients должен содержать {username: {'conn': ..., 'user_id': ...}}
    # Нужно найти conn по user_id. Это неудобно.
    # Лучше, чтобы active_clients был {user_id: {'conn': ..., 'username': ...}}
    # ИЛИ чтобы send_json_message_func принимала user_id и сама находила conn.
    # ПОКА ОСТАВИМ КАК ЕСТЬ, НО ЭТО МЕСТО ДЛЯ УЛУЧШЕНИЯ active_clients.
    # Временно найдем по user_id перебором (неэффективно, но для примера)
    for username, client_data in active_clients.items():
        if client_data['user_id'] == current_user_id:
            current_user_conn = client_data['conn']
            break

    if not current_user_conn:
        logger.error(f"Не найдено активное соединение для user_id {current_user_id} при отправке списка чатов.")
        return

    send_json_message_func(current_user_conn, {
        "type": "chat_list_response",
        "payload": {"chats": user_chats}
    })


# --- Модифицированная функция для запроса истории ---
def process_request_chat_history(db_conn, payload, current_user_id, active_clients, send_json_message_func, logger):
    """Обрабатывает запрос на получение истории чата по chat_id."""
    chat_id_to_request = payload.get("chat_id")  # Теперь ожидаем chat_id

    current_user_conn = None  # Аналогично предыдущей функции, ищем conn
    for username, client_data in active_clients.items():
        if client_data['user_id'] == current_user_id:
            current_user_conn = client_data['conn']
            break
    if not current_user_conn: return

    if chat_id_to_request is None:  # Проверяем, что chat_id передан
        logger.warning(f"Запрос истории от user_id {current_user_id} без указания chat_id.")
        send_json_message_func(current_user_conn, {"type": "error_notification",
                                                   "payload": {"message": "Не указан ID чата для запроса истории."}})
        return

    # TODO: Проверка, имеет ли current_user_id доступ к этому chat_id (является ли участником)
    # Это важный аспект безопасности, который нужно будет добавить.
    # Пока предполагаем, что клиент запрашивает только свои чаты.

    logger.info(f"User_id {current_user_id} запросил историю для чата ID {chat_id_to_request}.")
    history_messages = db_handler.get_chat_history_from_db(db_conn, chat_id_to_request, limit=50, logger=logger)

    send_json_message_func(current_user_conn, {
        "type": "chat_history",
        "payload": {
            "chat_id": chat_id_to_request,  # Возвращаем chat_id, для которого история
            "messages": history_messages
        }
    })


# --- Новая/модифицированная функция для отправки сообщения в чат ---
def process_send_message_to_chat(db_conn, payload, current_username, current_user_id, active_clients, clients_lock,
                                 send_json_message_func, logger):
    """Обрабатывает отправку сообщения в указанный chat_id."""
    target_chat_id = payload.get("chat_id")
    text = payload.get("text")

    # Получаем соединение текущего пользователя (отправителя) для возможной отправки ему ошибок/уведомлений
    # Предполагаем, что current_username есть в active_clients, так как он аутентифицирован
    sender_conn = None
    if current_username in active_clients:  # Проверка на случай, если ключ username
        sender_conn = active_clients[current_username]['conn']
    else:  # Если active_clients индексируется по user_id или другая структура
        # Нужно будет найти sender_conn другим способом, если current_username не ключ
        # Например, если бы мы передавали conn отправителя напрямую:
        # sender_conn = current_user_conn
        logger.error(
            f"Не найдено соединение для отправителя {current_username} в active_clients. Невозможно отправить ответ/ошибку.")
        # В этом случае, если sender_conn не найден, отправка ошибок отправителю не сработает.
        # Для текущей структуры active_clients = {username: {'conn': ..., 'user_id': ...}} это должно работать.

    if target_chat_id is None or not text:
        logger.warning(f"Некорректное сообщение от {current_username}: отсутствует chat_id или текст.")
        if sender_conn: send_json_message_func(sender_conn, {"type": "error_notification", "payload": {
            "message": "Некорректный формат сообщения: отсутствует ID чата или текст."}})
        return

    try:
        target_chat_id = int(target_chat_id)
    except ValueError:
        logger.warning(f"Некорректный chat_id '{target_chat_id}' от {current_username}.")
        if sender_conn: send_json_message_func(sender_conn, {"type": "error_notification",
                                                             "payload": {"message": "Некорректный ID чата."}})
        return

    is_member = False
    try:
        with db_conn.cursor() as cur:
            cur.execute("SELECT 1 FROM chat_members WHERE chat_id = %s AND user_id = %s",
                        (target_chat_id, current_user_id))
            if cur.fetchone():
                is_member = True
    except psycopg2.Error as e:  # psycopg2 должен быть импортирован в этом файле
        logger.error(f"Ошибка проверки членства пользователя {current_user_id} в чате {target_chat_id}: {e}")
        if sender_conn: send_json_message_func(sender_conn, {"type": "error_notification", "payload": {
            "message": "Ошибка сервера при проверке чата."}})
        return

    if not is_member:
        logger.warning(
            f"Пользователь {current_username} (ID: {current_user_id}) попытался отправить сообщение в чат {target_chat_id}, не являясь участником.")
        if sender_conn: send_json_message_func(sender_conn, {"type": "error_notification", "payload": {
            "message": "Вы не являетесь участником этого чата."}})
        return

    saved_message_data = db_handler.save_message_to_db(db_conn, target_chat_id, current_user_id, 'text', text, logger)

    if not saved_message_data:
        logger.error(f"Сообщение от {current_username} в чат {target_chat_id} не было сохранено в БД.")
        if sender_conn: send_json_message_func(sender_conn, {"type": "error_notification", "payload": {
            "message": "Ошибка сервера: сообщение не сохранено."}})
        return

    saved_message_id = saved_message_data["message_id"]
    message_timestamp = saved_message_data["timestamp"]  # Это строка ISO формата из db_handler
    logger.info(f"Сообщение (ID: {saved_message_id}) от {current_username} в чат {target_chat_id} сохранено.")

    chat_participants_ids = []
    try:
        with db_conn.cursor() as cur:
            # Выбираем всех участников чата, КРОМЕ отправителя, для рассылки
            cur.execute("SELECT user_id FROM chat_members WHERE chat_id = %s AND user_id != %s",
                        (target_chat_id, current_user_id))
            for row in cur.fetchall():
                chat_participants_ids.append(row[0])
    except psycopg2.Error as e:
        logger.error(f"Ошибка получения участников чата {target_chat_id} для рассылки: {e}")
        # Сообщение сохранено, но доставить не сможем (или сможем не всем)

    logger.debug(
        f"Участники чата {target_chat_id} для рассылки (кроме {current_user_id} - {current_username}): {chat_participants_ids}")

    # Рассылаем сообщение всем ОНЛАЙН участникам чата
    # Мы не можем напрямую итерировать и изменять active_clients под блокировкой,
    # поэтому сначала соберем информацию о тех, кому нужно отправить.
    # Но для простого чтения и отправки итерация под блокировкой допустима.
    with clients_lock:
        for other_username, client_data_receiver in active_clients.items():
            # Проверяем, есть ли 'user_id' в client_data и совпадает ли он с одним из участников
            if client_data_receiver.get('user_id') in chat_participants_ids:
                logger.info(
                    f"Доставка сообщения (ID: {saved_message_id}) от {current_username} участнику {other_username} (ID: {client_data_receiver['user_id']}) чата {target_chat_id}.")
                send_json_message_func(client_data_receiver['conn'], {
                    "type": "incoming_chat_message",
                    "payload": {
                        "chat_id": target_chat_id,
                        "message_id": saved_message_id,
                        "sender_username": current_username,
                        "sender_id": current_user_id,
                        "text": text,
                        "timestamp": message_timestamp
                    }
                })