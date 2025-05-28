import socket
import threading # Добавим для возможности остановки сервера

HOST = '127.0.0.1'  # Адрес для прослушивания (localhost)
PORT = 65432        # Порт для прослушивания (незанятый)

# Флаг для управления работой сервера
server_running = True

def handle_client(conn, addr):
    """Обрабатывает соединение с клиентом."""
    print(f"Подключился клиент: {addr}")
    try:
        # Просто отправляем приветственное сообщение и закрываем соединение
        message_to_send = "Привет от сервера!"
        conn.sendall(message_to_send.encode('utf-8'))
        print(f"Приветствие отправлено клиенту {addr}")
    except Exception as e:
        print(f"Ошибка при обработке клиента {addr}: {e}")
    finally:
        conn.close()
        print(f"Соединение с клиентом {addr} закрыто.")

def run_server():
    global server_running
    # Устанавливаем SO_REUSEADDR, чтобы можно было быстро перезапускать сервер
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((HOST, PORT))
            s.listen()
            print(f"Сервер запущен и слушает на {HOST}:{PORT}")
            print("Для остановки сервера нажмите Ctrl+C в этой консоли.")

            s.settimeout(1.0) # Устанавливаем таймаут для accept, чтобы проверять server_running

            while server_running:
                try:
                    conn, addr = s.accept()
                    # Для каждого клиента будем создавать новый поток (пока очень упрощенно)
                    # В будущем лучше использовать менеджер потоков или asyncio
                    client_thread = threading.Thread(target=handle_client, args=(conn, addr))
                    client_thread.daemon = True # Потоки-демоны завершаются при выходе основного потока
                    client_thread.start()
                except socket.timeout:
                    continue # Просто продолжаем цикл, если таймаут
                except Exception as e:
                    if server_running: # Выводим ошибку, только если сервер еще должен работать
                        print(f"Ошибка на сервере при принятии соединения: {e}")
                    break # Выходим из цикла при других ошибках сокета

        except OSError as e:
            print(f"Ошибка при запуске сервера (возможно, порт занят): {e}")
        except KeyboardInterrupt:
            print("Получен сигнал остановки (KeyboardInterrupt)...")
        finally:
            server_running = False # Устанавливаем флаг, чтобы остановить все
            print("Сервер останавливается...")
            # Здесь можно было бы дождаться завершения активных клиентских потоков, но пока упростим
            print("Сервер остановлен.")


if __name__ == '__main__':
    run_server()