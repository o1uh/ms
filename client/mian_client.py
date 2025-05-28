# client/main_client.py (или main_window.py)
import sys
import json
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                               QLabel, QLineEdit, QPushButton, QTextEdit, QMessageBox,
                               QListWidget, QListWidgetItem, QStackedWidget)
from PySide6.QtNetwork import QTcpSocket, QAbstractSocket
from PySide6.QtCore import Qt

# Настройка пути для импорта logger.py из корневой папки проекта
import os

# Определение абсолютного пути к текущему файлу и затем к корневой папке
# Это более надежно, чем относительные '../'
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
sys.path.append(PROJECT_ROOT)
from logger import setup_logger  # Предполагается, что logger.py в PROJECT_ROOT

client_logger = setup_logger('ClientApp', 'client_session')


class ChatClientWindow(QWidget):  # Или QMainWindow, если предпочитаете
    def __init__(self):
        super().__init__()
        client_logger.info("Инициализация главного окна клиента...")
        self.setWindowTitle("Мессенджер Клиент v0.3 - Список чатов")  # Обновляем версию
        self.setGeometry(200, 200, 600, 550)  # Немного больше для нового UI

        self.socket = QTcpSocket(self)
        self.socket.connected.connect(self.on_connected_to_server)
        self.socket.disconnected.connect(self.on_disconnected_from_server)
        self.socket.errorOccurred.connect(self.on_socket_error)
        self.socket.readyRead.connect(self.on_ready_read)

        self.client_buffer = ""
        self.current_username = None
        self.current_user_id = None

        self.active_chat_id = None
        self.active_chat_name = None  # Имя собеседника или группы
        self.active_chat_data = None  # Полные данные о чате из списка

        self.init_ui()
        self.switch_to_panel(self.connect_panel)
        self.status_label.setText("Статус: Отключен")

        client_logger.info("UI клиента инициализирован.")

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
        self.connect_button.clicked.connect(self.connect_to_server)
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
        self.login_button.clicked.connect(self.send_login_request)
        self.register_button = QPushButton("Зарегистрироваться")
        self.register_button.clicked.connect(self.send_register_request)
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
        self.refresh_chat_list_button.clicked.connect(self.send_request_chat_list)

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
        self.chat_panel_back_button.clicked.connect(self.show_chat_list_panel)
        self.chat_panel_title_label = QLabel("Чат с: Не выбран")
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.message_input = QLineEdit()
        self.message_input.setPlaceholderText("Введите сообщение...")
        self.send_button = QPushButton("Отправить")
        self.send_button.clicked.connect(self.send_message_to_active_chat)

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
        # Обновление доступности кнопок и состояния можно вынести в отдельные методы или делать здесь
        is_connected = self.socket.state() == QAbstractSocket.ConnectedState
        is_authenticated = self.current_user_id is not None

        self.connect_button.setEnabled(panel_widget == self.connect_panel and not is_connected)
        self.login_button.setEnabled(panel_widget == self.auth_panel and is_connected)
        self.register_button.setEnabled(panel_widget == self.auth_panel and is_connected)
        self.start_or_open_chat_button.setEnabled(panel_widget == self.chat_list_panel and is_authenticated)
        self.refresh_chat_list_button.setEnabled(panel_widget == self.chat_list_panel and is_authenticated)
        self.send_button.setEnabled(
            panel_widget == self.chat_panel and is_authenticated and self.active_chat_id is not None)

    def show_connect_panel(self, message="Отключен"):
        self.switch_to_panel(self.connect_panel)
        self.status_label.setText(f"Статус: {message}")
        client_logger.info(f"UI: Панель подключения. Статус: {message}")

    def show_auth_panel(self, message="Введите данные для входа/регистрации"):
        self.switch_to_panel(self.auth_panel)
        self.status_label.setText(f"Статус: {message}")
        client_logger.info(f"UI: Панель аутентификации. Статус: {message}")

    def show_chat_list_panel(self):  # message теперь не нужен, статус из self.current_username
        if not self.current_user_id:  # Если вдруг вызвали без логина
            self.show_auth_panel("Сначала войдите или зарегистрируйтесь.")
            return
        self.switch_to_panel(self.chat_list_panel)
        self.status_label.setText(f"Статус: Вы вошли как {self.current_username} (ID: {self.current_user_id})")
        client_logger.info(f"UI: Панель списка чатов для {self.current_username}.")
        self.send_request_chat_list()  # Запрашиваем список чатов при каждом показе

    def open_chat_with_data(self, chat_id, chat_name, other_username=None):
        """Открывает панель чата с известными данными."""
        self.active_chat_id = chat_id
        self.active_chat_name = chat_name  # Для direct это будет other_username
        self.chat_panel_title_label.setText(f"Чат с: {self.active_chat_name}")
        self.chat_display.clear()
        self.switch_to_panel(self.chat_panel)
        self.status_label.setText(f"В чате с {self.active_chat_name}")
        client_logger.info(f"UI: Открыт чат ID {self.active_chat_id} ({self.active_chat_name}). Запрос истории.")
        if self.active_chat_id:  # Запрашиваем историю только если chat_id известен
            self.send_request_chat_history(self.active_chat_id)
        else:  # Это новый чат, истории еще нет
            self.chat_display.append(f"<i>Начните новый диалог с {self.active_chat_name}.</i>")
            client_logger.info(f"UI: Открыт новый чат (без ID) с {self.active_chat_name}.")

    # --- Сетевые операции ---
    def connect_to_server(self):
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
            client_logger.warning(f"Некорректный порт: {port_str}")
            return

        client_logger.info(f"Попытка подключения к {host}:{port}")
        self.status_label.setText("Статус: Подключение к серверу...")
        self.connect_button.setEnabled(False)
        self.socket.connectToHost(host, port)

    def on_connected_to_server(self):
        client_logger.info(f"Успешно подключено к серверу {self.socket.peerName()}:{self.socket.peerPort()}")
        self.show_auth_panel(f"Подключено к {self.socket.peerName()}. Введите данные.")

    def on_disconnected_from_server(self):
        client_logger.info("Отключено от сервера.")
        self.current_username = None;
        self.current_user_id = None
        self.active_chat_id = None;
        self.active_chat_name = None;
        self.active_chat_data = None
        self.chat_list_widget.clear()
        self.show_connect_panel("Соединение с сервером разорвано.")
        # QMessageBox.information(self, "Отключено", "Соединение с сервером потеряно или закрыто.") # Может быть назойливо

    def on_socket_error(self, socket_error: QAbstractSocket.SocketError):
        error_message = self.socket.errorString()
        client_logger.error(f"Ошибка сокета: {socket_error} ({type(socket_error)}) - {error_message}")
        self.show_connect_panel(f"Ошибка подключения: {error_message}")
        # Не показываем QMessageBox при RemoteHostClosedError, так как on_disconnected вызовется
        if socket_error != QAbstractSocket.SocketError.RemoteHostClosedError:
            QMessageBox.critical(self, "Ошибка сокета", f"Произошла ошибка: {error_message}")

    def send_json_message(self, message_data):
        if self.socket.state() == QAbstractSocket.ConnectedState:
            try:
                json_message = json.dumps(message_data, ensure_ascii=False) + '\n'
                self.socket.write(json_message.encode('utf-8'))
                client_logger.debug(f"Отправлено на сервер: {json_message.strip()}")
                return True  # Успешная отправка
            except Exception as e:
                client_logger.error(f"Ошибка при отправке JSON: {e}", exc_info=True)
                QMessageBox.warning(self, "Ошибка отправки", f"Не удалось отправить сообщение: {e}")
        else:
            client_logger.warning("Попытка отправки сообщения при отсутствующем соединении.")
            QMessageBox.warning(self, "Нет соединения", "Нет соединения с сервером.")
        return False  # Ошибка отправки

    # ... продолжение client/main_client.py (или main_window.py) ...

    # --- Методы для аутентификации ---
    def send_register_request(self):
        username = self.username_input.text().strip()
        password = self.password_input.text()

        if not username or not password:
            QMessageBox.warning(self, "Регистрация", "Имя пользователя и пароль не могут быть пустыми.")
            return
        if len(password) < 4:
            QMessageBox.warning(self, "Регистрация", "Пароль должен быть не менее 4 символов.")
            return

        client_logger.info(f"Отправка запроса на регистрацию для: {username}")
        self.status_label.setText("Статус: Регистрация...")
        self.login_button.setEnabled(False);
        self.register_button.setEnabled(False)
        self.send_json_message({"type": "register", "payload": {"username": username, "password": password}})

    def send_login_request(self):
        username = self.username_input.text().strip()
        password = self.password_input.text()

        if not username or not password:
            QMessageBox.warning(self, "Вход", "Имя пользователя и пароль не могут быть пустыми.")
            return

        client_logger.info(f"Отправка запроса на вход для: {username}")
        self.status_label.setText("Статус: Вход...")
        self.login_button.setEnabled(False);
        self.register_button.setEnabled(False)
        self.send_json_message({"type": "login", "payload": {"username": username, "password": password}})

    # --- Методы для работы с чатами ---
    def send_request_chat_list(self):
        """Отправляет запрос на получение списка чатов."""
        if not self.current_user_id:
            client_logger.warning("Попытка запроса списка чатов без аутентификации.")
            return
        client_logger.info(f"Пользователь {self.current_username} запрашивает список чатов.")
        self.status_label.setText(f"Статус: Обновление списка чатов... ({self.current_username})")
        self.send_json_message({"type": "request_chat_list", "payload": {}})

    def on_start_or_open_chat_with_user(self):
        """Инициирует начало нового чата или открытие существующего по имени пользователя."""
        if not self.current_user_id: return  # Должны быть залогинены

        target_username = self.new_chat_user_input.text().strip()
        if not target_username:
            QMessageBox.warning(self, "Новый чат", "Введите имя пользователя для чата.")
            return
        if target_username == self.current_username:
            QMessageBox.warning(self, "Новый чат", "Нельзя начать чат с самим собой через это поле.")
            return

        client_logger.info(f"Попытка начать/открыть чат с: {target_username}")

        # Сначала ищем, нет ли уже такого чата в нашем списке
        for i in range(self.chat_list_widget.count()):
            item = self.chat_list_widget.item(i)
            chat_data = item.data(Qt.UserRole)
            if chat_data and chat_data.get("chat_type") == "direct" and chat_data.get(
                    "other_username") == target_username:
                client_logger.info(f"Найден существующий чат с {target_username} в списке. Открываем.")
                self.open_chat_from_list_item(item)
                self.new_chat_user_input.clear()
                return

        # Если чат не найден в списке, это новый диалог.
        # Мы не знаем chat_id, поэтому передадим None.
        # Сервер создаст чат при первой отправке сообщения в него.
        # Или, что лучше, мы можем отправить специальный запрос на "создание/получение" chat_id.
        # ПОКА: просто открываем панель, история будет пустой.
        client_logger.info(f"Новый диалог с {target_username}. Открытие панели чата (ID пока не известен).")
        self.open_chat_with_data(None, target_username)  # chat_id is None, chat_name is target_username
        self.new_chat_user_input.clear()

    def on_chat_list_item_selected(self, item: QListWidgetItem):
        """Вызывается при двойном клике на чат в списке."""
        self.open_chat_from_list_item(item)

    def open_chat_from_list_item(self, item: QListWidgetItem):
        chat_data = item.data(Qt.UserRole)
        if chat_data:
            chat_id = chat_data.get("chat_id")
            chat_name_to_display = chat_data.get("chat_name")  # Для direct это имя собеседника, для group - имя группы

            client_logger.info(f"Выбран чат из списка: ID {chat_id}, Отображаемое имя {chat_name_to_display}")
            self.open_chat_with_data(chat_id, chat_name_to_display)
        else:
            client_logger.warning("Выбран элемент списка чатов без сохраненных данных.")

    def send_request_chat_history(self, chat_id):
        if chat_id is None:
            client_logger.info(f"Не запрашиваем историю, так как chat_id не известен (вероятно, новый чат).")
            # В open_chat_with_data мы уже устанавливаем сообщение, если chat_id is None
            return

        if not self.current_user_id: return
        client_logger.info(f"Запрос истории для чата ID: {chat_id}")
        self.send_json_message({"type": "request_chat_history", "payload": {"chat_id": chat_id}})

    def send_message_to_active_chat(self):
        if not self.current_user_id:
            QMessageBox.warning(self, "Ошибка", "Вы не вошли на сервер.")
            return

        text = self.message_input.text().strip()
        if not text:  # Не отправляем пустые сообщения
            return

        # Если active_chat_id ЕЩЕ НЕИЗВЕСТЕН (это новый чат, инициированный пользователем),
        # то мы не можем отправить сообщение с chat_id.
        # Сервер должен был бы создать чат и вернуть его ID клиенту
        # при вызове on_start_or_open_chat_with_user, если чат новый.
        # Это требует доработки протокола: "ensure_chat_exists_with_user" -> returns chat_id.
        # ТЕКУЩЕЕ УПРОЩЕНИЕ: если active_chat_id is None, мы не должны были сюда попасть,
        # так как кнопка отправки должна быть неактивна или чат должен был быть создан.
        # Но если все же попали, выведем ошибку.
        if self.active_chat_id is None:
            QMessageBox.warning(self, "Ошибка",
                                "Не удалось определить чат для отправки. Попробуйте заново выбрать чат.")
            client_logger.error(
                f"Попытка отправки сообщения, когда active_chat_id is None. active_chat_name: {self.active_chat_name}")
            return

        payload_data = {
            "chat_id": self.active_chat_id,
            "text": text
        }

        client_logger.info(f"Отправка сообщения в чат ID {self.active_chat_id} (для {self.active_chat_name}): {text}")
        if self.send_json_message({"type": "send_message_to_chat", "payload": payload_data}):
            # Отображаем свое сообщение сразу, если отправка была инициирована
            self.chat_display.append(f"<b>Вы</b>: {text} <i>(отправка...)</i>")  # Можно добавить индикатор отправки
            self.message_input.clear()
            self.message_input.setFocus()
        # Если send_json_message вернул False, там уже было QMessageBox

    # ... продолжение client/main_client.py (или main_window.py) ...

    # --- Обработка ответов сервера в on_ready_read ---
    def on_ready_read(self):
        try:
            self.client_buffer += self.socket.readAll().data().decode('utf-8')
        except UnicodeDecodeError:
            client_logger.error("Ошибка декодирования входящих данных (не UTF-8).", exc_info=True)
            self.client_buffer = ""
            return

        # client_logger.debug(f"on_ready_read: текущий буфер (до обработки split): \"{self.client_buffer}\"")

        while '\n' in self.client_buffer:
            message_str, self.client_buffer = self.client_buffer.split('\n', 1)
            client_logger.info(f"Получено полное сообщение от сервера: {message_str}")

            try:
                message_data = json.loads(message_str)
                msg_type = message_data.get("type")
                payload = message_data.get("payload", {})

                if msg_type == "register_status":
                    status = payload.get("status")
                    msg = payload.get("message")
                    if status == "success":
                        client_logger.info(f"Регистрация успешна. Сообщение: {msg}")
                        QMessageBox.information(self, "Регистрация успешна", msg + "\nТеперь вы можете войти.")
                    else:
                        client_logger.warning(f"Ошибка регистрации. Сообщение: {msg}")
                        QMessageBox.warning(self, "Ошибка регистрации", msg)
                    self.show_auth_panel(f"Подключено. {msg if status != 'success' else 'Введите данные для входа.'}")
                    # Кнопки уже должны быть разблокированы через switch_to_panel -> show_auth_panel

                elif msg_type == "login_status":
                    status = payload.get("status")
                    msg = payload.get("message")
                    if status == "success":
                        self.current_username = payload.get("username")
                        self.current_user_id = payload.get("user_id")
                        client_logger.info(f"Логин успешен как {self.current_username} (ID: {self.current_user_id}).")
                        self.show_chat_list_panel()  # Переходим к списку чатов, он сам запросит список
                    else:
                        client_logger.warning(f"Ошибка логина: {msg}")
                        QMessageBox.warning(self, "Ошибка входа", msg)
                        self.show_auth_panel(f"Подключено. Ошибка входа: {msg}")

                elif msg_type == "chat_list_response":
                    chats = payload.get("chats", [])
                    client_logger.info(f"Получен список из {len(chats)} чатов.")
                    self.chat_list_widget.clear()
                    if not chats:
                        self.chat_list_widget.addItem("У вас пока нет чатов. Начните новый!")
                    else:
                        for chat_info in chats:
                            # chat_name уже должен быть именем собеседника для direct или именем группы
                            item_text = f"{chat_info.get('chat_name', 'Неизвестный чат')}"
                            last_msg_preview = chat_info.get('last_message_text', '')
                            if last_msg_preview and len(last_msg_preview) > 30:
                                last_msg_preview = last_msg_preview[:30] + "..."

                            if last_msg_preview:  # and last_msg_preview != "Нет сообщений": # Убрал "Нет сообщений" чтобы не дублировать
                                item_text += f"\n  └ {last_msg_preview}"

                            list_item = QListWidgetItem(item_text)
                            list_item.setData(Qt.UserRole, chat_info)
                            self.chat_list_widget.addItem(list_item)
                    self.status_label.setText(f"Статус: Список чатов ({self.current_username})")

                elif msg_type == "chat_history":
                    chat_id_history = payload.get("chat_id")
                    messages = payload.get("messages", [])
                    client_logger.info(f"Получена история для чата ID {chat_id_history} ({len(messages)} сообщений).")

                    if self.active_chat_id == chat_id_history:
                        # Удаляем сообщение "Загрузка истории..." если оно там было
                        # Простой способ - очистить и заполнить.
                        # Если хотим сохранить "Загрузка...", нужно его найти и удалить.
                        # Пока просто очищаем.
                        self.chat_display.clear()
                        if not messages:
                            self.chat_display.append(f"<i>История с {self.active_chat_name} пуста.</i>")
                        else:
                            for msg_data in messages:
                                sender = msg_data.get("sender_username")
                                text = msg_data.get("text")
                                # Форматирование timestamp (только дата для краткости в истории)
                                timestamp_iso = msg_data.get("timestamp", "")
                                display_ts = ""
                                if timestamp_iso:
                                    try:
                                        # Преобразуем строку ISO в объект datetime, затем форматируем
                                        dt_obj = datetime.fromisoformat(timestamp_iso.replace('Z', '+00:00'))
                                        display_ts = dt_obj.strftime("%Y-%m-%d %H:%M")
                                    except ValueError:
                                        display_ts = timestamp_iso.split('T')[0]  # Запасной вариант

                                display_sender_name = "Вы" if sender == self.current_username else sender
                                self.chat_display.append(
                                    f"<b>{display_sender_name}</b>: {text} <small><i>({display_ts})</i></small>")
                    else:
                        client_logger.warning(
                            f"Получена история для чата {chat_id_history}, но активен чат {self.active_chat_id}. Игнорируем.")

                elif msg_type == "incoming_chat_message":
                    chat_id_msg = payload.get("chat_id")
                    sender = payload.get("sender_username")
                    text = payload.get("text")
                    timestamp_iso = payload.get("timestamp", "")
                    display_ts_incoming = ""
                    if timestamp_iso:
                        try:
                            dt_obj = datetime.fromisoformat(timestamp_iso.replace('Z', '+00:00'))
                            display_ts_incoming = dt_obj.strftime("%Y-%m-%d %H:%M")
                        except ValueError:
                            display_ts_incoming = timestamp_iso.split('T')[0]

                    client_logger.info(f"Входящее сообщение в чат ID {chat_id_msg} от {sender}: {text}")

                    if self.active_chat_id == chat_id_msg:
                        # Если чат, для которого пришло сообщение, сейчас активен
                        self.chat_display.append(
                            f"<b>{sender}</b>: {text} <small><i>({display_ts_incoming})</i></small>")
                    else:
                        # Сообщение для неактивного чата
                        client_logger.info(f"Новое сообщение в неактивном чате ID {chat_id_msg} от {sender}.")
                        QMessageBox.information(self, "Новое сообщение",
                                                f"Новое сообщение от {sender} в другом чате:\n'{text}'")
                        # TODO: Обновить список чатов: найти чат с chat_id_msg,
                        # сделать его жирным, обновить last_message_text и last_message_at,
                        # поднять вверх списка. Или запросить self.send_request_chat_list()
                        self.send_request_chat_list()  # Простой вариант - запросить обновление всего списка

                elif msg_type == "error_notification":
                    error_msg = payload.get("message")
                    client_logger.warning(f"Уведомление об ошибке от сервера: {error_msg}")
                    if self.stacked_widget.currentWidget() == self.chat_panel:
                        self.chat_display.append(f"<i style='color:red;'>СЕРВЕР: {error_msg}</i>")
                    else:
                        QMessageBox.warning(self, "Серверное уведомление", error_msg)
                else:
                    client_logger.warning(f"Получен неизвестный тип сообщения от сервера: {msg_type}")

            except json.JSONDecodeError:
                client_logger.error(f"Ошибка декодирования JSON от сервера: {message_str}", exc_info=True)
            except Exception as e:
                client_logger.error(f"Неизвестная ошибка при обработке сообщения от сервера: {e}", exc_info=True)

    def closeEvent(self, event):
        """Обработка события закрытия окна."""
        client_logger.info("Окно клиента закрывается. Отключение от сервера.")
        if self.socket.state() == QAbstractSocket.ConnectedState:
            self.socket.disconnectFromHost()
            # Даем время на отправку disconnect и обработку на сервере, если нужно
            # self.socket.waitForDisconnected(1000)
        event.accept()


if __name__ == '__main__':
    # Этот импорт datetime нужен здесь, если используется в on_ready_read
    from datetime import datetime  # Перемещаем импорт сюда или в начало файла

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
