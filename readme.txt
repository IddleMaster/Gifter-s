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

Y para ejecutar docker : docker compose up --build
otros comandos que no recuerdo que hacian referentes a docker: 
docker compose ps
docker compose retart web (para reiniciarla)
para runearla creo:
docker run -p 8000:8000 imagen_django
y para construirla: docker build --no-cache -t imagen_django .

hemos tenido que agregarle unas lineas respecto al phpmyadmin

y volvimos a ejecutar docker compose up --build

Para entrar a mysql de php: 

http://localhost:8080
usuario: root
contraseña:rootpass

para entrar a la pagina:
http://localhost:8000

Recordar en caso de que no funcione hay que ponerle enel liveshare que se compartan los terminales en el localhost

El requirements normal es utilizado para iniciar el proyecto y que tenga los requisitos para arrancar, mientras que el requirements2
es para que el contenedor de docker se pueda construir}


en resumidas cuentas : requirements.txt lo usaremos solo si queremos correr el proyecto fuera de Docker (entorno local).

Y requirements2.txt: para construir el contenedot Docker!