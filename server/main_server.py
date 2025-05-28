# server/main_server.py
import socket
import threading
import json  # Для работы с JSON
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from logger import setup_logger  # Используем ваше имя файла logger.py

server_logger = setup_logger('ServerApp', 'server_run')

HOST = '127.0.0.1'
PORT = 65432
server_running = True

# Словарь для хранения активных клиентов: {username: connection_object}
active_clients = {}
# Блокировка для синхронизации доступа к active_clients из разных потоков
clients_lock = threading.Lock()


def send_message(conn, message_data):
    """Отправляет JSON-сообщение клиенту, добавляя разделитель."""
    try:
        json_message = json.dumps(message_data) + '\n'
        conn.sendall(json_message.encode('utf-8'))
        server_logger.debug(f"Отправлено {conn.getpeername()}: {json_message.strip()}")
    except Exception as e:
        server_logger.error(f"Ошибка отправки сообщения {conn.getpeername()}: {e}", exc_info=True)


def handle_client(conn, addr):
    """Обрабатывает соединение с клиентом в отдельном потоке."""
    server_logger.info(f"Новое подключение от {addr}")
    current_username = None
    client_buffer = ""  # Буфер для накопления данных от клиента

    try:
        # 1. Ожидание сообщения "login"
        # Мы будем читать данные в цикле, пока не получим полное сообщение
        # или пока клиент не отвалится
        login_successful = False
        while server_running and not login_successful:
            try:
                # Читаем небольшой кусок данных
                data = conn.recv(1024)
                if not data:
                    server_logger.info(f"Клиент {addr} отключился до логина.")
                    break  # Клиент отключился

                client_buffer += data.decode('utf-8')

                # Ищем разделитель \n
                while '\n' in client_buffer:
                    message_str, client_buffer = client_buffer.split('\n', 1)
                    server_logger.debug(f"Получено от {addr} (до логина, сырое): {message_str}")

                    try:
                        message_data = json.loads(message_str)
                        msg_type = message_data.get("type")
                        payload = message_data.get("payload", {})

                        if msg_type == "login":
                            username_attempt = payload.get("username")
                            if username_attempt:
                                with clients_lock:
                                    if username_attempt not in active_clients:
                                        current_username = username_attempt
                                        active_clients[current_username] = conn
                                        login_successful = True
                                        server_logger.info(f"Клиент {addr} залогинился как {current_username}")
                                        send_message(conn, {"type": "login_status", "payload": {"status": "success",
                                                                                                "message": "Успешный вход.",
                                                                                                "username": current_username}})
                                    else:
                                        server_logger.warning(
                                            f"Попытка логина с занятым именем {username_attempt} от {addr}")
                                        send_message(conn, {"type": "login_status", "payload": {"status": "error",
                                                                                                "message": f"Имя пользователя '{username_attempt}' уже занято."}})
                                        # Не закрываем соединение сразу, даем клиенту шанс попробовать другое имя (пока не реализовано)
                                        # Для v0.1 можно просто закрыть соединение после ошибки, если хотите
                                        # conn.close() # <-- если хотите закрывать
                                        # break # <-- если хотите закрывать
                            else:
                                server_logger.warning(f"Некорректный формат логина от {addr}: отсутствует username")
                                send_message(conn, {"type": "error_notification", "payload": {
                                    "message": "Некорректный формат логина: отсутствует username."}})
                        else:
                            server_logger.warning(
                                f"Получено сообщение неизвестного типа {msg_type} от {addr} до логина.")
                            send_message(conn,
                                         {"type": "error_notification", "payload": {"message": "Ожидался логин."}})

                        if login_successful:  # Выходим из цикла while '\n' in client_buffer
                            break
                    except json.JSONDecodeError:
                        server_logger.error(f"Ошибка декодирования JSON от {addr}: {message_str}", exc_info=True)
                        send_message(conn,
                                     {"type": "error_notification", "payload": {"message": "Ошибка формата JSON."}})
                    except Exception as e:
                        server_logger.error(f"Неизвестная ошибка при обработке сообщения до логина от {addr}: {e}",
                                            exc_info=True)
                        send_message(conn, {"type": "error_notification",
                                            "payload": {"message": "Внутренняя ошибка сервера."}})

                if login_successful or not data:  # Выходим из цикла while server_running
                    break

            except ConnectionResetError:  # Клиент резко оборвал соединение
                server_logger.warning(f"Соединение сброшено клиентом {addr} (до логина).")
                break
            except Exception as e:
                server_logger.error(f"Ошибка чтения от {addr} (до логина): {e}", exc_info=True)
                break

        if not login_successful:  # Если так и не залогинился
            return  # Просто завершаем обработку этого клиента

        # 2. Цикл обработки сообщений от залогиненного клиента
        client_buffer = ""  # Сбрасываем буфер после логина
        while server_running:
            try:
                data = conn.recv(1024)
                if not data:
                    server_logger.info(f"Клиент {current_username} ({addr}) отключился.")
                    break  # Клиент отключился

                client_buffer += data.decode('utf-8')

                while '\n' in client_buffer:
                    message_str, client_buffer = client_buffer.split('\n', 1)
                    server_logger.debug(f"Получено от {current_username} ({addr}): {message_str}")

                    try:
                        message_data = json.loads(message_str)
                        msg_type = message_data.get("type")
                        payload = message_data.get("payload", {})

                        if msg_type == "private_message":
                            recipient = payload.get("recipient")
                            text = payload.get("text")

                            if recipient and text:
                                with clients_lock:  # Блокируем доступ к словарю клиентов
                                    recipient_conn = active_clients.get(recipient)

                                if recipient_conn:
                                    server_logger.info(
                                        f"Пересылка сообщения от {current_username} к {recipient}: {text}")
                                    send_message(recipient_conn, {
                                        "type": "incoming_message",
                                        "payload": {
                                            "sender": current_username,
                                            "text": text
                                        }
                                    })
                                else:
                                    server_logger.warning(
                                        f"Получатель {recipient} не найден или оффлайн (сообщение от {current_username}).")
                                    send_message(conn, {"type": "error_notification", "payload": {
                                        "message": f"Пользователь '{recipient}' не найден или оффлайн."}})
                            else:
                                server_logger.warning(
                                    f"Некорректное личное сообщение от {current_username}: отсутствует получатель или текст.")
                                send_message(conn, {"type": "error_notification",
                                                    "payload": {"message": "Некорректный формат личного сообщения."}})

                        # Сюда можно добавить обработку других типов сообщений в будущем
                        # elif msg_type == "another_type":
                        #    pass

                        else:
                            server_logger.warning(
                                f"Получено сообщение неизвестного типа {msg_type} от {current_username}.")
                            send_message(conn, {"type": "error_notification",
                                                "payload": {"message": f"Неизвестный тип сообщения: {msg_type}"}})

                    except json.JSONDecodeError:
                        server_logger.error(f"Ошибка декодирования JSON от {current_username}: {message_str}",
                                            exc_info=True)
                        send_message(conn,
                                     {"type": "error_notification", "payload": {"message": "Ошибка формата JSON."}})
                    except Exception as e:
                        server_logger.error(f"Неизвестная ошибка при обработке сообщения от {current_username}: {e}",
                                            exc_info=True)
                        send_message(conn, {"type": "error_notification",
                                            "payload": {"message": "Внутренняя ошибка сервера."}})

            except ConnectionResetError:  # Клиент резко оборвал соединение
                server_logger.warning(f"Соединение сброшено клиентом {current_username} ({addr}).")
                break
            except Exception as e:
                server_logger.error(f"Ошибка чтения от {current_username} ({addr}): {e}", exc_info=True)
                break

    except Exception as e:
        server_logger.critical(
            f"Критическая ошибка в обработчике клиента {addr} (пользователь: {current_username}): {e}", exc_info=True)
    finally:
        # Очистка при отключении клиента
        if current_username:
            with clients_lock:
                if current_username in active_clients:
                    del active_clients[current_username]
            server_logger.info(f"Клиент {current_username} ({addr}) удален из активных.")
        conn.close()
        server_logger.debug(f"Сокет для {addr} (пользователь: {current_username}) окончательно закрыт.")


