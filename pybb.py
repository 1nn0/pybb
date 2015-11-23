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
        notification = settings
        if int(priority) == 2:
            notification['priority'] = int(priority)
            notification['retry'] = 30
            notification['expire'] = 360
        else:
            notification['priority'] = int(priority)
        notification['message'] = message
        print(notification)
        req = requests.post(url, data=notification)
        if req.status_code == requests.codes.ok:
            print('Push-сообщение отправлено')
            write_log("Push-сообщение отправлено")
        else:
            print("Что-то пошло не так: " + str(req.json()))
    else:
        print('Не заданы параметры для Push-уведомлений, проверьте секцию [push] в конфиге')


# Класс для получения настроек для заданий из конфига. Конфиг должен лежать в той-же директории
# что и сам скрипт.
class Parameters(object):
    def __init__(self):
        self.config = ConfigParser()
        if os.path.isfile('config.ini'):
            self.config.read('config.ini')
        else:
            print("Не найден конфиг!")
            exit(1)

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
            conf = dict(self.config.items('conf'))
            if conf['arch'] == '7zip':
                if os.name == 'nt':
                    conf['extension'] = '.7z'
                    conf['archcmd'] = '7z.exe a -mx=9 -mfb=64'
                    conf['archcmd_sql'] = '7z.exe a -mx=9 -mfb=64 -si '
                    print('Архиватор: ' + conf['arch'])
                else:
                    conf['extension'] = '.7z'
                    conf['archcmd'] = '7za a -mx=9 -mfb=64'
                    conf['archcmd_sql'] = '7za a -mx=9 -mfb=64 -si '
                    print('Архиватор: ' + conf['arch'])
            elif conf['arch'] == 'bzip2':
                conf['extension'] = '.tar.bz2'
                conf['archcmd'] = 'tar -cvjSf'
                conf['archcmd_sql'] = 'tar -cvjSf -T'
                print('Архиватор: ' + conf['arch'])
            else:
                conf['extension'] = '.tar.gz'
                conf['archcmd'] = 'tar -zcvf'
                conf['archcmd_sql'] = 'tar -zcvf -T'
                print('Архиватор: ' + conf['arch'])
            conf['localpath'] = os.path.join(conf['path'], str(datetime.date.today())) + os.sep
            return conf

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

class DoBackup(workerpool.Job):
    def __init__(self, archivate, job_name):
        workerpool.Job.__init__(self)
        self.archivate = archivate
        self.name = job_name

    def run(self):
        try:
            subprocess.check_call(self.archivate, shell=True)
            write_log('Задание успешно выполнено: ' + self.name)
            send_push('Архивация выполнена: ' + self.name, -2)
        except:
            send_push('Возникла ошибка при выполнинии задания: ' + self.name, 1)
            write_log('Возникла ошибка при выполнинии задания: ' + str(subprocess.CalledProcessError))


# Функция обработки заданий для директорий. Формирует команду для архивации и ставит задание в очередь.

def backup_folders(settings, folders):
    #   settings = params.get_params()
    #   folders = params.get_folders()

    if settings:
        try:
            localpath = settings['localpath']
            if not os.path.isdir(localpath):
                os.mkdir(localpath)
            write_log(localpath)
            print('Директория для бекапов: ' + localpath)
        except:
            print('Не задана или не существует директория для хранения резервных копий!')
            exit(1)

        try:
            archcmd = settings['archcmd']
            extension = settings['extension']
        except:
            print('Отсутсвует или неверно задана команда архивирования!')
            exit(1)

    else:
        print('В конфиге отсутствуют настройки архивации и ханения! Проверь конфиг!')
        exit(1)

    if folders:
        for (name, path) in folders.items():
            if name.endswith('_r'):
                if not os.path.isdir(os.path.join(localpath, name)):
                    os.mkdir(os.path.join(localpath, name))
                for item in os.listdir(path):
                    if not item.startswith('.') or os.path.isfile(os.path.join(path, item)):
                        fullcmd = archcmd + " " + os.path.join(localpath, name, item) + extension + " " + os.path.join(
                            path, item)
                        pool.put(DoBackup(fullcmd, item))
            else:
                fullcmd = archcmd + " " + localpath + name + extension + " " + path
                pool.put(DoBackup(fullcmd, name))
    else:
        print("Не назначены задания для директорий!")


# Функция обработки заданий для баз данных MySQL\PostgreSQL

def backup_databases(type, sql, settings):
    user = sql['user']
    password = sql['password']
    host = sql['host']
    bases = sql['bases']
    archcmd = settings['archcmd_sql']
    localpath = settings['localpath']
    extension = settings['extension']
    if not os.path.isdir(localpath):
        os.mkdir(localpath)
    if type == 'mysql':
        for base in bases.split(" "):
            archcmd2 = archcmd + os.path.join(localpath, base) + extension
            fullcmd = 'mysqldump --opt -u {0} -p{1} -h {2} {3}'.format(user, password, host,
                                                                       base) + " " + "|" + " " + archcmd2
            print(fullcmd)
            # pool.put(DoBackup(fullcmd, base))
    elif type == 'psql':
        for base in bases.split(" "):
            archcmd2 = archcmd + os.path.join(localpath, base) + extension
            fullcmd = 'pg_dump -u {0} -h {2} -c {3}'.format(user, host, base) + " " + "|" + " " + archcmd2
            print(fullcmd)
            # pool.put(DoBackup(fullcmd, base))


# Функция очистки от старых резервных копий
def cleanup():
    try:
        days = int(params.get_params()['days'])
        del_path = os.path.join(params.get_params()['path'],
                                str((datetime.date.today() - datetime.timedelta(days=days))))
        if os.path.isdir(del_path):
            shutil.rmtree(del_path)
            write_log("Бекап удален: " + del_path)
        else:
            print("Нечего удалять.")
    except KeyError:
        write_log("При очистке возникла ошибка: не задан параметр days в секции [conf]")
        print("Возникла какая-то ошибка при удалении: не задан параметр days в секции [conf]")
        send_push('При очистке возникла ошибка', '1')
        exit(1)
    except:
        write_log("При очистке возникла какая-то ошибка, проверьте вручную")
        send_push('При очистке возникла ошибка', '1')


# Иницализируем пул воркеров и очередь заданий.
pool = workerpool.WorkerPool(size=1)
# Инициализируем объект конфига
params = Parameters()
setup = params.get_params()
# Выполняем задания
backup_folders(setup, params.get_folders())
backup_databases('mysql', params.get_mysql(), setup)
pool.shutdown()
pool.wait()
# Чистим архив
cleanup()
# Пишем всякую чухню в лог и в консоль.
send_push("Все готово, босс!", -1)
write_log("Such good, many backup, very archives, so wow!")
print("Such good, many backup, very archives, so wow!")
input("Press enter to Exit")
