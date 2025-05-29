# client/widgets/chat_list_panel.py
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QListWidget, \
    QListWidgetItem
from PySide6.QtCore import Signal, Slot, Qt


class ChatListPanel(QWidget):
    # Сигналы
    request_new_chat = Signal(str)  # username для нового чата
    chat_selected = Signal(dict)  # chat_data (словарь с информацией о чате)
    refresh_list_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # Секция для начала нового чата
        new_chat_group_layout = QHBoxLayout()
        self.new_chat_user_input = QLineEdit()
        self.new_chat_user_input.setPlaceholderText("Никнейм для нового/существующего чата...")

        self.start_or_open_chat_button = QPushButton("Открыть / Начать чат")
        self.start_or_open_chat_button.clicked.connect(self._on_start_new_chat_clicked)

        new_chat_group_layout.addWidget(self.new_chat_user_input)
        new_chat_group_layout.addWidget(self.start_or_open_chat_button)

        # Список чатов
        self.chat_list_widget = QListWidget()
        self.chat_list_widget.itemDoubleClicked.connect(self._on_chat_item_double_clicked)  # Двойной клик
        # Можно также добавить обработку одинарного клика + Enter или отдельную кнопку "Открыть чат"

        # Кнопка обновления списка
        self.refresh_chat_list_button = QPushButton("Обновить список чатов")
        self.refresh_chat_list_button.clicked.connect(self.refresh_list_requested)  # Просто испускаем сигнал

        layout.addWidget(QLabel("Начать новый или открыть существующий чат:"))
        layout.addLayout(new_chat_group_layout)
        layout.addWidget(QLabel("Ваши активные чаты:"))
        layout.addWidget(self.chat_list_widget)
        layout.addWidget(self.refresh_chat_list_button)

        self.setLayout(layout)

        self.new_chat_user_input.returnPressed.connect(self.start_or_open_chat_button.click)

    @Slot()
    def _on_start_new_chat_clicked(self):
        target_username = self.new_chat_user_input.text().strip()
        if target_username:
            self.request_new_chat.emit(target_username)
            self.new_chat_user_input.clear()  # Очищаем поле после запроса
        # Валидацию (не пустой, не сам себе) лучше делать в main_window перед вызовом обработчика

    @Slot(QListWidgetItem)
    def _on_chat_item_double_clicked(self, item: QListWidgetItem):
        chat_data = item.data(Qt.UserRole)
        if chat_data:
            self.chat_selected.emit(chat_data)

    def update_chat_list(self, chats_data: list):
        """Обновляет QListWidget списком чатов."""
        self.chat_list_widget.clear()
        if not chats_data:
            self.chat_list_widget.addItem("У вас пока нет чатов. Начните новый!")
        else:
            for chat_info in chats_data:
                item_text = f"{chat_info.get('chat_name', 'Неизвестный чат')}"
                last_msg_preview = chat_info.get('last_message_text', '')
                if last_msg_preview and len(last_msg_preview) > 30:
                    last_msg_preview = last_msg_preview[:30] + "..."
                if last_msg_preview:
                    item_text += f"\n  └ {last_msg_preview}"

                list_item = QListWidgetItem(item_text)
                list_item.setData(Qt.UserRole, chat_info)  # Сохраняем все данные чата
                self.chat_list_widget.addItem(list_item)

    def set_buttons_enabled(self, enabled: bool):
        self.start_or_open_chat_button.setEnabled(enabled)
        self.refresh_chat_list_button.setEnabled(enabled)
        self.chat_list_widget.setEnabled(enabled)  # Сам список тоже можно блокировать