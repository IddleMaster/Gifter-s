# desktop_admin/dialogs.py (REEMPLAZAR CreateProductDialog)

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QComboBox, QPushButton, QFileDialog, QMessageBox, QWidget
)
from PyQt6.QtGui import QPixmap, QIcon
from PyQt6.QtCore import Qt, QSize
import os # Importar os para manejar rutas de archivo

class CreateProductDialog(QDialog):
    def __init__(self, categories, brands, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Crear Nuevo Producto")
        self.setGeometry(100, 100, 400, 500) # Ajustar tamaño para la imagen
        self.setWindowIcon(QIcon("path/to/your/icon.png")) # Opcional: añade un icono

        self.categories = categories
        self.brands = brands
        self.selected_image_path = None # Nueva variable para la ruta de la imagen

        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)

        # Campo Nombre
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("<b>Nombre:</b>"))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Nombre del producto")
        name_layout.addWidget(self.name_input)
        main_layout.addLayout(name_layout)

        # Campo Descripción
        desc_layout = QHBoxLayout()
        desc_layout.addWidget(QLabel("<b>Descripción:</b>"))
        self.description_input = QLineEdit()
        self.description_input.setPlaceholderText("Descripción breve del producto")
        desc_layout.addWidget(self.description_input)
        main_layout.addLayout(desc_layout)

        # ComboBox Categoría
        cat_layout = QHBoxLayout()
        cat_layout.addWidget(QLabel("<b>Categoría:</b>"))
        self.category_combo = QComboBox()
        self.category_combo.addItem("--- Selecciona una Categoría ---")
        for cat in self.categories:
            self.category_combo.addItem(cat['name'], cat['id'])
        cat_layout.addWidget(self.category_combo)
        main_layout.addLayout(cat_layout)

        # ComboBox Marca
        brand_layout = QHBoxLayout()
        brand_layout.addWidget(QLabel("<b>Marca:</b>"))
        self.brand_combo = QComboBox()
        self.brand_combo.addItem("--- Selecciona una Marca ---")
        for brand in self.brands:
            self.brand_combo.addItem(brand['name'], brand['id'])
        brand_layout.addWidget(self.brand_combo)
        main_layout.addLayout(brand_layout)

        # === 👇 SECCIÓN NUEVA: Imagen del Producto 👇 ===
        image_section_layout = QVBoxLayout()
        image_section_layout.setSpacing(10)
        image_section_layout.addWidget(QLabel("<b>Imagen del Producto:</b>"))

        # 1. Label para mostrar la imagen (preview)
        self.image_preview_label = QLabel("No hay imagen seleccionada")
        self.image_preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_preview_label.setFixedSize(200, 200) # Tamaño fijo para la preview
        self.image_preview_label.setStyleSheet("border: 1px dashed gray; background-color: #f0f0f0;")
        image_section_layout.addWidget(self.image_preview_label, alignment=Qt.AlignmentFlag.AlignCenter)

        # 2. Botón para seleccionar imagen
        btn_select_image = QPushButton("Seleccionar Imagen...")
        btn_select_image.clicked.connect(self.select_image)
        btn_select_image.setStyleSheet("""
            QPushButton { 
                background-color: #007bff; color: white; padding: 8px 15px; 
                border-radius: 5px; font-size: 14px;
            }
            QPushButton:hover { background-color: #0056b3; }
        """)
        image_section_layout.addWidget(btn_select_image, alignment=Qt.AlignmentFlag.AlignCenter)
        
        main_layout.addLayout(image_section_layout)
        # ====================================================

        # Botones de acción
        button_layout = QHBoxLayout()
        self.cancel_button = QPushButton("Cancelar")
        self.cancel_button.clicked.connect(self.reject)
        self.cancel_button.setStyleSheet("""
            QPushButton { 
                background-color: #6c757d; color: white; padding: 10px 20px; 
                border-radius: 5px; font-size: 14px;
            }
            QPushButton:hover { background-color: #5a6268; }
        """)
        button_layout.addWidget(self.cancel_button)

        self.save_button = QPushButton("Guardar Producto")
        self.save_button.clicked.connect(self.accept)
        self.save_button.setStyleSheet("""
            QPushButton { 
                background-color: #28a745; color: white; padding: 10px 20px; 
                border-radius: 5px; font-size: 14px;
            }
            QPushButton:hover { background-color: #218838; }
        """)
        button_layout.addWidget(self.save_button)
        main_layout.addLayout(button_layout)

    def select_image(self):
        """Abre un cuadro de diálogo para seleccionar un archivo de imagen."""
        options = QFileDialog.Option.DontUseNativeDialog
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar Imagen del Producto", "",
            "Archivos de Imagen (*.png *.jpg *.jpeg *.gif);;Todos los Archivos (*)",
            options=options
        )
        if file_path:
            self.selected_image_path = file_path
            # Mostrar la imagen en el QLabel de preview
            pixmap = QPixmap(file_path)
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(
                    self.image_preview_label.size(), 
                    Qt.AspectRatioMode.KeepAspectRatio, 
                    Qt.TransformationMode.SmoothTransformation
                )
                self.image_preview_label.setPixmap(scaled_pixmap)
                self.image_preview_label.setText("") # Borra el texto "No hay imagen..."
            else:
                self.image_preview_label.setText("Error al cargar imagen")
                self.selected_image_path = None # Resetear si hay un error

    def get_product_data(self):
        """Retorna un diccionario con los datos del producto, incluyendo la ruta de la imagen."""
        return {
            "name": self.name_input.text(),
            "description": self.description_input.text(),
            "category_id": self.category_combo.currentData(),
            "brand_id": self.brand_combo.currentData(),
            "image_path": self.selected_image_path # Retorna la ruta de la imagen
        }

    def accept(self):
        """
        Validación antes de cerrar el diálogo.
        """
        name = self.name_input.text().strip()
        description = self.description_input.text().strip()
        category_id = self.category_combo.currentData()
        brand_id = self.brand_combo.currentData()

        if not name:
            QMessageBox.warning(self, "Campos Incompletos", "El nombre del producto no puede estar vacío.")
            return
        if not description:
            QMessageBox.warning(self, "Campos Incompletos", "La descripción del producto no puede estar vacía.")
            return
        if category_id is None:
            QMessageBox.warning(self, "Campos Incompletos", "Debes seleccionar una categoría.")
            return
        if brand_id is None:
            QMessageBox.warning(self, "Campos Incompletos", "Debes seleccionar una marca.")
            return
        # La imagen no es obligatoria, así que no se valida aquí.

        super().accept() # Si todo es válido, cierra el diálogo