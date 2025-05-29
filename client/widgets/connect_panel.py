# client/widgets/connect_panel.py
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton
from PySide6.QtCore import Signal, Slot


# Логгер можно импортировать так же, как в main_window.py, если он нужен здесь для детального логирования
# import sys, os
# CURRENT_DIR_CP = os.path.dirname(os.path.abspath(__file__)) # client/widgets
# CLIENT_DIR_CP = os.path.dirname(CURRENT_DIR_CP) # client/
# PROJECT_ROOT_CP = os.path.dirname(CLIENT_DIR_CP) # ms/
# sys.path.append(PROJECT_ROOT_CP)
# from logger import setup_logger
# connect_panel_logger = setup_logger('ConnectPanel', 'client_connect_panel')

class ConnectPanel(QWidget):
    # Сигнал, который будет испускаться при попытке подключения
    # Передает host (str) и port (int)
    connect_requested = Signal(str, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        # connect_panel_logger.info("Инициализация ConnectPanel...")
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        self.ip_label = QLabel("IP Сервера:")
        self.ip_input = QLineEdit("127.0.0.1")  # Значение по умолчанию
        self.port_label = QLabel("Порт Сервера:")
        self.port_input = QLineEdit("65432")  # Значение по умолчанию

        self.connect_button = QPushButton("Подключиться к Серверу")
        self.connect_button.clicked.connect(self._on_connect_button_clicked)

        layout.addWidget(self.ip_label)
        layout.addWidget(self.ip_input)
        layout.addWidget(self.port_label)
        layout.addWidget(self.port_input)
        layout.addWidget(self.connect_button)
        layout.addStretch(1)  # Чтобы элементы были вверху

        self.setLayout(layout)

    @Slot()
    def _on_connect_button_clicked(self):
        host = self.ip_input.text().strip()
        port_str = self.port_input.text().strip()

        if not host or not port_str:
            # Здесь можно было бы испустить сигнал ошибки или показать QMessageBox
            # Но пока что валидацию оставим в main_window, а панель просто передаст данные
            # connect_panel_logger.warning("IP или порт не введены.")
            # QMessageBox.warning(self, "Ошибка", "IP адрес и порт не могут быть пустыми.")
            # Для простоты, панель просто испускает сигнал, а main_window валидирует.
            # Либо панель может сама валидировать и испускать сигнал только если все ок.
            # Давайте сделаем валидацию прямо здесь, чтобы панель была более самостоятельной.
            from PySide6.QtWidgets import QMessageBox  # Локальный импорт для QMessageBox
            QMessageBox.warning(self, "Подключение", "IP адрес и порт не могут быть пустыми.")
            return

        try:
            port = int(port_str)
            if not (0 < port < 65535):
                raise ValueError("Порт вне допустимого диапазона")
        except ValueError:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Ошибка", "Порт должен быть числом от 1 до 65535.")
            # connect_panel_logger.warning(f"Некорректный порт: {port_str}")
            return

        # connect_panel_logger.info(f"Запрос на подключение к {host}:{port}")
        self.connect_requested.emit(host, port)

    def set_button_enabled(self, enabled: bool):
        """Метод для установки состояния активности кнопки подключения извне."""
        self.connect_button.setEnabled(enabled)

    def get_connection_inputs(self):
        """Возвращает введенные IP и порт (на случай, если они понадобятся до сигнала)."""
        return self.ip_input.text().strip(), self.port_input.text().strip()