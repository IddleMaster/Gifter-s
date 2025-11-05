HACER ESTO CHIQUILLOS!!!

Instala las dependencias: `pip install -r requirements.txt`

Aplica las migraciones: `python manage.py migrate`

Ejecuta el servidor: `python manage.py runserver`

# Configurar tu usuario de Git (si no lo has hecho antes)
git config --global user.name "Tu Nombre"
git config --global user.email "tu.email@ejemplo.com"
solo en caso de para configurar el usuario, de todas formas debería funcionar con el source control de la izquierda en visual


AHORA EN CASO DE QUERER HACER MIGRACIONES : 
Se trabaja en models.py 
Luego de crear las tablas ejecutamos :

docker compose exec web python manage.py makemigrations
docker compose exec web python manage.py migrate

RECORDAR TENER ABIERTO DOCKER PARA QUE FUNCIONE!

Y para ejecutar docker : docker compose up --build
otros comandos que no recuerdo que hacian referentes a docker: 
docker compose ps
docker compose restart web (para reiniciarla MUY UTIL!!! pruebalo cuando no arranque!)
para runearla creo:
docker run -p 8000:8000 imagen_django
y para construirla: docker build --no-cache -t imagen_django .

hemos tenido que agregarle unas lineas respecto al phpmyadmin

y volvimos a ejecutar docker compose up --build
PARA HACER LAS MIGRACIONES EN DOCKER:

docker compose exec web python manage.py makemigrations
docker compose exec web python manage.py migrate

COMANDOS PERSONALIZADOS CREADOS PARA DOCKER!

Con este comando se sube el csv
 docker compose exec web python manage.py import_products productos.csv

CON ESTE COMANDO AÑADIMOS IMAGENES DEAFULTS
 docker compose exec web python manage.py assign_default_images

para confirmar, ver en phpmyadmin

HE AQUÍ UN COMANDO PARA AGREGAR O EDITAR CATEGORÍAS:

docker-compose exec web python manage.py update_categories



Para entrar a mysql de php: 

http://localhost:8080
usuario: root
contraseña:rootpass

para entrar a la pagina:
http://localhost:8000

Recordar en caso de que no funcione hay que ponerle enel liveshare que se compartan los terminales en el localhost

El requirements normal es utilizado para iniciar el proyecto y que tenga los requisitos para arrancar, mientras que el requirements2
es para que el contenedor de docker se pueda construir


en resumidas cuentas : requirements.txt lo usaremos solo si queremos correr el proyecto fuera de Docker (entorno local).

Y requirements2.txt: para construir el contenedot Docker!


MÁS ORDENADO:

# Entrar al contenedor y ejecutar migraciones
docker compose exec web bash
python manage.py makemigrations
python manage.py migrate
exit

# O hacerlo en un solo comando
docker compose exec web python manage.py makemigrations
docker compose exec web python manage.py migrate


credenciales django
giftersg4@gmail.com
gifters123.


James@gmail.com email
1234 Nombre
apellido alcornoque
Pass: 123456
PAGINAS...

http://localhost:8000/feed/
                                /id/
http://localhost:8000/chat/room/1/


Para actualizar el descargable despues de cambiar el escritorio: 
 pyinstaller --onefile --windowed desktop_admin/main.py

meiliservidorgithub
GiftersClave123

########################
PARA COPIAR UN BACKUP AL ESCRITORIO POR EJ:
    docker-compose cp db-backup:/backups/NOMBRE_DEL_ARCHIVO.sql .
    #Así se vería:; docker-compose cp db-backup:/backups/backup-2025-10-30_03-00-01.sql .


###Para poder hacer una restauración del respaldo! (Backup de BD)
docker-compose exec db sh -c "mysql -u gifters_user -pgifters_pass gifters < /backups/NOMBRE_DEL_ARCHIVO.sql"
##$## así se bvería
docker-compose exec db sh -c "mysql -u gifters_user -pgifters_pass gifters < /backups/backup-2025-10-30_03-00-01.sql"
