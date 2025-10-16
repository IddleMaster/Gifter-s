import sys
import os
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel, QLineEdit,
    QPushButton, QMessageBox, QDialog, QFormLayout, QFileDialog, QStatusBar
)
from api_client import ApiClient

# URL base de tu API de Django
API_BASE_URL = "http://127.0.0.1:8000/api"

class LoginDialog(QDialog):
    """
    Diálogo de inicio de sesión para el administrador.
    """
    def __init__(self, api_client, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Login - Gifter's Admin")
        self.api_client = api_client
        
        self.email_input = QLineEdit()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        
        self.login_button = QPushButton("Ingresar")
        self.login_button.clicked.connect(self.attempt_login)
        
        layout = QFormLayout()
        layout.addRow("Email:", self.email_input)
        layout.addRow("Contraseña:", self.password_input)
        layout.addWidget(self.login_button)
        
        self.setLayout(layout)

    def attempt_login(self):
        email = self.email_input.text()
        password = self.password_input.text()
        
        if not email or not password:
            QMessageBox.warning(self, "Error", "Por favor, ingresa email y contraseña.")
            return

        success, message = self.api_client.login(email, password)
        
        if success:
            self.accept() # Cierra el diálogo de login con éxito
        else:
            QMessageBox.critical(self, "Login Fallido", message)


class MainWindow(QMainWindow):
    """
    Ventana principal de la aplicación de administración.
    """
    def __init__(self, api_client):
        super().__init__()
        self.setWindowTitle("Panel de Administración de Gifter's")
        self.setGeometry(100, 100, 800, 600)
        self.api_client = api_client

        # Menú
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("Archivo")
        exit_action = file_menu.addAction("Salir")
        exit_action.triggered.connect(self.close)

        product_menu = menu_bar.addMenu("Productos")
        import_action = product_menu.addAction("Importar desde CSV...")
        import_action.triggered.connect(self.open_csv_importer)
        
        # Widget central y layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        self.welcome_label = QLabel("Bienvenido al Panel de Administración")
        self.welcome_label.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(self.welcome_label)
        
        # Barra de estado
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage("Listo.")

    def open_csv_importer(self):
        """
        Abre un diálogo para seleccionar un archivo CSV y lo sube a la API.
        """
        file_path, _ = QFileDialog.getOpenFileName(self, "Seleccionar Archivo CSV", "", "CSV Files (*.csv)")
        
        if file_path:
            self.statusBar.showMessage("Subiendo archivo CSV...")
            QApplication.processEvents() # Actualiza la UI
            
            success, message = self.api_client.upload_products_csv(file_path)
            
            if success:
                QMessageBox.information(self, "Importación Iniciada", message)
                self.statusBar.showMessage("Importación iniciada en el servidor.")
            else:
                QMessageBox.critical(self, "Error de Importación", message)
                self.statusBar.showMessage("Error al subir el archivo.")


if __name__ == '__main__':
    app = QApplication(sys.argv)
    
    # Crear cliente de API
    api = ApiClient(base_url=API_BASE_URL)
    
    # Mostrar diálogo de login
    login_dialog = LoginDialog(api)
    
    # Si el login es exitoso (el usuario cierra el diálogo con 'accept'), mostrar la ventana principal
    if login_dialog.exec() == QDialog.DialogCode.Accepted:
        main_window = MainWindow(api)
        main_window.show()
        sys.exit(app.exec())
    else:
        # Si el usuario cierra el diálogo de login, la aplicación termina
        sys.exit(0)