def run_server():
    global server_running
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((HOST, PORT))
            s.listen()  # По умолчанию listen(баклог) довольно большой, но можно указать, например, 5
            server_logger.info(f"Сервер запущен и слушает на {HOST}:{PORT}")
            server_logger.info("Для остановки сервера нажмите Ctrl+C в этой консоли.")

            s.settimeout(1.0)

            while server_running:
                try:
                    conn, addr = s.accept()
                    # Для каждого клиента будем создавать новый поток
                    client_thread = threading.Thread(target=handle_client, args=(conn, addr))
                    client_thread.daemon = True
                    client_thread.start()
                except socket.timeout:
                    continue
                except Exception as e:
                    if server_running:
                        server_logger.error(f"Ошибка на сервере при принятии соединения: {e}", exc_info=True)
                    break
        except OSError as e:
            server_logger.critical(f"Критическая ошибка при запуске сервера (возможно, порт занят): {e}", exc_info=True)
        except KeyboardInterrupt:
            server_logger.info("Получен сигнал остановки (KeyboardInterrupt)...")
        finally:
            server_running = False
            server_logger.info("Сервер останавливается...")

            # Копируем список ключей, чтобы избежать ошибки изменения словаря во время итерации
            # Это нужно, если бы мы закрывали соединения здесь, но мы закрываем их в handle_client
            # current_client_sockets = []
            # with clients_lock:
            #     current_client_sockets = list(active_clients.values()) # Получаем список сокетов

            # for client_conn in current_client_sockets:
            #     try:
            #         # Можно отправить сообщение о закрытии сервера, но клиент может уже отвалиться
            #         # send_message(client_conn, {"type": "error_notification", "payload": {"message": "Сервер останавливается."}})
            #         client_conn.close()
            #     except Exception as e:
            #         server_logger.error(f"Ошибка при закрытии клиентского сокета при остановке сервера: {e}")

            # active_clients.clear() # Очищаем, хотя потоки сами должны убрать
            print("Ожидание завершения потоков (может занять несколько секунд)...")  # Для информации
            # На практике, для грациозного завершения потоков нужен более сложный механизм,
            # например, использование threading.Event для сигнализации потокам о завершении
            # и client_thread.join() с таймаутом. Но для v0.1 это усложнение.
            s.close()  # Закрываем слушающий сокет
            server_logger.info("Сервер остановлен.")


if __name__ == '__main__':
    server_logger.info("Запуск серверного приложения...")
    run_server()