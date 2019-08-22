# encoding:utf-8
import subprocess


def check(_line, args):
    for a in args:
        if a not in _line:
            return False
    return True


if __name__ == '__main__':
    greps = [' itn from ',' to ']
    sp = subprocess.Popen('adb logcat', shell=True, stdout=subprocess.PIPE)
    for line in iter(sp.stdout.readline, ''):
        if check(line,greps):
            print(line[:-1])
