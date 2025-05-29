# client/network/socket_handler.py
import json
from PySide6.QtNetwork import QTcpSocket, QAbstractSocket
from PySide6.QtCore import QObject, Signal  # QObject для сигналов

# Импортируем логгер. Предполагаем, что logger.py в корне проекта.
import sys
import os

CURRENT_DIR_SOCKET = os.path.dirname(os.path.abspath(__file__))  # client/network
CLIENT_DIR_SOCKET = os.path.dirname(CURRENT_DIR_SOCKET)  # client/
PROJECT_ROOT_SOCKET = os.path.dirname(CLIENT_DIR_SOCKET)  # ms/
sys.path.append(PROJECT_ROOT_SOCKET)
from logger import setup_logger

# Можно создать отдельный логгер для этого модуля или использовать общий клиентский
# Пока используем новый, чтобы было видно, откуда логи
socket_logger = setup_logger('SocketHandler', 'client_socket_handler')


class SocketHandler(QObject):  # Наследуемся от QObject для использования сигналов
    # --- Сигналы, которые будет испускать этот класс ---
    connected_to_server = Signal()
    disconnected_from_server = Signal()
    socket_error_occurred = Signal(QAbstractSocket.SocketError, str)  # ошибка сокета, строка ошибки

    # Сигналы для различных ответов от сервера
    login_status_received = Signal(dict)  # payload от login_status
    register_status_received = Signal(dict)  # payload от register_status
    chat_list_received = Signal(dict)  # payload от chat_list_response
    chat_history_received = Signal(dict)  # payload от chat_history
    incoming_message_received = Signal(dict)  # payload от incoming_chat_message
    error_notification_received = Signal(dict)  # payload от error_notification
    unknown_message_received = Signal(str, dict)  # тип сообщения, payload

    def __init__(self, parent=None):
        super().__init__(parent)
        self.socket = QTcpSocket(self)
        self.client_buffer = ""

        # Подключаем внутренние сигналы сокета к нашим методам-обработчикам
        self.socket.connected.connect(self._on_connected)
        self.socket.disconnected.connect(self._on_disconnected)
        self.socket.errorOccurred.connect(self._on_socket_error)
        self.socket.readyRead.connect(self._on_ready_read)

        socket_logger.info("SocketHandler инициализирован.")

    def connect_to_host(self, host, port):
        socket_logger.info(f"Попытка подключения к {host}:{port}")
        if self.socket.state() != QAbstractSocket.UnconnectedState:
            socket_logger.warning(
                "Попытка подключения, когда сокет не в состоянии UnconnectedState. Сначала отключаемся.")
            self.disconnect_from_host()  # Гарантируем, что предыдущее соединение закрыто
        self.socket.connectToHost(host, port)

    def disconnect_from_host(self):
        socket_logger.info("Отключение от хоста...")
        if self.socket.state() != QAbstractSocket.UnconnectedState:
            self.socket.disconnectFromHost()
            # Можно добавить waitForDisconnected, если это критично, но обычно disconnectFromHost достаточно
            # if self.socket.state() != QAbstractSocket.UnconnectedState:
            #     self.socket.waitForDisconnected(1000) # Таймаут 1 сек

    def send_json_message(self, message_data: dict):
        if self.socket.state() == QAbstractSocket.ConnectedState:
            try:
                json_message = json.dumps(message_data, ensure_ascii=False) + '\n'
                self.socket.write(json_message.encode('utf-8'))
                socket_logger.debug(f"Отправлено: {json_message.strip()}")
                return True
            except Exception as e:
                socket_logger.error(f"Ошибка при отправке JSON: {e}", exc_info=True)
        else:
            socket_logger.warning("Попытка отправки сообщения при отсутствующем соединении.")
        return False

    def get_socket_state(self):
        return self.socket.state()

    def get_peer_address_info(self):
        if self.socket.state() == QAbstractSocket.ConnectedState:
            return f"{self.socket.peerName()}:{self.socket.peerPort()}"
        return None

    # --- Приватные слоты-обработчики сигналов QTcpSocket ---
    def _on_connected(self):
        socket_logger.info("Соединение с сервером установлено.")
        self.client_buffer = ""  # Очищаем буфер при новом соединении
        self.connected_to_server.emit()

    def _on_disconnected(self):
        socket_logger.info("Соединение с сервером разорвано.")
        self.client_buffer = ""
        self.disconnected_from_server.emit()

    def _on_socket_error(self, socket_error: QAbstractSocket.SocketError):
        error_string = self.socket.errorString()
        socket_logger.error(f"Ошибка сокета: {socket_error} - {error_string}")
        self.socket_error_occurred.emit(socket_error, error_string)

    def _on_ready_read(self):
        try:
            self.client_buffer += self.socket.readAll().data().decode('utf-8')
        except UnicodeDecodeError:
            socket_logger.error("Ошибка декодирования входящих данных (не UTF-8). Данные отброшены.", exc_info=True)
            self.client_buffer = ""  # Очищаем буфер, чтобы избежать проблем с поврежденными данными
            return

        # socket_logger.debug(f"Данные в буфере (перед обработкой split): \"{self.client_buffer.replaceHCRT()+'\n', '<NL>').replace('\r', '<CR>')}\"")

        while '\n' in self.client_buffer:
            message_str, self.client_buffer = self.client_buffer.split('\n', 1)
            socket_logger.info(f"Получено полное сообщение от сервера: {message_str}")

            try:
                message_data = json.loads(message_str)
                msg_type = message_data.get("type")
                payload = message_data.get("payload", {})

                if msg_type == "login_status":
                    self.login_status_received.emit(payload)
                elif msg_type == "register_status":
                    self.register_status_received.emit(payload)
                elif msg_type == "chat_list_response":
                    self.chat_list_received.emit(payload)
                elif msg_type == "chat_history":
                    self.chat_history_received.emit(payload)
                elif msg_type == "incoming_chat_message":
                    self.incoming_message_received.emit(payload)
                elif msg_type == "error_notification":
                    self.error_notification_received.emit(payload)
                else:
                    socket_logger.warning(f"Получен неизвестный тип сообщения от сервера: {msg_type}")
                    self.unknown_message_received.emit(msg_type, payload)

            except json.JSONDecodeError:
                socket_logger.error(f"Ошибка декодирования JSON от сервера: {message_str}", exc_info=True)
                # Можно отправить сигнал об ошибке JSON, если UI должен на это реагировать
            except Exception as e:
                socket_logger.error(f"Неизвестная ошибка при обработке сообщения от сервера: {e}", exc_info=True)