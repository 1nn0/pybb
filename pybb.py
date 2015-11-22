#! python3

import datetime
import os
import subprocess
from builtins import print
from configparser import ConfigParser

import workerpool


# Пишем логи, вот так просто.
def write_log(message):
    with open("backup.log", 'a') as log:
        log.writelines(message + "\n")
        log.close()

# Класс для получения настроек для заданий из конфига. Конфиг должен лежать в той-же директории
# что и сам скрипт.
class Parameters(object):

    def __init__(self):
        self.config = ConfigParser()
        if os.path.isfile('config.ini'):
            self.config.read('config.ini')
        else:
            print("Не найден конфиг!")
            exit()

    # Метод проверяет задана ли секция в конфиге отвечающая за пути к директориям для бекапа
    # если задана, возвращает словарь вида {имя_бекапа: путь}
    def get_folders(self):

        if 'folders' in self.config.sections():
            return dict(self.config.items('folders'))
        else:
            return False

    # Метод проверяет задана ли секция отвечающая за параметры архивирования и хранения
    # резервных копий, возвращает словарь вида {название_параметра: значение}
    def get_params(self):

        if 'conf' in self.config.sections():
            return dict(self.config.items('conf'))
        else:
            return False

    # Метод заглушка для MySQL
    def get_mysql(self):
        pass

    # Метод заглушка для PostgreSQL
    def get_psql(self):
        pass

    # Метод заглушка для виртуальных машин VirtualBox
    def get_vms(self):
        pass


# Класс для подготовки задачи для пула модуля workerpool. Необходим для реализации последовательного
# выполнения всех архиваций или же многопоточной архивации\копирования файлов и каталогов
# На вход принимает строку с командой и выполняет ее через subprocess.

class FolderBackup(workerpool.Job):
    def __init__(self, archivate, job_name):
        workerpool.Job.__init__(self)
        self.archivate = archivate
        self.name = job_name

    def run(self):
        try:
            subprocess.check_call(self.archivate, shell=True)
            write_log('Задание успешно выполнено: ' + self.name)
        except:
            write_log('Возникла ошибка при выполнинии задания: ' + str(subprocess.CalledProcessError))

def backup_folders():

    date = datetime.date.today()  # Дата исполнения с отсечением времени
    params = Parameters()
    settings = params.get_params()
    folders = params.get_folders()

    if settings:
        try:
            localpath = settings['path'] + str(date) + "\\"
            if not os.path.isdir(localpath):
                os.mkdir(localpath)
            write_log(localpath)
            print('Директория для бекапов: ' + localpath)
        except:
            print('Не задана директория для хранения резервных копий!')
            exit()

        try:
            if settings['arch'] == '7zip':
                if os.name == 'nt':
                    archcmd = '7z.exe a -mx=9 -mfb=64'
                    print('Архиватор: ' + settings['arch'])
                else:
                    archcmd = '7za a -mx=9 -mfb=64'
                    print('Архиватор: ' + settings['arch'])
            elif settings['arch'] == 'bzip2':
                archcmd = 'tar -cvjSf'
                print('Архиватор: ' + settings['arch'])
            else:
                archcmd = 'tar -zcvf'
                print('Архиватор: ' + settings['arch'])
        except:
            print('Отсутсвует или неверно задана команда архивирования!')
            exit()

    else:
        print('В конфиге отсутствуют настройки архивации и ханения! Проверь конфиг!')
        exit()

    if folders:
        for (name, path) in folders.items():
            if 'tar' in archcmd:
                fullcmd = archcmd + " " + path + " " + localpath + name
                pool.put(FolderBackup(fullcmd, name))
            else:
                fullcmd = archcmd + " " + localpath + name + " " + path
                pool.put(FolderBackup(fullcmd, name))
    else:
        print("Не назначены задания для директорий!")

# pgcmd = "-h localhost -U $PG_USR -c $DB"

# Инициируем пул воркеров и очередь заданий.
pool = workerpool.WorkerPool(size=1)
backup_folders()
pool.wait()
pool.shutdown()

write_log("Such good, many backup, very archives, so wow!")
print("Such good, many backup, very archives, so wow!")
input("Press enter to Exit")
