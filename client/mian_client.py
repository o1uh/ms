import sys
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QPushButton

class HelloWorldWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Простой Клиент v0.1") # Немного изменим заголовок
        self.setGeometry(300, 300, 350, 200) # x, y, ширина, высота

        layout = QVBoxLayout()

        self.label = QLabel("Клиент мессенджера готов к работе!", self)
        layout.addWidget(self.label)

        self.test_button = QPushButton("Тестовая кнопка", self)
        self.test_button.clicked.connect(self.on_test_button_click)
        layout.addWidget(self.test_button)

        self.setLayout(layout)
        print("Клиентский UI инициализирован.")

    def on_test_button_click(self):
        self.label.setText("Тестовая кнопка была нажата!")
        print("Тестовая кнопка нажата на клиенте.")

if __name__ == '__main__':
    print("Запуск клиентского приложения...")
    app = QApplication(sys.argv)
    window = HelloWorldWindow()
    window.show()
    print("Главное окно клиента отображено.")
    sys.exit(app.exec())