# client/main_client.py
import sys
import json
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                               QLabel, QLineEdit, QPushButton, QTextEdit, QMessageBox)
from PySide6.QtNetwork import QTcpSocket, QAbstractSocket
from PySide6.QtCore import Qt, QTimer  # QTimer для обработки буфера

import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from logger import setup_logger  # Используем ваше имя файла logger.py

client_logger = setup_logger('ClientApp', 'client_session')


class ChatClientWindow(QWidget):
    def __init__(self):
        super().__init__()
        client_logger.info("Инициализация главного окна клиента...")
        self.setWindowTitle("Мессенджер Клиент v0.1")
        self.setGeometry(200, 200, 500, 400)

        self.socket = QTcpSocket(self)
        self.socket.connected.connect(self.on_connected_to_server)
        self.socket.disconnected.connect(self.on_disconnected_from_server)
        self.socket.errorOccurred.connect(self.on_socket_error)
        self.socket.readyRead.connect(self.on_ready_read)

        self.client_buffer = ""  # Буфер для входящих данных
        self.current_username = None

        self.init_ui()
        self.update_ui_state("disconnected")  # Начальное состояние

        client_logger.info("UI клиента инициализирован.")

    def init_ui(self):
        self.main_layout = QVBoxLayout(self)

        # --- Панель подключения ---
        self.connect_panel = QWidget()
        connect_layout = QVBoxLayout(self.connect_panel)

        self.ip_label = QLabel("IP Сервера:")
        self.ip_input = QLineEdit("127.0.0.1")
        self.port_label = QLabel("Порт Сервера:")
        self.port_input = QLineEdit("65432")
        self.connect_button = QPushButton("Подключиться к Серверу")
        self.connect_button.clicked.connect(self.connect_to_server)
        self.status_label = QLabel("Статус: Отключен")

        connect_layout.addWidget(self.ip_label)
        connect_layout.addWidget(self.ip_input)
        connect_layout.addWidget(self.port_label)
        connect_layout.addWidget(self.port_input)
        connect_layout.addWidget(self.connect_button)
        connect_layout.addWidget(self.status_label)
        self.main_layout.addWidget(self.connect_panel)

        # --- Панель логина ---
        self.login_panel = QWidget()
        login_layout = QVBoxLayout(self.login_panel)

        self.username_label = QLabel("Ваш Никнейм:")
        self.username_input = QLineEdit()
        self.login_button = QPushButton("Войти")
        self.login_button.clicked.connect(self.send_login_request)

        login_layout.addWidget(self.username_label)
        login_layout.addWidget(self.username_input)
        login_layout.addWidget(self.login_button)
        self.main_layout.addWidget(self.login_panel)

        # --- Панель чата ---
        self.chat_panel = QWidget()
        chat_layout = QVBoxLayout(self.chat_panel)

        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)

        recipient_layout = QHBoxLayout()
        self.recipient_label = QLabel("Получатель:")
        self.recipient_input = QLineEdit()
        recipient_layout.addWidget(self.recipient_label)
        recipient_layout.addWidget(self.recipient_input)

        self.message_input = QLineEdit()
        self.message_input.setPlaceholderText("Введите сообщение...")
        self.send_button = QPushButton("Отправить")
        self.send_button.clicked.connect(self.send_private_message)

        self.logged_in_as_label = QLabel("")

        chat_layout.addWidget(self.logged_in_as_label)
        chat_layout.addWidget(self.chat_display)
        chat_layout.addLayout(recipient_layout)
        chat_layout.addWidget(self.message_input)
        chat_layout.addWidget(self.send_button)
        self.main_layout.addWidget(self.chat_panel)

        # Связываем Enter в поле ввода сообщения с кнопкой отправки
        self.message_input.returnPressed.connect(self.send_button.click)
        self.username_input.returnPressed.connect(self.login_button.click)

    def update_ui_state(self, state):
        client_logger.info(f"Изменение состояния UI на: {state}")
        if state == "disconnected":
            self.connect_panel.setVisible(True)
            self.login_panel.setVisible(False)
            self.chat_panel.setVisible(False)
            self.status_label.setText("Статус: Отключен")
        elif state == "connecting_to_server":
            self.connect_panel.setVisible(True)
            self.login_panel.setVisible(False)
            self.chat_panel.setVisible(False)
            self.status_label.setText("Статус: Подключение к серверу...")
            self.connect_button.setEnabled(False)
        elif state == "awaiting_login":  # TCP подключено, ждем ввода ника
            self.connect_panel.setVisible(False)
            self.login_panel.setVisible(True)
            self.chat_panel.setVisible(False)
            self.status_label.setText(
                f"Статус: Подключено к {self.socket.peerName()}:{self.socket.peerPort()}. Введите ник.")
        elif state == "logging_in":  # Ник отправлен, ждем ответа от сервера
            self.connect_panel.setVisible(False)
            self.login_panel.setVisible(True)  # Оставляем видимой, но блокируем кнопку
            self.chat_panel.setVisible(False)
            self.login_button.setEnabled(False)
            self.status_label.setText("Статус: Вход на сервер...")
        elif state == "chatting":
            self.connect_panel.setVisible(False)
            self.login_panel.setVisible(False)
            self.chat_panel.setVisible(True)
            self.logged_in_as_label.setText(f"Вы вошли как: {self.current_username}")
            self.status_label.setText(
                f"Статус: В сети ({self.current_username})")  # Можно убрать, если есть logged_in_as_label

        # Сбрасываем доступность кнопок, если они были заблокированы
        if state != "connecting_to_server":
            self.connect_button.setEnabled(True)
        if state != "logging_in":
            self.login_button.setEnabled(True)

    def connect_to_server(self):
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
        self.update_ui_state("awaiting_login")

    def on_disconnected_from_server(self):
        client_logger.info("Отключено от сервера.")
        self.current_username = None
        self.update_ui_state("disconnected")
        QMessageBox.information(self, "Отключено", "Соединение с сервером потеряно или закрыто.")

    def on_socket_error(self, socket_error):
        error_message = self.socket.errorString()
        client_logger.error(f"Ошибка сокета: {socket_error} - {error_message}")
        self.update_ui_state("disconnected")  # Возвращаем в состояние отключения
        QMessageBox.critical(self, "Ошибка сокета", f"Произошла ошибка: {error_message}")

    def send_json_message(self, message_data):
        """Отправляет JSON-сообщение серверу."""
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

    def send_login_request(self):
        username = self.username_input.text().strip()
        if not username:
            QMessageBox.warning(self, "Ошибка", "Никнейм не может быть пустым.")
            client_logger.warning("Попытка логина с пустым никнеймом.")
            return

        client_logger.info(f"Отправка запроса на логин с никнеймом: {username}")
        self.update_ui_state("logging_in")
        message = {
            "type": "login",
            "payload": {
                "username": username
            }
        }
        self.send_json_message(message)

    def send_private_message(self):
        if not self.current_username:
            QMessageBox.warning(self, "Ошибка", "Вы не вошли на сервер.")
            return

        recipient = self.recipient_input.text().strip()
        text = self.message_input.text().strip()

        if not recipient:
            QMessageBox.warning(self, "Ошибка", "Укажите получателя.")
            return
        if not text:
            QMessageBox.warning(self, "Ошибка", "Сообщение не может быть пустым.")
            return

        client_logger.info(f"Отправка личного сообщения для {recipient}: {text}")
        message = {
            "type": "private_message",
            "payload": {
                "recipient": recipient,
                "text": text
            }
        }
        self.send_json_message(message)
        self.chat_display.append(f"Вы -> {recipient}: {text}")  # Отображаем свое сообщение сразу
        self.message_input.clear()

    def on_ready_read(self):
        """Обрабатывает входящие данные от сервера."""
        try:
            self.client_buffer += self.socket.readAll().data().decode('utf-8')
        except UnicodeDecodeError:
            client_logger.error("Ошибка декодирования входящих данных (не UTF-8).", exc_info=True)
            self.client_buffer = ""  # Очищаем буфер, чтобы избежать проблем
            return

        client_logger.debug(f"on_ready_read: текущий буфер: \"{self.client_buffer}\"")

        while '\n' in self.client_buffer:
            message_str, self.client_buffer = self.client_buffer.split('\n', 1)
            client_logger.info(f"Получено полное сообщение от сервера: {message_str}")

            try:
                message_data = json.loads(message_str)
                msg_type = message_data.get("type")
                payload = message_data.get("payload", {})

                if msg_type == "login_status":
                    status = payload.get("status")
                    msg = payload.get("message")
                    if status == "success":
                        self.current_username = payload.get("username",
                                                            self.username_input.text().strip())  # Берем из ответа, если есть
                        client_logger.info(f"Логин успешен как {self.current_username}. Сообщение от сервера: {msg}")
                        self.update_ui_state("chatting")
                        self.chat_display.clear()  # Очищаем поле чата при новом логине
                        self.chat_display.append(f"<i>{msg}</i>")
                    else:
                        client_logger.warning(f"Ошибка логина. Сообщение от сервера: {msg}")
                        QMessageBox.warning(self, "Ошибка входа", msg)
                        self.update_ui_state("awaiting_login")  # Возвращаем к вводу ника или "disconnected"
                        self.login_button.setEnabled(True)  # Разблокируем кнопку логина

                elif msg_type == "incoming_message":
                    sender = payload.get("sender")
                    text = payload.get("text")
                    client_logger.info(f"Получено сообщение от {sender}: {text}")
                    self.chat_display.append(f"<b>{sender}</b>: {text}")

                elif msg_type == "error_notification":
                    error_msg = payload.get("message")
                    client_logger.warning(f"Уведомление об ошибке от сервера: {error_msg}")
                    self.chat_display.append(f"<i>СЕРВЕР: {error_msg}</i>")  # Можно и в QMessageBox
                    # QMessageBox.warning(self, "Серверное уведомление", error_msg)

                else:
                    client_logger.warning(f"Получен неизвестный тип сообщения от сервера: {msg_type}")

            except json.JSONDecodeError:
                client_logger.error(f"Ошибка декодирования JSON от сервера: {message_str}", exc_info=True)
            except Exception as e:
                client_logger.error(f"Неизвестная ошибка при обработке сообщения от сервера: {e}", exc_info=True)


if __name__ == '__main__':
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