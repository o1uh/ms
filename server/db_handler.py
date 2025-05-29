import psycopg2
from datetime import datetime, timezone
import os
# import sys
# sys.path.append(os.path.dirname(__file__)) # Если logger.py в той же папке
# from logger import setup_logger
# db_logger = setup_logger('DBHandler', 'db_handler_run') # Пример

# --- Конфигурация БД ---
DB_NAME = os.environ.get("DB_NAME", "mas_db")
DB_USER = os.environ.get("DB_USER", "admin")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "admin")
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = os.environ.get("DB_PORT", "5432")


def get_db_connection(logger):
    """Устанавливает и возвращает соединение с БД."""
    try:
        conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD, host=DB_HOST, port=DB_PORT)
        logger.info("Успешное подключение к базе данных PostgreSQL.")
        return conn
    except psycopg2.Error as e:
        logger.critical(f"Ошибка подключения к PostgreSQL: {e}", exc_info=True)
        return None

def create_user_in_db(conn, username, password_hash, salt, logger):
    """Создает нового пользователя в БД."""
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (username, password_hash, salt) VALUES (%s, %s, %s) RETURNING user_id",
                (username, password_hash, salt)
            )
            user_id = cur.fetchone()[0]
            conn.commit()
            logger.info(f"Пользователь '{username}' (ID: {user_id}) успешно создан в БД.")
            return user_id
    except psycopg2.Error as e:
        conn.rollback()
        logger.error(f"Ошибка при создании пользователя '{username}' в БД: {e}", exc_info=True)
        if hasattr(e, 'pgcode') and e.pgcode == '23505': # Код ошибки для нарушения уникальности
            return "username_exists"
        return None

def get_user_from_db(conn, username, logger):
    """Получает данные пользователя из БД по имени пользователя."""
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT user_id, username, password_hash, salt FROM users WHERE username = %s", (username,))
            user_data = cur.fetchone()
            if user_data:
                return {"user_id": user_data[0], "username": user_data[1], "password_hash": user_data[2], "salt": user_data[3]}
        return None
    except psycopg2.Error as e:
        logger.error(f"Ошибка при получении пользователя '{username}' из БД: {e}", exc_info=True)
        return None

