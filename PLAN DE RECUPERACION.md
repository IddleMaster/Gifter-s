1 Instalamos Docker y Docker compose
sudo apt-get update
sudo apt-get install docker-ce docker-ce-cli containerd.io docker-compose-plugin


2 Obtenemos el código de la aplicación //repositorio

git clone https://github.com/IddleMaster/Gifter-s /opt/gifters
cd /opt/gifters

3 Restaurar Archivos Críticos:

nano .env 
# (Pegar el contenido del .env respaldado y guardar)    

# (Asumiendo que subiste 'media.zip' al servidor)
unzip media.zip
# (Mover/copiar la carpeta 'media' a la raíz del proyecto, si no está ya allí)

4Levantar los servicios sin datos

docker-compose up -d

5. Restaurar la Base de Datos (RPO):

# (Asumiendo que se subió 'backup-xxxx.sql' a /tmp/ en el host)
docker-compose cp /tmp/backup-xxxx.sql db:/backups/backup-a-restaurar.sql

# Comando de restauración:
docker-compose exec db sh -c "mysql -u gifters_user -pgifters_pass gifters < /backups/backup-a-restaurar.sql"

6. Verificación Final:
docker-compose logs -f web
