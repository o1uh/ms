# server/db_handler.py
import psycopg2
import os # Для доступа к переменным окружения, если захотите
# Можно импортировать логгер, если он нужен внутри этих функций напрямую
# Но лучше, чтобы вызывающий код передавал логгер или обрабатывал логирование
# Для простоты пока оставим server_logger как глобальный или передаваемый

# Предположим, что server_logger будет импортирован из main_server или настроен здесь
# Это нужно будет решить. Пока что, для функций, где он используется,
# я закомментирую его или предположу, что он доступен.
# import sys
# sys.path.append(os.path.dirname(__file__)) # Если logger.py в той же папке
# from logger import setup_logger
# db_logger = setup_logger('DBHandler', 'db_handler_run') # Пример

# --- Конфигурация БД ---
# Лучше вынести в конфигурационный файл или переменные окружения в будущем
DB_NAME = os.environ.get("DB_NAME", "mas_db")
DB_USER = os.environ.get("DB_USER", "admin")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "admin") # ЗАМЕНИТЕ НА ВАШ ПАРОЛЬ ИЛИ ИСПОЛЬЗУЙТЕ ENV
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = os.environ.get("DB_PORT", "5432")


def get_db_connection(logger): # Теперь логгер передается
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
    """Сохраняет сообщение в БД."""
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO messages (chat_id, sender_id, content_type, content) VALUES (%s, %s, %s, %s) RETURNING message_id, sent_at",
                (chat_id, sender_id, content_type, content)
            )
            message_info = cur.fetchone()
            conn.commit()
            if message_info:
                logger.info(f"Сообщение ID: {message_info[0]} от user_id: {sender_id} в chat_id: {chat_id} сохранено в БД ({message_info[1]}).")
                return message_info[0]
        return None
    except psycopg2.Error as e:
        conn.rollback()
        logger.error(f"Ошибка при сохранении сообщения в БД (chat_id: {chat_id}, sender_id: {sender_id}): {e}", exc_info=True)
        return None