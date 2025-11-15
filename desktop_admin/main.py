import datetime
import sys
import os
import logging 
import traceback
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QMessageBox, QDialog, QFormLayout, QFileDialog, QStatusBar,
    QStackedWidget, QTableWidget, QTableWidgetItem, QHeaderView,QAbstractItemView,QComboBox, 
    QSpinBox, QDoubleSpinBox,QGroupBox,QTextEdit, QCheckBox, QGridLayout,QScrollArea
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QKeySequence, QShortcut, QPixmap
from api_client import ApiClient
from local_auth_cache import LocalAuthCache

# --- Define la ruta de los logs ---
LOG_DIR = "logs"
LOG_FILE_PATH = os.path.join(LOG_DIR, "admin_app.log")
WEB_LOG_CACHE_FILE = os.path.join(LOG_DIR, "last_web_logs.cache")
# -----------------------------------

try:
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR)
        
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(LOG_FILE_PATH, mode='a', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
except PermissionError:
    print("ADVERTENCIA: No se pudo crear el archivo de log. Loggeando solo a consola.")
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler()]
    )

logging.info("Aplicación de Administración iniciada.")

# URL base de tu API de Django
API_BASE_URL = "http://127.0.0.1:8000/api"

# ---
# --- CLASE: LoginDialog
# ---
class LoginDialog(QDialog):
    """
    Diálogo de inicio de sesión para el administrador.
    (Rediseñado para coincidir con la UI web)
    """
    def __init__(self, api_client, local_auth_cache, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Login - Gifter's Admin")
        self.setMinimumSize(400, 550) 
        self.api_client = api_client
        self.local_auth_cache = local_auth_cache
        self.offline_mode = False
        
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch(1)

        # --- 1. Imagen del Regalo (RUTA CORREGIDA) ---
        gift_label = QLabel(self)
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            image_path = os.path.join(script_dir, "gift_icon.png")
            
            pixmap = QPixmap(image_path)
            gift_label.setPixmap(pixmap.scaled(
                120, 120, 
                Qt.AspectRatioMode.KeepAspectRatio, 
                Qt.TransformationMode.SmoothTransformation
            ))
            gift_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(gift_label)
        except Exception as e:
            logging.warning(f"No se pudo cargar la imagen del logo desde {image_path}: {e}")
            gift_label.setText("🎁") 
            gift_label.setFont(QFont("Arial", 48))
            layout.addWidget(gift_label)

        # --- 2. Título "Gifter's" ---
        title_label = QLabel("Gifter's")
        title_label.setObjectName("Title")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        
        # --- 3. Subtítulo "Inicia Sesión" ---
        subtitle_label = QLabel("Inicia Sesión")
        subtitle_label.setObjectName("Subtitle")
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle_label)

        # --- 4. Campos de Texto ---
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("Email")
        self.email_input.setFixedHeight(45)
        
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Contraseña")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setFixedHeight(45)

        layout.addWidget(self.email_input)
        layout.addWidget(self.password_input)
        
        # --- 5. Botón de Ingresar ---
        self.login_button = QPushButton("Ingresar")
        self.login_button.clicked.connect(self.attempt_login)
        self.login_button.setFixedHeight(45)
        
        layout.addWidget(self.login_button)
        layout.addStretch(1)

        # --- 6. Links (CORREGIDO) ---
        forgot_label = QLabel("¿Olvidaste tu contraseña?")
        forgot_label.setObjectName("Link")
        forgot_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        layout.addWidget(forgot_label)
        layout.addStretch(1)
        
        # --- 7. Aplicar Estilos (QSS) ---
        self.setStyleSheet("""
            QDialog { background-color: #f7faff; }
            QLabel#Title {
                font-family: 'Arial', sans-serif; font-size: 28pt; font-weight: 600;
                color: #004a99; margin-top: 15px;
            }
            QLabel#Subtitle {
                font-family: 'Arial', sans-serif; font-size: 16pt;
                color: #333; margin-bottom: 25px;
            }
            QLineEdit {
                border: 1px solid #ced4da; border-radius: 8px; padding: 0 15px;
                font-size: 12pt; background-color: white;
            }
            QLineEdit:focus { border: 1px solid #007bff; }
            QPushButton {
                background-color: #007bff; color: white; border: none;
                border-radius: 8px; padding: 10px; font-size: 12pt; font-weight: 500;
            }
            QPushButton:hover { background-color: #0056b3; }
            QLabel#Link { color: #007bff; font-size: 10pt; margin-top: 10px; }
        """)

    def attempt_login(self):
        email = self.email_input.text()
        password = self.password_input.text()
        
        if not email or not password:
            QMessageBox.warning(self, "Error", "Por favor, ingresa email y contraseña.")
            return

        success, message = self.api_client.login(email, password)
        
        if success:
            self.offline_mode = False 
            self.accept()
            return
        
        is_connection_error = "No se pudo conectar" in message or "Error de conexión" in message
        
        if is_connection_error:
            logging.warning("Login online falló. Intentando validación de caché local...")
            
            if self.local_auth_cache.check_offline_password(email, password):
                logging.info(f"Login offline exitoso para {email}.")
                QMessageBox.information(self, "Modo Offline",
                    "No se pudo conectar con el servidor. Se ha iniciado sesión en modo offline.\n"
                    "La información mostrada (excepto los logs) podría no estar actualizada.")
                self.offline_mode = True 
                self.accept() 
            else:
                logging.warning(f"Password offline no coincide o no existe para {email}.")
                QMessageBox.critical(self, "Login Fallido", 
                    "No se pudo conectar con el servidor. La contraseña local no coincide o no existe.\n"
                    "Por favor, conéctate a internet para tu primer inicio de sesión.")
        else:
            logging.warning(f"Login online fallido (no por conexión): {message}")
            QMessageBox.critical(self, "Login Fallido", message)

# ---
# --- CLASE: CreateProductDialog
# ---
class CreateProductDialog(QDialog):
    """
    Diálogo para ingresar datos de un nuevo producto.
    Usa ComboBoxes para categoría y marca.
    """
    def __init__(self, categories_list, brands_list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Crear Nuevo Producto")

        self.name_input = QLineEdit()
        self.desc_input = QLineEdit()
        
        self.category_input = QComboBox()
        self.brand_input = QComboBox()

        if not categories_list:
            self.category_input.addItem("Error: No se cargaron categorías", None)
            self.category_input.setEnabled(False)
        else:
            self.category_input.addItem("--- Selecciona una Categoría ---", None)
            for cat in categories_list:
                self.category_input.addItem(cat['nombre_categoria'], cat['id_categoria'])

        if not brands_list:
            self.brand_input.addItem("Error: No se cargaron marcas", None)
            self.brand_input.setEnabled(False)
        else:
            self.brand_input.addItem("--- Selecciona una Marca ---", None)
            for brand in brands_list:
                self.brand_input.addItem(brand['nombre_marca'], brand['id_marca'])

        self.save_button = QPushButton("Guardar Producto")
        self.cancel_button = QPushButton("Cancelar")
        self.save_button.clicked.connect(self.accept) 
        self.cancel_button.clicked.connect(self.reject) 

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        form_layout.addRow("Nombre:", self.name_input)
        form_layout.addRow("Descripción:", self.desc_input)
        form_layout.addRow("Categoría:", self.category_input)
        form_layout.addRow("Marca:", self.brand_input)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.save_button)
        layout.addLayout(form_layout)
        layout.addLayout(button_layout)

    def get_data(self):
        return {
            'nombre_producto': self.name_input.text().strip(),
            'descripcion': self.desc_input.text().strip(),
            'precio': 0, # Envía 0 por defecto
            'id_categoria': self.category_input.currentData(), 
            'id_marca': self.brand_input.currentData() 
        }

# ---
# --- CLASE: CreateCategoryDialog
# ---
class CreateCategoryDialog(QDialog):
    """Diálogo simple para crear una nueva Categoría."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Crear Nueva Categoría")
        
        self.name_input = QLineEdit()
        self.save_button = QPushButton("Guardar")
        self.cancel_button = QPushButton("Cancelar")
        
        self.save_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)
        
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        form_layout.addRow("Nombre Categoría:", self.name_input)
        
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.save_button)
        
        layout.addLayout(form_layout)
        layout.addLayout(button_layout)
        
    def get_data(self):
        return {'nombre_categoria': self.name_input.text().strip()}

# ---
# --- CLASE: CreateBrandDialog
# ---
class CreateBrandDialog(QDialog):
    """Diálogo simple para crear una nueva Marca."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Crear Nueva Marca")
        
        self.name_input = QLineEdit()
        self.save_button = QPushButton("Guardar")
        self.cancel_button = QPushButton("Cancelar")
        
        self.save_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)
        
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        form_layout.addRow("Nombre Marca:", self.name_input)
        
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.save_button)
        
        layout.addLayout(form_layout)
        layout.addLayout(button_layout)
        
    def get_data(self):
        return {'nombre_marca': self.name_input.text().strip()}

