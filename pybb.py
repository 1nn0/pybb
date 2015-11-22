#! python3

from builtins import print
import datetime
import subprocess
from configparser import ConfigParser
import os
import workerpool
import requests

# Пишем логи, вот так просто.
def write_log(message):
    with open("backup.log", 'a') as log:
        log.writelines(message + "\n")
        log.close()


def get_conf():

    # Проверяем есть ли конфиг и если есть, парсим его
    config = ConfigParser()
    if os.path.isfile('config.ini'):
        config.read('config.ini')
    else:
        print("Не найден конфиг!")

    # Инициируем базовые установки и берем данные из конфига.
    backups = dict(config.items('folders'))
    date = datetime.date.today() # Дата исполнения с отсечением времени
    try:
        localpath = config.get('conf', 'path') + str(date) + "\\"
        if not os.path.isdir(localpath):
            os.mkdir(localpath)
        write_log(localpath)
        print('Директория для бекапов: ' + localpath)
    except:
        print('Не задана директория для хранения резервных копий')
        exit()

    if config.get('conf', 'arch') == '7zip':
        if os.name == 'nt':
            archcmd = '7z.exe a -mx=9 -mfb=64'
        else:
            archcmd = '7za a -mx=9 -mfb=64'
    elif config.get('conf', 'arch') == 'bzip2':
        archcmd = 'tar -cvjSf'
    else:
        archcmd = 'tar -zcvf'
    print(archcmd)

    pgcmd = "-h localhost -U $PG_USR -c $DB"

    return localpath, archcmd, backups

# Класс для подготовки задачи для пула модуля workerpool. Необходим для реализации последовательного
# выполнения всех архиваций или же многопоточной архивации\копирования файлов и каталогов
# переменные path (что копируем), bpath (куда копируем), archiver (как копируем\сжимаем)

class FolderBackup(workerpool.Job):

    def __init__(self, path, bpath, archiver):
        workerpool.Job.__init__(self)
        self.path = path
        self.bpath = bpath
        self.archiver = archiver

    def run(self):
        # Проверяем что за команда нам пришла, и действуем соответствующим образом.
        if "7za" or "7z.exe" in self.archiver:
            self.archiver = self.archiver + " " + self.bpath + " " + self.path
        else:
            self.archiver = self.archiver + " " + self.path + " " + self.bpath
        subprocess.call(self.archiver, shell=True)



# Инициируем пул воркеров и очередь заданий.
pool = workerpool.WorkerPool(size=1)


# for key in backups:
#    filename = localpath+key+".7z"
#   job = FolderBackup(backups[key], filename, archcmd)
#    pool.put(job)

backup_path, command, backup_targets = get_conf()
pool.wait()
pool.shutdown()

write_log("Such good, many backup, very archives, so wow!")
print("Such good, many backup, very archives, so wow!")
input("Press enter to Exit")