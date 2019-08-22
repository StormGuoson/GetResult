import subprocess
import time, os

if __name__ == '__main__':
    header = []
    path = r'D:\2019-5-1\6c06541cc204408034b\tmp_wav'
    for s in os.listdir(path):
        h = s[:s.find('_')]
        if h not in header:
            header.append(h)
    for s in header:
        cmd_meg = 'type %s\\%s*.pcm >> %s\\total_%s.pcm' % (path, s, path, s)
        cmd_del = 'del %s\\%s*.pcm' % (path, s)
        os.system(cmd_meg)
        os.system(cmd_del)
