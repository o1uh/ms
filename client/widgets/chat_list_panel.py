## client/widgets/chat_list_panel.py
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QListWidget, QListWidgetItem, QMessageBox
from PySide6.QtCore import Signal, Slot, Qt

class ChatListPanel(QWidget):
    # Сигналы
    request_new_direct_chat = Signal(str) # username для нового личного чата
    request_create_group = Signal(str, list) # group_name, list_of_member_usernames
    chat_selected = Signal(dict)   # chat_data (словарь с информацией о чате)
    refresh_list_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)

        # --- Секция для начала нового личного чата ---
        new_direct_chat_layout = QHBoxLayout()
        self.new_direct_chat_user_input = QLineEdit()
        self.new_direct_chat_user_input.setPlaceholderText("Никнейм для личного чата...")
        self.start_direct_chat_button = QPushButton("Начать личный чат")
        self.start_direct_chat_button.clicked.connect(self._on_start_direct_chat_clicked)
        new_direct_chat_layout.addWidget(self.new_direct_chat_user_input)
        new_direct_chat_layout.addWidget(self.start_direct_chat_button)

        # --- Секция для создания новой группы ---
        new_group_layout_main = QVBoxLayout()
        new_group_title_label = QLabel("Создать новую группу:")

        self.new_group_name_input = QLineEdit()
        self.new_group_name_input.setPlaceholderText("Название новой группы...")

        self.new_group_members_input = QLineEdit()
        self.new_group_members_input.setPlaceholderText("Никнеймы участников через запятую (необязательно)...")

        self.create_group_button = QPushButton("Создать группу")
        self.create_group_button.clicked.connect(self._on_create_group_clicked)

        new_group_layout_main.addWidget(new_group_title_label)
        new_group_layout_main.addWidget(QLabel("Название группы:"))
        new_group_layout_main.addWidget(self.new_group_name_input)
        new_group_layout_main.addWidget(QLabel("Участники (через запятую):"))
        new_group_layout_main.addWidget(self.new_group_members_input)
        new_group_layout_main.addWidget(self.create_group_button)

        # --- Список чатов ---
        self.chat_list_widget = QListWidget()
        self.chat_list_widget.itemDoubleClicked.connect(self._on_chat_item_double_clicked)

        self.refresh_chat_list_button = QPushButton("Обновить список чатов")
        self.refresh_chat_list_button.clicked.connect(self.refresh_list_requested)

        main_layout.addWidget(QLabel("Начать новый личный чат:"))
        main_layout.addLayout(new_direct_chat_layout)
        main_layout.addSpacing(15) # Добавим отступ
        main_layout.addLayout(new_group_layout_main)
        main_layout.addSpacing(15)
        main_layout.addWidget(QLabel("Ваши активные чаты:"))
        main_layout.addWidget(self.chat_list_widget)
        main_layout.addWidget(self.refresh_chat_list_button)

        self.setLayout(main_layout)

        # Связка Enter
        self.new_direct_chat_user_input.returnPressed.connect(self.start_direct_chat_button.click)
        self.new_group_members_input.returnPressed.connect(self.create_group_button.click) # Enter на участниках тоже создаст группу

    @Slot()
    def _on_start_direct_chat_clicked(self):
        target_username = self.new_direct_chat_user_input.text().strip()
        if target_username:
            self.request_new_direct_chat.emit(target_username)
            # self.new_direct_chat_user_input.clear() # Очищать или нет - по желанию
        else:
            QMessageBox.warning(self, "Личный чат", "Введите имя пользователя.")

    @Slot()
    def _on_start_direct_chat_clicked(self):  # Этот метод теперь просто испускает сигнал
        target_username = self.new_direct_chat_user_input.text().strip()
        if target_username:  # Базовая проверка, остальную валидацию сделает main_window
            self.request_new_direct_chat.emit(target_username)
        else:
            QMessageBox.warning(self, "Новый чат", "Введите имя пользователя.")

    @Slot()
    def _on_create_group_clicked(self):
        group_name = self.new_group_name_input.text().strip()
        members_str = self.new_group_members_input.text().strip()

        if not group_name:
            QMessageBox.warning(self, "Создание группы", "Название группы не может быть пустым.")
            return

        member_usernames = []
        if members_str:
            member_usernames = [name.strip() for name in members_str.split(',') if name.strip()]

        self.request_create_group.emit(group_name, member_usernames)

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
                if chat_info.get('chat_type') == 'group':
                    item_text += " (Группа)"  # Помечаем группу
                last_msg_preview = chat_info.get('last_message_text', '')
                if last_msg_preview and len(last_msg_preview) > 30:
                    last_msg_preview = last_msg_preview[:30] + "..."
                if last_msg_preview:
                    item_text += f"\n  └ {last_msg_preview}"
                list_item = QListWidgetItem(item_text)
                list_item.setData(Qt.UserRole, chat_info)
                self.chat_list_widget.addItem(list_item)

    def set_buttons_enabled(self, enabled: bool):
        self.start_direct_chat_button.setEnabled(enabled)  # Управляем кнопкой для личного чата
        self.create_group_button.setEnabled(enabled)  # Управляем кнопкой для создания группы
        self.refresh_chat_list_button.setEnabled(enabled)
        self.chat_list_widget.setEnabled(enabled)
        # Поля ввода тоже можно блокировать/разблокировать, если нужно
        self.new_direct_chat_user_input.setEnabled(enabled)
        self.new_group_name_input.setEnabled(enabled)
        self.new_group_members_input.setEnabled(enabled)