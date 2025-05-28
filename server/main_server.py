# server/main_server.py
import socket
import threading
import json
import sys
import os

# --- Настройка путей и импортов ---
# Добавляем путь к корневой папке проекта, чтобы найти logger.py
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from logger import setup_logger

# Импортируем наши новые модули
from server import db_handler
from server import auth_handler
from server import message_handler

# --- Настройка логгера ---
server_logger = setup_logger('ServerApp', 'server_run')

# --- Глобальные переменные ---
HOST = os.environ.get("SERVER_HOST", '127.0.0.1')
PORT = int(os.environ.get("SERVER_PORT", 65432))
server_running = True
# {username: {'conn': connection_object, 'user_id': db_user_id, 'addr': address_tuple}}
active_clients = {}
clients_lock = threading.Lock()


# --- Вспомогательная функция для отправки JSON (остается здесь) ---
def send_json_message(conn, message_data):
    """Отправляет JSON-сообщение клиенту, добавляя разделитель."""
    try:
        # Используем ensure_ascii=False для корректной отправки кириллицы без \uXXXX
        json_message = json.dumps(message_data, ensure_ascii=False) + '\n'
        conn.sendall(json_message.encode('utf-8'))
        # Для лога можно использовать peername, если conn еще жив
        # server_logger.debug(f"Отправлено {conn.getpeername()}: {json_message.strip()}")
    except Exception as e:
        # server_logger.error(f"Ошибка отправки сообщения {conn.getpeername()}: {e}", exc_info=True)
        # Если conn уже закрыт, getpeername() вызовет ошибку. Логируем осторожно.
        server_logger.error(f"Ошибка отправки сообщения: {e}", exc_info=True)


