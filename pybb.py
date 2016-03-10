#!/usr/bin/python3.4

import datetime
import os
import subprocess
from builtins import print
from configparser import ConfigParser
import workerpool
import shutil
import requests
from ftplib import FTP


# Пишем логи, вот так просто.
def write_log(message):
    with open("backup.log", 'a') as log:
        log.writelines(str(datetime.date.today()) + ': ' + message + "\n")
        log.close()


# Функция реальзует отправку Push-уведомлений через сервис Pushover
def send_push(message, priority):
    settings = params.get_push()
    url = 'https://api.pushover.net/1/messages.json'
    if settings:
        notification = settings
        if int(priority) == 2:
            notification['priority'] = int(priority)
            notification['retry'] = 30
            notification['expire'] = 360
            notification['title'] = 'ВНИМАНИЕ!'
        else:
            notification['priority'] = int(priority)
            notification['title'] = 'Инфо.'
        notification['message'] = message
        req = requests.post(url, data=notification)
        if req.status_code == requests.codes.ok:
            write_log("Push-сообщение отправлено успешно!")
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
            os._exit(1)

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
                    conf['archcmd'] = '7z.exe a -m0=lzma2 -mx=9 -mfb=64'
                    conf['archcmd_sql'] = '7z.exe a -m0=lzma2 -mx=9 -mfb=64 -si '
                    print('Архиватор: ' + conf['arch'])
                else:
                    conf['extension'] = '.7z'
                    conf['archcmd'] = '7za a -m0=lzma2 -mx=9 -mfb=64'
                    conf['archcmd_sql'] = '7za a -m0=lzma2 -mx=9 -mfb=64 -si '
                    print('Архиватор: ' + conf['arch'])
            elif conf['arch'] == 'bzip2':
                conf['extension'] = '.tar.bz2'
                conf['archcmd'] = 'tar -cvjSf'
                conf['archcmd_sql'] = 'bzip2 -cq9 > '
                print('Архиватор: ' + conf['arch'])
            else:
                conf['extension'] = '.tar.gz'
                conf['archcmd'] = 'tar -zcvf'
                conf['archcmd_sql'] = 'gzip -9 > '
                print('Архиватор: ' + conf['arch'])
            conf['localpath'] = os.path.join(conf['path'], str(datetime.date.today()))
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

    def get_ftp(self):
        if 'ftp' in self.config.sections():
            ftp_settings = dict(self.config.items('ftp', raw=True))
            if 'user' in ftp_settings.keys():
                if ftp_settings['user'] == '':
                    ftp_settings['user'] = 'Anonymous'
            else:
                print('Ошибка в секции [ftp] параметр user')
            return ftp_settings
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
    if settings:
        try:
            localpath = settings['localpath']
            if not os.path.isdir(localpath):
                os.mkdir(localpath)
            write_log(localpath)
            print('Директория для бекапов: ' + localpath)
        except:
            print('Не задана или не существует директория для хранения резервных копий!')
            os._exit(1)

        try:
            archcmd = settings['archcmd']
            extension = settings['extension']
        except:
            print('Отсутсвует или неверно задана команда архивирования!')
            os._exit(1)

    else:
        print('В конфиге отсутствуют настройки архивации и ханения! Проверь конфиг!')
        os._exit(1)

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
                fullcmd = archcmd + " " + os.path.join(localpath, name) + extension + " " + path
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
            pool.put(DoBackup(fullcmd, base))
    elif type == 'psql':
        for base in bases.split(" "):
            archcmd2 = archcmd + os.path.join(localpath, base) + extension
            fullcmd = 'pg_dump -U {0} -h {1} -c {2}'.format(user, host, base) + " " + "|" + " " + archcmd2
            print(fullcmd)
            pool.put(DoBackup(fullcmd, base))


# Функция бекапа виртуальных машин VirtualBox (пока просто заглушка)
def backup_vms(settings, vms_settings):
    return False

def ftp_upload(path, ftp):
    if os.path.isdir(path):
        files = os.listdir(path)
        os.chdir(path)
        for f in files:
            if os.path.isfile(os.path.join(path, f)):
                fh = open(f, 'rb')
                ftp.storbinary('STOR %s' % f, fh)
                fh.close()
            elif os.path.isdir(os.path.join(path, f)):
                ftp.mkd(f)
                ftp.cwd(f)
                ftp_upload(os.path.join(path, f), ftp)
    else:
        f = open(path, 'rb')
        ftp.storbinary('STOR %s' % os.path.basename(path), f)
        f.close()

    ftp.cwd('..')
    os.chdir('..')

# Функция для синхронизации локальных каталогов с ФТП-сервером.
def ftp_sync(settings, ftp_settings):

    localpath = os.path.dirname(settings['localpath'])
    print(localpath)
    remote_path = ftp_settings['remote_path']
    host = ftp_settings['host']
    user = ftp_settings['user']
    if not user == 'Anonymous':
        password = ftp_settings['password']
    else:
        password = ''
    try:
        ftp = FTP(host)
    except:
        print('Не могу соединится с FTP-сервером, проверьте настройки')
        write_log('Не могу соединится с FTP-сервером, проверьте настройки')
        send_push('Не могу соединится с FTP-сервером, проверьте настройки', 1)

    ftp.login(user=user, passwd=password)
    ftp.set_pasv(True)
    ftp.cwd(remote_path)
    print('Ftp NLST ' + str(ftp.nlst()))
    os.chdir(os.path.abspath(localpath))

    local_files = set(os.listdir(localpath))
    remote_files = set(ftp.nlst())
    transfer_list = list(local_files - remote_files)
    delete_list = list(remote_files - local_files)
    print('Transfer list ' + str(transfer_list))
    print('Delete list ' + str(delete_list))
    for item in transfer_list:
        if os.path.isdir(os.path.join(localpath, item)):
            ftp.mkd(remote_path + '/' + item)
            ftp.cwd(remote_path + '/' + item)
            item = os.path.join(localpath, item)
            print(item)
            ftp_upload(item, ftp)
        else:
            ftp_upload(item, ftp)


    ftp.quit()
    ftp.close()


# Функция очистки от старых архивов
def cleanup(settings):
    try:
        days = int(settings['days'])
        del_path = os.path.join(settings['path'],
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
if params.get_psql():
    backup_databases('psql', params.get_psql(), setup)
elif params.get_mysql():
    backup_databases('mysql', params.get_mysql(), setup)
else:
    write_log("Нет БД для резервирования")

#Завершаем нашу очередь заданий
pool.shutdown()
pool.wait()

# Чистим архив
cleanup(setup)

# Синхронизируем с ФТП, если настроили
if params.get_ftp():
    ftp_sync(setup, params.get_ftp())
else:
    print("Сихронизация с ФТП не настроена.")

# Пишем всякую чухню в лог и в консоль.
send_push("Все готово, босс!", -1)
write_log("Such good, many backup, very archives, so wow!")
print("Such good, many backup, very archives, so wow!")
