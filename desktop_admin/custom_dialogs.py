# desktop_admin/custom_dialogs.py

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox, QWidget
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QIcon 
import os # <-- AÑADIDO
import logging # <-- AÑADIDO

class ReauthDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Re-autenticación")
        
        # --- 👇 CÓDIGO PARA APLICAR ÍCONO (Ahora funcional) 👇 ---
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            icon_file = os.path.join(script_dir, "gift_icon.ico") 
            if not os.path.exists(icon_file):
                icon_file = os.path.join(script_dir, "gift_icon.png")
            
            # Aplica el ícono a esta ventana modal (ReauthDialog)
            self.setWindowIcon(QIcon(icon_file)) 
        except Exception:
            # Usamos logging.warning en lugar de print
            logging.warning("No se pudo cargar el ícono del ReauthDialog.") 
        # --- -------------------------------------------- ---

        self.setFixedSize(400, 230)
        
        self.password = ""
        
        self.init_ui()
        self.apply_styles()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(0) # Eliminar espacio entre secciones principales
        main_layout.setContentsMargins(0, 0, 0, 0)

        # 1. ENCABEZADO (Fondo Azul Oscuro)
        header_widget = QWidget()
        header_widget.setObjectName("HeaderWidget")
        header_layout = QVBoxLayout(header_widget)
        header_layout.setContentsMargins(20, 20, 20, 20)
        
        message_label = QLabel("Tu sesión expiró. Ingresa tu contraseña para continuar:")
        message_label.setObjectName("MessageLabel")
        message_label.setWordWrap(True) # ¡IMPORTANTE! Permite que el texto fluya a la siguiente línea
        
        header_layout.addWidget(message_label)
        main_layout.addWidget(header_widget)


        # 2. CUERPO (Fondo Claro: Campo y Botones)
        body_widget = QWidget()
        body_layout = QVBoxLayout(body_widget)
        body_layout.setSpacing(15)
        body_layout.setContentsMargins(20, 10, 20, 20) # Reducir margen superior

        # Campo de Contraseña
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Contraseña")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setObjectName("PasswordInput")
        self.password_input.setFixedHeight(35)
        body_layout.addWidget(self.password_input)

        # Botones Aceptar / Cancelar
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.cancel_button = QPushButton("Cancelar")
        self.cancel_button.setObjectName("SecondaryButton")
        self.cancel_button.setFixedWidth(100)
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)

        self.ok_button = QPushButton("Aceptar")
        self.ok_button.setObjectName("SuccessButton")
        self.ok_button.setFixedWidth(100)
        self.ok_button.clicked.connect(self.accept)
        button_layout.addWidget(self.ok_button)

        body_layout.addLayout(button_layout)
        main_layout.addWidget(body_widget)


    def apply_styles(self):
        self.setStyleSheet("""
            /* 1. Base del Diálogo */
            QDialog {
                background-color: #f0f2f5; 
            }
            
            /* 2. Contenedor del Título (HeaderWidget - Azul Oscuro) */
            #HeaderWidget {
                background-color: #0a2342; /* Azul oscuro de tu sidebar */
                border-bottom: 2px solid #005bc5;
            }
            
            /* 3. Contenedor del Cuerpo (BodyWidget - AHORA AZUL OSCURO) */
            /* Nota: El QDialog base se pinta de claro, pero el widget contenedor 
               interno 'body_widget' lo pintamos de azul oscuro para que se vea uniforme. */
            QWidget { 
                background-color: #0a2342; /* ¡Fondo Azul Oscuro del Cuerpo! */
            }
            
            /* 4. Título y Mensaje (Texto Blanco en fondo oscuro) */
            #MessageLabel {
                color: white; 
                font-size: 14pt;
                font-weight: 500;
            }
            
            /* 5. Campo de Contraseña (MANTENER BLANCO) */
            #PasswordInput {
                background-color: white; /* ¡BLANCO para el campo de entrada! */
                border: 1px solid #ced4da;
                border-radius: 4px;
                padding: 6px;
                font-size: 12pt;
                color: black;
            }
            
            /* 6. Estilos de Botón */
            QPushButton {
                border: none;
                border-radius: 5px;
                padding: 8px 15px;
                font-weight: bold;
                /* El texto de los botones ya es blanco por el QWidget base de Gifter's */
            }
            
            /* Botón Aceptar (Verde) */
            QPushButton#SuccessButton {
                background-color: #28a745;
                color: white;
            }
            QPushButton#SuccessButton:hover { 
                background-color: #218838;
            }

            /* Botón Cancelar (Gris) */
            QPushButton#SecondaryButton {
                background-color: #6c757d;
                color: white;
            }
            QPushButton#SecondaryButton:hover {
                background-color: #5a6268;
            }
        """)
    def accept(self):
        if not self.password_input.text().strip():
             QMessageBox.warning(self, "Contraseña Requerida", "Debes ingresar tu contraseña.")
             return

        self.password = self.password_input.text()
        super().accept()

    def get_password(self):
        return self.password