# --- Основной обработчик клиента ---
def handle_client(conn, addr):
    server_logger.info(f"Новое подключение от {addr}")
    current_username = None
    current_user_id = None
    client_buffer = ""

    db_conn = db_handler.get_db_connection(server_logger)
    if not db_conn:
        server_logger.error(f"Не удалось получить соединение с БД для клиента {addr}. Закрытие соединения.")
        if conn:
            try:
                conn.close()
            except Exception as e_conn_close:
                server_logger.error(f"Ошибка при закрытии conn после неудачного подключения к БД: {e_conn_close}")
        return

    try:
        authenticated = False
        auth_attempts = 0
        MAX_AUTH_ATTEMPTS = 5

        while server_running and not authenticated and auth_attempts < MAX_AUTH_ATTEMPTS:
            auth_attempts += 1
            try:
                data = conn.recv(1024)
                if not data:
                    server_logger.info(f"Клиент {addr} отключился до аутентификации.")
                    break

                client_buffer += data.decode('utf-8')

                while '\n' in client_buffer:
                    message_str, client_buffer = client_buffer.split('\n', 1)
                    server_logger.debug(f"Получено от {addr} (аутентификация): {message_str}")

                    try:
                        message_data = json.loads(message_str)
                        msg_type = message_data.get("type")
                        payload = message_data.get("payload", {})

                        if msg_type == "register":
                            username = payload.get("username")
                            password = payload.get("password")

                            if not username or not password:
                                send_json_message(conn, {"type": "register_status", "payload": {"status": "error",
                                                                                                "message": "Имя пользователя и пароль не могут быть пустыми."}})
                                continue
                            if len(password) < 4:  # Простая валидация
                                send_json_message(conn, {"type": "register_status", "payload": {"status": "error",
                                                                                                "message": "Пароль должен быть не менее 4 символов."}})
                                continue

                            existing_user = db_handler.get_user_from_db(db_conn, username, server_logger)
                            if existing_user:
                                send_json_message(conn, {"type": "register_status", "payload": {"status": "error",
                                                                                                "message": f"Имя пользователя '{username}' уже занято."}})
                            else:
                                salt = auth_handler.generate_salt()
                                password_hash = auth_handler.hash_password(password, salt)
                                reg_user_id = db_handler.create_user_in_db(db_conn, username, password_hash, salt,
                                                                           server_logger)

                                if reg_user_id and reg_user_id != "username_exists":
                                    send_json_message(conn, {"type": "register_status", "payload": {"status": "success",
                                                                                                    "message": f"Пользователь '{username}' успешно зарегистрирован. Теперь вы можете войти."}})
                                else:
                                    send_json_message(conn, {"type": "register_status", "payload": {"status": "error",
                                                                                                    "message": "Ошибка при регистрации пользователя."}})

                        elif msg_type == "login":
                            username = payload.get("username")
                            password = payload.get("password")

                            if not username or not password:
                                send_json_message(conn, {"type": "login_status", "payload": {"status": "error",
                                                                                             "message": "Имя пользователя и пароль не могут быть пустыми."}})
                                continue

                            db_user_data = db_handler.get_user_from_db(db_conn, username, server_logger)
                            if db_user_data and auth_handler.verify_password(db_user_data["password_hash"],
                                                                             db_user_data["salt"], password):
                                with clients_lock:
                                    if username in active_clients:
                                        send_json_message(conn, {"type": "login_status", "payload": {"status": "error",
                                                                                                     "message": f"Пользователь '{username}' уже в сети."}})
                                    else:
                                        current_username = db_user_data["username"]
                                        current_user_id = db_user_data["user_id"]
                                        active_clients[current_username] = {'conn': conn, 'user_id': current_user_id,
                                                                            'addr': addr}
                                        authenticated = True
                                        server_logger.info(
                                            f"Клиент {addr} аутентифицирован как {current_username} (ID: {current_user_id})")
                                        send_json_message(conn, {"type": "login_status",
                                                                 "payload": {"status": "success",
                                                                             "message": "Успешный вход.",
                                                                             "username": current_username,
                                                                             "user_id": current_user_id}})
                            else:
                                server_logger.warning(
                                    f"Неудачная попытка входа для пользователя '{username}' от {addr}")
                                send_json_message(conn, {"type": "login_status", "payload": {"status": "error",
                                                                                             "message": "Неверное имя пользователя или пароль."}})

                        else:
                            server_logger.warning(f"Получено сообщение типа '{msg_type}' от {addr} до аутентификации.")
                            send_json_message(conn, {"type": "error_notification",
                                                     "payload": {"message": "Ожидалась регистрация или вход."}})

                        if authenticated: break

                    except json.JSONDecodeError:
                        server_logger.error(f"Ошибка декодирования JSON от {addr}: {message_str}", exc_info=True)
                        send_json_message(conn, {"type": "error_notification",
                                                 "payload": {"message": "Ошибка формата JSON."}})
                    except Exception as e:
                        server_logger.error(f"Ошибка при обработке сообщения аутентификации от {addr}: {e}",
                                            exc_info=True)
                        send_json_message(conn, {"type": "error_notification",
                                                 "payload": {"message": "Внутренняя ошибка сервера."}})

                if authenticated or not data: break

            except ConnectionResetError:
                server_logger.warning(f"Соединение сброшено клиентом {addr} (аутентификация).")
                break  # Выход из цикла while server_running and not authenticated...
            except Exception as e:
                server_logger.error(f"Ошибка чтения от {addr} (аутентификация): {e}", exc_info=True)
                break  # Выход из цикла

        if not authenticated:
            server_logger.info(
                f"Клиент {addr} не прошел аутентификацию после {auth_attempts} попыток. Закрытие соединения.")
            # db_conn и conn закроются в finally
            return

            # Сразу после успешной аутентификации, отправляем клиенту список его чатов
        message_handler.process_request_chat_list(
            db_conn, current_user_id, active_clients, send_json_message, server_logger
        )

        client_buffer = ""
        while server_running:
            try:
                data = conn.recv(1024)
                if not data:
                    server_logger.info(f"Клиент {current_username} ({addr}) отключился.")
                    break

                client_buffer += data.decode('utf-8')

                while '\n' in client_buffer:
                    message_str, client_buffer = client_buffer.split('\n', 1)
                    server_logger.debug(f"Получено от {current_username} ({addr}): {message_str}")

                    try:
                        message_data = json.loads(message_str)
                        msg_type = message_data.get("type")
                        payload = message_data.get("payload", {})

                        if msg_type == "send_message_to_chat":
                            message_handler.process_send_message_to_chat(
                                db_conn, payload, current_username, current_user_id,
                                active_clients, clients_lock, send_json_message, server_logger
                            )
                        elif msg_type == "request_chat_history":
                            message_handler.process_request_chat_history(
                                db_conn, payload, current_user_id,
                                active_clients,  # Передаем active_clients
                                send_json_message,
                                server_logger
                            )
                        elif msg_type == "request_chat_list":  # Повторный запрос списка чатов
                            message_handler.process_request_chat_list(
                                db_conn, current_user_id, active_clients, send_json_message, server_logger
                            )
                        else:
                            server_logger.warning(
                                f"Получено сообщение неизвестного типа '{msg_type}' от {current_username}.")
                            send_json_message(conn, {"type": "error_notification",
                                                     "payload": {"message": f"Неизвестный тип сообщения: {msg_type}"}})

                    except json.JSONDecodeError:
                        server_logger.error(f"Ошибка декодирования JSON от {current_username}: {message_str}",
                                            exc_info=True)
                        send_json_message(conn, {"type": "error_notification",
                                                 "payload": {"message": "Ошибка формата JSON."}})
                    except Exception as e:
                        server_logger.error(f"Ошибка при обработке сообщения от {current_username}: {e}", exc_info=True)
                        send_json_message(conn, {"type": "error_notification",
                                                 "payload": {"message": "Внутренняя ошибка сервера."}})

            except ConnectionResetError:
                server_logger.warning(f"Соединение сброшено клиентом {current_username} ({addr}).")
                break  # Выход из основного цикла while server_running
            except Exception as e:
                server_logger.error(f"Ошибка чтения от {current_username} ({addr}): {e}", exc_info=True)
                break  # Выход из основного цикла

    except Exception as e:
        server_logger.critical(
            f"Неперехваченная критическая ошибка в обработчике клиента {addr} (пользователь: {current_username}): {e}",
            exc_info=True)
    finally:
        if current_username:
            with clients_lock:
                # Проверяем, что удаляем именно это соединение, если вдруг пользователь переподключился быстро
                if current_username in active_clients and active_clients[current_username]['conn'] == conn:
                    del active_clients[current_username]
            server_logger.info(f"Клиент {current_username} ({addr}) удален из активных.")

        if db_conn:
            try:
                db_conn.close()
                server_logger.debug(f"Соединение с БД для {addr} (пользователь: {current_username}) закрыто.")
            except Exception as e_db_close:
                server_logger.error(f"Ошибка при закрытии соединения с БД для {addr}: {e_db_close}")

        if conn:
            try:
                conn.close()
            except Exception as e_conn_close:
                server_logger.error(f"Ошибка при закрытии сокета для {addr}: {e_conn_close}")
        server_logger.debug(f"Ресурсы для {addr} (пользователь: {current_username}) освобождены.")


