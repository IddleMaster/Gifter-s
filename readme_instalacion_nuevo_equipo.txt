GUÍA PARA LEVANTAR GIFTERS DESDE GITHUB (LOCAL + DOCKER + ESCRITORIO)
1. Clonar proyecto
git clone https://github.com/LO-QUE-SEA/Gifter-s.git
cd Gifter-s

2. Eliminar cualquier entorno virtual incluido
Remove-Item -Recurse -Force .\desktop_env -ErrorAction SilentlyContinue

3. Crear entorno virtual nuevo
python -m venv desktop_env
& ".\desktop_env\Scripts\Activate.ps1"
python -m pip install --upgrade pip


Instalar:
pip install PyQt6
pip install requests


(Agregar manualmente cualquier librería que pida el desktop_admin al ejecutar)


6. Construir imagen Docker
docker compose build --no-cache web

7. Levantar el stack
docker compose up

8. Importar base de datos MySQL (solo la primera vez)
En la máquina antigua (maquina donde funcione todo basicamente):
entrar al phpmyadmin (localhost:8080) y exportar la base de datos "gifters"

En la máquina nueva (importar):
entrar a phpmyadmin y darle a la base de datos "gifters" (esta creada pero le faltan datos) ir a las tablas, darle
a seleccionar todo y luego eliminar todas las tablas
Luego ir a importar en la barra superior y importar la base de datos del equipo antiguo donde si funciona la base de datos

9. Crear superusuario (si es necesario ya con la base de datos restaurada ya deberia estar el super user JAMES)
docker compose exec web python manage.py createsuperuser


11. Levantar aplicación web local
docker compose up


Abrir:

http://localhost:8000

12. Levantar aplicación de escritorio

Con el entorno virtual activo:

& ".\desktop_env\Scripts\Activate.ps1"
python desktop_admin/main.py
