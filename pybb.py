#! python3

import datetime
import os
import subprocess
from builtins import print
from configparser import ConfigParser
import workerpool
import shutil
import requests


# Пишем логи, вот так просто.
def write_log(message):
    with open("backup.log", 'a') as log:
        log.writelines(str(datetime.date.today()) + ': ' + message + "\n")
        log.close()


def send_push(message, priority):
    settings = params.get_push()
    url = 'https://api.pushover.net/1/messages.json'
    if settings:
        print(settings)
        notification = settings
        notification['prioroty'] = str(priority)
        notification['message'] = message
        req = requests.post(url, data=notification)
        if req.status_code == requests.codes.ok:
            print('Push-сообщение отправлено')
            write_log("Push-сообщение отправлено")
        else:
            print("Что-то пошло не так: " + str(req.json()))


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

    # То же самое, только для MySQL
    def get_mysql(self):
        if 'mysql' in self.config.sections():
            return dict(self.config.items('mysql'))
        else:
            return False

    # То же самое, только для PostgreSQL
    def get_psql(self):
        if 'psql' in self.config.sections():
            return dict(self.config.items('psql'))
        else:
            return False

    # Метод заглушка для виртуальных машин VirtualBox
    def get_vms(self):
        if 'vms' in self.config.sections():
            return dict(self.config.items('vms'))
        else:
            return False

    def get_push(self):
        if 'push' in self.config.sections():
            return dict(self.config.items('push', raw=True))
        else:
            return False


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


# Функция обработки заданий для директорий. Формирует команду для архивации и ставит задание в очередь.
def backup_folders():
    date = datetime.date.today()  # Дата исполнения с отсечением времени
    # params = Parameters()
    settings = params.get_params()
    folders = params.get_folders()

    if settings:
        try:
            localpath = os.path.join(settings['path'], str(date)) + os.sep
            if not os.path.isdir(localpath):
                os.mkdir(localpath)
            write_log(localpath)
            print('Директория для бекапов: ' + localpath)
        except:
            print('Не задана или не существует директория для хранения резервных копий!')
            exit()

        try:
            if settings['arch'] == '7zip':
                if os.name == 'nt':
                    extension = '.7z'
                    archcmd = '7z.exe a -mx=9 -mfb=64'
                    print('Архиватор: ' + settings['arch'])
                else:
                    extension = '.7z'
                    archcmd = '7za a -mx=9 -mfb=64'
                    print('Архиватор: ' + settings['arch'])
            elif settings['arch'] == 'bzip2':
                extension = '.tar.bz2'
                archcmd = 'tar -cvjSf'
                print('Архиватор: ' + settings['arch'])
            else:
                extension = '.tar.gz'
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
            fullcmd = archcmd + " " + localpath + name + extension + " " + path
            pool.put(FolderBackup(fullcmd, name))
    else:
        print("Не назначены задания для директорий!")


# Функция очистки от старых копий
def cleanup():
    # params = Parameters()
    days = int(params.get_params()['days'])
    del_path = os.path.join(params.get_params()['path'], str((datetime.date.today() - datetime.timedelta(days=days))))
    try:
        if os.path.isdir(del_path):
            shutil.rmtree(del_path)
            write_log("Бекап удален: " + del_path)
        else:
            print("Нечего удалять.")
    except:
        write_log("При очистке возникла ошибка, проверьте вручную.")
        print("Возникла какая-то ошибка при удалении")


# pgcmd = "-h localhost -U $PG_USR -c $DB"

# Иницализируем пул воркеров и очередь заданий.
pool = workerpool.WorkerPool(size=1)
# Инициализируем объект конфига
params = Parameters()
# Выполняем задания
backup_folders()
pool.shutdown()
pool.wait()
# Чистим архив
cleanup()
# Пишем всякую чухню в лог и в консоль.
send_push("Все готово, босс!", '0')
write_log("Such good, many backup, very archives, so wow!")
print("Such good, many backup, very archives, so wow!")
input("Press enter to Exit")