# --- Функция запуска сервера (остается почти такой же) ---
def run_server():
    global server_running
    # Создаем слушающий сокет один раз при запуске сервера
    listening_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listening_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        listening_socket.bind((HOST, PORT))
        listening_socket.listen()
        server_logger.info(f"Сервер запущен и слушает на {HOST}:{PORT}")
        server_logger.info("Для остановки сервера нажмите Ctrl+C в этой консоли.")

        listening_socket.settimeout(1.0)

        while server_running:
            try:
                conn, addr = listening_socket.accept()
                client_thread = threading.Thread(target=handle_client, args=(conn, addr))
                client_thread.daemon = True
                client_thread.start()
            except socket.timeout:
                continue  # Просто проверяем server_running и снова ждем
            except Exception as e:  # Любая другая ошибка при accept
                if server_running:
                    server_logger.error(f"Ошибка на сервере при принятии соединения: {e}", exc_info=True)
                break
    except OSError as e:
        server_logger.critical(f"Критическая ошибка при запуске сервера (порт {PORT} может быть занят): {e}",
                               exc_info=True)
    except KeyboardInterrupt:
        server_logger.info("Получен сигнал KeyboardInterrupt (Ctrl+C)...")
    finally:
        server_running = False  # Сигнал всем потокам handle_client завершаться
        server_logger.info("Сервер останавливается...")

        # Даем немного времени потокам завершиться. В идеале - join для каждого потока.
        # Но это усложнит управление списком потоков.
        # threading.enumerate() может помочь, но нужно аккуратно.
        # Пока оставим так, потоки-демоны должны завершиться.

        listening_socket.close()  # Закрываем слушающий сокет
        server_logger.info("Сервер полностью остановлен.")


if __name__ == '__main__':
    server_logger.info("Запуск серверного приложения...")
    run_server()