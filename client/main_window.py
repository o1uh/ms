# client/main_window.py
import sys
import json
from datetime import datetime

from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                               QLabel, QLineEdit, QPushButton, QTextEdit, QMessageBox,
                               QListWidget, QListWidgetItem, QStackedWidget)
from PySide6.QtNetwork import QAbstractSocket
from PySide6.QtCore import Qt, Slot

# Настройка пути для импорта logger.py
import os

CURRENT_DIR_MW = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT_MW = os.path.dirname(CURRENT_DIR_MW)
sys.path.append(PROJECT_ROOT_MW)
from logger import setup_logger

# Импортируем SocketHandler и панели
from .network.socket_handler import SocketHandler
from .widgets.connect_panel import ConnectPanel
from .widgets.auth_panel import AuthPanel
from .widgets.chat_list_panel import ChatListPanel
from .widgets.chat_panel import ChatPanel

main_window_logger = setup_logger('MainWindow', 'client_main_window_refactored_full')


class ChatClientWindow(QWidget):  # Или QMainWindow
    def __init__(self):
        super().__init__()
        main_window_logger.info("Инициализация ChatClientWindow...")
        self.setWindowTitle("Мессенджер Клиент v0.5 - Полный Рефакторинг")
        self.setGeometry(200, 200, 500, 600)  # Немного изменил размер для панелей

        self.socket_handler = SocketHandler(self)

        # Подключаем сигналы от SocketHandler
        self.socket_handler.connected_to_server.connect(self.handle_connected_to_server)
        self.socket_handler.disconnected_from_server.connect(self.handle_disconnected_from_server)
        self.socket_handler.socket_error_occurred.connect(self.handle_socket_error)
        self.socket_handler.login_status_received.connect(self.handle_login_status_response)
        self.socket_handler.register_status_received.connect(self.handle_register_status_response)
        self.socket_handler.chat_list_received.connect(self.handle_chat_list_response)
        self.socket_handler.chat_history_received.connect(self.handle_chat_history_response)
        self.socket_handler.incoming_message_received.connect(self.handle_incoming_chat_message)
        self.socket_handler.error_notification_received.connect(self.handle_error_notification)
        self.socket_handler.unknown_message_received.connect(self.handle_unknown_message)

        self.current_username = None
        self.current_user_id = None
        self.active_chat_id = None
        self.active_chat_name = None  # Имя собеседника или группы для отображения

        self.init_ui_with_panels()
        self.switch_to_panel(self.connect_panel_widget)
        self.status_label.setText("Статус: Отключен")
        main_window_logger.info("UI и SocketHandler для ChatClientWindow инициализированы.")

    def init_ui_with_panels(self):
        self.main_layout = QVBoxLayout(self)
        self.status_label = QLabel("Статус: Отключен")

        self.stacked_widget = QStackedWidget()
        self.main_layout.addWidget(self.stacked_widget)
        self.main_layout.addWidget(self.status_label)

        # 1. Панель подключения
        self.connect_panel_widget = ConnectPanel(self)
        self.connect_panel_widget.connect_requested.connect(self.attempt_server_connection)
        self.stacked_widget.addWidget(self.connect_panel_widget)

        # 2. Панель аутентификации
        self.auth_panel_widget = AuthPanel(self)
        self.auth_panel_widget.login_requested.connect(self.attempt_login)
        self.auth_panel_widget.register_requested.connect(self.attempt_registration)
        self.stacked_widget.addWidget(self.auth_panel_widget)

        # 3. Панель списка чатов
        self.chat_list_panel_widget = ChatListPanel(self)
        self.chat_list_panel_widget.request_new_chat.connect(self.on_request_new_chat_from_panel)
        self.chat_list_panel_widget.chat_selected.connect(self.on_chat_selected_from_panel)
        self.chat_list_panel_widget.refresh_list_requested.connect(self.attempt_request_chat_list)
        self.stacked_widget.addWidget(self.chat_list_panel_widget)

        # 4. Панель активного чата
        self.chat_panel_widget = ChatPanel(self)
        self.chat_panel_widget.send_message_requested.connect(self.attempt_send_message_to_active_chat)
        self.chat_panel_widget.back_to_list_requested.connect(self.show_chat_list_panel_ui_action)
        self.stacked_widget.addWidget(self.chat_panel_widget)

    def switch_to_panel(self, panel_widget: QWidget):
        """Переключает активную панель и обновляет состояние кнопок."""
        self.stacked_widget.setCurrentWidget(panel_widget)

        is_connected = self.socket_handler.get_socket_state() == QAbstractSocket.ConnectedState
        is_authenticated = self.current_user_id is not None

        # Управляем состоянием кнопок на каждой панели
        if hasattr(self, 'connect_panel_widget'):  # Проверка на случай вызова до полной инициализации
            self.connect_panel_widget.set_button_enabled(panel_widget == self.connect_panel_widget and not is_connected)

        if hasattr(self, 'auth_panel_widget'):
            self.auth_panel_widget.set_buttons_enabled(panel_widget == self.auth_panel_widget and is_connected)

        if hasattr(self, 'chat_list_panel_widget'):
            self.chat_list_panel_widget.set_buttons_enabled(
                panel_widget == self.chat_list_panel_widget and is_authenticated)

        if hasattr(self, 'chat_panel_widget'):
            can_send = (panel_widget == self.chat_panel_widget and
                        is_authenticated and
                        (self.active_chat_id is not None or
                         (
                                     self.active_chat_id is None and self.active_chat_name is not None)))  # Разрешаем отправку в "новый" чат
            self.chat_panel_widget.set_send_button_enabled(can_send)

    # --- Методы для переключения UI и обновления статуса ---
    @Slot()  # Для кнопки "Назад" из ChatPanel
    def show_chat_list_panel_ui_action(self):
        if not self.current_user_id:
            self.show_auth_panel_ui_action("Сначала войдите или зарегистрируйтесь.")
            return
        self.active_chat_id = None
        self.active_chat_name = None
        self.active_chat_data = None  # Сбрасываем активный чат
        self.switch_to_panel(self.chat_list_panel_widget)
        self.status_label.setText(f"Статус: Вы вошли как {self.current_username} (ID: {self.current_user_id})")
        main_window_logger.info(f"UI: Панель списка чатов для {self.current_username}.")
        self.attempt_request_chat_list()  # Запрашиваем список чатов при каждом показе

    def show_connect_panel_ui_action(self, message="Отключен"):
        self.active_chat_id = None;
        self.active_chat_name = None;
        self.active_chat_data = None  # Сброс активного чата
        self.current_username = None;
        self.current_user_id = None  # Сброс пользователя
        self.switch_to_panel(self.connect_panel_widget)
        self.status_label.setText(f"Статус: {message}")
        if hasattr(self, 'chat_list_panel_widget'): self.chat_list_panel_widget.update_chat_list([])  # Очищаем список
        if hasattr(self, 'chat_panel_widget'): self.chat_panel_widget.chat_display.clear()  # Очищаем чат
        main_window_logger.info(f"UI: Панель подключения. Статус: {message}")

    def show_auth_panel_ui_action(self, message="Введите данные для входа/регистрации"):
        self.active_chat_id = None;
        self.active_chat_name = None;
        self.active_chat_data = None
        self.switch_to_panel(self.auth_panel_widget)
        self.status_label.setText(f"Статус: {message}")
        main_window_logger.info(f"UI: Панель аутентификации. Статус: {message}")
        if hasattr(self, 'auth_panel_widget'): self.auth_panel_widget.focus_username_input()

    def show_specific_chat_panel_ui_action(self, chat_id, chat_name_to_display, other_username=None):
        """Открывает панель чата с известными данными."""
        main_window_logger.info(f"UI: Запрос на открытие чата ID {chat_id} ({chat_name_to_display}).")
        self.active_chat_id = chat_id
        self.active_chat_name = chat_name_to_display  # Это имя собеседника для direct или имя группы

        self.chat_panel_widget.configure_chat(chat_id, chat_name_to_display, self.current_username)
        self.switch_to_panel(self.chat_panel_widget)
        self.status_label.setText(f"В чате с {self.active_chat_name}")

        if self.active_chat_id:  # Запрашиваем историю только если chat_id известен
            self.attempt_request_chat_history(self.active_chat_id)
        # Если chat_id is None, то configure_chat уже отобразит "Начните новый диалог..."

    # --- Методы-инициаторы действий (вызывают методы SocketHandler) ---
    @Slot(str, int)  # Слот для сигнала от ConnectPanel
    def attempt_server_connection(self, host: str, port: int):
        main_window_logger.info(f"Получен запрос на подключение к {host}:{port} от ConnectPanel.")
        self.status_label.setText("Статус: Подключение к серверу...")
        self.connect_panel_widget.set_button_enabled(False)
        self.socket_handler.connect_to_host(host, port)

    @Slot(str, str)  # Слот для сигнала от AuthPanel
    def attempt_registration(self, username: str, password: str):
        main_window_logger.info(f"Попытка регистрации для {username} через SocketHandler.")
        self.status_label.setText("Статус: Регистрация...")
        self.auth_panel_widget.set_buttons_enabled(False)
        message_data = {"type": "register", "payload": {"username": username, "password": password}}
        self.socket_handler.send_json_message(message_data)

    @Slot(str, str)  # Слот для сигнала от AuthPanel
    def attempt_login(self, username: str, password: str):
        main_window_logger.info(f"Попытка входа для {username} через SocketHandler.")
        self.status_label.setText("Статус: Вход...")
        self.auth_panel_widget.set_buttons_enabled(False)
        message_data = {"type": "login", "payload": {"username": username, "password": password}}
        self.socket_handler.send_json_message(message_data)

    @Slot()  # Слот для сигнала от ChatListPanel
    def attempt_request_chat_list(self):
        if not self.current_user_id:
            main_window_logger.warning("Попытка запроса списка чатов без аутентификации (attempt).")
            return
        main_window_logger.info(f"Пользователь {self.current_username} запрашивает список чатов через SocketHandler.")
        self.status_label.setText(f"Статус: Обновление списка чатов...")
        message_data = {"type": "request_chat_list", "payload": {}}
        self.socket_handler.send_json_message(message_data)

    def attempt_request_chat_history(self, chat_id: int):  # chat_id должен быть int
        if chat_id is None:
            main_window_logger.info(
                f"Не запрашиваем историю, так как chat_id не известен (вероятно, новый чат с {self.active_chat_name}).")
            # Логика для нового чата уже в open_chat_panel_ui_action -> chat_panel_widget.configure_chat
            return
        if not self.current_user_id: return
        main_window_logger.info(f"Запрос истории для чата ID: {chat_id} через SocketHandler.")
        message_data = {"type": "request_chat_history", "payload": {"chat_id": chat_id}}
        self.socket_handler.send_json_message(message_data)

    @Slot(str)  # Слот для сигнала от ChatPanel
    def attempt_send_message_to_active_chat(self, text: str):  # Принимаем текст от панели
        if not self.current_user_id:
            QMessageBox.warning(self, "Ошибка", "Вы не вошли на сервер.")
            return

        if not text:  # Проверка на пустое сообщение уже в панели, но можно и здесь
            main_window_logger.warning("Попытка отправки пустого сообщения.")
            return

        # Ключевой момент: если active_chat_id is None (новый чат)
        if self.active_chat_id is None:
            if self.active_chat_name:  # Если есть имя собеседника для нового чата
                main_window_logger.info(f"Отправка первого сообщения в новый чат с {self.active_chat_name}: {text}")
                # Отправляем специальное сообщение для создания чата ИЛИ сервер должен это обработать
                # Пока что наш сервер ожидает chat_id в "send_message_to_chat".
                # Это место нужно будет согласовать с серверной логикой "get_or_create_direct_chat"
                # или добавить новый тип запроса "create_direct_chat_and_send_message".
                # ВРЕМЕННОЕ РЕШЕНИЕ: Отправляем как есть, сервер должен создать чат по участникам, если chat_id не указан,
                # но это потребует доработки сервера.
                # ЛИБО: кнопка "Начать чат" должна сначала создать чат и получить ID.
                # Для текущей реализации сервера, которая строго требует chat_id:
                QMessageBox.warning(self, "Новый чат",
                                    "Сначала чат должен быть создан на сервере (например, сервер должен вернуть ID чата после его инициации). Отправка в новый чат без ID пока не поддерживается.")
                main_window_logger.error(
                    f"Попытка отправки сообщения в новый чат '{self.active_chat_name}' без chat_id.")
                return
            else:  # Не должно произойти, если UI корректно управляет состояниями
                QMessageBox.warning(self, "Ошибка", "Не выбран активный чат для отправки.")
                return

        payload_data = {"chat_id": self.active_chat_id, "text": text}
        main_window_logger.info(
            f"Отправка сообщения в чат ID {self.active_chat_id} (для {self.active_chat_name}): {text} через SocketHandler.")

        if self.socket_handler.send_json_message({"type": "send_message_to_chat", "payload": payload_data}):
            # Оптимистичное отображение (или дождаться подтверждения от сервера)
            # Теперь это делает сама ChatPanel
            pass
            # Обновление UI после отправки (например, очистка поля ввода) должно быть в ChatPanel

    # --- Обработчики действий UI, связанных с чатами (вызываются из ChatListPanel) ---
    @Slot(str)  # Слот для сигнала request_new_chat от ChatListPanel
    def on_request_new_chat_from_panel(self, target_username: str):
        if not self.current_user_id: return
        if not target_username:
            QMessageBox.warning(self, "Новый чат", "Введите имя пользователя.")
            return
        if target_username == self.current_username:
            QMessageBox.warning(self, "Новый чат", "Нельзя начать чат с самим собой.")
            return

        main_window_logger.info(f"Запрос на новый/существующий чат с {target_username} от панели.")

        # 1. Проверяем, есть ли уже такой чат в загруженном списке
        for i in range(self.chat_list_panel_widget.chat_list_widget.count()):
            item = self.chat_list_panel_widget.chat_list_widget.item(i)
            chat_data = item.data(Qt.UserRole)
            if chat_data and chat_data.get("chat_type") == "direct" and chat_data.get(
                    "other_username") == target_username:
                main_window_logger.info(f"Чат с {target_username} уже есть в списке. Открываем.")
                self.open_chat_from_data(chat_data)  # Используем данные из элемента списка
                return

        # 2. Если чата нет в списке - это новый диалог.
        #    Мы не знаем chat_id. Сервер его создаст при первой отправке сообщения.
        #    Пока что просто откроем панель чата.
        main_window_logger.info(f"Новый диалог с {target_username}. Открытие панели чата (ID пока не известен).")
        self.open_chat_panel_ui_action(None, target_username)  # chat_id is None, chat_name is target_username

    @Slot(dict)  # Слот для сигнала chat_selected от ChatListPanel
    def on_chat_selected_from_panel(self, chat_data: dict):
        main_window_logger.info(f"Выбран чат из списка (панель): {chat_data}")
        self.open_chat_from_data(chat_data)

    def open_chat_from_data(self, chat_data: dict):
        """Вспомогательный метод для открытия чата по его данным."""
        if chat_data:
            chat_id = chat_data.get("chat_id")
            # Для direct чатов имя чата (chat_name) в списке - это имя собеседника
            chat_name_to_display = chat_data.get("chat_name")
            self.show_specific_chat_panel_ui_action(chat_id, chat_name_to_display)
        else:
            main_window_logger.warning("Попытка открыть чат без данных.")

    # --- Слоты-обработчики сигналов от SocketHandler (ответы сервера) ---
    @Slot(dict)
    def handle_login_status_response(self, payload: dict):
        main_window_logger.info(f"СИГНАЛ: Получен статус логина: {payload}")
        status = payload.get("status")
        msg = payload.get("message")

        # Разблокируем кнопки на панели аутентификации в любом случае
        if hasattr(self, 'auth_panel_widget'):  # Проверка, если UI еще не полностью создан
            self.auth_panel_widget.set_buttons_enabled(True)

        if status == "success":
            self.current_username = payload.get("username")
            self.current_user_id = payload.get("user_id")
            main_window_logger.info(f"Логин успешен как {self.current_username} (ID: {self.current_user_id}).")
            if hasattr(self, 'auth_panel_widget'): self.auth_panel_widget.clear_inputs()
            self.show_chat_list_panel_ui_action()
        else:
            main_window_logger.warning(f"Ошибка логина: {msg}")
            QMessageBox.warning(self, "Ошибка входа", msg)
            # Остаемся на панели аутентификации
            self.show_auth_panel_ui_action(f"Подключено. Ошибка входа: {msg}")

    @Slot(dict)
    def handle_register_status_response(self, payload: dict):
        main_window_logger.info(f"СИГНАЛ: Получен статус регистрации: {payload}")
        status = payload.get("status")
        msg = payload.get("message")

        if hasattr(self, 'auth_panel_widget'):
            self.auth_panel_widget.set_buttons_enabled(True)

        if status == "success":
            QMessageBox.information(self, "Регистрация успешна", msg + "\nТеперь вы можете войти.")
        else:
            QMessageBox.warning(self, "Ошибка регистрации", msg)

        # Остаемся на панели аутентификации
        self.show_auth_panel_ui_action(f"Подключено. {msg if status != 'success' else 'Введите данные для входа.'}")

    @Slot(dict)
    def handle_chat_list_response(self, payload: dict):
        chats = payload.get("chats", [])
        main_window_logger.info(f"СИГНАЛ: Получен список из {len(chats)} чатов.")

        if self.stacked_widget.currentWidget() == self.chat_list_panel_widget:
            self.chat_list_panel_widget.update_chat_list(chats)
            self.status_label.setText(f"Статус: Список чатов ({self.current_username})")
        else:
            main_window_logger.warning("Получен список чатов, но панель списка чатов не активна. UI не обновлен.")

    @Slot(dict)
    def handle_chat_history_response(self, payload: dict):
        chat_id_history = payload.get("chat_id")
        messages = payload.get("messages", [])
        main_window_logger.info(f"СИГНАЛ: Получена история для чата ID {chat_id_history} ({len(messages)} сообщений).")

        if self.active_chat_id == chat_id_history and self.stacked_widget.currentWidget() == self.chat_panel_widget:
            self.chat_panel_widget.display_history(messages)
        else:
            main_window_logger.warning(
                f"Получена история для чата {chat_id_history}, но активен другой чат ({self.active_chat_id}) или панель чата не видна.")

    @Slot(dict)
    def handle_incoming_chat_message(self, payload: dict):
        chat_id_msg = payload.get("chat_id")
        sender = payload.get("sender_username")  # Используем username отправителя
        text = payload.get("text")
        timestamp_iso = payload.get("timestamp", "")

        main_window_logger.info(f"СИГНАЛ: Входящее сообщение в чат ID {chat_id_msg} от {sender}: {text}")

        # Обновляем список чатов, чтобы последнее сообщение и порядок обновились
        # Это также может поднять чат вверх или как-то его выделить (пока просто обновление)
        if self.stacked_widget.currentWidget() == self.chat_list_panel_widget or self.active_chat_id != chat_id_msg:
            self.attempt_request_chat_list()

        if self.active_chat_id == chat_id_msg and self.stacked_widget.currentWidget() == self.chat_panel_widget:
            self.chat_panel_widget.add_message_to_display(sender, text, timestamp_iso, False)  # False - не от себя
        elif self.stacked_widget.currentWidget() != self.chat_panel_widget or self.active_chat_id != chat_id_msg:
            # Сообщение для неактивного чата
            main_window_logger.info(f"Новое сообщение в неактивном чате ID {chat_id_msg} от {sender}.")
            # Можно добавить более заметное уведомление
            # Например, обновить текст элемента в self.chat_list_panel_widget или счетчик
            QMessageBox.information(self, "Новое сообщение", f"Новое сообщение от {sender} в другом чате:\n'{text}'")

    @Slot(dict)
    def handle_error_notification(self, payload: dict):
        error_msg = payload.get("message")
        main_window_logger.warning(f"СИГНАЛ: Уведомление об ошибке от сервера: {error_msg}")
        if self.stacked_widget.currentWidget() == self.chat_panel_widget and self.active_chat_id is not None:
            self.chat_panel_widget.add_server_notification(error_msg)
        else:
            QMessageBox.warning(self, "Серверное уведомление", error_msg)
            if self.stacked_widget.currentWidget() == self.auth_panel_widget:
                self.auth_panel_widget.set_buttons_enabled(True)  # Разблокируем кнопки на AuthPanel

    @Slot(str, dict)
    def handle_unknown_message(self, msg_type: str, payload: dict):
        main_window_logger.warning(
            f"СИГНАЛ: Получен неизвестный тип сообщения от сервера: {msg_type}, payload: {payload}")
        # QMessageBox.information(self, "Неизвестное сообщение", f"Получено неизвестное сообщение от сервера: {msg_type}")

    def closeEvent(self, event):
        """Обработка события закрытия окна."""
        main_window_logger.info("Окно клиента закрывается. Отключение от сервера через SocketHandler.")
        self.socket_handler.disconnect_from_host()
        # waitForDisconnected здесь не нужен, т.к. приложение и так закрывается.
        event.accept()

    @Slot()  # Явно помечаем как слот Qt
    def handle_connected_to_server(self):
        main_window_logger.info(f"СИГНАЛ: Успешно подключено к серверу (через SocketHandler).")
        # self.socket_handler.get_peer_address_info() может вернуть None, если сокет уже закрылся,
        # но в момент сигнала connected он должен быть доступен.
        peer_info = self.socket_handler.get_peer_address_info()
        self.show_auth_panel_ui_action(f"Подключено к {peer_info if peer_info else 'серверу'}. Введите данные.")
        # Убедимся, что кнопка подключения на ConnectPanel деактивирована
        if hasattr(self, 'connect_panel_widget'):
            self.connect_panel_widget.set_button_enabled(False)

    @Slot()
    def handle_disconnected_from_server(self):
        main_window_logger.info("СИГНАЛ: Отключено от сервера (через SocketHandler).")
        self.current_username = None
        self.current_user_id = None
        self.active_chat_id = None
        self.active_chat_name = None
        # self.active_chat_data = None # Если вы его использовали

        if hasattr(self, 'chat_list_panel_widget'):  # Проверка на существование атрибута
            self.chat_list_panel_widget.update_chat_list([])  # Очищаем список чатов
        if hasattr(self, 'chat_panel_widget'):  # Проверка на существование атрибута
            self.chat_panel_widget.chat_display.clear()  # Очищаем текущий чат, если был открыт

        # Переключаемся на панель подключения и обновляем статус
        self.show_connect_panel_ui_action("Соединение с сервером разорвано.")
        # QMessageBox здесь обычно не нужен, так как UI уже обновился
        # QMessageBox.information(self, "Отключено", "Соединение с сервером потеряно или закрыто.")

    @Slot(QAbstractSocket.SocketError, str)  # Указываем типы аргументов для слота
    def handle_socket_error(self, socket_error_enum: QAbstractSocket.SocketError, error_string: str):
        main_window_logger.error(f"СИГНАЛ: Ошибка сокета: {socket_error_enum} - {error_string} (через SocketHandler).")

        # Сбрасываем состояние пользователя и чата при любой ошибке сокета, которая приводит к разрыву
        self.current_username = None
        self.current_user_id = None
        self.active_chat_id = None
        self.active_chat_name = None

        # Переключаемся на панель подключения и отображаем ошибку
        self.show_connect_panel_ui_action(f"Ошибка подключения: {error_string}")

        # Не показываем QMessageBox при RemoteHostClosedError,
        # так как handle_disconnected_from_server обычно вызывается после этого и обновляет UI.
        if socket_error_enum != QAbstractSocket.SocketError.RemoteHostClosedError:
            QMessageBox.critical(self, "Ошибка сокета", f"Произошла ошибка: {error_string}")