# client/widgets/chat_panel.py
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton, QTextEdit, QMessageBox
from PySide6.QtCore import Signal, Slot
from datetime import datetime  # Для форматирования времени своего сообщения


class ChatPanel(QWidget):
    # Сигналы
    send_message_requested = Signal(str)  # text сообщения
    back_to_list_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_chat_id = None
        self._current_chat_name = "Не выбран"
        self._current_username_of_app_user = ""  # Имя пользователя этого клиента
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        self.back_button = QPushButton("<< Назад к списку чатов")
        self.back_button.clicked.connect(self.back_to_list_requested)

        self.title_label = QLabel(f"Чат с: {self._current_chat_name}")

        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)

        self.message_input = QLineEdit()
        self.message_input.setPlaceholderText("Введите сообщение...")
        self.message_input.returnPressed.connect(self._on_send_button_clicked)

        self.send_button = QPushButton("Отправить")
        self.send_button.clicked.connect(self._on_send_button_clicked)

        layout.addWidget(self.back_button)
        layout.addWidget(self.title_label)
        layout.addWidget(self.chat_display)
        layout.addWidget(self.message_input)
        layout.addWidget(self.send_button)
        self.setLayout(layout)

    def configure_chat(self, chat_id, chat_name, app_username):
        """Настраивает панель для конкретного чата."""
        self._current_chat_id = chat_id
        self._current_chat_name = chat_name
        self._current_username_of_app_user = app_username
        self.title_label.setText(f"Чат с: {self._current_chat_name}")
        self.chat_display.clear()
        if self._current_chat_id is None:  # Это новый чат, ID еще не определен
            self.chat_display.append(f"<i>Начните новый диалог с {self._current_chat_name}.</i>")
        else:
            self.chat_display.append(f"<i>Загрузка истории для чата ID {self._current_chat_id}...</i>")
        self.message_input.setFocus()

    def add_message_to_display(self, sender_username: str, text: str, timestamp_str: str, is_self: bool):
        """Добавляет отформатированное сообщение в QTextEdit."""
        display_sender_name = "Вы" if is_self else sender_username
        formatted_ts = ""
        if timestamp_str:
            try:
                dt_obj = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                formatted_ts = dt_obj.strftime("%Y-%m-%d %H:%M")
            except ValueError:
                formatted_ts = timestamp_str.split('T')[0]  # Запасной вариант

        self.chat_display.append(f"<b>{display_sender_name}</b>: {text} <small><i>({formatted_ts})</i></small>")

    def display_history(self, messages: list):
        """Отображает историю сообщений."""
        self.chat_display.clear()
        if not messages:
            self.chat_display.append(f"<i>История с {self._current_chat_name} пуста.</i>")
            return
        for msg_data in messages:
            self.add_message_to_display(
                msg_data.get("sender_username"),
                msg_data.get("text"),
                msg_data.get("timestamp"),
                msg_data.get("sender_username") == self._current_username_of_app_user
            )

    def add_server_notification(self, message: str):
        self.chat_display.append(f"<i style='color:red;'>СЕРВЕР: {message}</i>")

    @Slot()
    def _on_send_button_clicked(self):
        text = self.message_input.text().strip()
        if not text:
            return  # Не отправляем пустое сообщение

        if self._current_chat_id is None:
            # Это логика для нового чата, где ID еще не известен.
            # Главное окно должно будет обработать этот случай:
            # сначала "создать" чат на сервере (по именам участников), получить ID,
            # а потом уже отправить сообщение с этим ID.
            # Пока что, панель просто испустит сигнал с текстом,
            # а main_window должен будет решить, как получить chat_id.
            # Или, эта кнопка должна быть неактивна, пока chat_id не известен.
            # Для простоты, пока испускаем сигнал, а main_window разберется.
            # Это место для улучшения: панель не должна отправлять, если не знает ID.
            QMessageBox.warning(self, "Отправка",
                                "ID чата еще не определен. Попробуйте после обновления списка чатов или это новый чат (отправка пока не реализована без ID).")
            return

        self.send_message_requested.emit(text)
        # Оптимистичное отображение (или дождаться подтверждения от сервера)
        self.add_message_to_display(self._current_username_of_app_user, text, datetime.now().isoformat(), True)
        self.message_input.clear()
        self.message_input.setFocus()

    def set_send_button_enabled(self, enabled: bool):
        self.send_button.setEnabled(enabled)