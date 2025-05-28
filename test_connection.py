import socket

HOST = '127.0.0.1'
PORT = 65432

try:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        print(f"Клиент: подключаюсь к {HOST}:{PORT}...")
        s.connect((HOST, PORT))
        print(f"Клиент: подключился.")
        data = s.recv(1024) # Получаем до 1024 байт
        print(f"Клиент: получено от сервера: '{data.decode('utf-8')}'")
except ConnectionRefusedError:
    print(f"Клиент: не удалось подключиться. Сервер не запущен или порт неверный.")
except Exception as e:
    print(f"Клиент: произошла ошибка: {e}")
finally:
    print("Клиент: завершение работы.")