def get_or_create_direct_chat(conn, user1_id, user2_id, logger):
    """Находит существующий личный чат или создает новый. Возвращает chat_id."""
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT cm1.chat_id
                FROM chat_members cm1
                JOIN chat_members cm2 ON cm1.chat_id = cm2.chat_id
                JOIN chats ch ON cm1.chat_id = ch.chat_id
                WHERE cm1.user_id = %s AND cm2.user_id = %s AND ch.chat_type = 'direct'
                LIMIT 1;
            """, (user1_id, user2_id))
            chat = cur.fetchone()

            if chat:
                logger.debug(f"Найден существующий direct чат ID: {chat[0]} для пользователей {user1_id} и {user2_id}")
                return chat[0]
            else:
                logger.info(f"Создание нового direct чата для пользователей {user1_id} и {user2_id}")
                cur.execute(
                    "INSERT INTO chats (chat_type, creator_id) VALUES (%s, %s) RETURNING chat_id",
                    ('direct', user1_id)
                )
                new_chat_id = cur.fetchone()[0]
                cur.execute(
                    "INSERT INTO chat_members (chat_id, user_id) VALUES (%s, %s), (%s, %s)",
                    (new_chat_id, user1_id, new_chat_id, user2_id)
                )
                conn.commit()
                logger.info(f"Новый direct чат ID: {new_chat_id} создан, участники добавлены.")
                return new_chat_id
    except psycopg2.Error as e:
        conn.rollback()
        logger.error(f"Ошибка при получении/создании direct чата для {user1_id}, {user2_id}: {e}", exc_info=True)
        return None


def save_message_to_db(conn, chat_id, sender_id, content_type, content, logger):
    message_id_result = None
    timestamp_result_iso = None
    try:
        current_utc_time = datetime.now(timezone.utc)
        with conn.cursor() as cur:
            # 1. Вставляем сообщение
            logger.debug(
                f"Попытка INSERT сообщения: chat_id={chat_id}, sender_id={sender_id}, content='{content[:20]}...'")
            cur.execute(
                "INSERT INTO messages (chat_id, sender_id, content_type, content, sent_at) VALUES (%s, %s, %s, %s, %s) RETURNING message_id, sent_at",
                (chat_id, sender_id, content_type, content, current_utc_time)
            )
            message_info = cur.fetchone()

            if message_info:
                message_id_result = message_info[0]
                db_assigned_sent_at = message_info[1]
                timestamp_result_iso = db_assigned_sent_at.isoformat()
                logger.debug(f"Сообщение вставлено, ID: {message_id_result}, Время БД: {timestamp_result_iso}")

                # 2. Обновляем last_message_at в таблице chats
                logger.debug(f"Попытка UPDATE chats: chat_id={chat_id}, last_message_at={timestamp_result_iso}")
                cur.execute(
                    "UPDATE chats SET last_message_at = %s WHERE chat_id = %s",
                    (db_assigned_sent_at, chat_id)
                )
                # Если мы дошли сюда без ошибок, можно коммитить
                conn.commit()
                logger.info(
                    f"Сообщение ID: {message_id_result} от user_id: {sender_id} в chat_id: {chat_id} сохранено, last_message_at обновлено ({timestamp_result_iso}).")
                return {"message_id": message_id_result, "timestamp": timestamp_result_iso}
            else:
                # Этого не должно произойти, если RETURNING что-то вернул, но на всякий случай
                logger.error(f"INSERT сообщения не вернул message_info для chat_id: {chat_id}, sender_id: {sender_id}")
                conn.rollback()  # Откатываем, если что-то пошло не так до коммита
                return None

    except psycopg2.Error as e:
        logger.error(f"Psycopg2 ошибка в save_message_to_db (chat_id: {chat_id}, sender_id: {sender_id}): {e}",
                     exc_info=True)
        if conn:  # Проверяем, что conn не None
            try:
                conn.rollback()
            except psycopg2.Error as rb_e:
                logger.error(f"Ошибка при откате транзакции: {rb_e}")
        return None
    except Exception as e:  # Ловим другие возможные ошибки
        logger.error(f"Общая ошибка в save_message_to_db (chat_id: {chat_id}, sender_id: {sender_id}): {e}",
                     exc_info=True)
        if conn:
            try:
                conn.rollback()
            except psycopg2.Error as rb_e:
                logger.error(f"Ошибка при откате транзакции: {rb_e}")
        return None

def get_user_chats(conn, user_id, logger):
    """Получает список чатов, в которых участвует пользователь."""
    chats_info = []
    try:
        with conn.cursor() as cur:
            # Выбираем чаты, в которых состоит пользователь
            # Для каждого чата определяем его тип и других участников (для direct)
            # или название (для group)
            # Также получаем последнее сообщение и его время
            cur.execute("""
                SELECT
                    c.chat_id,
                    c.chat_type,
                    c.chat_name, 
                    c.last_message_at,
                    (SELECT m.content FROM messages m WHERE m.chat_id = c.chat_id ORDER BY m.sent_at DESC LIMIT 1) as last_message_text,
                    -- Для direct чатов находим другого участника
                    (CASE
                        WHEN c.chat_type = 'direct' THEN (
                            SELECT u.user_id 
                            FROM chat_members cm_other
                            JOIN users u ON cm_other.user_id = u.user_id
                            WHERE cm_other.chat_id = c.chat_id AND cm_other.user_id != %s
                            LIMIT 1
                        )
                        ELSE NULL
                    END) as other_user_id,
                    (CASE
                        WHEN c.chat_type = 'direct' THEN (
                            SELECT u.username 
                            FROM chat_members cm_other
                            JOIN users u ON cm_other.user_id = u.user_id
                            WHERE cm_other.chat_id = c.chat_id AND cm_other.user_id != %s
                            LIMIT 1
                        )
                        ELSE NULL
                    END) as other_username
                FROM chats c
                JOIN chat_members cm_user ON c.chat_id = cm_user.chat_id
                WHERE cm_user.user_id = %s
                ORDER BY c.last_message_at DESC NULLS LAST, c.created_at DESC; 
            """, (user_id, user_id, user_id)) # user_id передается три раза для подзапросов

            raw_chats = cur.fetchall()
            for row in raw_chats:
                chat_name_from_db = row[2]  # Исходное имя чата из БД (может быть NULL для direct)
                chat_type = row[1]
                other_username_val = row[6]

                chat_name_to_display = chat_name_from_db
                if chat_type == 'direct' and other_username_val:
                    chat_name_to_display = other_username_val

                chats_info.append({
                    "chat_id": row[0],
                    "chat_type": chat_type,
                    "chat_name": chat_name_to_display,  # Имя для отображения
                    "last_message_at": row[3].isoformat() if row[3] else None,
                    "last_message_text": row[4] if row[4] else "Нет сообщений",
                    "other_user_id": row[5] if chat_type == 'direct' else None,
                    "other_username": other_username_val if chat_type == 'direct' else None,
                    "unread_count": 0
                })
            logger.debug(f"Для user_id {user_id} найдено {len(chats_info)} чатов.")
    except psycopg2.Error as e:
        logger.error(f"Ошибка при получении списка чатов для user_id {user_id}: {e}", exc_info=True)
    return chats_info


def get_chat_history_from_db(conn, chat_id, limit=50, logger=None):  # limit - сколько сообщений загружать
    """Получает последние 'limit' сообщений для указанного chat_id."""
    # Эта функция уже была почти готова, убедимся, что она соответствует
    messages = []
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT m.message_id, u.username AS sender_username, m.sender_id, m.content, m.sent_at
                FROM messages m
                JOIN users u ON m.sender_id = u.user_id
                WHERE m.chat_id = %s AND m.is_deleted = FALSE
                ORDER BY m.sent_at ASC, m.message_id ASC 
                LIMIT %s; 
            """, (chat_id, limit))

            raw_messages = cur.fetchall()
            for row in raw_messages:
                messages.append({
                    "message_id": row[0],
                    "sender_username": row[1],
                    "sender_id": row[2],  # Добавили sender_id
                    "text": row[3],
                    "timestamp": row[4].isoformat()
                })
            if logger:
                logger.debug(f"Извлечено {len(messages)} сообщений для chat_id: {chat_id}")
    except psycopg2.Error as e:
        if logger:
            logger.error(f"Ошибка при получении истории чата {chat_id} из БД: {e}", exc_info=True)
    return messages


