# client/main_client.py
import sys
import json
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                               QLabel, QLineEdit, QPushButton, QTextEdit, QMessageBox)
from PySide6.QtNetwork import QTcpSocket, QAbstractSocket
from PySide6.QtCore import Qt

import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from logger import setup_logger

client_logger = setup_logger('ClientApp', 'client_session')


class ChatClientWindow(QWidget):
    def __init__(self):
        super().__init__()
        client_logger.info("Инициализация главного окна клиента...")
        self.setWindowTitle("Мессенджер Клиент v0.2")  # Версия обновлена
        self.setGeometry(200, 200, 500, 450)  # Немного увеличим высоту для новых кнопок

        self.socket = QTcpSocket(self)
        self.socket.connected.connect(self.on_connected_to_server)
        self.socket.disconnected.connect(self.on_disconnected_from_server)
        self.socket.errorOccurred.connect(self.on_socket_error)
        self.socket.readyRead.connect(self.on_ready_read)

        self.client_buffer = ""
        self.current_username = None
        self.current_user_id = None  # Будем хранить ID пользователя

        self.init_ui()
        self.update_ui_state("disconnected")

        client_logger.info("UI клиента инициализирован.")

    def init_ui(self):
        self.main_layout = QVBoxLayout(self)

        # --- Панель подключения ---
        self.connect_panel = QWidget()
        connect_layout = QVBoxLayout(self.connect_panel)

        self.ip_input = QLineEdit("127.0.0.1")
        self.port_input = QLineEdit("65432")
        self.connect_button = QPushButton("Подключиться к Серверу")
        self.connect_button.clicked.connect(self.connect_to_server)
        self.status_label = QLabel("Статус: Отключен")  # Этот лейбл будет общим

        connect_layout.addWidget(QLabel("IP Сервера:"))
        connect_layout.addWidget(self.ip_input)
        connect_layout.addWidget(QLabel("Порт Сервера:"))
        connect_layout.addWidget(self.port_input)
        connect_layout.addWidget(self.connect_button)
        self.main_layout.addWidget(self.connect_panel)
        self.main_layout.addWidget(self.status_label)  # Общий статус лейбл

        # --- Панель логина/регистрации ---
        self.auth_panel = QWidget()  # Переименуем в auth_panel
        auth_layout = QVBoxLayout(self.auth_panel)

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Имя пользователя (логин)")
        self.password_input = QLineEdit()  # Новое поле для пароля
        self.password_input.setPlaceholderText("Пароль")
        self.password_input.setEchoMode(QLineEdit.Password)  # Скрывать пароль

        auth_buttons_layout = QHBoxLayout()  # Горизонтальный layout для кнопок
        self.login_button = QPushButton("Войти")
        self.login_button.clicked.connect(self.send_login_request)
        self.register_button = QPushButton("Зарегистрироваться")  # Новая кнопка
        self.register_button.clicked.connect(self.send_register_request)

        auth_buttons_layout.addWidget(self.login_button)
        auth_buttons_layout.addWidget(self.register_button)

        auth_layout.addWidget(QLabel("Имя пользователя:"))
        auth_layout.addWidget(self.username_input)
        auth_layout.addWidget(QLabel("Пароль:"))
        auth_layout.addWidget(self.password_input)
        auth_layout.addLayout(auth_buttons_layout)
        self.main_layout.addWidget(self.auth_panel)

        # --- Панель чата ---
        self.chat_panel = QWidget()
        # ... (остальная часть chat_panel остается такой же, как в предыдущей версии) ...
        chat_layout = QVBoxLayout(self.chat_panel)
        self.logged_in_as_label = QLabel("")
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        recipient_layout = QHBoxLayout()
        self.recipient_label = QLabel("Получатель (никнейм):")
        self.recipient_input = QLineEdit()
        recipient_layout.addWidget(self.recipient_label)
        recipient_layout.addWidget(self.recipient_input)
        self.message_input = QLineEdit()
        self.message_input.setPlaceholderText("Введите сообщение...")
        self.send_button = QPushButton("Отправить")
        self.send_button.clicked.connect(self.send_private_message)
        chat_layout.addWidget(self.logged_in_as_label)
        chat_layout.addWidget(self.chat_display)
        chat_layout.addLayout(recipient_layout)
        chat_layout.addWidget(self.message_input)
        chat_layout.addWidget(self.send_button)
        self.main_layout.addWidget(self.chat_panel)

        self.message_input.returnPressed.connect(self.send_button.click)
        # Свяжем Enter в поле пароля с кнопкой "Войти" (основное действие)
        self.password_input.returnPressed.connect(self.login_button.click)

    def update_ui_state(self, state):
        client_logger.info(f"Изменение состояния UI на: {state}")
        # Сначала скроем все основные панели
        self.connect_panel.setVisible(False)
        self.auth_panel.setVisible(False)
        self.chat_panel.setVisible(False)

        # Затем покажем нужные
        if state == "disconnected":
            self.connect_panel.setVisible(True)
            self.status_label.setText("Статус: Отключен")
            self.connect_button.setEnabled(True)
        elif state == "connecting_to_server":
            self.connect_panel.setVisible(True)
            self.status_label.setText("Статус: Подключение к серверу...")
            self.connect_button.setEnabled(False)  # Блокируем кнопку во время подключения
        elif state == "awaiting_auth":  # TCP подключено, ждем ввода логина/пароля
            self.auth_panel.setVisible(True)
            self.status_label.setText(
                f"Статус: Подключено к {self.socket.peerName()}:{self.socket.peerPort()}. Введите данные.")
            self.login_button.setEnabled(True)
            self.register_button.setEnabled(True)
        elif state == "authenticating":  # Данные отправлены, ждем ответа от сервера
            self.auth_panel.setVisible(True)
            self.status_label.setText("Статус: Аутентификация...")
            self.login_button.setEnabled(False)
            self.register_button.setEnabled(False)
        elif state == "chatting":
            self.chat_panel.setVisible(True)
            self.logged_in_as_label.setText(f"Вы вошли как: {self.current_username} (ID: {self.current_user_id})")
            self.status_label.setText(f"Статус: В сети ({self.current_username})")

        # Сброс доступности кнопок, если они не должны быть заблокированы в текущем состоянии
        if state != "connecting_to_server":
            self.connect_button.setEnabled(True)
        if state != "authenticating":
            self.login_button.setEnabled(True)
            self.register_button.setEnabled(True)

    def connect_to_server(self):
        # ... (метод остается таким же) ...
        host = self.ip_input.text()
        try:
            port = int(self.port_input.text())
        except ValueError:
            QMessageBox.warning(self, "Ошибка", "Порт должен быть числом.")
            client_logger.warning("Попытка ввода нечислового порта.")
            return
        client_logger.info(f"Попытка подключения к {host}:{port}")
        self.update_ui_state("connecting_to_server")
        self.socket.connectToHost(host, port)

    def on_connected_to_server(self):
        client_logger.info(f"Успешно подключено к серверу {self.socket.peerName()}:{self.socket.peerPort()}")
        self.update_ui_state("awaiting_auth")  # Изменили состояние

    def on_disconnected_from_server(self):
        client_logger.info("Отключено от сервера.")
        self.current_username = None
        self.current_user_id = None
        self.update_ui_state("disconnected")
        QMessageBox.information(self, "Отключено", "Соединение с сервером потеряно или закрыто.")

    def on_socket_error(self, socket_error: QAbstractSocket.SocketError):  # Явно указываем тип для подсказок
        error_message = self.socket.errorString()
        client_logger.error(f"Ошибка сокета: {socket_error} - {error_message}")
        # Если ошибка произошла после того, как мы были подключены, то update_ui_state("disconnected")
        # Если это ошибка при попытке подключения, connect_button уже заблокирован,
        # и update_ui_state("disconnected") его разблокирует.
        self.update_ui_state("disconnected")
        if socket_error != QAbstractSocket.RemoteHostClosedError:  # Не показываем QMessageBox, если просто сервер закрыл соединение
            QMessageBox.critical(self, "Ошибка сокета", f"Произошла ошибка: {error_message}")

    def send_json_message(self, message_data):
        # ... (метод остается таким же) ...
        if self.socket.state() == QAbstractSocket.ConnectedState:
            try:
                json_message = json.dumps(message_data) + '\n'
                self.socket.write(json_message.encode('utf-8'))
                client_logger.debug(f"Отправлено на сервер: {json_message.strip()}")
            except Exception as e:
                client_logger.error(f"Ошибка при отправке JSON: {e}", exc_info=True)
                QMessageBox.warning(self, "Ошибка отправки", f"Не удалось отправить сообщение: {e}")
        else:
            client_logger.warning("Попытка отправки сообщения при отсутствующем соединении.")
            QMessageBox.warning(self, "Нет соединения", "Не удалось отправить сообщение: нет соединения с сервером.")

    def send_register_request(self):
        username = self.username_input.text().strip()
        password = self.password_input.text()  # Пароль не тримим, пробелы могут быть частью

        if not username or not password:
            QMessageBox.warning(self, "Регистрация", "Имя пользователя и пароль не могут быть пустыми.")
            return
        if len(password) < 4:  # Такая же проверка, как на сервере
            QMessageBox.warning(self, "Регистрация", "Пароль должен быть не менее 4 символов.")
            return

        client_logger.info(f"Отправка запроса на регистрацию для: {username}")
        self.update_ui_state("authenticating")  # Общее состояние для ожидания ответа
        message = {
            "type": "register",
            "payload": {
                "username": username,
                "password": password
            }
        }
        self.send_json_message(message)

    def send_login_request(self):
        username = self.username_input.text().strip()
        password = self.password_input.text()

        if not username or not password:
            QMessageBox.warning(self, "Вход", "Имя пользователя и пароль не могут быть пустыми.")
            return

        client_logger.info(f"Отправка запроса на вход для: {username}")
        self.update_ui_state("authenticating")
        message = {
            "type": "login",
            "payload": {
                "username": username,
                "password": password
            }
        }
        self.send_json_message(message)

    def send_private_message(self):
        # ... (метод остается почти таким же, но проверяет current_user_id или current_username) ...
        if not self.current_user_id:  # Проверяем, что мы аутентифицированы
            QMessageBox.warning(self, "Ошибка", "Вы не вошли на сервер.")
            return
        # ... (остальная логика отправки сообщения) ...
        recipient = self.recipient_input.text().strip()
        text = self.message_input.text().strip()
        if not recipient: QMessageBox.warning(self, "Ошибка", "Укажите получателя."); return
        if not text: QMessageBox.warning(self, "Ошибка", "Сообщение не может быть пустым."); return
        client_logger.info(f"Отправка личного сообщения для {recipient}: {text}")
        message_data = {"type": "private_message", "payload": {"recipient": recipient, "text": text}}
        self.send_json_message(message_data)
        self.chat_display.append(f"Вы -> {recipient}: {text}")
        self.message_input.clear()

    def on_ready_read(self):
        # ... (начало метода такое же: чтение в буфер, цикл по '\n') ...
        try:
            self.client_buffer += self.socket.readAll().data().decode('utf-8')
        except UnicodeDecodeError:  # ... обработка ошибки декодирования ...
            client_logger.error("Ошибка декодирования входящих данных (не UTF-8).", exc_info=True)
            self.client_buffer = ""
            return
        client_logger.debug(f"on_ready_read: текущий буфер (до обработки split): \"{self.client_buffer}\"")

        while '\n' in self.client_buffer:
            message_str, self.client_buffer = self.client_buffer.split('\n', 1)
            client_logger.info(f"Получено полное сообщение от сервера: {message_str}")

            try:
                message_data = json.loads(message_str)
                msg_type = message_data.get("type")
                payload = message_data.get("payload", {})

                if msg_type == "register_status":  # Новый обработчик
                    status = payload.get("status")
                    msg = payload.get("message")
                    if status == "success":
                        client_logger.info(f"Регистрация успешна. Сообщение: {msg}")
                        QMessageBox.information(self, "Регистрация успешна", msg + "\nТеперь вы можете войти.")
                        self.update_ui_state("awaiting_auth")  # Возвращаем к панели логина/регистрации
                    else:
                        client_logger.warning(f"Ошибка регистрации. Сообщение: {msg}")
                        QMessageBox.warning(self, "Ошибка регистрации", msg)
                        self.update_ui_state("awaiting_auth")  # Возвращаем к панели логина/регистрации
                    self.login_button.setEnabled(True)  # Разблокируем кнопки в любом случае
                    self.register_button.setEnabled(True)


                elif msg_type == "login_status":
                    status = payload.get("status")
                    msg = payload.get("message")
                    if status == "success":
                        self.current_username = payload.get("username")
                        self.current_user_id = payload.get("user_id")  # Сохраняем user_id
                        client_logger.info(
                            f"Логин успешен как {self.current_username} (ID: {self.current_user_id}). Сообщение: {msg}")
                        self.update_ui_state("chatting")
                        self.chat_display.clear()
                        self.chat_display.append(f"<i>{msg}</i>")
                    else:
                        client_logger.warning(f"Ошибка логина. Сообщение: {msg}")
                        QMessageBox.warning(self, "Ошибка входа", msg)
                        self.update_ui_state("awaiting_auth")  # Возвращаем к панели логина/регистрации
                    self.login_button.setEnabled(True)  # Разблокируем кнопки в любом случае
                    self.register_button.setEnabled(True)

                elif msg_type == "incoming_message":
                    # ... (остается таким же) ...
                    sender = payload.get("sender")
                    text = payload.get("text")
                    client_logger.info(f"Получено сообщение от {sender}: {text}")
                    self.chat_display.append(f"<b>{sender}</b>: {text}")

                elif msg_type == "error_notification":
                    # ... (остается таким же) ...
                    error_msg = payload.get("message")
                    client_logger.warning(f"Уведомление об ошибке от сервера: {error_msg}")
                    self.chat_display.append(f"<i>СЕРВЕР: {error_msg}</i>")

                else:
                    client_logger.warning(f"Получен неизвестный тип сообщения от сервера: {msg_type}")

            # ... (обработка json.JSONDecodeError и Exception остается такой же) ...
            except json.JSONDecodeError:
                client_logger.error(f"Ошибка декодирования JSON от сервера: {message_str}", exc_info=True)
            except Exception as e:
                client_logger.error(f"Неизвестная ошибка при обработке сообщения от сервера: {e}", exc_info=True)


if __name__ == '__main__':
    # ... (код запуска приложения остается таким же) ...
    client_logger.info("Запуск клиентского приложения...")
    app = QApplication(sys.argv)
    window = ChatClientWindow()
    window.show()
    client_logger.info("Главное окно клиента отображено.")
    try:
        exit_code = app.exec()
        client_logger.info(f"Клиентское приложение завершено с кодом: {exit_code}")
        sys.exit(exit_code)
    except Exception as e:
        client_logger.critical(f"Критическая ошибка в клиентском приложении: {e}", exc_info=True)
        sys.exit(1)