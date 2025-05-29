# client/main_window.py
import sys
import json
from datetime import datetime  # Импорт datetime в начало файла

from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                               QLabel, QLineEdit, QPushButton, QTextEdit, QMessageBox,
                               QListWidget, QListWidgetItem, QStackedWidget)
from PySide6.QtNetwork import QAbstractSocket  # QTcpSocket больше не нужен здесь напрямую
from PySide6.QtCore import Qt, Slot

# Настройка пути для импорта logger.py из корневой папки проекта
import os

CURRENT_DIR_MW = os.path.dirname(os.path.abspath(__file__))  # client/
PROJECT_ROOT_MW = os.path.dirname(CURRENT_DIR_MW)  # ms/
sys.path.append(PROJECT_ROOT_MW)
from logger import setup_logger

# Импортируем наш SocketHandler
from .network.socket_handler import SocketHandler

main_window_logger = setup_logger('MainWindow', 'client_main_window_refactored')


class ChatClientWindow(QWidget):
    def __init__(self):
        super().__init__()
        main_window_logger.info("Инициализация ChatClientWindow...")
        self.setWindowTitle("Мессенджер Клиент v0.4 - Рефакторинг")
        self.setGeometry(200, 200, 600, 550)

        # --- Создаем SocketHandler ---
        self.socket_handler = SocketHandler(self)

        # --- Подключаем сигналы от SocketHandler к методам этого класса ---
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
        self.active_chat_name = None
        # self.active_chat_data = None # Пока не используется явно

        self.init_ui()
        self.switch_to_panel(self.connect_panel)
        self.status_label.setText("Статус: Отключен")

        main_window_logger.info("UI и SocketHandler для ChatClientWindow инициализированы.")



    def init_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.status_label = QLabel("Статус: Отключен")

        self.stacked_widget = QStackedWidget()
        self.main_layout.addWidget(self.stacked_widget)
        self.main_layout.addWidget(self.status_label)

        # --- 1. Панель подключения ---
        self.connect_panel = QWidget()
        connect_layout = QVBoxLayout(self.connect_panel)
        self.ip_input = QLineEdit("127.0.0.1")
        self.port_input = QLineEdit("65432")
        self.connect_button = QPushButton("Подключиться к Серверу")
        self.connect_button.clicked.connect(self.attempt_server_connection)
        connect_layout.addWidget(QLabel("IP Сервера:"))
        connect_layout.addWidget(self.ip_input)
        connect_layout.addWidget(QLabel("Порт Сервера:"))
        connect_layout.addWidget(self.port_input)
        connect_layout.addWidget(self.connect_button)
        connect_layout.addStretch(1)
        self.stacked_widget.addWidget(self.connect_panel)

        # --- 2. Панель аутентификации ---
        self.auth_panel = QWidget()
        auth_layout = QVBoxLayout(self.auth_panel)
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Имя пользователя (логин)")
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Пароль")
        self.password_input.setEchoMode(QLineEdit.Password)
        auth_buttons_layout = QHBoxLayout()
        self.login_button = QPushButton("Войти")
        self.login_button.clicked.connect(self.attempt_login)
        self.register_button = QPushButton("Зарегистрироваться")
        self.register_button.clicked.connect(self.attempt_registration)
        auth_buttons_layout.addWidget(self.login_button)
        auth_buttons_layout.addWidget(self.register_button)
        auth_layout.addWidget(QLabel("Имя пользователя:"))
        auth_layout.addWidget(self.username_input)
        auth_layout.addWidget(QLabel("Пароль:"))
        auth_layout.addWidget(self.password_input)
        auth_layout.addLayout(auth_buttons_layout)
        auth_layout.addStretch(1)
        self.stacked_widget.addWidget(self.auth_panel)

        # --- 3. Панель списка чатов ---
        self.chat_list_panel = QWidget()
        chat_list_layout = QVBoxLayout(self.chat_list_panel)

        new_chat_group_layout = QHBoxLayout()
        self.new_chat_user_input = QLineEdit()
        self.new_chat_user_input.setPlaceholderText("Никнейм для нового/существующего чата...")
        self.start_or_open_chat_button = QPushButton("Открыть / Начать чат")
        self.start_or_open_chat_button.clicked.connect(self.on_start_or_open_chat_with_user)
        new_chat_group_layout.addWidget(self.new_chat_user_input)
        new_chat_group_layout.addWidget(self.start_or_open_chat_button)

        self.chat_list_widget = QListWidget()
        self.chat_list_widget.itemDoubleClicked.connect(self.on_chat_list_item_selected)

        self.refresh_chat_list_button = QPushButton("Обновить список чатов")
        self.refresh_chat_list_button.clicked.connect(self.attempt_request_chat_list)

        chat_list_layout.addWidget(QLabel("Начать новый или открыть существующий чат:"))
        chat_list_layout.addLayout(new_chat_group_layout)
        chat_list_layout.addWidget(QLabel("Ваши активные чаты:"))
        chat_list_layout.addWidget(self.chat_list_widget)
        chat_list_layout.addWidget(self.refresh_chat_list_button)
        self.stacked_widget.addWidget(self.chat_list_panel)

        # --- 4. Панель активного чата ---
        self.chat_panel = QWidget()
        chat_panel_layout = QVBoxLayout(self.chat_panel)
        self.chat_panel_back_button = QPushButton("<< Назад к списку чатов")
        self.chat_panel_back_button.clicked.connect(self.show_chat_list_panel_ui_action)  # Новый метод для действия UI
        self.chat_panel_title_label = QLabel("Чат с: Не выбран")
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.message_input = QLineEdit()
        self.message_input.setPlaceholderText("Введите сообщение...")
        self.send_button = QPushButton("Отправить")
        self.send_button.clicked.connect(self.attempt_send_message_to_active_chat)

        chat_panel_layout.addWidget(self.chat_panel_back_button)
        chat_panel_layout.addWidget(self.chat_panel_title_label)
        chat_panel_layout.addWidget(self.chat_display)
        chat_panel_layout.addWidget(self.message_input)
        chat_panel_layout.addWidget(self.send_button)
        self.stacked_widget.addWidget(self.chat_panel)

        # Привязка Enter
        self.message_input.returnPressed.connect(self.send_button.click)
        self.password_input.returnPressed.connect(self.login_button.click)
        self.new_chat_user_input.returnPressed.connect(self.start_or_open_chat_button.click)

    def switch_to_panel(self, panel_widget):
        self.stacked_widget.setCurrentWidget(panel_widget)
        is_connected = self.socket_handler.get_socket_state() == QAbstractSocket.ConnectedState
        is_authenticated = self.current_user_id is not None

        self.connect_button.setEnabled(panel_widget == self.connect_panel and not is_connected)
        self.login_button.setEnabled(panel_widget == self.auth_panel and is_connected)
        self.register_button.setEnabled(panel_widget == self.auth_panel and is_connected)
        self.start_or_open_chat_button.setEnabled(panel_widget == self.chat_list_panel and is_authenticated)
        self.refresh_chat_list_button.setEnabled(panel_widget == self.chat_list_panel and is_authenticated)

        # Кнопка отправки активна, только если мы в панели чата, аутентифицированы И есть активный chat_id
        # (или если мы разрешим отправку в "новый" чат без ID, но это усложнение для начала)
        can_send_message = (panel_widget == self.chat_panel and
                            is_authenticated and
                            self.active_chat_id is not None)  # Или self.active_chat_name для нового чата
        self.send_button.setEnabled(can_send_message)



    # --- Методы для переключения панелей и обновления статуса ---
    def show_connect_panel_ui_action(self,
                                     message="Отключен"):  # Добавляем _ui_action для методов, вызываемых из UI напрямую
        self.switch_to_panel(self.connect_panel)
        self.status_label.setText(f"Статус: {message}")
        main_window_logger.info(f"UI: Панель подключения. Статус: {message}")

    def show_auth_panel_ui_action(self, message="Введите данные для входа/регистрации"):
        self.switch_to_panel(self.auth_panel)
        self.status_label.setText(f"Статус: {message}")
        main_window_logger.info(f"UI: Панель аутентификации. Статус: {message}")

    def show_chat_list_panel_ui_action(self):  # Вызывается кнопкой "Назад" или после логина
        if not self.current_user_id:
            self.show_auth_panel_ui_action("Сначала войдите или зарегистрируйтесь.")
            return
        self.active_chat_id = None  # Сбрасываем активный чат при возврате к списку
        self.active_chat_name = None
        self.switch_to_panel(self.chat_list_panel)
        self.status_label.setText(f"Статус: Вы вошли как {self.current_username} (ID: {self.current_user_id})")
        main_window_logger.info(f"UI: Панель списка чатов для {self.current_username}.")
        self.attempt_request_chat_list()

    def open_chat_panel_ui_action(self, chat_id, chat_name_to_display):  # chat_name_to_display - имя собеседника/группы
        """Открывает панель чата с известными данными (обычно после выбора из списка)."""
        self.active_chat_id = chat_id
        self.active_chat_name = chat_name_to_display
        self.chat_panel_title_label.setText(f"Чат с: {self.active_chat_name}")
        self.chat_display.clear()  # Очищаем перед загрузкой новой истории
        self.switch_to_panel(self.chat_panel)
        self.status_label.setText(f"В чате с {self.active_chat_name}")
        main_window_logger.info(f"UI: Открыт чат ID {self.active_chat_id} ({self.active_chat_name}). Запрос истории.")

        if self.active_chat_id:
            self.chat_display.append(f"<i>Загрузка истории для чата ID {self.active_chat_id}...</i>")
            self.attempt_request_chat_history(self.active_chat_id)
        else:
            # Это случай "нового" чата, где ID еще не определен сервером.
            # Сервер должен будет создать чат при первой отправке сообщения.
            self.chat_display.append(f"<i>Начните новый диалог с {self.active_chat_name}.</i>")
            main_window_logger.info(f"UI: Открыт новый чат (без ID) с {self.active_chat_name}.")
            self.send_button.setEnabled(True)  # Разрешаем отправку в новый чат

    # --- Методы-инициаторы действий (вызывают методы SocketHandler) ---
    def attempt_server_connection(self):
        host = self.ip_input.text().strip()
        port_str = self.port_input.text().strip()
        if not host or not port_str:
            QMessageBox.warning(self, "Подключение", "IP адрес и порт не могут быть пустыми.")
            return
        try:
            port = int(port_str)
            if not (0 < port < 65536): raise ValueError("Порт вне диапазона")
        except ValueError:
            QMessageBox.warning(self, "Ошибка", "Порт должен быть числом от 1 до 65535.")
            main_window_logger.warning(f"Некорректный порт: {port_str}")
            return

        main_window_logger.info(f"Попытка подключения к {host}:{port} через SocketHandler.")
        self.status_label.setText("Статус: Подключение к серверу...")
        self.connect_button.setEnabled(False)
        self.socket_handler.connect_to_host(host, port)

    def attempt_registration(self):
        username = self.username_input.text().strip()
        password = self.password_input.text()
        if not username or not password:
            QMessageBox.warning(self, "Регистрация", "Имя пользователя и пароль не могут быть пустыми.")
            return
        if len(password) < 4:
            QMessageBox.warning(self, "Регистрация", "Пароль должен быть не менее 4 символов.")
            return

        main_window_logger.info(f"Попытка регистрации для {username} через SocketHandler.")
        self.status_label.setText("Статус: Регистрация...")
        self.login_button.setEnabled(False);
        self.register_button.setEnabled(False)
        message_data = {"type": "register", "payload": {"username": username, "password": password}}
        self.socket_handler.send_json_message(message_data)

    def attempt_login(self):
        username = self.username_input.text().strip()
        password = self.password_input.text()
        if not username or not password:
            QMessageBox.warning(self, "Вход", "Имя пользователя и пароль не могут быть пустыми.")
            return

        main_window_logger.info(f"Попытка входа для {username} через SocketHandler.")
        self.status_label.setText("Статус: Вход...")
        self.login_button.setEnabled(False);
        self.register_button.setEnabled(False)
        message_data = {"type": "login", "payload": {"username": username, "password": password}}
        self.socket_handler.send_json_message(message_data)

    def attempt_request_chat_list(self):
        if not self.current_user_id:
            main_window_logger.warning("Попытка запроса списка чатов без аутентификации (attempt).")
            return
        main_window_logger.info(f"Пользователь {self.current_username} запрашивает список чатов через SocketHandler.")
        self.status_label.setText(f"Статус: Обновление списка чатов... ({self.current_username})")
        message_data = {"type": "request_chat_list", "payload": {}}
        self.socket_handler.send_json_message(message_data)

    def attempt_request_chat_history(self, chat_id):
        # chat_id может быть None для нового чата, SocketHandler не будет отправлять запрос
        if chat_id is None:
            main_window_logger.info(
                f"Не запрашиваем историю, так как chat_id не известен (новый чат с {self.active_chat_name}).")
            # self.chat_display.setText(f"<i>Начните новый диалог с {self.active_chat_name}.</i>") # Уже делается в open_chat_panel_ui_action
            return
        if not self.current_user_id: return
        main_window_logger.info(f"Запрос истории для чата ID: {chat_id} через SocketHandler.")
        message_data = {"type": "request_chat_history", "payload": {"chat_id": chat_id}}
        self.socket_handler.send_json_message(message_data)

    def attempt_send_message_to_active_chat(self):
        if not self.current_user_id:
            QMessageBox.warning(self, "Ошибка", "Вы не вошли на сервер.")
            return

        text = self.message_input.text().strip()
        if not text: return  # Не отправляем пустые сообщения

        # Ключевой момент: как получить chat_id для нового чата?
        # Текущая логика: on_start_or_open_chat_with_user открывает панель с chat_id=None.
        # Сервер должен создать чат при ПЕРВОМ сообщении и вернуть chat_id (это сложно).
        # ИЛИ клиент должен сначала "создать/получить" чат.
        # Пока что, если active_chat_id is None, мы не сможем отправить сообщение с chat_id.
        # Это место для будущей доработки протокола "создания чата".

        if self.active_chat_id is None:
            # Это означает, что мы в "новом" чате, для которого ID еще не определен.
            # Мы должны отправить сообщение, указав target_username (self.active_chat_name)
            # Это потребует от сервера обработки "send_message_to_chat" без chat_id, но с target_username.
            # Либо, как я писал ранее, on_start_or_open_chat_with_user должен сначала получить chat_id.
            # ДЛЯ ТЕКУЩЕЙ РЕАЛИЗАЦИИ СЕРВЕРА (который ожидает chat_id):
            QMessageBox.warning(self, "Ошибка",
                                "Не удалось определить ID чата. Попробуйте заново выбрать или создать чат, чтобы сервер его зарегистрировал.")
            main_window_logger.error(
                f"Попытка отправки сообщения, когда active_chat_id is None. active_chat_name: {self.active_chat_name}")
            return

        payload_data = {"chat_id": self.active_chat_id, "text": text}
        main_window_logger.info(
            f"Отправка сообщения в чат ID {self.active_chat_id} (для {self.active_chat_name}): {text} через SocketHandler.")

        if self.socket_handler.send_json_message({"type": "send_message_to_chat", "payload": payload_data}):
            # Оптимистичное отображение
            # Получаем текущее время для отображения (локальное, т.к. от сервера еще не пришло)
            now_ts = datetime.now().strftime("%Y-%m-%d %H:%M")
            self.chat_display.append(f"<b>Вы</b>: {text} <small><i>({now_ts})</i></small>")
            self.message_input.clear()
            self.message_input.setFocus()
            # Обновляем кнопку отправки, если она была неактивна
            self.switch_to_panel(self.chat_panel)  # Обновит состояние кнопки send_button



    # --- Обработчики UI действий (вызываются кнопками и элементами списка) ---
    def on_start_or_open_chat_with_user(self):
        if not self.current_user_id:
            QMessageBox.warning(self, "Действие невозможно", "Сначала войдите или зарегистрируйтесь.")
            return

        target_username = self.new_chat_user_input.text().strip()
        if not target_username:
            QMessageBox.warning(self, "Новый чат", "Введите имя пользователя для начала чата.")
            return
        if target_username == self.current_username:
            QMessageBox.warning(self, "Новый чат", "Нельзя начать чат с самим собой таким образом.")
            return

        main_window_logger.info(f"Попытка начать/открыть чат с: {target_username}")

        # 1. Ищем чат в существующем списке (если он уже был загружен)
        for i in range(self.chat_list_widget.count()):
            item = self.chat_list_widget.item(i)
            chat_data = item.data(Qt.UserRole)
            # Убедимся, что chat_data не None и содержит нужные ключи
            if chat_data and chat_data.get("chat_type") == "direct" and chat_data.get(
                    "other_username") == target_username:
                main_window_logger.info(f"Найден существующий чат с {target_username} в списке. Открываем.")
                self.open_chat_from_list_item(item)
                self.new_chat_user_input.clear()
                return

        # 2. Если чат не найден в списке, это может быть новый диалог ИЛИ существующий, но еще не загруженный.
        #    Протокол: Клиент должен инициировать создание/получение ID чата.
        #    Пока что мы сделаем УПРОЩЕНИЕ: мы откроем панель чата, но БЕЗ chat_id.
        #    Первое сообщение, отправленное в такой чат, должно будет инициировать его создание на сервере.
        #    Это потребует, чтобы сервер мог обработать send_message_to_chat, где chat_id=None, но есть target_username.
        #    ИЛИ, сервер в ответе на send_message_to_chat для нового чата должен вернуть chat_id.
        #    ТЕКУЩАЯ РЕАЛИЗАЦИЯ СЕРВЕРА ожидает chat_id в send_message_to_chat.
        #    Значит, нам нужен способ "создать" чат на сервере перед отправкой первого сообщения.
        #    Пока что, для v0.4, если чата нет в списке, мы просто откроем панель, но отправка будет заблокирована,
        #    пока мы не реализуем механизм получения chat_id для нового чата.
        main_window_logger.info(
            f"Новый (или не загруженный) диалог с {target_username}. Открытие панели чата (ID пока не известен).")
        self.open_chat_panel_ui_action(None, target_username)  # chat_id is None, chat_name is target_username
        self.new_chat_user_input.clear()
        # Кнопка отправки будет неактивна, т.к. active_chat_id is None (см. switch_to_panel)
        QMessageBox.information(self, "Новый чат",
                                f"Открыт новый чат с {target_username}.\nИстория будет запрошена после создания чата на сервере (отправьте первое сообщение). \n(Примечание: текущая версия сервера может не создать чат без первого сообщения с chat_id. Это будет доработано.)")

    def on_chat_list_item_selected(self, item: QListWidgetItem):
        """Вызывается при двойном клике на чат в списке."""
        self.open_chat_from_list_item(item)

    def open_chat_from_list_item(self, item: QListWidgetItem):
        chat_data = item.data(Qt.UserRole)
        if chat_data:
            chat_id = chat_data.get("chat_id")
            # Для direct чатов имя чата (chat_name) в списке - это имя собеседника
            chat_name_to_display = chat_data.get("chat_name")

            main_window_logger.info(f"Выбран чат из списка: ID {chat_id}, Отображаемое имя {chat_name_to_display}")
            self.open_chat_panel_ui_action(chat_id, chat_name_to_display)
        else:
            main_window_logger.warning("Выбран элемент списка чатов без сохраненных данных.")

    # --- Обработка ответов сервера (слоты для сигналов SocketHandler) ---
    @Slot(dict)
    def handle_login_status_response(self, payload: dict):
        # ... (этот метод был в части 2, здесь полностью) ...
        main_window_logger.info(f"СИГНАЛ: Получен статус логина: {payload}")
        status = payload.get("status")
        msg = payload.get("message")
        self.login_button.setEnabled(True);
        self.register_button.setEnabled(True)  # Разблокируем кнопки

        if status == "success":
            self.current_username = payload.get("username")
            self.current_user_id = payload.get("user_id")
            main_window_logger.info(f"Логин успешен как {self.current_username} (ID: {self.current_user_id}).")
            self.username_input.clear()
            self.password_input.clear()
            self.show_chat_list_panel_ui_action()  # Переходим к списку чатов
        else:
            main_window_logger.warning(f"Ошибка логина: {msg}")
            QMessageBox.warning(self, "Ошибка входа", msg)
            self.show_auth_panel_ui_action(f"Подключено. Ошибка входа: {msg}")

    @Slot(dict)
    def handle_register_status_response(self, payload: dict):
        # ... (этот метод был в части 2, здесь полностью) ...
        main_window_logger.info(f"СИГНАЛ: Получен статус регистрации: {payload}")
        status = payload.get("status")
        msg = payload.get("message")
        self.login_button.setEnabled(True);
        self.register_button.setEnabled(True)  # Разблокируем кнопки

        if status == "success":
            QMessageBox.information(self, "Регистрация успешна", msg + "\nТеперь вы можете войти.")
        else:
            QMessageBox.warning(self, "Ошибка регистрации", msg)
        # Остаемся на панели аутентификации
        self.show_auth_panel_ui_action(f"Подключено. {msg if status != 'success' else 'Введите данные для входа.'}")

    @Slot(dict)
    def handle_chat_list_response(self, payload: dict):
        # ... (этот метод был в части 2, здесь полностью) ...
        chats = payload.get("chats", [])
        main_window_logger.info(f"СИГНАЛ: Получен список из {len(chats)} чатов.")
        self.chat_list_widget.clear()

        # Проверяем, активна ли панель списка чатов
        if not self.stacked_widget.currentWidget() == self.chat_list_panel:
            main_window_logger.warning(
                "Получен список чатов, но панель списка чатов не активна. Обновление UI отложено.")
            return  # Не обновляем UI, если панель не видна

        if not chats:
            self.chat_list_widget.addItem("У вас пока нет чатов. Начните новый!")
        else:
            for chat_info in chats:
                item_text = f"{chat_info.get('chat_name', 'Неизвестный чат')}"
                last_msg_preview = chat_info.get('last_message_text', '')
                if last_msg_preview and len(last_msg_preview) > 30:
                    last_msg_preview = last_msg_preview[:30] + "..."
                if last_msg_preview:
                    item_text += f"\n  └ {last_msg_preview}"
                list_item = QListWidgetItem(item_text)
                list_item.setData(Qt.UserRole, chat_info)
                self.chat_list_widget.addItem(list_item)
        self.status_label.setText(f"Статус: Список чатов ({self.current_username})")

    @Slot(dict)
    def handle_chat_history_response(self, payload: dict):
        # ... (этот метод был в части 2, здесь полностью) ...
        chat_id_history = payload.get("chat_id")
        messages = payload.get("messages", [])
        main_window_logger.info(f"СИГНАЛ: Получена история для чата ID {chat_id_history} ({len(messages)} сообщений).")

        if self.active_chat_id == chat_id_history and self.stacked_widget.currentWidget() == self.chat_panel:
            self.chat_display.clear()
            if not messages:
                self.chat_display.append(f"<i>История с {self.active_chat_name} пуста. Начните диалог!</i>")
            else:
                for msg_data in messages:
                    sender = msg_data.get("sender_username");
                    text = msg_data.get("text")
                    timestamp_iso = msg_data.get("timestamp", "")
                    display_ts = ""
                    if timestamp_iso:
                        try:
                            dt_obj = datetime.fromisoformat(
                                timestamp_iso.replace('Z', '+00:00')); display_ts = dt_obj.strftime("%Y-%m-%d %H:%M")
                        except ValueError:
                            display_ts = timestamp_iso.split('T')[0]
                    display_sender_name = "Вы" if sender == self.current_username else sender
                    self.chat_display.append(
                        f"<b>{display_sender_name}</b>: {text} <small><i>({display_ts})</i></small>")
        else:
            main_window_logger.warning(
                f"Получена история для чата {chat_id_history}, но активен другой чат ({self.active_chat_id}) или панель чата не видна.")

    @Slot(dict)
    def handle_incoming_chat_message(self, payload: dict):
        # ... (этот метод был в части 2, здесь полностью) ...
        chat_id_msg = payload.get("chat_id")
        sender = payload.get("sender_username")
        text = payload.get("text")
        timestamp_iso = payload.get("timestamp", "")

        main_window_logger.info(f"СИГНАЛ: Входящее сообщение в чат ID {chat_id_msg} от {sender}: {text}")

        display_ts_incoming = ""
        if timestamp_iso:
            try:
                dt_obj = datetime.fromisoformat(
                    timestamp_iso.replace('Z', '+00:00')); display_ts_incoming = dt_obj.strftime("%Y-%m-%d %H:%M")
            except ValueError:
                display_ts_incoming = timestamp_iso.split('T')[0]

        # Обновляем список чатов, чтобы последнее сообщение и порядок обновились
        # Это также подсветит чат, если он не активен (пока нет явной подсветки, но список обновится)
        self.attempt_request_chat_list()

        if self.active_chat_id == chat_id_msg and self.stacked_widget.currentWidget() == self.chat_panel:
            self.chat_display.append(f"<b>{sender}</b>: {text} <small><i>({display_ts_incoming})</i></small>")
        else:
            main_window_logger.info(f"Новое сообщение в неактивном чате ID {chat_id_msg} от {sender}.")
            # Вместо QMessageBox, которое блокирует, можно сделать неблокирующее уведомление или просто обновить список.
            # QMessageBox.information(self, "Новое сообщение", f"Новое сообщение от {sender} в чате (ID: {chat_id_msg}):\n'{text}'")
            # Обновление списка уже вызвано выше. Можно добавить всплывающее системное уведомление позже.

    @Slot(dict)
    def handle_error_notification(self, payload: dict):
        # ... (этот метод был в части 2, здесь полностью) ...
        error_msg = payload.get("message")
        main_window_logger.warning(f"СИГНАЛ: Уведомление об ошибке от сервера: {error_msg}")
        if self.stacked_widget.currentWidget() == self.chat_panel and self.active_chat_id is not None:
            self.chat_display.append(f"<i style='color:red;'>СЕРВЕР: {error_msg}</i>")
        else:
            QMessageBox.warning(self, "Серверное уведомление", error_msg)
            if self.stacked_widget.currentWidget() == self.auth_panel:
                self.login_button.setEnabled(True);
                self.register_button.setEnabled(True)

    @Slot(str, dict)
    def handle_unknown_message(self, msg_type: str, payload: dict):
        # ... (этот метод был в части 2, здесь полностью) ...
        main_window_logger.warning(
            f"СИГНАЛ: Получен неизвестный тип сообщения от сервера: {msg_type}, payload: {payload}")

    def closeEvent(self, event):
        # ... (этот метод был в части 2, здесь полностью) ...
        main_window_logger.info("Окно клиента закрывается. Отключение от сервера через SocketHandler.")
        self.socket_handler.disconnect_from_host()
        event.accept()

    @Slot()
    def handle_connected_to_server(self):
        main_window_logger.info(f"СИГНАЛ: Успешно подключено к серверу (через SocketHandler).")
        peer_info = self.socket_handler.get_peer_address_info()
        self.show_auth_panel_ui_action(f"Подключено к {peer_info if peer_info else 'серверу'}. Введите данные.")


    @Slot()  # Явно помечаем как слот Qt
    def handle_disconnected_from_server(self):
        main_window_logger.info("СИГНАЛ: Отключено от сервера (через SocketHandler).")
        self.current_username = None
        self.current_user_id = None
        self.active_chat_id = None
        self.active_chat_name = None
        # self.active_chat_data = None # Если вы его использовали

        self.chat_list_widget.clear()  # Очищаем список чатов
        self.chat_display.clear()  # Очищаем текущий чат, если был открыт

        # Переключаемся на панель подключения и обновляем статус
        self.show_connect_panel_ui_action("Соединение с сервером разорвано.")
        # QMessageBox здесь обычно не нужен, так как UI уже обновился
        # QMessageBox.information(self, "Отключено", "Соединение с сервером потеряно или закрыто.")


    @Slot(QAbstractSocket.SocketError, str)  # Указываем типы аргументов для слота
    def handle_socket_error(self, socket_error_enum: QAbstractSocket.SocketError, error_string: str):
        main_window_logger.error(f"СИГНАЛ: Ошибка сокета: {socket_error_enum} - {error_string} (через SocketHandler).")

        # Переключаемся на панель подключения и отображаем ошибку
        self.show_connect_panel_ui_action(f"Ошибка подключения: {error_string}")

        # Не показываем QMessageBox при RemoteHostClosedError,
        # так как handle_disconnected_from_server обычно вызывается после этого и обновляет UI.
        # Также, если ошибка произошла до успешного подключения, disconnected может не вызваться.
        if socket_error_enum != QAbstractSocket.SocketError.RemoteHostClosedError:
            QMessageBox.critical(self, "Ошибка сокета", f"Произошла ошибка: {error_string}")

        # Сбрасываем состояние, если оно было установлено
        self.current_username = None
        self.current_user_id = None
        self.active_chat_id = None
        self.active_chat_name = None
# Точка входа приложения (если этот файл запускается напрямую, а не run_client.py)
# Для новой структуры с run_client.py, этот блок if __name__ == '__main__': здесь не так критичен,
# но его можно оставить для возможности запуска этого файла напрямую для отладки UI.
if __name__ == '__main__':
    main_window_logger.info("Запуск ChatClientWindow напрямую (для отладки UI)...")
    app = QApplication(sys.argv)
    window = ChatClientWindow()
    window.show()
    sys.exit(app.exec())