# ---
# --- CLASE: MainWindow
# ---
class MainWindow(QMainWindow):
    def __init__(self, api_client, is_offline=False, user_email=""): 
        super().__init__()
        self.setWindowTitle("Panel de Administración de Gifter's")
        self.setGeometry(100, 100, 900, 700)
        self.api_client = api_client
        self.is_offline = is_offline  
        self.user_email = user_email.lower()
        self.setStatusBar(QStatusBar(self))
        self.all_categories = []
        self.all_brands = []

        #-- Widget Central y Layout --
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("Archivo")
        exit_action = file_menu.addAction("Salir")
        exit_action.triggered.connect(self.close)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        sidebar_widget = self.create_sidebar()
        main_layout.addWidget(sidebar_widget)

        # --- Stack Principal (derecha) ---
        self.stacked_widget = QStackedWidget()
        main_layout.addWidget(self.stacked_widget, 1)

        # --- Crear las 3 Páginas Principales ---
        self.page_reportes = self.create_reportes_page()
        self.page_admin = self.create_admin_page()
        self.page_catalogo = self.create_catalogo_page()

        # --- Añadir Páginas al Stack Principal ---
        self.stacked_widget.addWidget(self.page_reportes)   # Índice 0
        self.stacked_widget.addWidget(self.page_admin)      # Índice 1
        self.stacked_widget.addWidget(self.page_catalogo)   # Índice 2
        
        # --- Conectar Sidebar al Stack Principal ---
        self.btn_reportes.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(0))
        self.btn_importar.clicked.connect(self.open_csv_importer) 
        
        # --- Carga Inicial ---
        if self.is_offline:
            self.statusBar().showMessage("Modo Offline. Los datos no se actualizarán.")
            self.statusBar().setStyleSheet("background-color: #ffc107; color: black;")
            logging.info("Modo Offline: Omitiendo carga inicial de datos desde la API.")
        else:
            self.statusBar().showMessage("Listo.")
            logging.info("Cargando datos iniciales (productos, usuarios, cats/marcas)...")
            self.load_products()
            self.load_users()
            self.load_categories_and_brands() 

    # ---
    # --- SECCIÓN 1: Creación de Páginas Principales
    # ---
            
    def create_sidebar(self):
        sidebar_widget = QWidget()
        sidebar_widget.setStyleSheet("""
            QWidget { background-color: #0a2342; color: white; }
            QPushButton {
                background-color: #004a99; color: white; border: none;
                padding: 15px; text-align: left; font-size: 16px;
            }
            QPushButton:hover { background-color: #005bc5; }
            QPushButton:pressed { background-color: #003366; }
        """)
        sidebar_widget.setFixedWidth(220)

        sidebar_layout = QVBoxLayout(sidebar_widget)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(1)

        title_label = QLabel("Gifter's Admin")
        title_label.setFont(QFont("Arial", 20, QFont.Weight.Bold))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setContentsMargins(10, 20, 10, 30)
        sidebar_layout.addWidget(title_label)

        self.btn_reportes = QPushButton("Reportes")
        self.btn_importar = QPushButton("Importar CSV")
        
        sidebar_layout.addWidget(self.btn_reportes)
        sidebar_layout.addWidget(self.btn_importar)
        
        if self.is_offline:
            self.btn_importar.setEnabled(False)
            self.btn_importar.setText("Importar CSV (Offline)")
        
        sidebar_layout.addStretch()
        return sidebar_widget

    def create_reportes_page(self):
        """
        Crea la página de Reportes (Índice 0), que contiene su propio
        QStackedWidget ('self.reports_stack') con 7 sub-páginas.
        """
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)

        self.reports_stack = QStackedWidget()
        layout.addWidget(self.reports_stack)

        # --- Crear las 7 sub-páginas de Reportes ---
        report_menu_page = self.create_report_main_menu_page() # Menú (Tarjetas)
        self.moderation_report_page = self.create_moderation_report_page()
        self.search_report_page = self.create_search_report_page()
        self.reviews_report_page = self.create_reviews_report_page()
        self.top_users_report_page = self.create_top_users_report_page()
        self.log_viewer_page = self.create_log_viewer_page()
        self.local_log_viewer_page = self.create_local_log_viewer_page()

        # --- Añadir las 7 sub-páginas al stack de reportes ---
        self.reports_stack.addWidget(report_menu_page)         # Índice 0
        self.reports_stack.addWidget(self.moderation_report_page) # Índice 1
        self.reports_stack.addWidget(self.search_report_page)     # Índice 2
        self.reports_stack.addWidget(self.reviews_report_page)    # Índice 3
        self.reports_stack.addWidget(self.top_users_report_page)  # Índice 4
        self.reports_stack.addWidget(self.log_viewer_page)      # Índice 5
        self.reports_stack.addWidget(self.local_log_viewer_page)  # Índice 6

        return page

    def create_admin_page(self):
        """Crea la página de Administración de Usuarios (Índice 1)."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("Administración de Usuarios")
        title.setFont(QFont("Arial", 24, QFont.Weight.Bold))
        layout.addWidget(title)

        self.table_users = QTableWidget()
        self.table_users.setColumnCount(7)
        self.table_users.setHorizontalHeaderLabels(["ID", "Nombre", "Apellido", "Correo", "Usename", "Es Admin","Is Active"])
        self.table_users.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_users.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_users.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

        if self.is_offline:
            self.table_users.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        else:
            self.table_users.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked)
            
        self.table_users.setSortingEnabled(False)
        self.table_users.itemChanged.connect(self.handle_user_change) 

        layout.addWidget(self.table_users)
        
        # Botón de Borrar Usuario
        button_layout = QHBoxLayout()
        button_layout.addStretch() 
        
        self.btn_delete_user = QPushButton("Borrar Usuario Seleccionado")
        self.btn_delete_user.setStyleSheet("background-color: #dc3545; color: white; padding: 10px; font-size: 14px;")
        self.btn_delete_user.clicked.connect(self.handle_delete_user)
        
        if self.is_offline:
            self.btn_delete_user.setEnabled(False) 
            
        button_layout.addWidget(self.btn_delete_user)
        layout.addLayout(button_layout)

        return page

    def create_catalogo_page(self):
        """
        Crea la página de Catálogo (Índice 2), que contiene su propio
        QStackedWidget ('self.catalogo_stack') con 4 sub-páginas.
        """
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)

        self.catalogo_stack = QStackedWidget()
        layout.addWidget(self.catalogo_stack)

        # --- Crear las 4 sub-páginas de Catálogo ---
        catalogo_menu_page = self.create_catalogo_menu_page() # Menú (3 botones)
        product_table_page = self.create_product_table_page() # Tabla de Productos
        category_list_page = self.create_category_list_page() # Página de Categorías
        brand_list_page = self.create_brand_list_page()       # Página de Marcas

        # --- Añadir las 4 sub-páginas al stack de catálogo ---
        self.catalogo_stack.addWidget(catalogo_menu_page)    # Índice 0
        self.catalogo_stack.addWidget(product_table_page)   # Índice 1
        self.catalogo_stack.addWidget(category_list_page)   # Índice 2
        self.catalogo_stack.addWidget(brand_list_page)      # Índice 3

        return page

    # ---
    # --- SECCIÓN 2: Creación de Sub-Páginas
    # ---

    # --- Sub-Páginas de REPORTES ---
    
    def create_report_main_menu_page(self):
        """
        Crea el widget para el MENÚ PRINCIPAL de reportes (Índice 0).
        (Rediseñado para poner las 2 secciones de tarjetas en horizontal)
        """
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True) 
        scroll_area.setStyleSheet("QScrollArea { border: none; }")

        main_widget = QWidget()
        main_widget.setStyleSheet("""
            QWidget { background-color: #f0f2f5; }
            QGroupBox {
                background-color: white; border: 1px solid #e0e0e0;
                border-radius: 8px; margin-top: 10px; padding: 15px;
            }
            QGroupBox::title {
                subcontrol-origin: margin; subcontrol-position: top left;
                padding: 0 10px; font-size: 14pt; font-weight: bold; color: #333;
            }
            QLabel#SectionTitle {
                font-size: 14pt; font-weight: bold; color: #333;
                padding-top: 15px; padding-bottom: 5px;
            }
        """)

        # Layout vertical principal
        layout = QVBoxLayout(main_widget)
        layout.setContentsMargins(25, 20, 25, 20)
        layout.setSpacing(15)

        # --- Sección 1: Reportes de Catálogo (Fila 1) ---
        layout.addWidget(QLabel("Reportes de Catálogo", objectName="SectionTitle"))
        row1_layout = QHBoxLayout()
        row1_layout.setSpacing(20)

        # Tarjeta 1: Generar Reporte de Productos
        card_gen_report = QGroupBox("Generar Reporte de Productos")
        card_gen_report.setMinimumWidth(320) 
        card_gen_layout = QVBoxLayout(card_gen_report)
        format_layout = QHBoxLayout()
        format_label = QLabel("Formato:")
        self.combo_report_format = QComboBox()
        self.combo_report_format.addItems(["CSV", "Excel (.xlsx)", "PDF"])
        format_layout.addWidget(format_label)
        format_layout.addWidget(self.combo_report_format)
        self.btn_download_report = QPushButton("Descargar Reporte")
        self.btn_download_report.setStyleSheet("background-color: #28a745; color: white; padding: 10px; font-size: 14px;")
        self.btn_download_report.clicked.connect(self.handle_download_report)
        card_gen_layout.addLayout(format_layout)
        card_gen_layout.addStretch()
        card_gen_layout.addWidget(self.btn_download_report)
        row1_layout.addWidget(card_gen_report)

        # Tarjeta 2: Cargar Archivo CSV
        card_load_csv = QGroupBox("Cargar Archivo CSV")
        card_load_csv.setMinimumWidth(320) 
        card_load_csv_layout = QVBoxLayout(card_load_csv)
        card_load_csv_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.btn_importar_card = QPushButton("☁️\nSeleccionar Archivo")
        self.btn_importar_card.setMinimumHeight(100)
        self.btn_importar_card.setFont(QFont("Arial", 12))
        self.btn_importar_card.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_importar_card.setStyleSheet("""
            QPushButton { 
                border: 2px dashed #007bff; border-radius: 8px; 
                background-color: #f8f9fa; color: #007bff;
            }
            QPushButton:hover { background-color: #e9f2ff; }
        """)
        self.btn_importar_card.clicked.connect(self.open_csv_importer)
        card_load_csv_layout.addWidget(self.btn_importar_card)
        row1_layout.addWidget(card_load_csv)
        row1_layout.addStretch(1) 
        layout.addLayout(row1_layout)

        # --- 👇 MODIFICACIÓN AQUÍ 👇 ---
        
        # --- Layout Horizontal para las dos cuadrículas ---
        middle_row_layout = QHBoxLayout()
        layout.addLayout(middle_row_layout)

        # --- Columna Izquierda: Información General ---
        info_column = QVBoxLayout()
        info_column.addWidget(QLabel("Información General y Monitoreo", objectName="SectionTitle"))
        
        grid_layout = QGridLayout()
        grid_layout.setSpacing(20)
        
        card_search = self.create_info_card("Búsquedas Populares", "🔍", "#007bff",
            lambda: (self.reports_stack.setCurrentIndex(2), self.load_search_report()))
        card_reviews = self.create_info_card("Reseñas del Sitio", "💬", "#28a745",
            lambda: (self.reports_stack.setCurrentIndex(3), self.load_reviews_report()))
        card_top_users = self.create_info_card("Top 10 Usuarios", "👥", "#ffc107",
            lambda: (self.reports_stack.setCurrentIndex(4), self.load_top_users_report()))
        card_logs_web = self.create_info_card("Logs del Servidor", "🖥️", "#ffc107",
            lambda: (self.reports_stack.setCurrentIndex(5), self.load_web_logs()))

        grid_layout.addWidget(card_search, 0, 0)
        grid_layout.addWidget(card_reviews, 0, 1)
        grid_layout.addWidget(card_top_users, 1, 0)
        grid_layout.addWidget(card_logs_web, 1, 1)
        
        info_column.addLayout(grid_layout)
        info_column.addStretch(1) # Estira para alinear con la otra columna
        middle_row_layout.addLayout(info_column, 1) # '1' = factor de estiramiento

        # --- Columna Derecha: Navegación Principal ---
        nav_column = QVBoxLayout()
        nav_column.addWidget(QLabel("Navegación Principal", objectName="SectionTitle"))
        
        grid_layout_2 = QGridLayout()
        grid_layout_2.setSpacing(20)

        card_moderation = self.create_info_card(
            "Reporte de Moderación", "🛡️", "#dc3545", # Rojo
            lambda: (self.reports_stack.setCurrentIndex(1), self.load_moderation_report())
        )
        card_log_local = self.create_info_card(
            "Ver Log Local", "📄", "#6c757d", # Gris
            lambda: (self.reports_stack.setCurrentIndex(6), self.load_local_logs())
        )
        card_admin_users = self.create_info_card(
            "Administrar Usuarios", "🧑‍⚖️", "#17a2b8", # Teal/Info
            lambda: self.stacked_widget.setCurrentIndex(1) # Va al stack principal
        )
        card_admin_catalog = self.create_info_card(
            "Administrar Catálogo", "📚", "#17a2b8", # Teal/Info
            lambda: self.stacked_widget.setCurrentIndex(2) # Va al stack principal
        )

        grid_layout_2.addWidget(card_moderation, 0, 0)
        grid_layout_2.addWidget(card_log_local, 0, 1)
        grid_layout_2.addWidget(card_admin_users, 1, 0)
        grid_layout_2.addWidget(card_admin_catalog, 1, 1)
        
        nav_column.addLayout(grid_layout_2)
        nav_column.addStretch(1) # Estira para alinear
        middle_row_layout.addLayout(nav_column, 1) # '1' = factor de estiramiento

        # --- (Sección "Acciones Rápidas" eliminada) ---
        # --- ------------------------------- ---

        layout.addStretch(1) 
        
        scroll_area.setWidget(main_widget)
        return scroll_area
    
    def create_moderation_report_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 20, 20, 20)
        
        layout.addWidget(self.create_back_button(self.reports_stack))
        title = QLabel("Reporte de Moderación")
        title.setFont(QFont("Arial", 20, QFont.Weight.Bold))
        layout.addWidget(title)
        refresh_button = QPushButton("Actualizar Datos")
        refresh_button.clicked.connect(self.load_moderation_report)
        layout.addWidget(refresh_button)
        layout.addWidget(QLabel("Usuarios que más reportan:"))
        self.table_top_reporters = QTableWidget()
        layout.addWidget(self.table_top_reporters)
        layout.addWidget(QLabel("Usuarios más reportados:"))
        self.table_most_reported = QTableWidget()
        layout.addWidget(self.table_most_reported)
        
        #self.btn_goto_moderation.clicked.connect(self.load_moderation_report)
        return page

    def create_search_report_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 20, 20, 20)
        
        layout.addWidget(self.create_back_button(self.reports_stack))
        title = QLabel("Reporte de Búsquedas Populares")
        title.setFont(QFont("Arial", 20, QFont.Weight.Bold))
        layout.addWidget(title)
        
        button_layout = QHBoxLayout()
        refresh_button = QPushButton("Actualizar Datos")
        refresh_button.clicked.connect(self.load_search_report)
        button_layout.addWidget(refresh_button)
        
        self.btn_download_search_pdf = QPushButton("Descargar como PDF")
        self.btn_download_search_pdf.setStyleSheet("background-color: #dc3545; color: white; padding: 8px; font-size: 14px;")
        self.btn_download_search_pdf.clicked.connect(self.handle_download_search_pdf)
        button_layout.addWidget(self.btn_download_search_pdf)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        self.table_popular_searches = QTableWidget()
        layout.addWidget(self.table_popular_searches)
        
        #self.btn_goto_search.clicked.connect(self.load_search_report)
        return page

    def create_reviews_report_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 20, 20, 20)
        
        layout.addWidget(self.create_back_button(self.reports_stack))
        title = QLabel("Reporte de Reseñas del Sitio")
        title.setFont(QFont("Arial", 20, QFont.Weight.Bold))
        layout.addWidget(title)
        
        button_layout = QHBoxLayout()
        refresh_button = QPushButton("Actualizar Datos")
        refresh_button.clicked.connect(self.load_reviews_report)
        button_layout.addWidget(refresh_button)
        
        self.btn_download_reviews_pdf = QPushButton("Descargar como PDF")
        self.btn_download_reviews_pdf.setStyleSheet("background-color: #dc3545; color: white; padding: 8px; font-size: 14px;")
        self.btn_download_reviews_pdf.clicked.connect(self.handle_download_reviews_pdf)
        button_layout.addWidget(self.btn_download_reviews_pdf)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        layout.addWidget(QLabel("Estadísticas de Calificación:"))
        self.table_review_stats = QTableWidget()
        layout.addWidget(self.table_review_stats)
        layout.addWidget(QLabel("Últimas Reseñas:"))
        self.table_latest_reviews = QTableWidget()
        layout.addWidget(self.table_latest_reviews)
        
        #self.btn_goto_reviews.clicked.connect(self.load_reviews_report)
        return page

    def create_top_users_report_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 20, 20, 20)
        
        layout.addWidget(self.create_back_button(self.reports_stack))
        title = QLabel("Reporte de Top Usuarios Activos")
        title.setFont(QFont("Arial", 20, QFont.Weight.Bold))
        layout.addWidget(title)
        refresh_button = QPushButton("Actualizar Datos")
        refresh_button.clicked.connect(self.load_top_users_report)
        layout.addWidget(refresh_button)
        self.label_total_interactions = QLabel("Total de interacciones (según RegistroActividad): N/A")
        layout.addWidget(self.label_total_interactions)
        self.table_top_users = QTableWidget()
        self.table_top_users_headers = [
            "ID", "Usuario", "Puntaje Total", "Posts", "Comentarios", 
            "Likes", "Seguidores Nuevos", "Favoritos Añadidos", "Otros"
        ]
        self.table_top_users.setColumnCount(len(self.table_top_users_headers))
        self.table_top_users.setHorizontalHeaderLabels(self.table_top_users_headers)
        layout.addWidget(self.table_top_users)
        
        #self.btn_goto_top_users.clicked.connect(self.load_top_users_report)
        return page

    def create_log_viewer_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 20, 20, 20)
        
        layout.addWidget(self.create_back_button(self.reports_stack))
        title = QLabel("Visor de Logs del Servidor (web_app.log)")
        title.setFont(QFont("Arial", 20, QFont.Weight.Bold))
        layout.addWidget(title)

        button_layout = QHBoxLayout()
        refresh_button = QPushButton("Actualizar Logs (F5)")
        refresh_button.setStyleSheet("background-color: #007bff; color: white; padding: 8px; font-size: 14px;")
        refresh_button.clicked.connect(self.load_web_logs)
        button_layout.addWidget(refresh_button)

        self.btn_download_web_logs = QPushButton("Descargar Logs Vistos")
        self.btn_download_web_logs.setStyleSheet("background-color: #28a745; color: white; padding: 8px; font-size: 14px;")
        self.btn_download_web_logs.clicked.connect(self.handle_download_web_logs)
        button_layout.addWidget(self.btn_download_web_logs)

        button_layout.addStretch()
        layout.addLayout(button_layout)

        self.log_text_area = QTextEdit()
        self.log_text_area.setReadOnly(True)
        self.log_text_area.setFont(QFont("Courier", 10))
        self.log_text_area.setStyleSheet("background-color: #f8f9fa; color: #212529;")
        
        try:
            if os.path.exists(WEB_LOG_CACHE_FILE):
                with open(WEB_LOG_CACHE_FILE, 'r', encoding='utf-8') as f:
                    self.log_text_area.setPlainText(f.read())
                logging.info(f"Cargado log del servidor desde caché: {WEB_LOG_CACHE_FILE}")
            else:
                self.log_text_area.setPlainText("--- Aún no se han cargado logs del servidor. Presiona 'Actualizar Logs (F5)' ---")
        except Exception as e:
            self.log_text_area.setPlainText(f"Error al cargar log cacheado: {e}")
            logging.error(f"Error al cargar log cacheado: {e}", exc_info=True)
            
        layout.addWidget(self.log_text_area)
        
        QShortcut(QKeySequence(Qt.Key.Key_F5), self.log_text_area, self.load_web_logs)
        
        return page

    def create_local_log_viewer_page(self):
        """Crea la página (Índice 6) para mostrar los logs locales."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 20, 20, 20)
        
        layout.addWidget(self.create_back_button(self.reports_stack, "Volver al Menú de Reportes"))
        title = QLabel("Visor de Logs Locales (admin_app.log)")
        title.setFont(QFont("Arial", 20, QFont.Weight.Bold))
        layout.addWidget(title)

        button_layout = QHBoxLayout()
        refresh_button = QPushButton("Actualizar Log (F5)")
        refresh_button.setStyleSheet("background-color: #007bff; color: white; padding: 8px; font-size: 14px;")
        refresh_button.clicked.connect(self.load_local_logs)
        button_layout.addWidget(refresh_button)

        download_button = QPushButton("Descargar Log")
        download_button.setStyleSheet("background-color: #28a745; color: white; padding: 8px; font-size: 14px;")
        download_button.clicked.connect(self.handle_download_local_logs)
        button_layout.addWidget(download_button)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)

        self.local_log_text_area = QTextEdit() 
        self.local_log_text_area.setReadOnly(True)
        self.local_log_text_area.setFont(QFont("Courier", 10))
        self.local_log_text_area.setStyleSheet("background-color: #f8f9fa; color: #212529;")
        
        layout.addWidget(self.local_log_text_area)
        
        self.load_local_logs() # Carga inicial
        
        QShortcut(QKeySequence(Qt.Key.Key_F5), self.local_log_text_area, self.load_local_logs)
        
        return page

    # --- Sub-Páginas de CATÁLOGO ---

    def create_catalogo_menu_page(self):
        """Crea el widget para el MENÚ PRINCIPAL de Catálogo."""
        page = QWidget()
        main_layout = QVBoxLayout(page)
        
        button_style = """
            QPushButton {
                background-color: #005bc5; color: white; border: 1px solid #004a99;
                border-radius: 5px; padding: 20px; font-size: 16px; font-weight: bold;
            }
            QPushButton:hover { background-color: #007bff; }
            QPushButton:pressed { background-color: #004a99; }
        """
        
        button_layout = QHBoxLayout()
        button_layout.setSpacing(30)

        # Botón 1: Ver Catálogo
        self.btn_goto_products = QPushButton("📦\n\nVer Catálogo\nde Productos")
        self.btn_goto_products.setFixedSize(160, 160)
        self.btn_goto_products.setStyleSheet(button_style)
        self.btn_goto_products.clicked.connect(lambda: self.catalogo_stack.setCurrentIndex(1))
        
        # Botón 2: Administrar Categorías
        self.btn_admin_cat = QPushButton("🏷️\n\nAdministrar\nCategorías")
        self.btn_admin_cat.setFixedSize(160, 160)
        self.btn_admin_cat.setStyleSheet(button_style)
        self.btn_admin_cat.clicked.connect(lambda: self.catalogo_stack.setCurrentIndex(2))
        self.btn_admin_cat.clicked.connect(self.load_category_table)
        
        # Botón 3: Administrar Marcas
        self.btn_admin_brand = QPushButton("🏢\n\nAdministrar\nMarcas")
        self.btn_admin_brand.setFixedSize(160, 160)
        self.btn_admin_brand.setStyleSheet(button_style)
        self.btn_admin_brand.clicked.connect(lambda: self.catalogo_stack.setCurrentIndex(3))
        self.btn_admin_brand.clicked.connect(self.load_brand_table)

        if self.is_offline:
            self.btn_admin_cat.setEnabled(False)
            self.btn_admin_brand.setEnabled(False)

        button_layout.addStretch()
        button_layout.addWidget(self.btn_goto_products)
        button_layout.addWidget(self.btn_admin_cat)
        button_layout.addWidget(self.btn_admin_brand)
        button_layout.addStretch()
        
        main_layout.addStretch()
        main_layout.addLayout(button_layout)
        main_layout.addStretch()
        
        return page

    def create_product_table_page(self):
        """Crea la página de Catálogo (Mockup 4) - AHORA ES UNA SUB-PÁGINA."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 20, 20, 20)
        
        layout.addWidget(self.create_back_button(self.catalogo_stack, "Volver al Menú de Catálogo"))

        title = QLabel("Catálogo de Productos")
        title.setFont(QFont("Arial", 24, QFont.Weight.Bold))
        layout.addWidget(title)

        self.table_products = QTableWidget()
        self.table_products.setColumnCount(4)
        self.table_products.setHorizontalHeaderLabels(["ID", "Nombre", "Categoría", "Marca"])
        
        self.table_products.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_products.setSortingEnabled(False)
        self.table_products.itemChanged.connect(self.handle_product_change)
        self.table_products.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_products.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        
        if self.is_offline:
            self.table_products.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        else:
            self.table_products.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked)
        
        layout.addWidget(self.table_products)

        button_row_layout = QHBoxLayout()
        self.btn_create_product = QPushButton("Crear Nuevo Producto")
        self.btn_create_product.setStyleSheet("background-color: #007bff; color: white; padding: 10px; font-size: 14px;")
        self.btn_create_product.clicked.connect(self.handle_create_product)
        button_row_layout.addWidget(self.btn_create_product)
        button_row_layout.addStretch()
        self.btn_delete_product = QPushButton("Borrar Producto Seleccionado")
        self.btn_delete_product.setStyleSheet("background-color: #dc3545; color: white; padding: 10px; font-size: 14px;")
        self.btn_delete_product.clicked.connect(self.handle_delete_product)
        button_row_layout.addWidget(self.btn_delete_product)
        
        if self.is_offline:
            self.btn_create_product.setEnabled(False)
            self.btn_delete_product.setEnabled(False)

        layout.addLayout(button_row_layout)
        
        return page

    def create_category_list_page(self):
        """Crea la página (Índice 2 del stack de catálogo) para listar Categorías."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 20, 20, 20)
        
        layout.addWidget(self.create_back_button(self.catalogo_stack, "Volver al Menú de Catálogo"))
        
        title = QLabel("Administrar Categorías")
        title.setFont(QFont("Arial", 24, QFont.Weight.Bold))
        layout.addWidget(title)

        button_layout = QHBoxLayout()
        self.btn_new_category_dialog = QPushButton("Crear Nueva Categoría")
        self.btn_new_category_dialog.setStyleSheet("background-color: #007bff; color: white; padding: 10px; font-size: 14px;")
        self.btn_new_category_dialog.clicked.connect(self.handle_create_category)
        button_layout.addWidget(self.btn_new_category_dialog)
        button_layout.addStretch()
        
        self.btn_delete_category = QPushButton("Borrar Categoría Seleccionada")
        self.btn_delete_category.setStyleSheet("background-color: #dc3545; color: white; padding: 10px; font-size: 14px;")
        self.btn_delete_category.clicked.connect(self.handle_delete_category)
        button_layout.addWidget(self.btn_delete_category)
        layout.addLayout(button_layout)
        
        if self.is_offline:
            self.btn_new_category_dialog.setEnabled(False)
            self.btn_delete_category.setEnabled(False)

        self.table_categories = QTableWidget()
        self.table_categories.setColumnCount(2)
        self.table_categories.setHorizontalHeaderLabels(["ID", "Nombre"])
        self.table_categories.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_categories.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table_categories.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table_categories.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_categories.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        layout.addWidget(self.table_categories)
        
        return page

    def create_brand_list_page(self):
        """Crea la página (Índice 3 del stack de catálogo) para listar Marcas."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 20, 20, 20)

        layout.addWidget(self.create_back_button(self.catalogo_stack, "Volver al Menú de Catálogo"))

        title = QLabel("Administrar Marcas")
        title.setFont(QFont("Arial", 24, QFont.Weight.Bold))
        layout.addWidget(title)

        button_layout = QHBoxLayout()
        self.btn_new_brand_dialog = QPushButton("Crear Nueva Marca")
        self.btn_new_brand_dialog.setStyleSheet("background-color: #007bff; color: white; padding: 10px; font-size: 14px;")
        self.btn_new_brand_dialog.clicked.connect(self.handle_create_brand)
        button_layout.addWidget(self.btn_new_brand_dialog)
        button_layout.addStretch()

        self.btn_delete_brand = QPushButton("Borrar Marca Seleccionada")
        self.btn_delete_brand.setStyleSheet("background-color: #dc3545; color: white; padding: 10px; font-size: 14px;")
        self.btn_delete_brand.clicked.connect(self.handle_delete_brand)
        button_layout.addWidget(self.btn_delete_brand)
        
        layout.addLayout(button_layout)

        if self.is_offline:
            self.btn_new_brand_dialog.setEnabled(False)
            self.btn_delete_brand.setEnabled(False)

        self.table_brands = QTableWidget()
        self.table_brands.setColumnCount(2)
        self.table_brands.setHorizontalHeaderLabels(["ID", "Nombre"])
        self.table_brands.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_brands.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table_brands.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table_brands.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_brands.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        layout.addWidget(self.table_brands)
        
        return page

    # ---
    # --- SECCIÓN 3: Funciones Helper (Botones, Tablas)
    # ---
        
    def create_back_button(self, stack_widget, text="Volver al Menú"):
        """
        Helper para crear un botón de 'Volver' que controla un
        QStackedWidget específico.
        """
        back_button = QPushButton(text)
        back_button.setStyleSheet("background-color: #6c757d; color: white; padding: 8px; font-size: 14px;")
        back_button.clicked.connect(lambda: stack_widget.setCurrentIndex(0))
        return back_button

    def create_info_card(self, title, icon_char, style_color, on_click_action):
        """
        Helper para crear las tarjetas de info (Búsquedas, Reseñas, etc.)
        style_color: 'blue', 'green', 'yellow'
        """
        card = QGroupBox()
        card.setMinimumSize(180, 135) # Tamaño mínimo de la tarjeta
        
        layout = QVBoxLayout(card)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Texto oscuro para todos los fondos de tarjeta
        text_color = "#333" 
        hover_color = "#000"

        # 1. Icono y Título
        header_layout = QHBoxLayout()
        icon_label = QLabel(icon_char)
        icon_label.setObjectName("InfoCardIcon")
        title_label = QLabel(title)
        title_label.setObjectName("InfoCardTitle")
        
        header_layout.addWidget(icon_label)
        header_layout.addWidget(title_label, 1) 
        layout.addLayout(header_layout)
        
        # 2. Link "Ver Detalle"
        details_button = QPushButton("Ver Detalle")
        details_button.setObjectName("LinkButton")
        details_button.setCursor(Qt.CursorShape.PointingHandCursor)
        details_button.clicked.connect(on_click_action)
        
        layout.addStretch() 
        layout.addWidget(details_button, 0, Qt.AlignmentFlag.AlignRight)

        # 3. Aplicar Estilo
        card_style = f"""
            QGroupBox {{
                background-color: {style_color};
                border-radius: 8px;
            }}
        """
        # --- 👇 CORRECCIÓN AQUÍ: Añadido 'background-color: transparent;' 👇 ---
        card.setStyleSheet(card_style + f"""
            QLabel#InfoCardIcon {{
                font-size: 24pt;
                color: {text_color}; 
                padding-right: 10px;
                background-color: transparent;
            }}
            QLabel#InfoCardTitle {{
                font-size: 11pt;
                font-weight: bold;
                color: {text_color};
                background-color: transparent;
            }}
            QPushButton#LinkButton {{
                background-color: transparent;
                border: none;
                color: {text_color};
                font-size: 9pt;
                text-decoration: underline;
                padding: 5px;
            }}
            QPushButton#LinkButton:hover {{
                color: {hover_color};
            }}
        """)
        
        return card

    def populate_table(self, table_widget, headers, data):
        """Helper obsoleto (mantener por si se usa en algún lado)."""
        logging.warning("Usando populate_table obsoleto. Considera cambiar a populate_table_with_keys.")
        table_widget.blockSignals(True)
        table_widget.setRowCount(0)
        table_widget.setColumnCount(len(headers))
        table_widget.setHorizontalHeaderLabels(headers)
        if not data:
            table_widget.blockSignals(False)
            return
        # ... (lógica de 'populate_table')
        table_widget.blockSignals(False)

    def populate_table_with_keys(self, table_widget, headers, data, key_map):
        """
        Helper MEJORADO para llenar un QTableWidget, usando un mapeo explícito de claves.
        key_map: Un diccionario como {"Header Columna": "clave_en_json"}
        """
        table_widget.blockSignals(True)
        table_widget.setRowCount(0)
        table_widget.setColumnCount(len(headers))
        table_widget.setHorizontalHeaderLabels(headers)
        
        if not data:
            table_widget.blockSignals(False)
            return

        table_widget.setRowCount(len(data))
        
        for row_idx, row_data in enumerate(data):
            for col_idx, header in enumerate(headers):
                key_in_json = key_map.get(header, header) 
                value = row_data.get(key_in_json, "N/A")

                if header == "Fecha" and value != "N/A":
                    try:
                        dt = datetime.datetime.fromisoformat(str(value).replace('Z', '+00:00'))
                        value = dt.strftime('%Y-%m-%d %H:%M')
                    except (ValueError, TypeError):
                        value = str(value)
                else:
                    value = str(value)

                item = QTableWidgetItem(value)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                table_widget.setItem(row_idx, col_idx, item)
                
        table_widget.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table_widget.blockSignals(False)

    # ---
    # --- SECCIÓN 4: Funciones de Carga de Datos (Loaders)
    # ---
        
    def load_products(self):
        """Carga los productos desde la API y los muestra en la tabla."""
        if self.is_offline: 
            self.statusBar().showMessage("Modo Offline: Carga de productos omitida.", 3000)
            return
        self.statusBar().showMessage("Cargando productos...") 
        self.table_products.blockSignals(True)

        products, error = self.api_client.get_products()

        if error:
            logging.error(f"Error al cargar productos: {error}")
            QMessageBox.critical(self, "Error al cargar productos", error)
            self.statusBar().showMessage("Error al cargar productos.") 
            self.table_products.blockSignals(False)
            return

        if products is None:
            logging.warning("No se pudieron obtener los productos (API devolvió None).")
            QMessageBox.warning(self, "Productos", "No se pudieron obtener los productos.")
            self.statusBar().showMessage("No se pudieron obtener los productos.") 
            self.table_products.blockSignals(False)
            return

        self.table_products.setRowCount(0)
        self.table_products.setRowCount(len(products))

        for row_index, product in enumerate(products):
            product_id = str(product.get('id_producto', ''))
            nombre = product.get('nombre_producto', '')
            categoria_nombre = product.get('categoria_nombre', '') 
            marca_nombre = product.get('marca_nombre', '')

            item_id = QTableWidgetItem(product_id)
            item_name = QTableWidgetItem(nombre)
            item_category = QTableWidgetItem(categoria_nombre)
            item_brand = QTableWidgetItem(marca_nombre)

            item_id.setFlags(item_id.flags() & ~Qt.ItemFlag.ItemIsEditable)
            item_category.setFlags(item_category.flags() & ~Qt.ItemFlag.ItemIsEditable)
            item_brand.setFlags(item_brand.flags() & ~Qt.ItemFlag.ItemIsEditable)

            self.table_products.setItem(row_index, 0, item_id)
            self.table_products.setItem(row_index, 1, item_name)
            self.table_products.setItem(row_index, 2, item_category)
            self.table_products.setItem(row_index, 3, item_brand)

        logging.info(f"Se cargaron {len(products)} productos.")
        self.statusBar().showMessage(f"Se cargaron {len(products)} productos.") 
        self.table_products.blockSignals(False)

    def load_users(self):
        """Carga los usuarios desde la API y los muestra en la tabla."""
        if self.is_offline:
            self.statusBar().showMessage("Modo Offline: Carga de usuarios omitida.", 3000)
            return
        self.statusBar().showMessage("Cargando usuarios...")
        self.table_users.blockSignals(True) 

        users, error = self.api_client.get_users()

        if error:
            logging.error(f"Error al cargar usuarios: {error}")
            QMessageBox.critical(self, "Error al cargar usuarios", error)
            self.statusBar().showMessage("Error al cargar usuarios.")
            self.table_users.blockSignals(False)
            return

        if users is None:
            logging.warning("No se pudieron obtener los usuarios (API devolvió None).")
            QMessageBox.warning(self, "Usuarios", "No se pudieron obtener los usuarios.")
            self.statusBar().showMessage("No se pudieron obtener los usuarios.")
            self.table_users.blockSignals(False)
            return

        self.table_users.setRowCount(0) 
        self.table_users.setRowCount(len(users))

        for row_index, user in enumerate(users):
            user_id = str(user.get('id', ''))
            nombre = user.get('nombre', '')
            apellido = user.get('apellido', '')
            correo = user.get('correo', '')
            username = user.get('nombre_usuario', '')
            
            item_id = QTableWidgetItem(user_id)
            item_nombre = QTableWidgetItem(nombre)
            item_apellido = QTableWidgetItem(apellido)
            item_correo = QTableWidgetItem(correo)
            item_username = QTableWidgetItem(username)

            item_id.setFlags(item_id.flags() & ~Qt.ItemFlag.ItemIsEditable)
            item_correo.setFlags(item_correo.flags() & ~Qt.ItemFlag.ItemIsEditable)

            self.table_users.setItem(row_index, 0, item_id)
            self.table_users.setItem(row_index, 1, item_nombre)
            self.table_users.setItem(row_index, 2, item_apellido)
            self.table_users.setItem(row_index, 3, item_correo)
            self.table_users.setItem(row_index, 4, item_username)

            es_admin_bool = user.get('es_admin', False)
            is_active_bool = user.get('is_active', False)

            check_admin = QCheckBox()
            check_admin.setChecked(es_admin_bool)
            check_admin.stateChanged.connect(lambda state, uid=user_id: self.handle_user_checkbox_change(state, uid, "Es Admin"))
            
            widget_admin = QWidget()
            layout_admin = QHBoxLayout(widget_admin)
            layout_admin.addWidget(check_admin)
            layout_admin.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout_admin.setContentsMargins(0,0,0,0)
            widget_admin.setLayout(layout_admin)
            
            check_active = QCheckBox()
            check_active.setChecked(is_active_bool)
            check_active.stateChanged.connect(lambda state, uid=user_id: self.handle_user_checkbox_change(state, uid, "Is Active"))

            widget_active = QWidget()
            layout_active = QHBoxLayout(widget_active)
            layout_active.addWidget(check_active)
            layout_active.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout_active.setContentsMargins(0,0,0,0)
            widget_active.setLayout(layout_active)

            self.table_users.setCellWidget(row_index, 5, widget_admin)
            self.table_users.setCellWidget(row_index, 6, widget_active)

        logging.info(f"Se cargaron {len(users)} usuarios.")
        self.statusBar().showMessage(f"Se cargaron {len(users)} usuarios.")
        self.table_users.blockSignals(False)
        
    def load_categories_and_brands(self):
        """Carga las listas de categorías y marcas al iniciar la app."""
        if self.is_offline:
            logging.warning("Modo Offline: Omitiendo carga de categorías y marcas.")
            return

        self.statusBar().showMessage("Cargando categorías y marcas...")
        
        categories, error_cat = self.api_client.get_categories()
        if error_cat:
            logging.error(f"Error al cargar categorías: {error_cat}")
            QMessageBox.critical(self, "Error de Carga", f"No se pudieron cargar las categorías:\n{error_cat}")
            self.all_categories = []
        else:
            self.all_categories = categories
            logging.info(f"Se cargaron {len(self.all_categories)} categorías.")
            
        brands, error_brand = self.api_client.get_brands()
        if error_brand:
            logging.error(f"Error al cargar marcas: {error_brand}")
            QMessageBox.critical(self, "Error de Carga", f"No se pudieron cargar las marcas:\n{error_brand}")
            self.all_brands = []
        else:
            self.all_brands = brands
            logging.info(f"Se cargaron {len(self.all_brands)} marcas.")
        
        self.statusBar().showMessage("Categorías y marcas cargadas.", 3000)

    def load_category_table(self):
        """Puebla la tabla de categorías con los datos cacheados."""
        if self.is_offline:
            return 
            
        self.statusBar().showMessage("Cargando lista de categorías...")
        data = self.all_categories
        
        self.populate_table_with_keys(
            self.table_categories, 
            ["ID", "Nombre"], 
            data,
            key_map={"ID": "id_categoria", "Nombre": "nombre_categoria"}
        )
        self.statusBar().showMessage(f"Se cargaron {len(data)} categorías.", 3000)

    def load_brand_table(self):
        """Puebla la tabla de marcas con los datos cacheados."""
        if self.is_offline:
            return
            
        self.statusBar().showMessage("Cargando lista de marcas...")
        data = self.all_brands
        
        self.populate_table_with_keys(
            self.table_brands, 
            ["ID", "Nombre"], 
            data,
            key_map={"ID": "id_marca", "Nombre": "nombre_marca"}
        )
        self.statusBar().showMessage(f"Se cargaron {len(data)} marcas.", 3000)

    def load_moderation_report(self):
        self.statusBar().showMessage("Cargando reporte de moderación...")
        QApplication.processEvents()
        data, error = self.api_client.get_moderation_report()
        
        if error:
            logging.error(f"Error al cargar reporte de moderación: {error}")
            QMessageBox.critical(self, "Error", error)
            self.statusBar().showMessage("Error al cargar reporte de moderación.", 5000)
            return

        self.populate_table_with_keys(
            self.table_top_reporters, 
            ["ID", "Usuario", "Conteo"], 
            data.get('top_reporters', []),
            key_map={"ID": "id_user__id", "Usuario": "id_user__nombre_usuario", "Conteo": "count"}
        )
        self.populate_table_with_keys(
            self.table_most_reported, 
            ["ID", "Usuario", "Conteo"], 
            data.get('most_reported_users', []),
            key_map={"ID": "id_post__id_usuario__id", "Usuario": "id_post__id_usuario__nombre_usuario", "Conteo": "count"}
        )
        logging.info("Reporte de moderación cargado.")
        self.statusBar().showMessage("Reporte de moderación cargado.", 3000)

    def load_search_report(self):
        self.statusBar().showMessage("Cargando reporte de búsquedas...")
        QApplication.processEvents()
        data, error = self.api_client.get_popular_search_report()
        
        if error:
            logging.error(f"Error al cargar reporte de búsquedas: {error}")
            QMessageBox.critical(self, "Error", error)
            self.statusBar().showMessage("Error al cargar reporte de búsquedas.", 5000)
            return

        self.populate_table_with_keys(
            self.table_popular_searches, 
            ["Término", "Conteo"], 
            data.get('popular_searches', []),
            key_map={"Término": "term_lower", "Conteo": "count"}
        )
        logging.info("Reporte de búsquedas cargado.")
        self.statusBar().showMessage("Reporte de búsquedas cargado.", 3000)

    def load_reviews_report(self):
        self.statusBar().showMessage("Cargando reporte de reseñas...")
        QApplication.processEvents()
        data, error = self.api_client.get_site_reviews_report()
        
        if error:
            logging.error(f"Error al cargar reporte de reseñas: {error}")
            QMessageBox.critical(self, "Error", error)
            self.statusBar().showMessage("Error al cargar reporte de reseñas.", 5000)
            return

        self.populate_table_with_keys(
            self.table_review_stats, 
            ["Calificación", "Conteo"], 
            data.get('review_stats', []),
            key_map={"Calificación": "calificacion", "Conteo": "count"}
        )
        
        self.populate_table_with_keys(
            self.table_latest_reviews, 
            ["Usuario", "Calificación", "Comentario", "Fecha"], 
            data.get('latest_reviews', []),
            key_map={
                "Usuario": "id_usuario__nombre_usuario", 
                "Calificación": "calificacion", 
                "Comentario": "comentario", 
                "Fecha": "fecha_resena"
            }
        )
        logging.info("Reporte de reseñas cargado.")
        self.statusBar().showMessage("Reporte de reseñas cargado.", 3000)

    def load_top_users_report(self):
        self.statusBar().showMessage("Cargando reporte de top usuarios...")
        QApplication.processEvents()
        data, error = self.api_client.get_top_active_users_report()
        
        if error:
            logging.error(f"Error al cargar reporte de top usuarios: {error}")
            QMessageBox.critical(self, "Error", error)
            self.statusBar().showMessage("Error al cargar reporte de top usuarios.", 5000)
            return

        total_interactions = data.get('total_tracked_interactions', 'N/A')
        self.label_total_interactions.setText(f"Total de interacciones (según RegistroActividad): {total_interactions}")
        top_users_data = data.get('top_active_users', [])
        
        self.table_top_users.blockSignals(True)
        self.table_top_users.setRowCount(0)
        self.table_top_users.setRowCount(len(top_users_data))

        activity_key_map = {
            'nuevo_post': "Posts", 'nuevo_comentario': "Comentarios",
            'nueva_reaccion': "Likes", 'nuevo_seguidor': "Seguidores Nuevos",
            'nuevo_regalo': "Favoritos Añadidos", 'otro': "Otros" 
        }

        for row_idx, user_data in enumerate(top_users_data):
            user_id = user_data.get('user_id', 'N/A')
            username = user_data.get('nombre_usuario', 'N/A')
            total_score = user_data.get('total_score', 0)
            breakdown = user_data.get('breakdown', {})

            item_id = QTableWidgetItem(str(user_id))
            item_username = QTableWidgetItem(str(username))
            item_score = QTableWidgetItem(str(total_score))
            
            item_id.setFlags(item_id.flags() & ~Qt.ItemFlag.ItemIsEditable)
            item_username.setFlags(item_username.flags() & ~Qt.ItemFlag.ItemIsEditable)
            item_score.setFlags(item_score.flags() & ~Qt.ItemFlag.ItemIsEditable)
            
            self.table_top_users.setItem(row_idx, 0, item_id)
            self.table_top_users.setItem(row_idx, 1, item_username)
            self.table_top_users.setItem(row_idx, 2, item_score)

            for activity_key, column_name in activity_key_map.items():
                try:
                    col_idx = self.table_top_users_headers.index(column_name)
                    count = breakdown.get(activity_key, 0)
                    item_breakdown = QTableWidgetItem(str(count))
                    item_breakdown.setFlags(item_breakdown.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    self.table_top_users.setItem(row_idx, col_idx, item_breakdown)
                except ValueError:
                    logging.warning(f"No se encontró la columna '{column_name}' en las cabeceras de Top Usuarios.")
                        
        self.table_top_users.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_top_users.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents) 
        self.table_top_users.blockSignals(False)
        
        logging.info("Reporte de top usuarios cargado.")
        self.statusBar().showMessage("Reporte de top usuarios cargado.", 3000)

    def load_web_logs(self):
        """Llama a la API para obtener los logs, los muestra y los guarda en caché."""
        if self.is_offline:
            self.statusBar().showMessage("Modo Offline: No se pueden actualizar los logs del servidor.", 3000)
            QMessageBox.warning(self, "Modo Offline", "No puedes actualizar los logs del servidor mientras estás sin conexión.")
            return
        self.statusBar().showMessage("Cargando logs del servidor...")
        QApplication.processEvents()
        
        log_lines, error = self.api_client.get_web_logs()
        
        if error:
            logging.error(f"Error al cargar logs del servidor: {error}")
            QMessageBox.critical(self, "Error", f"No se pudieron cargar los logs (¿está el servidor conectado?)\n\n{error}")
            self.statusBar().showMessage("Error al cargar logs del servidor.", 5000)
            return
        
        if log_lines:
            log_content = "\n".join(log_lines)
            self.log_text_area.setPlainText(log_content)
            self.log_text_area.verticalScrollBar().setValue(self.log_text_area.verticalScrollBar().maximum())
            
            try:
                with open(WEB_LOG_CACHE_FILE, 'w', encoding='utf-8') as f:
                    f.write(log_content)
                logging.info(f"Logs del servidor cacheados en {WEB_LOG_CACHE_FILE}")
            except Exception as e:
                logging.error(f"No se pudo escribir el cache del log web: {e}", exc_info=True)
            
        else:
            self.log_text_area.setPlainText("--- No hay logs para mostrar (El servidor devolvió 0 líneas) ---")

        logging.info("Logs del servidor cargados exitosamente.")
        self.statusBar().showMessage(f"Logs del servidor actualizados ({len(log_lines)} líneas).", 3000)

    def load_local_logs(self):
        """Carga el archivo de log local (admin_app.log) en el visor."""
        self.statusBar().showMessage(f"Cargando log local desde {LOG_FILE_PATH}...")
        QApplication.processEvents()
        
        try:
            if os.path.exists(LOG_FILE_PATH):
                with open(LOG_FILE_PATH, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read()
                self.local_log_text_area.setPlainText(content)
                self.local_log_text_area.verticalScrollBar().setValue(self.local_log_text_area.verticalScrollBar().maximum())
                self.statusBar().showMessage("Log local cargado.", 3000)
                logging.info(f"Log local '{LOG_FILE_PATH}' cargado en el visor.")
            else:
                self.local_log_text_area.setPlainText(f"--- El archivo de log '{LOG_FILE_PATH}' no existe. ---")
                self.statusBar().showMessage("El archivo de log local no existe.", 3000)
        except Exception as e:
            self.local_log_text_area.setPlainText(f"Error al cargar log local: {e}")
            logging.error(f"Error al cargar log local: {e}", exc_info=True)
            self.statusBar().showMessage("Error al cargar log local.", 5000)

    # ---
    # --- SECCIÓN 5: Funciones de Acción (Handlers)
    # ---

    def handle_product_change(self, item):
        """Se llama cuando una celda de productos cambia."""
        if self.table_products.signalsBlocked():
            return

        row = item.row()
        col = item.column()
        new_value = item.text()

        product_id_item = self.table_products.item(row, 0)
        if not product_id_item:
            logging.error(f"handle_product_change: No se pudo obtener el ID del producto de la fila {row}.")
            return

        product_id = product_id_item.text()
        header_name = self.table_products.horizontalHeaderItem(col).text()

        logging.info(f"Enviando actualización: Producto ID={product_id}, Campo='{header_name}', Nuevo Valor='{new_value}'")
        self.statusBar().showMessage(f"Guardando Producto {product_id}...")
        QApplication.processEvents()

        success, message = self.api_client.update_product(product_id, header_name, new_value)

        if success:
            logging.info(f"Producto {product_id} guardado exitosamente.")
            self.statusBar().showMessage(f"Producto {product_id} guardado.", 3000)
        else:
            QMessageBox.critical(self, "Error al Guardar", message)
            self.statusBar().showMessage(f"Error al guardar Producto {product_id}.", 5000)
            self.load_products() 

    def handle_delete_product(self):
        """Maneja el clic en el botón 'Borrar Producto Seleccionado'."""
        selected_items = self.table_products.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Borrar Producto", "Por favor, selecciona una fila para borrar.")
            return
        
        selected_row = self.table_products.currentRow()
        product_id_item = self.table_products.item(selected_row, 0)
        product_name_item = self.table_products.item(selected_row, 1)
    
        if not product_id_item:
            logging.error("handle_delete_product: No se pudo obtener el ID del producto seleccionado.")
            QMessageBox.critical(self, "Error", "No se pudo obtener el ID del producto seleccionado.")
            return
    
        product_id = product_id_item.text()
        product_name = product_name_item.text() if product_name_item else f"ID {product_id}"
    
        reply = QMessageBox.question(self, 'Confirmar Borrado',
                                     f"¿Estás seguro de que quieres borrar el producto '{product_name}' (ID: {product_id})?\n"
                                     "Esta acción no se puede deshacer.",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
    
        if reply == QMessageBox.StandardButton.Yes:
            logging.info(f"Iniciando borrado de producto ID={product_id}, Nombre='{product_name}'")
            self.statusBar().showMessage(f"Borrando Producto {product_id}...")
            QApplication.processEvents()
    
            success, message = self.api_client.delete_product(product_id)
    
            if success:
                logging.info(f"Producto {product_id} borrado exitosamente.")
                self.statusBar().showMessage(f"Producto {product_id} borrado exitosamente.", 3000)
                self.load_products()
            else:
                QMessageBox.critical(self, "Error al Borrar", message)
                self.statusBar().showMessage(f"Error al borrar Producto {product_id}.", 5000)
        else:
            logging.info("Borrado de producto cancelado por el usuario.")
            self.statusBar().showMessage("Borrado cancelado.")
        
    def open_csv_importer(self):
        """Abre un diálogo para seleccionar un CSV y lo sube a la API."""
        file_path, _ = QFileDialog.getOpenFileName(self, "Seleccionar Archivo CSV", "", "CSV Files (*.csv)")
        
        if file_path:
            logging.info(f"Iniciando subida de CSV: {file_path}")
            self.statusBar().showMessage("Subiendo archivo CSV...")
            QApplication.processEvents()
            
            success, message = self.api_client.upload_products_csv(file_path)
            
            if success:
                logging.info(f"Subida de CSV {file_path} exitosa.")
                QMessageBox.information(self, "Importación Iniciada", message)
                self.statusBar().showMessage("Importación iniciada en el servidor.")
                self.load_products() 
            else:
                logging.error(f"Fallo la subida de CSV {file_path}: {message}")
                QMessageBox.critical(self, "Error de Importación", message)
                self.statusBar().showMessage("Error al subir el archivo.")
                
    def handle_user_change(self, item):
        """
        Se llama cuando el contenido de una celda de TEXTO en la tabla de usuarios cambia.
        """
        if self.table_users.signalsBlocked():
            return

        row = item.row()
        col = item.column()
        new_value = item.text()

        user_id_item = self.table_users.item(row, 0)
        if not user_id_item:
            logging.error(f"handle_user_change: No se pudo obtener el ID del usuario de la fila {row}.")
            return

        user_id = user_id_item.text()
        header_name = self.table_users.horizontalHeaderItem(col).text()

        if header_name in ["ID", "Correo", "Es Admin", "Is Active"]:
            logging.warning(f"Se intentó editar campo no editable o de widget: '{header_name}'")
            return

        logging.info(f"Enviando actualización de usuario: ID={user_id}, Campo='{header_name}', Nuevo Valor='{new_value}'")
        self.statusBar().showMessage(f"Guardando Usuario {user_id}...")
        QApplication.processEvents()

        success, message = self.api_client.update_user(user_id, header_name, new_value)

        if success:
            logging.info(f"Usuario {user_id} guardado exitosamente.")
            self.statusBar().showMessage(f"Usuario {user_id} guardado.", 3000) 
        else:
            QMessageBox.critical(self, "Error al Guardar Usuario", message)
            self.statusBar().showMessage(f"Error al guardar Usuario {user_id}.", 5000)
            self.load_users()
    
    def handle_user_checkbox_change(self, state, user_id, column_name):
        """
        Se llama cuando un QCheckBox en la tabla de usuarios cambia.
        'state' es 2 (Checked) o 0 (Unchecked).
        """
        if self.table_users.signalsBlocked():
            return
        
        new_value = (state > 0) 
        
        logging.info(f"Enviando actualización de checkbox: Usuario ID={user_id}, Campo='{column_name}', Nuevo Valor='{new_value}'")
        self.statusBar().showMessage(f"Guardando Usuario {user_id}...")
        QApplication.processEvents()

        success, message = self.api_client.update_user(user_id, column_name, new_value)
        
        if success:
            logging.info(f"Usuario {user_id} (checkbox) guardado exitosamente.")
            self.statusBar().showMessage(f"Usuario {user_id} guardado.", 3000)
        else:
            QMessageBox.critical(self, "Error al Guardar Usuario", message)
            self.statusBar().showMessage(f"Error al guardar Usuario {user_id}.", 5000)
            self.load_users()
                 
    def handle_create_product(self):
        """Abre el diálogo para crear un producto y envía los datos a la API."""
        if self.is_offline or not self.all_categories or not self.all_brands:
            logging.warning("Intento de crear producto sin conexión o sin listas de cat/marca.")
            QMessageBox.warning(self, "Error", 
                "No se pueden crear productos en modo offline o si falló la carga de categorías/marcas.\n"
                "Reinicia la aplicación con conexión.")
            return

        dialog = CreateProductDialog(self.all_categories, self.all_brands, self)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            product_data = dialog.get_data()

            if not product_data['nombre_producto']:
                logging.warning("Intento de crear producto sin nombre.")
                QMessageBox.warning(self, "Datos Incompletos", "El nombre del producto es obligatorio.")
                return 
            if not product_data['id_categoria']:
                logging.warning("Intento de crear producto sin categoría.")
                QMessageBox.warning(self, "Datos Incompletos", "Debes seleccionar una categoría.")
                return 
            if not product_data['id_marca']:
                logging.warning("Intento de crear producto sin marca.")
                QMessageBox.warning(self, "Datos Incompletos", "Debes seleccionar una marca.")
                return 
            
            self.statusBar().showMessage("Creando nuevo producto...")
            QApplication.processEvents()

            new_product, message = self.api_client.create_product(product_data)

            if new_product:
                logging.info(f"Producto creado. ID: {new_product.get('id_producto')}, Nombre: {new_product.get('nombre_producto')}")
                self.statusBar().showMessage(f"Producto '{new_product.get('nombre_producto')}' creado (ID: {new_product.get('id_producto')}).", 5000)
                QMessageBox.information(self, "Producto Creado", message)
                self.load_products() 
            else:
                QMessageBox.critical(self, "Error al Crear Producto", message)
                self.statusBar().showMessage("Error al crear el producto.", 5000)
        else:
            logging.info("Creación de producto cancelada.")
            self.statusBar().showMessage("Creación de producto cancelada.", 3000)
            
    def handle_create_category(self):
        """Abre el diálogo para crear una categoría y la envía a la API."""
        dialog = CreateCategoryDialog(self)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            category_data = dialog.get_data()
            
            if not category_data['nombre_categoria']:
                logging.warning("Intento de crear categoría sin nombre.")
                QMessageBox.warning(self, "Datos Incompletos", "El nombre de la categoría es obligatorio.")
                return
            
            self.statusBar().showMessage("Creando nueva categoría...")
            QApplication.processEvents()
            
            new_cat, message = self.api_client.create_category(category_data)
            
            if new_cat:
                logging.info(f"Categoría creada: {new_cat}")
                self.statusBar().showMessage(f"Categoría '{new_cat.get('nombre_categoria')}' creada.", 5000)
                QMessageBox.information(self, "Categoría Creada", message)
                # Recargamos las listas
                self.load_categories_and_brands()
                self.load_category_table()
            else:
                QMessageBox.critical(self, "Error al Crear Categoría", message)
                self.statusBar().showMessage("Error al crear la categoría.", 5000)
        else:
            logging.info("Creación de categoría cancelada.")
            self.statusBar().showMessage("Creación de categoría cancelada.", 3000)

    def handle_create_brand(self):
        """Abre el diálogo para crear una marca y la envía a la API."""
        dialog = CreateBrandDialog(self)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            brand_data = dialog.get_data()
            
            if not brand_data['nombre_marca']:
                logging.warning("Intento de crear marca sin nombre.")
                QMessageBox.warning(self, "Datos Incompletos", "El nombre de la marca es obligatorio.")
                return
            
            self.statusBar().showMessage("Creando nueva marca...")
            QApplication.processEvents()
            
            new_brand, message = self.api_client.create_brand(brand_data)
            
            if new_brand:
                logging.info(f"Marca creada: {new_brand}")
                self.statusBar().showMessage(f"Marca '{new_brand.get('nombre_marca')}' creada.", 5000)
                QMessageBox.information(self, "Marca Creada", message)
                # Recargamos las listas
                self.load_categories_and_brands()
                self.load_brand_table()
            else:
                QMessageBox.critical(self, "Error al Crear Marca", message)
                self.statusBar().showMessage("Error al crear la marca.", 5000)
        else:
            logging.info("Creación de marca cancelada.")
            self.statusBar().showMessage("Creación de marca cancelada.", 3000)
    
    def handle_delete_category(self):
        """Maneja el borrado de la categoría seleccionada."""
        selected_row = self.table_categories.currentRow()
        if selected_row < 0:
            QMessageBox.warning(self, "Borrar Categoría", "Por favor, selecciona una fila para borrar.")
            return

        try:
            category_id = self.table_categories.item(selected_row, 0).text()
            category_name = self.table_categories.item(selected_row, 1).text()
        except AttributeError:
            QMessageBox.critical(self, "Error", "No se pudo leer la fila seleccionada.")
            return
            
        if category_name == "Sin Categoría":
            QMessageBox.warning(self, "Acción no permitida", "No puedes eliminar la categoría por defecto 'Sin Categoría'.")
            return

        msg_box = QMessageBox(self)
        msg_box.setWindowTitle('Confirmar Borrado')
        msg_box.setIcon(QMessageBox.Icon.Warning)
        msg_box.setText(f"¿Estás seguro de que quieres eliminar la categoría '{category_name}'?")
        msg_box.setInformativeText(
            "Esta acción NO borrará los productos asociados.\n\n"
            "Los productos que usaban esta categoría serán reasignados a 'Sin Categoría'."
        )
        yes_button = msg_box.addButton("Sí, Eliminar", QMessageBox.ButtonRole.DestructiveRole)
        no_button = msg_box.addButton("Cancelar", QMessageBox.ButtonRole.RejectRole)
        msg_box.setDefaultButton(no_button)
        msg_box.exec()

        if msg_box.clickedButton() == yes_button:
            logging.info(f"Iniciando borrado de categoría ID={category_id}, Nombre='{category_name}'")
            self.statusBar().showMessage(f"Borrando Categoría {category_id}...")
            QApplication.processEvents()
            
            success, message = self.api_client.delete_category(category_id)
            
            if success:
                logging.info(f"Categoría {category_id} borrada.")
                self.statusBar().showMessage(f"Categoría '{category_name}' borrada exitosamente.", 3000)
                self.load_categories_and_brands()
                self.load_category_table()
                self.load_products() # Recargar productos para que muestren "Sin Categoría"
            else:
                QMessageBox.critical(self, "Error al Borrar", message)
                self.statusBar().showMessage(f"Error al borrar Categoría {category_id}.", 5000)
        else:
            logging.info("Borrado de categoría cancelado.")
            self.statusBar().showMessage("Borrado cancelado.")

    def handle_delete_brand(self):
        """Maneja el borrado de la marca seleccionada."""
        selected_row = self.table_brands.currentRow()
        if selected_row < 0:
            QMessageBox.warning(self, "Borrar Marca", "Por favor, selecciona una fila para borrar.")
            return

        try:
            brand_id = self.table_brands.item(selected_row, 0).text()
            brand_name = self.table_brands.item(selected_row, 1).text()
        except AttributeError:
            QMessageBox.critical(self, "Error", "No se pudo leer la fila seleccionada.")
            return
            
        if brand_name == "Sin Marca":
            QMessageBox.warning(self, "Acción no permitida", "No puedes eliminar la marca por defecto 'Sin Marca'.")
            return

        msg_box = QMessageBox(self)
        msg_box.setWindowTitle('Confirmar Borrado')
        msg_box.setIcon(QMessageBox.Icon.Warning)
        msg_box.setText(f"¿Estás seguro de que quieres eliminar la marca '{brand_name}'?")
        msg_box.setInformativeText(
            "Esta acción NO borrará los productos asociados.\n\n"
            "Los productos que usaban esta marca serán reasignados a 'Sin Marca'."
        )
        yes_button = msg_box.addButton("Sí, Eliminar", QMessageBox.ButtonRole.DestructiveRole)
        no_button = msg_box.addButton("Cancelar", QMessageBox.ButtonRole.RejectRole)
        msg_box.setDefaultButton(no_button)
        msg_box.exec()

        if msg_box.clickedButton() == yes_button:
            logging.info(f"Iniciando borrado de marca ID={brand_id}, Nombre='{brand_name}'")
            self.statusBar().showMessage(f"Borrando Marca {brand_id}...")
            QApplication.processEvents()
            
            success, message = self.api_client.delete_brand(brand_id)
            
            if success:
                logging.info(f"Marca {brand_id} borrada.")
                self.statusBar().showMessage(f"Marca '{brand_name}' borrada exitosamente.", 3000)
                self.load_categories_and_brands()
                self.load_brand_table()
                self.load_products() 
            else:
                QMessageBox.critical(self, "Error al Borrar", message)
                self.statusBar().showMessage(f"Error al borrar Marca {brand_id}.", 5000)
        else:
            logging.info("Borrado de marca cancelado.")
            self.statusBar().showMessage("Borrado cancelado.")
    
    def handle_delete_user(self):
        """Maneja el clic en el botón 'Borrar Usuario Seleccionado'."""
        selected_row = self.table_users.currentRow()
        if selected_row < 0:
            QMessageBox.warning(self, "Borrar Usuario", "Por favor, selecciona una fila para borrar.")
            return
    
        user_id_item = self.table_users.item(selected_row, 0)
        email_item = self.table_users.item(selected_row, 3)
        username_item = self.table_users.item(selected_row, 4)
        
        # --- 👇 MODIFICADO: Leer el WIDGET, no el ITEM 👇 ---
        try:
            widget_admin = self.table_users.cellWidget(selected_row, 5)
            is_admin_bool = widget_admin.findChild(QCheckBox).isChecked()
        except AttributeError:
             logging.error(f"handle_delete_user: No se pudo leer el checkbox 'Es Admin' para la fila {selected_row}.")
             QMessageBox.critical(self, "Error", "No se pudo leer el estado de administrador de la fila.")
             return
        # --- -------------------------------------------- ---
    
        if not user_id_item or not email_item:
            logging.error("handle_delete_user: No se pudo obtener el ID o Email del usuario seleccionado.")
            QMessageBox.critical(self, "Error", "No se pudo obtener la información del usuario seleccionado.")
            return
    
        user_id = user_id_item.text()
        email = email_item.text().lower()
        username = username_item.text() if username_item else f"ID {user_id}"
        # (is_admin_bool ya se definió arriba)

        # 1. Verificación de Seguridad: No borrar admins
        if is_admin_bool:
            logging.warning(f"El admin {self.user_email} intentó borrar al admin: {email}. Bloqueado por la UI.")
            QMessageBox.warning(self, "Acción no permitida",
                                "No se puede eliminar a un usuario administrador.\n\n"
                                "Para eliminarlo, primero edite sus permisos (desmarque 'Es Admin'), "
                                "guarde los cambios y vuelva a intentarlo.")
            return
        
        # 2. Verificación de Seguridad: No borrarse a sí mismo
        if email == self.user_email:
            logging.warning(f"El admin {self.user_email} intentó borrarse a sí mismo.")
            QMessageBox.warning(self, "Acción no permitida", "No puedes eliminar tu propia cuenta de administrador.")
            return

        # 3. Advertencia y Sugerencia de Desactivación
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle('Confirmar Borrado Permanente')
        msg_box.setIcon(QMessageBox.Icon.Warning)
        msg_box.setText(f"¿Estás SEGURO de que quieres eliminar PERMANENTEMENTE al usuario '{username}'?")
        msg_box.setInformativeText(
            "Esta acción es IRREVERSIBLE y borrará todos sus posts, comentarios, wishlists y datos de perfil.\n\n"
            "ALTERNATIVA: Si solo quieres suspender la cuenta, puedes desmarcar la casilla 'Is Active' y guardar."
        )
        yes_button = msg_box.addButton("Sí, Eliminar Todo", QMessageBox.ButtonRole.DestructiveRole)
        no_button = msg_box.addButton("Cancelar", QMessageBox.ButtonRole.RejectRole)
        msg_box.setDefaultButton(no_button)
        
        msg_box.exec()

        # 4. Ejecutar Borrado si se confirma
        if msg_box.clickedButton() == yes_button:
            logging.info(f"Iniciando borrado permanente de usuario ID={user_id}, Email='{email}'")
            self.statusBar().showMessage(f"Borrando Usuario {user_id}...")
            QApplication.processEvents()
    
            success, message = self.api_client.delete_user(user_id)
    
            if success:
                logging.info(f"Usuario {user_id} borrado exitosamente.")
                self.statusBar().showMessage(f"Usuario {user_id} borrado exitosamente.", 3000)
                self.load_users()
            else:
                QMessageBox.critical(self, "Error al Borrar", message)
                self.statusBar().showMessage(f"Error al borrar Usuario {user_id}.", 5000)
        else:
            logging.info("Borrado de usuario cancelado por el administrador.")
            self.statusBar().showMessage("Borrado cancelado.")
            
    def handle_download_reviews_pdf(self):
        """
        Descarga el reporte de reseñas del sitio en PDF.
        """
        report_format = 'pdf'
        file_extension = '.pdf'
        file_filter = "PDF Files (*.pdf)"
    
        logging.info(f"Iniciando descarga de reporte de reseñas en formato: {report_format}")
        self.statusBar().showMessage(f"Generando reporte de reseñas ({report_format.upper()})...")
        QApplication.processEvents()
    
        content_bytes, error = self.api_client.download_site_reviews_report_pdf()
    
        if error:
            logging.error(f"Error al descargar reporte de reseñas {report_format}: {error}")
            QMessageBox.critical(self, "Error al Descargar Reporte", error)
            self.statusBar().showMessage("Error al descargar reporte de reseñas.", 5000)
            return
        if not content_bytes:
            logging.warning(f"Descarga de reporte de reseñas {report_format} no devolvió contenido.")
            QMessageBox.warning(self, "Descargar Reporte", "No se recibió contenido para el reporte.")
            self.statusBar().showMessage("No se recibió contenido del reporte.", 3000)
            return
    
        default_filename = f"reporte_resenas_sitio_{datetime.date.today()}{file_extension}"
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            f"Guardar Reporte {report_format.upper()}",
            os.path.join(os.path.expanduser("~"), "Downloads", default_filename),
            file_filter
        )
    
        if save_path:
            if not save_path.lower().endswith(file_extension):
                save_path += file_extension
            try:
                with open(save_path, 'wb') as f:
                    f.write(content_bytes)
                logging.info(f"Reporte de reseñas {report_format} guardado en: {save_path}")
                self.statusBar().showMessage(f"Reporte {report_format.upper()} guardado en {save_path}", 5000)
                QMessageBox.information(self, "Reporte Guardado", f"El reporte ({report_format.upper()}) se guardó en:\n{save_path}")
            except Exception as e:
                logging.error(f"Error al guardar reporte de reseñas en {save_path}: {e}", exc_info=True)
                QMessageBox.critical(self, "Error al Guardar Archivo", f"No se pudo guardar el archivo:\n{e}")
                self.statusBar().showMessage("Error al guardar el archivo.", 5000)
        else:
            logging.info("Descarga de reporte de reseñas cancelada.")
            self.statusBar().showMessage("Descarga cancelada.", 3000)
            
    def handle_download_search_pdf(self):
        """
        Descarga el reporte de búsquedas populares en PDF.
        """
        report_format = 'pdf'
        file_extension = '.pdf'
        file_filter = "PDF Files (*.pdf)"
    
        logging.info(f"Iniciando descarga de reporte de búsquedas en formato: {report_format}")
        self.statusBar().showMessage(f"Generando reporte de búsquedas ({report_format.upper()})...")
        QApplication.processEvents()
    
        content_bytes, error = self.api_client.download_popular_search_report_pdf()
    
        if error:
            logging.error(f"Error al descargar reporte de búsquedas {report_format}: {error}")
            QMessageBox.critical(self, "Error al Descargar Reporte", error)
            self.statusBar().showMessage("Error al descargar reporte de búsquedas.", 5000)
            return
        if not content_bytes:
            logging.warning(f"Descarga de reporte de búsquedas {report_format} no devolvió contenido.")
            QMessageBox.warning(self, "Descargar Reporte", "No se recibió contenido para el reporte.")
            self.statusBar().showMessage("No se recibió contenido del reporte.", 3000)
            return
    
        default_filename = f"reporte_busquedas_populares_{datetime.date.today()}{file_extension}"
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            f"Guardar Reporte {report_format.upper()}",
            os.path.join(os.path.expanduser("~"), "Downloads", default_filename),
            file_filter
        )
    
        if save_path:
            if not save_path.lower().endswith(file_extension):
                save_path += file_extension
            try:
                with open(save_path, 'wb') as f:
                    f.write(content_bytes)
                logging.info(f"Reporte de búsquedas {report_format} guardado en: {save_path}")
                self.statusBar().showMessage(f"Reporte {report_format.upper()} guardado en {save_path}", 5000)
                QMessageBox.information(self, "Reporte Guardado", f"El reporte ({report_format.upper()}) se guardó en:\n{save_path}")
            except Exception as e:
                logging.error(f"Error al guardar reporte de búsquedas en {save_path}: {e}", exc_info=True)
                QMessageBox.critical(self, "Error al Guardar Archivo", f"No se pudo guardar el archivo:\n{e}")
                self.statusBar().showMessage("Error al guardar el archivo.", 5000)
        else:
            logging.info("Descarga de reporte de búsquedas cancelada.")
            self.statusBar().showMessage("Descarga cancelada.", 3000)

    def handle_download_report(self):
        """
        Descarga el reporte en el formato seleccionado (CSV, Excel o PDF).
        """
        selected_text = self.combo_report_format.currentText()
        report_format = 'csv'
        file_extension = '.csv'
        file_filter = "CSV Files (*.csv)"

        if "Excel" in selected_text:
            report_format = 'excel'
            file_extension = '.xlsx'
            file_filter = "Excel Files (*.xlsx)"
        elif "PDF" in selected_text:
            report_format = 'pdf'
            file_extension = '.pdf'
            file_filter = "PDF Files (*.pdf)"

        logging.info(f"Iniciando descarga de reporte de productos en formato: {report_format}")
        self.statusBar().showMessage(f"Generando reporte de productos ({report_format.upper()})...")
        QApplication.processEvents()

        content_bytes, error = self.api_client.download_product_report(report_format)

        if error:
            logging.error(f"Error al descargar reporte {report_format}: {error}")
            QMessageBox.critical(self, "Error al Descargar Reporte", error)
            self.statusBar().showMessage("Error al descargar reporte.", 5000)
            return
        if not content_bytes:
            logging.warning(f"Descarga de reporte {report_format} no devolvió contenido.")
            QMessageBox.warning(self, "Descargar Reporte", "No se recibió contenido para el reporte.")
            self.statusBar().showMessage("No se recibió contenido del reporte.", 3000)
            return

        default_filename = f"productos_activos_{datetime.date.today()}{file_extension}"
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            f"Guardar Reporte {report_format.upper()}",
            os.path.join(os.path.expanduser("~"), "Downloads", default_filename), # Sugiere 'Descargas'
            file_filter
        )

        if save_path:
            if not save_path.lower().endswith(file_extension):
                save_path += file_extension
            try:
                with open(save_path, 'wb') as f:
                    f.write(content_bytes)
                logging.info(f"Reporte {report_format} guardado en: {save_path}")
                self.statusBar().showMessage(f"Reporte {report_format.upper()} guardado en {save_path}", 5000)
                QMessageBox.information(self, "Reporte Guardado", f"El reporte ({report_format.upper()}) se guardó en:\n{save_path}")
            except Exception as e:
                logging.error(f"Error al guardar reporte en {save_path}: {e}", exc_info=True)
                QMessageBox.critical(self, "Error al Guardar Archivo", f"No se pudo guardar el archivo:\n{e}")
                self.statusBar().showMessage("Error al guardar el archivo.", 5000)
        else:
            logging.info("Descarga de reporte cancelada por el usuario.")
            self.statusBar().showMessage("Descarga cancelada.", 3000)    
            
    def handle_download_web_logs(self):
        """
        Guarda el contenido actual del visor de logs del servidor en un archivo nuevo.
        """
        log_content = self.log_text_area.toPlainText()
        
        if not log_content or "---" in log_content:
            QMessageBox.warning(self, "Descargar Logs", "No hay logs para descargar. Presiona 'Actualizar Logs' primero.")
            return

        # Sugerir un nombre de archivo por defecto
        default_filename = f"web_app_logs_{datetime.date.today()}.log"
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar Logs del Servidor",
            os.path.join(os.path.expanduser("~"), "Downloads", default_filename),
            "Log Files (*.log);;Text Files (*.txt)"
        )

        if save_path:
            try:
                with open(save_path, 'w', encoding='utf-8') as f:
                    f.write(log_content)
                logging.info(f"Logs del servidor descargados manualmente en: {save_path}")
                self.statusBar().showMessage(f"Logs guardados en {save_path}", 5000)
                QMessageBox.information(self, "Logs Guardados", f"Los logs del servidor se guardaron en:\n{save_path}")
            except Exception as e:
                logging.error(f"Error al guardar log descargado en {save_path}: {e}", exc_info=True)
                QMessageBox.critical(self, "Error al Guardar", f"No se pudo guardar el archivo:\n{e}")
                self.statusBar().showMessage("Error al guardar el archivo.", 5000)
        else:
            logging.info("Descarga de logs del servidor cancelada.")
            self.statusBar().showMessage("Descarga cancelada.", 3000)
            
    def handle_download_local_logs(self):
        """Guarda el contenido actual del visor de logs LOCALES en un archivo de 'Descargas'."""
        log_content = self.local_log_text_area.toPlainText()
        
        if not log_content or "---" in log_content:
            QMessageBox.warning(self, "Descargar Logs", "No hay logs locales para descargar.")
            return

        default_filename = f"admin_app_copia_{datetime.date.today()}.log"
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar Logs Locales",
            os.path.join(os.path.expanduser("~"), "Downloads", default_filename),
            "Log Files (*.log);;Text Files (*.txt)"
        )

        if save_path:
            try:
                with open(save_path, 'w', encoding='utf-8') as f:
                    f.write(log_content)
                logging.info(f"Logs locales descargados manualmente en: {save_path}")
                self.statusBar().showMessage(f"Logs guardados en {save_path}", 5000)
                QMessageBox.information(self, "Logs Guardados", f"Los logs locales se guardaron en:\n{save_path}")
            except Exception as e:
                logging.error(f"Error al guardar log local descargado en {save_path}: {e}", exc_info=True)
                QMessageBox.critical(self, "Error al Guardar", f"No se pudo guardar el archivo:\n{e}")
                self.statusBar().showMessage("Error al guardar el archivo.", 5000)
        else:
            logging.info("Descarga de logs locales cancelada.")
            self.statusBar().showMessage("Descarga cancelada.", 3000)
# ---
# --- SECCIÓN 6: Manejador Global de Errores
# ---

def handle_uncaught_exception(exc_type, exc_value, exc_traceback):
    """
    Manejador global para cualquier error no capturado (crash).
    Loggea el error completo y muestra un mensaje al usuario.
    """
    error_message = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    logging.critical(f"CRASH NO MANEJADO (Unhandled Exception):\n{error_message}")
    
    user_message = f"""
    ¡Ups! La aplicación encontró un error fatal y debe cerrarse.
    
    Se ha guardado un informe detallado en 'logs/admin_app.log'.
    Por favor, reporta este error.

    Mensaje del error:
    {exc_value}
    """
    
    try:
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Icon.Critical)
        msg_box.setWindowTitle("Error Fatal de la Aplicación")
        msg_box.setText(user_message)
        msg_box.setDetailedText(error_message)
        msg_box.exec()
    except Exception as e:
        logging.error(f"No se pudo mostrar el QMessageBox de error fatal: {e}")

    logging.shutdown()



# --- Asignar el manejador ---
sys.excepthook = handle_uncaught_exception

# ---
# --- SECCIÓN 7: Punto de Entrada
# ---

if __name__ == '__main__':
    app = QApplication(sys.argv)
    
    local_cache = LocalAuthCache()
    api = ApiClient(base_url=API_BASE_URL, local_auth_cache=local_cache)
    login_dialog = LoginDialog(api, local_cache)
    
    if login_dialog.exec() == QDialog.DialogCode.Accepted:
        logging.info("Login exitoso, mostrando ventana principal.")
        
        is_offline = getattr(login_dialog, 'offline_mode', False)
        user_email = login_dialog.email_input.text()
        
        main_window = MainWindow(api, is_offline=is_offline, user_email=user_email)
        main_window.show()
        sys.exit(app.exec())
    else:
        logging.info("Login cancelado por el usuario. Saliendo de la aplicación.")
        sys.exit(0)
        