def create_group_chat_in_db(conn, group_name, creator_id, member_user_ids, logger):
    """Создает новый групповой чат и добавляет участников."""
    try:
        with conn.cursor() as cur:
            # 1. Создаем запись в таблице chats
            cur.execute(
                "INSERT INTO chats (chat_type, chat_name, creator_id) VALUES (%s, %s, %s) RETURNING chat_id",
                ('group', group_name, creator_id)
            )
            new_chat_id = cur.fetchone()[0]
            logger.info(f"Создан групповой чат '{group_name}' с ID: {new_chat_id} от создателя ID: {creator_id}")

            # 2. Добавляем создателя как админа
            cur.execute(
                "INSERT INTO chat_members (chat_id, user_id, role) VALUES (%s, %s, %s)",
                (new_chat_id, creator_id, 'admin')
            )
            logger.info(f"Создатель ID: {creator_id} добавлен в чат {new_chat_id} как админ.")

            # 3. Добавляем остальных участников как мемберов
            if member_user_ids:
                # Подготавливаем данные для executemany: список кортежей [(chat_id, user_id, role), ...]
                member_values = [(new_chat_id, member_id, 'member') for member_id in member_user_ids if
                                 member_id != creator_id]  # Убедимся, что создателя не добавляем дважды
                if member_values:  # Если есть кого добавлять
                    for member_id in member_user_ids:
                        if member_id == creator_id: continue  # Пропускаем создателя
                        try:
                            cur.execute(
                                "INSERT INTO chat_members (chat_id, user_id, role) VALUES (%s, %s, %s)",
                                (new_chat_id, member_id, 'member')
                            )
                            logger.info(f"Участник ID: {member_id} добавлен в чат {new_chat_id} как мембер.")
                        except psycopg2.Error as e_member:  # Например, если такой участник уже есть (нарушение UNIQUE)
                            logger.warning(
                                f"Не удалось добавить участника ID: {member_id} в чат {new_chat_id}: {e_member}")
                            # Продолжаем добавлять остальных

            conn.commit()
            return new_chat_id
    except psycopg2.Error as e:
        conn.rollback()
        logger.error(f"Ошибка при создании группового чата '{group_name}': {e}", exc_info=True)
        return None
