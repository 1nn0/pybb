from builtins import print
import datetime
import subprocess
from configparser import ConfigParser
import os
import workerpool
import requests

#Проверяем есть ли конфиг и если есть, парсим его
config = ConfigParser()
if os.path.isfile('config.ini'):
    config.read('config.ini')
else:
    print("Не найден конфиг!")

#Класс для подготовки задачи для пула модуля workerpool. Необходим для реализации последовательного
#выполнения всех архиваций или же многопоточной архивации\копирования файлов и каталогов
# переменные path (что копируем), bpath (куда копируем), archiever (как копируем\сжимаем)

class FolderBackup(workerpool.Job):

    def __init__(self, path, bpath, archiever):
        workerpool.Job.__init__(self)
        self.path = path
        self.bpath = bpath
        self.archiever = archiever

    def run(self):
        # Проверяем что за команда нам пришла, и действуем соответствующим образом.
        if "7za" or "7z.exe" in self.archiever:
            self.archiever = self.archiever + " " + self.bpath + " " + self.path
        subprocess.call(self.archiever, shell=True)



# Преобразовываем вложенный список значений в словарь.
backups = dict(config.items('folders'))

date = datetime.date.today() # Дата исполнения с отсечением времени
print(date)
localpath = 'test_bak\\' + str(date) + "\\\\"
os.mkdir(localpath)
ftppath = '/backup/' + backup_name + '/' + str(date)
pguser = "postgres"
pgpass = "postgres"
archcmd = '7z.exe a -mx=9 -mfb=64'
pgcmd = "-h localhost -U $PG_USR -c $DB"

for key in backups:
    filename = localpath+key+".7z"
    full_cmd = archcmd + " " + filename + " " + backups[key]
    print(full_cmd)
    subprocess.call(full_cmd, shell=True)