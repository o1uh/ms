# client/widgets/auth_panel.py
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox
from PySide6.QtCore import Signal, Slot


# Логгер (опционально для этого файла, можно логировать в main_window)
# import sys, os
# ... (настройка пути и импорт logger) ...
# auth_panel_logger = setup_logger('AuthPanel', 'client_auth_panel')

class AuthPanel(QWidget):
    # Сигналы: username, password
    login_requested = Signal(str, str)
    register_requested = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        # auth_panel_logger.info("Инициализация AuthPanel...")
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        self.username_label = QLabel("Имя пользователя (логин):")
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Введите ваш логин")

        self.password_label = QLabel("Пароль:")
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Введите ваш пароль")
        self.password_input.setEchoMode(QLineEdit.Password)

        buttons_layout = QHBoxLayout()
        self.login_button = QPushButton("Войти")
        self.login_button.clicked.connect(self._on_login_clicked)

        self.register_button = QPushButton("Зарегистрироваться")
        self.register_button.clicked.connect(self._on_register_clicked)

        buttons_layout.addWidget(self.login_button)
        buttons_layout.addWidget(self.register_button)

        layout.addWidget(self.username_label)
        layout.addWidget(self.username_input)
        layout.addWidget(self.password_label)
        layout.addWidget(self.password_input)
        layout.addLayout(buttons_layout)
        layout.addStretch(1)  # Чтобы элементы были вверху

        self.setLayout(layout)

        # Связка Enter в поле пароля с кнопкой "Войти"
        self.password_input.returnPressed.connect(self.login_button.click)
        self.username_input.returnPressed.connect(self.password_input.setFocus)  # Переход на поле пароля по Enter

    @Slot()
    def _on_login_clicked(self):
        username = self.username_input.text().strip()
        password = self.password_input.text()  # Пароль не тримим

        if not username or not password:
            QMessageBox.warning(self, "Вход", "Имя пользователя и пароль не могут быть пустыми.")
            return
        # auth_panel_logger.info(f"Запрос на вход для: {username}")
        self.login_requested.emit(username, password)

    @Slot()
    def _on_register_clicked(self):
        username = self.username_input.text().strip()
        password = self.password_input.text()

        if not username or not password:
            QMessageBox.warning(self, "Регистрация", "Имя пользователя и пароль не могут быть пустыми.")
            return
        if len(password) < 4:  # Минимальная валидация пароля
            QMessageBox.warning(self, "Регистрация", "Пароль должен быть не менее 4 символов.")
            return
        # auth_panel_logger.info(f"Запрос на регистрацию для: {username}")
        self.register_requested.emit(username, password)

    def set_buttons_enabled(self, enabled: bool):
        """Управляет активностью кнопок Войти и Зарегистрироваться."""
        self.login_button.setEnabled(enabled)
        self.register_button.setEnabled(enabled)

    def clear_inputs(self):
        """Очищает поля ввода."""
        self.username_input.clear()
        self.password_input.clear()

    def focus_username_input(self):
        """Устанавливает фокус на поле ввода имени пользователя."""
        self.username_input.setFocus()