import sys
import os
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QMessageBox, QDialog, QFormLayout, QFileDialog, QStatusBar,
    QStackedWidget, QTableWidget, QTableWidgetItem, QHeaderView,QAbstractItemView
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from api_client import ApiClient

# URL base de tu API de Django
API_BASE_URL = "http://127.0.0.1:8000/api"

class LoginDialog(QDialog):
    """
    Diálogo de inicio de sesión para el administrador.
    (Esta clase no necesita cambios)
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

        # Corregido para usar 'json' y 'correo'
        success, message = self.api_client.login(email, password)
        
        if success:
            self.accept() # Cierra el diálogo de login con éxito
        else:
            QMessageBox.critical(self, "Login Fallido", message)


class MainWindow(QMainWindow):
    """
    Ventana principal de la aplicación de administración.
    (Esta clase ha sido rediseñada para coincidir con los Mockups)
    """
    def __init__(self, api_client):
        super().__init__()
        self.setWindowTitle("Panel de Administración de Gifter's")
        self.setGeometry(100, 100, 900, 700) # Tamaño ajustado
        self.api_client = api_client

        # --- Menú Superior (Barra de Archivo) ---
        # Lo mantenemos igual
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("Archivo")
        exit_action = file_menu.addAction("Salir")
        exit_action.triggered.connect(self.close)

        #EN CASO DE QUE SE QUIERA AGREGAR LA FUNCION DE IMPORTAR CSV DESDE EL MENU
      # product_menu = menu_bar.addMenu("Productos")
      # import_action = product_menu.addAction("Importar desde CSV...")
       # import_action.triggered.connect(self.open_csv_importer)
        
        # --- Widget Central y Layout Principal ---
        # Usaremos un layout horizontal para dividir la app en Sidebar | Contenido
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0) # Sin bordes
        main_layout.setSpacing(0) # Sin espacio entre widgets

        # --- 1. Panel Lateral (Sidebar) ---
        sidebar_widget = self.create_sidebar()
        main_layout.addWidget(sidebar_widget)

        # --- 2. Área de Contenido (con QStackedWidget) ---
        # QStackedWidget nos permite tener "páginas" y cambiar entre ellas
        self.stacked_widget = QStackedWidget()
        main_layout.addWidget(self.stacked_widget, 1) # '1' hace que ocupe el resto del espacio

        # --- 3. Crear las Páginas ---
        self.page_reportes = self.create_reportes_page()
        self.page_admin = self.create_admin_page()
        self.page_catalogo = self.create_catalogo_page()

        # --- 4. Añadir las Páginas al Stack ---
        self.stacked_widget.addWidget(self.page_reportes)   # Índice 0
        self.stacked_widget.addWidget(self.page_admin)      # Índice 1
        self.stacked_widget.addWidget(self.page_catalogo)   # Índice 2

        # --- 5. Conectar Botones del Sidebar a las Páginas ---
        self.btn_reportes.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(0))
        self.btn_admin.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(1))
        self.btn_catalogo.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(2))
        self.btn_importar.clicked.connect(self.open_csv_importer) 
        
        # --- Barra de estado ---
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage("Listo.")
        #-----CARGA INICIAL DE DATOS!----
        self.load_products()
        self.load_users()
        
        

    def create_sidebar(self):
        """Crea el panel lateral izquierdo con los botones de navegación."""
        sidebar_widget = QWidget()
        # Estilo basado en el mockup (azul oscuro)
        sidebar_widget.setStyleSheet("""
            QWidget {
                background-color: #0a2342;
                color: white;
            }
            QPushButton {
                background-color: #004a99;
                color: white;
                border: none;
                padding: 15px;
                text-align: left;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #005bc5;
            }
            QPushButton:pressed {
                background-color: #003366;
            }
        """)
        sidebar_widget.setFixedWidth(220) # Ancho fijo para el sidebar

        sidebar_layout = QVBoxLayout(sidebar_widget)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(1)

        # Título/Logo
        title_label = QLabel("Gifter's Admin")
        title_label.setFont(QFont("Arial", 20, QFont.Weight.Bold))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setContentsMargins(10, 20, 10, 30) # Espaciado
        sidebar_layout.addWidget(title_label)

        # Botones de navegación
        self.btn_reportes = QPushButton("Reportes")
        self.btn_admin = QPushButton("Administración")
        self.btn_catalogo = QPushButton("Catálogo")
        self.btn_importar = QPushButton("Importar CSV")
        
        sidebar_layout.addWidget(self.btn_reportes)
        sidebar_layout.addWidget(self.btn_admin)
        sidebar_layout.addWidget(self.btn_catalogo)
        sidebar_layout.addWidget(self.btn_importar)
        
        sidebar_layout.addStretch() # Empuja todo hacia arriba
        return sidebar_widget

    def create_reportes_page(self):
        """Crea la página de Reportes (Mockup 2)."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 20, 20, 20)
        
        title = QLabel("Reportes")
        title.setFont(QFont("Arial", 24, QFont.Weight.Bold))
        layout.addWidget(title)
        
        layout.addWidget(QPushButton("Categoría"))
        
        layout.addStretch() # Empuja el botón de descarga al fondo
        
        layout.addWidget(QPushButton("Descargar"))
        
        return page

    def create_admin_page(self):
        """Crea la página de Administración (Mockup 3)."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 20, 20, 20)
        
        title = QLabel("Administración de Usuarios")
        title.setFont(QFont("Arial", 24, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Tabla para mostrar usuarios
        self.table_users = QTableWidget()
        self.table_users.setColumnCount(7) # Basado en tu mockup
        self.table_users.setHorizontalHeaderLabels(["ID", "Nombre", "Apellido", "Correo", "Usename", "Es Admin","Is Active"])
        # Hacer que las columnas ocupen todo el ancho
        self.table_users.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        
        # --- CAMBIOS AQUÍ ---
        self.table_users.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked)
        self.table_users.setSortingEnabled(False)
        # Conectar a la nueva función para manejar cambios de usuario
        self.table_users.itemChanged.connect(self.handle_user_change) 
        
        layout.addWidget(self.table_users)

        return page





    def create_catalogo_page(self):
        """Crea la página de Catálogo (Mockup 4)."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 20, 20, 20)
        
        title = QLabel("Catálogo de Productos")
        title.setFont(QFont("Arial", 24, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Tabla para mostrar productos
        self.table_products = QTableWidget()
        self.table_products.setColumnCount(4) # Ejemplo: ID, Nombre, Precio, Categoría
        self.table_products.setHorizontalHeaderLabels(["ID", "Nombre", "Precio", "Categoría"])
        self.table_products.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        # Permitir edición al hacer doble clic
        self.table_products.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked)
        # Deshabilitar ordenación por clic en cabecera por ahora
        self.table_products.setSortingEnabled(False)
        # Conectar la señal 'itemChanged' a una función (que crearemos luego)
        self.table_products.itemChanged.connect(self.handle_product_change)
        # --------------------    
        layout.addWidget(self.table_products)

        # TODO: Llamar a la función para cargar datos de la API
        # self.load_products()
        
        return page


    def load_products(self):
        """Carga los productos desde la API y los muestra en la tabla."""
        self.statusBar.showMessage("Cargando productos...")
    # Bloquear señales mientras llenamos la tabla para evitar llamadas a handle_product_change
        self.table_products.blockSignals(True)

        products, error = self.api_client.get_products()

        if error:
            QMessageBox.critical(self, "Error al cargar productos", error)
            self.statusBar.showMessage("Error al cargar productos.")
            self.table_products.blockSignals(False) # Desbloquear señales
            return

        if products is None:
            QMessageBox.warning(self, "Productos", "No se pudieron obtener los productos.")
            self.statusBar.showMessage("No se pudieron obtener los productos.")
            self.table_products.blockSignals(False) # Desbloquear señales
            return

        self.table_products.setRowCount(0)
        self.table_products.setRowCount(len(products))

        for row_index, product in enumerate(products):
        # Obtener datos (usando .get con default '')
            product_id = str(product.get('id_producto', ''))
            nombre = product.get('nombre_producto', '')
            precio = str(product.get('precio', ''))
        # Usar los nombres de categoría y marca que añadimos al Serializer
            categoria_nombre = product.get('categoria_nombre', '') 
            marca_nombre = product.get('marca_nombre', '') 

        # Crear QTableWidgetItem para cada celda
            item_id = QTableWidgetItem(product_id)
            item_name = QTableWidgetItem(nombre)
            item_price = QTableWidgetItem(precio)
            item_category = QTableWidgetItem(categoria_nombre)
            item_brand = QTableWidgetItem(marca_nombre) # Nuevo item para marca

        # --- SOLO EL ID NO ES EDITABLE ---
            item_id.setFlags(item_id.flags() & ~Qt.ItemFlag.ItemIsEditable)

            # Añadir items a la tabla
            self.table_products.setItem(row_index, 0, item_id)
            self.table_products.setItem(row_index, 1, item_name)
            self.table_products.setItem(row_index, 2, item_price)
            self.table_products.setItem(row_index, 3, item_category)
            self.table_products.setItem(row_index, 4, item_brand) # Añadir marca

        self.statusBar.showMessage(f"Se cargaron {len(products)} productos.")
        self.table_products.blockSignals(False)


    def handle_product_change(self, item):
        """
        Se llama cuando el contenido de una celda en la tabla de productos cambia.
        """
        # No procesar cambios si estamos llenando la tabla
        if self.table_products.signalsBlocked():
            return

        row = item.row()
        col = item.column()
        new_value = item.text()

        product_id_item = self.table_products.item(row, 0)
        if not product_id_item:
            print("Error: No se pudo obtener el ID del producto.")
            return

        product_id = product_id_item.text()
        header_name = self.table_products.horizontalHeaderItem(col).text()

        print(f"Enviando actualización: Producto ID={product_id}, Campo='{header_name}', Nuevo Valor='{new_value}'")
        self.statusBar.showMessage(f"Guardando Producto {product_id}...")
        QApplication.processEvents() # Actualiza la UI para mostrar "Guardando..."

        # --- LLAMADA A LA API ---
        success, message = self.api_client.update_product(product_id, header_name, new_value)
        # -------------------------

        if success:
            self.statusBar.showMessage(f"Producto {product_id} guardado.", 3000) # Muestra por 3 segundos
            # Opcional: Podrías cambiar el color de fondo de la celda brevemente para indicar éxito
        else:
            QMessageBox.critical(self, "Error al Guardar", message)
            self.statusBar.showMessage(f"Error al guardar Producto {product_id}.", 5000) # Muestra por 5 segundos
            # --- DESHACER EL CAMBIO VISUAL ---
            # Volver a cargar los datos de ESA fila podría ser lo más simple
            # O guardar el valor anterior y restaurarlo:
            # current_value = item.text() # Valor actual (el que falló al guardar)
            # item.setText(valor_anterior) # Necesitarías haber guardado el valor_anterior antes
            # Por ahora, simplemente informamos del error. Recargar manualmente refrescará.
            self.load_products() # Recarga toda la tabla para deshacer el cambio visual si falla
        
    def open_csv_importer(self):
        """
        Abre un diálogo para seleccionar un archivo CSV y lo sube a la API.
        (Esta función no necesita cambios)
        """
        file_path, _ = QFileDialog.getOpenFileName(self, "Seleccionar Archivo CSV", "", "CSV Files (*.csv)")
        
        if file_path:
            self.statusBar.showMessage("Subiendo archivo CSV...")
            QApplication.processEvents() # Actualiza la UI
            
            success, message = self.api_client.upload_products_csv(file_path)
            
            if success:
                QMessageBox.information(self, "Importación Iniciada", message)
                self.statusBar.showMessage("Importación iniciada en el servidor.")
                # TODO: Podrías llamar a self.load_products() aquí para refrescar la tabla
            else:
                QMessageBox.critical(self, "Error de Importación", message)
                self.statusBar.showMessage("Error al subir el archivo.")
                
    def load_users(self):
        """Carga los usuarios desde la API y los muestra en la tabla."""
        self.statusBar.showMessage("Cargando usuarios...")
        self.table_users.blockSignals(True) # Bloquear señales

        users, error = self.api_client.get_users()

        if error:
            QMessageBox.critical(self, "Error al cargar usuarios", error)
            self.statusBar.showMessage("Error al cargar usuarios.")
            self.table_users.blockSignals(False) # Desbloquear
            return

        if users is None:
             QMessageBox.warning(self, "Usuarios", "No se pudieron obtener los usuarios.")
             self.statusBar.showMessage("No se pudieron obtener los usuarios.")
             self.table_users.blockSignals(False) # Desbloquear
             return

        self.table_users.setRowCount(0) 
        self.table_users.setRowCount(len(users))

        for row_index, user in enumerate(users):
            # Obtener datos del AdminUserSerializer
            user_id = str(user.get('id', ''))
            nombre = user.get('nombre', '')
            apellido = user.get('apellido', '')
            correo = user.get('correo', '')
            username = user.get('nombre_usuario', '')
            es_admin = str(user.get('es_admin', 'False')) # Convertir booleano a string
            is_active = str(user.get('is_active', 'False')) # Convertir booleano a string

            # Crear items
            item_id = QTableWidgetItem(user_id)
            item_nombre = QTableWidgetItem(nombre)
            item_apellido = QTableWidgetItem(apellido)
            item_correo = QTableWidgetItem(correo)
            item_username = QTableWidgetItem(username)
            item_es_admin = QTableWidgetItem(es_admin)
            item_is_active = QTableWidgetItem(is_active)

            # --- SOLO ID Y CORREO NO SON EDITABLES ---
            item_id.setFlags(item_id.flags() & ~Qt.ItemFlag.ItemIsEditable)
            item_correo.setFlags(item_correo.flags() & ~Qt.ItemFlag.ItemIsEditable)

            # Añadir items a la tabla
            self.table_users.setItem(row_index, 0, item_id)
            self.table_users.setItem(row_index, 1, item_nombre)
            self.table_users.setItem(row_index, 2, item_apellido)
            self.table_users.setItem(row_index, 3, item_correo)
            self.table_users.setItem(row_index, 4, item_username)
            self.table_users.setItem(row_index, 5, item_es_admin)
            self.table_users.setItem(row_index, 6, item_is_active)

        self.statusBar.showMessage(f"Se cargaron {len(users)} usuarios.")
        self.table_users.blockSignals(False) # Desbloquear señales
        
    def handle_user_change(self, item):
        """
        Se llama cuando el contenido de una celda en la tabla de usuarios cambia.
        """
        if self.table_users.signalsBlocked():
            return

        row = item.row()
        col = item.column()
        new_value = item.text()

        user_id_item = self.table_users.item(row, 0) # ID está en columna 0
        if not user_id_item:
            print("Error: No se pudo obtener el ID del usuario.")
            return

        user_id = user_id_item.text()
        header_name = self.table_users.horizontalHeaderItem(col).text()

        # Validar que el campo sea editable antes de enviar
        if header_name in ["ID", "Correo"]:
            print(f"El campo '{header_name}' no es editable.")
            # Podríamos deshacer el cambio visual aquí si quisiéramos
            return

        print(f"Enviando actualización de usuario: ID={user_id}, Campo='{header_name}', Nuevo Valor='{new_value}'")
        self.statusBar.showMessage(f"Guardando Usuario {user_id}...")
        QApplication.processEvents()

        # --- LLAMADA A LA API ---
        success, message = self.api_client.update_user(user_id, header_name, new_value)
        # -------------------------

        if success:
            self.statusBar.showMessage(f"Usuario {user_id} guardado.", 3000) 
        else:
            QMessageBox.critical(self, "Error al Guardar Usuario", message)
            self.statusBar.showMessage(f"Error al guardar Usuario {user_id}.", 5000)
            # Recargar la tabla para deshacer el cambio visual si falla
            self.load_users()


if __name__ == '__main__':
    """
    (Esta sección no necesita cambios)
    """
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