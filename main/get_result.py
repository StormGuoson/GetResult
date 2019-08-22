# -*- coding: utf-8-*-
import signal
from Queue import Queue
import os
import subprocess
import sys
import threading
import time
import json
import win32clipboard as w
import win32con
import wx
from pykeyboard import PyKeyboard

reload(sys)
sys.setdefaultencoding('utf-8')

k = PyKeyboard()

L = threading.Lock()


def set_clipboard_text(t):
    w.OpenClipboard()
    w.EmptyClipboard()
    w.SetClipboardData(win32con.CF_TEXT, t.encode("gbk"))
    w.CloseClipboard()


def paste():
    k.press_key(k.control_l_key)
    time.sleep(0.03)
    k.tap_key('v')
    time.sleep(0.03)
    k.release_key(k.control_l_key)


def click(n):
    time.sleep(.03)
    k.tap_key(n)
    time.sleep(.03)


def auto_set(_text, _sn, _frame):
    global L
    L.acquire()
    try:
        _as(_text, _sn, _frame)
    except Exception as e:
        _frame.txt_log.write(repr(e) + '\n')
    L.release()


def _as(_text, _sn, frame):
    frame.txt_log.SetDefaultStyle(wx.TextAttr('BLACK'))
    frame.txt_log.write(_text + '\n')
    if _sn is not '':
        frame.txt_log.SetDefaultStyle(wx.TextAttr('BLUE'))
        frame.txt_log.write(_sn + '\n')
    if _text is '':
        return
    for d in range(len(ACTIVE_DEVICES)):
        d = str(d)
        if ('text' + d) not in DATA:
            return
        if DATA['text' + d] == '':
            return
    if not debug_mode:
        for s in range(len(ACTIVE_DEVICES)):
            s = str(s)
            set_clipboard_text(DATA['text' + s])
            paste()
            time.sleep(0.08)
            k.tap_key(k.escape_key)
            time.sleep(0.08)
            if DATA['sn' + s] is not '':
                k.tap_key(k.right_key)
                time.sleep(0.08)
                set_clipboard_text(DATA['sn' + s])
                time.sleep(0.08)
                paste()
                time.sleep(0.08)
            k.tap_key(k.escape_key)
            if int(s) == len(ACTIVE_DEVICES) - 1:
                k.tap_key(k.down_key)
                time.sleep(0.08)
            else:
                k.tap_key(k.right_key)
                time.sleep(0.08)
        for e in range(len(ACTIVE_DEVICES)):
            if DATA['sn' + str(e)] is not '':
                time.sleep(0.08)
                k.tap_key(k.left_key)
                time.sleep(0.08)
            if int(e) != len(ACTIVE_DEVICES) - 1:
                k.tap_key(k.left_key)
                time.sleep(0.08)
    # if write_rec:
    #     msg = ''
    #     for s in range(len(ACTIVE_DEVICES)):
    #         msg += DATA['text' + str(s)] + '\t' + DATA['sn' + str(s)]
    #         if s + 1 != len(ACTIVE_DEVICES):
    #             msg += '\t'
    #     save_memory(SAVE_RESULTS_PATH, msg + '\n')

    for d in range(len(ACTIVE_DEVICES)):
        d = str(d)
        DATA['text' + d] = DATA['sn' + d] = ''


STOP_ALL = True
debug_mode = False
is_save_log = False
SAVE_RESULTS_PATH = r'd:\log'
SAVE_AUDIO = r'd:\audio'
td = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]

ACTIVE_DEVICES = []  # 激活的设备
DEVICES_ORDERED = []  # 设备的连接顺序
UNACTIVE_DEVICES = []  # 休眠的设备
ACTIVE_MODULES = [-1, -1, -1, -1, -1]  # 各设备的模式

S111 = 'S111'
S201 = 'S201'

CURRENT_MODULE = S111  # 当前模式

cb_mod_list = [S111, S201, u'——']

parent_mod = {10000: S111,
              10001: S201}

child_mod = {}
activities = {}
DATA = {}


def save_log(no):
    dev = ACTIVE_DEVICES[int(no)]
    log_path = os.path.join(SAVE_RESULTS_PATH, '%s.txt' % str(dev))
    if not os.path.exists(SAVE_RESULTS_PATH):
        os.makedirs(SAVE_RESULTS_PATH)
    f = open(log_path, 'a+')
    return f


def write_wakeup(txt, no, *arg):
    L.acquire()
    txt.txt_log.SetDefaultStyle(wx.TextAttr('BLACK'))
    for d in range(len(ACTIVE_DEVICES)):
        d = str(d)
        DATA['text' + d] = DATA['sn' + d] = ''
    if ('wakeup_count' + no) in DATA:
        DATA['wakeup_count' + no] += 1
    else:
        DATA['wakeup_count' + no] = 1
    if len(arg) > 0:
        txt.txt_log.write(
            str(ACTIVE_DEVICES[int(no)]) + u' 唤醒次数 ' + str(DATA['wakeup_count' + no]) + '_' + str(arg[0]) + '\n')

    elif ('wakeup_angle' + no) in DATA:
        txt.txt_log.write(str(ACTIVE_DEVICES[int(no)]) + u' 唤醒次数 ' + str(DATA['wakeup_count' + no]) + '_' + DATA[
            'wakeup_angle' + no] + '\n')
    else:
        txt.txt_log.write(str(ACTIVE_DEVICES[int(no)]) + u' 唤醒次数 ' + str(DATA['wakeup_count' + no]) + '\n')
    print(ACTIVE_DEVICES[int(no)] + 'wakeupTime: ' + str(DATA['wakeup_count' + no]))
    L.release()


def main_doing(_line, _module, _res_txt, no):
    if _module == S111:
        module_s111(_line, _res_txt, no)
    elif _module == S201:
        module_s201(_line, _res_txt, no)


def module_s111(line, txt, no):
    # 08-21 11:54:45.063 I/TNLOG_SDK( 7897): [Agent](BaseSRCallback.java:37):OpenCloseAppSRCallback callback semantic: {"a":{"domain":"smart_car_control","intent":"open_app","query":"打开导航","session_complete":true,"slots":[{"name":"app","slot_struct":1,"type":"usr.app","values":[{"text":"导航","original_text":"导航"}]}]},"b":{"text":"导航","original_text":"导航"},"c":{"name":"app","slot_struct":1,"type":"usr.app","values":[{"text":"导航","original_text":"导航"}]},"bCloudResult":false,"is_wakeup":true,"operation":"open_app","semantic":{"domain":"smart_car_control","intent":"open_app","query":"打开导航","session_complete":true,"slots":[{"name":"app","slot_struct":1,"type":"usr.app","values":[{"text":"导航","original_text":"导航"}]}]},"service":"smart_car_control"} wecarnavi version: 3.1.0.h wecarspeech version: 2.1.5.006 clientsdk version: 1.0.2-284973
    # 08-21 11:54:15.253 D/TNLOG_SDK( 3403): [Agent](DayNightModeWakeupCallback.java:27):onWakeup 白天模式
    # 08-21 16:10:41.301 D/_WeCarSpeech_( 3234): [ClientDispatcher](ClientDispatcher.java:134):dispatchSystemWakeup onWakeup taskId = 156637504110901 sceneId = 8998c5de-8ac5-4733-b250-7106abecf762 word = 打开电台

    if 'wakeup_Type:wordWakeup' in line:
        write_wakeup(txt, no)
    elif 'onSpeechResult' in line and u'最终结果' in line:
        line = str(line[line.find('{'):line.rfind('}') + 1])
        line = json.loads(line)
        text = line['text']
        DATA['text' + no] = text
        # DATA['sn' + no] = 'null'
        # auto_set(DATA['text' + no], DATA['sn' + no], txt)
    # 唤醒后识别
    # elif u' itn from ' in line and ' to ' in line:
    #     # print line
    #     text = line[line.find(' to ') + 4: -1]
    #     DATA['text' + no] = text
    # elif u'semantic' in line:
    #     print line
    elif 'dbc:' in line:
        DATA['sn' + no] = ''
        tts = line[line.find('dbc:') + 4:-1]
        DATA['text' + no] = tts
        auto_set(DATA['text' + no], DATA['sn' + no], txt)


def module_s201(line, txt, no):
    if 'TSSCallback onWakeupResult type:0' in line:
        write_wakeup(txt, no)
    elif 'onSpeechResult' in line and u'最终结果' in line:
        line = str(line[line.find('{'):line.rfind('}') + 1])
        line = json.loads(line)
        text = line['text']
        DATA['text' + no] = text
        # DATA['sn' + no] = 'null'
        # auto_set(DATA['text' + no], DATA['sn' + no], txt)
    elif 'TSSCallback onWakeupResult type:1' in line:
        DATA['sn' + no] = ''
        line = str(line[line.find('{'):line.rfind('}') + 1])
        line = json.loads(line)
        text = line['keyword']

        DATA['text' + no] = text
        # DATA['sn' + no] = 'null'
        # auto_set(DATA['text' + no], DATA['sn' + no], txt)

    elif ':playTTS text' in line:
        tts = line[line.find('text:') + 5:line.rfind(',')]
        DATA['sn' + no] = tts
        auto_set(DATA['text' + no], DATA['sn' + no], txt)


class AsynchronousFileReader(threading.Thread):
    """
    Helper class to implement asynchronous reading of a file
    in a separate thread. Pushes read lines on a queue to
    be consumed in another thread.
    """

    def __init__(self, fd, queue):
        assert isinstance(queue, Queue)
        assert callable(fd.readline)
        threading.Thread.__init__(self)
        self._fd = fd
        self._queue = queue

    def run(self):
        """The body of the tread: read lines and put them on the queue."""
        for line in iter(self._fd.readline, ''):
            self._queue.put(line)

    def eof(self):
        """Check whether there is no more content to expect."""
        return not self.is_alive() and self._queue.empty()


def consume(command, frame, no):
    """
    Example of how to consume standard output and standard error of
    a subprocess asynchronously without risk on deadlocking.
    """
    print(command)
    global STOP_ALL, L
    time.sleep(float(no) / 10.0 * 3)
    td[int(no)] = time.time()
    # Launch the command as subprocess.
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               shell=True)
    # Launch the asynchronous readers of the process' stdout and stderr.
    stdout_queue = Queue()
    stdout_reader = AsynchronousFileReader(process.stdout, stdout_queue)
    stdout_reader.start()
    stderr_queue = Queue()
    stderr_reader = AsynchronousFileReader(process.stderr, stderr_queue)
    stderr_reader.start()
    # Check the queues if we received some output (until there is nothing more to get).
    frame.txt_log.SetDefaultStyle(wx.TextAttr('BLACK'))
    frame.txt_log.write(('No%s_' % str(int(no) + 1)) + ACTIVE_DEVICES[int(no)] + u' <<<开始>>>' + '\n')
    _mod = get_own_mod(no)
    log = None
    if is_save_log:
        log = save_log(no)
    while not stdout_reader.eof() or not stderr_reader.eof():
        if STOP_ALL:
            print('stop')
            L.acquire()
            frame.btn_start.SetLabel(u'开始')
            frame.txt_log.SetDefaultStyle(wx.TextAttr('BLACK'))
            frame.txt_log.write(('No%s' % str(int(no) + 1)) + u' <<<停止>>>' + '\n')
            L.release()
            break
        while not stdout_queue.empty():
            line = stdout_queue.get().decode("utf-8", errors="ignore")
            try:
                if is_save_log:
                    log.write(line[:-1])
                main_doing(line, _mod, frame, no)
            except Exception as e:
                frame.txt_log.SetDefaultStyle(wx.TextAttr('RED'))
                frame.txt_log.write(repr(e))
        while not stderr_queue.empty():
            line = stderr_queue.get().decode("utf-8", errors="ignore")
            L.acquire()
            frame.txt_log.SetDefaultStyle(wx.TextAttr('RED'))
            frame.txt_log.write(line)
            L.release()
            if 'replaced' in line:
                continue
            print('Received line on standard error: ' + repr(line))
            frame.txt_log.SetDefaultStyle(wx.TextAttr('RED'))
            frame.txt_log.write(repr(line))
            STOP_ALL = True
            frame.btn_start.SetLabel(u'开始')
        # Sleep a bit before asking the readers again.
        try:
            time.sleep(.1)
        except KeyboardInterrupt:
            pass
    if is_save_log:
        log.close()
    frame.FindWindowById(22).Enable(True)
    # Let's be tidy and join the threads we've started.
    # stdout_reader.join()
    # stderr_reader.join()
    # Close subprocess' file descriptors.
    # process.stdout.close()
    # process.stderr.close()
    # os.system("taskkill /t /f /pid %s" % process.pid)
    os.popen("taskkill /t /f /pid %s" % process.pid)
    process.kill()
    if STOP_ALL:
        return
    print('unlink')
    frame.btn_start.SetLabel(u'开始')
    L.acquire()
    try:
        frame.txt_log.SetDefaultStyle(wx.TextAttr('RED'))
        frame.txt_log.write(ACTIVE_DEVICES[int(no)] + u' <<<断开连接>>>' + '\n')
    except IndexError as e:
        print(repr(e))
    frame.refresh_devices()
    L.release()
    STOP_ALL = True


def save_memory(filename, _content):
    mp = str(filename[:filename.rfind(os.sep)]).encode('utf-8')
    if not os.path.exists(mp):
        os.makedirs(mp)
    with open(filename.decode(), "a+") as f:
        f.write(_content)


def get_own_mod(no):
    no = int(no)
    while no not in DEVICES_ORDERED:
        no += 1
    i = DEVICES_ORDERED.index(int(no))
    _mod = ACTIVE_MODULES[i]
    if _mod == u'——' or _mod == -1:
        _mod = CURRENT_MODULE
    return _mod


def get_device_list():
    global UNACTIVE_DEVICES, DEVICES_ORDERED
    device_sn_list = []
    UNACTIVE_DEVICES = []
    m_file = os.popen("adb devices")
    for line in m_file.readlines():
        if line.find("List of devices attached") != -1 or line.find('start') != -1 or line.find('daemon') != -1:
            continue
        elif len(line) > 5:
            device_sn_list.append(line.split("\t")[0])
            UNACTIVE_DEVICES.append(line.split("\t")[0])
    m_file.close()
    # if len(device_sn_list) == 1:
    #     DEVICES_ORDERED.append(0)
    return device_sn_list


class MyFrame(wx.Frame):
    btn_start = ''
    txt_log = ''
    devices_list = []
    cb_mods_lists = []
    sp = [None, None, None]

    def __init__(self):
        wx.Frame.__init__(self, None, -1, 'GG -- ver:20190821', size=(730, 350),
                          style=wx.DEFAULT_FRAME_STYLE | wx.STAY_ON_TOP)
        self.Centre()
        # 配置
        cb_lists = [wx.CheckBox(self, 21, label=u'上屏', pos=(10, 10)),
                    wx.CheckBox(self, 22, label=u'保存日志', pos=(10, 40))
                    ]
        cb_lists[0].SetValue(True)
        for cb in cb_lists:
            self.Bind(wx.EVT_CHECKBOX, self.set_options, cb)
        self.Bind(wx.EVT_TEXT, self.save_path, wx.TextCtrl(self, 23, value=r'd:\log', pos=(10, 60)))

        self.FindWindowById(22).Show(False)
        self.FindWindowById(23).Show(False)

        # 选择模式
        index = 0
        for key, value in parent_mod.items():
            if key == S111:
                rb = wx.RadioButton(self, key, label=value, pos=(10, 100), style=wx.RB_GROUP)
            else:
                rb = wx.RadioButton(self, key, label=value, pos=(10, 100 + (index * 30)))
            self.Bind(wx.EVT_RADIOBUTTON, self.set_module, rb)
            index += 1
        i = list(parent_mod.keys())[0]
        self.FindWindowById(i).SetValue(True)

        # 模式细化
        # combo_cw_tv = wx.ComboBox(self, 10000 * 2, pos=(90, 96), size=(90, -1), choices=child_mod[10000])
        # combo_cw_tv.SetValue(child_mod[10000][0])
        # combo_cw_tv.Bind(wx.EVT_COMBOBOX, self.set_mode_tree)
        # combo_huawei = wx.ComboBox(self, 10001 * 2, pos=(90, 126), size=(90, -1), choices=child_mod[10001])
        # combo_huawei.SetValue(child_mod[10001][0])
        # combo_huawei.Bind(wx.EVT_COMBOBOX, self.set_mode_tree)
        # combo_ainemo = wx.ComboBox(self, 10002 * 2, pos=(90, 156), size=(90, -1), choices=child_mod[10002])
        # combo_ainemo.SetValue(child_mod[10002][0])
        # combo_ainemo.Bind(wx.EVT_COMBOBOX, self.set_mode_tree)

        # 开始btn
        self.btn_start = wx.Button(self, 31, label=u'开始', pos=(200, 20))
        self.Bind(wx.EVT_BUTTON, self.button_action, self.btn_start)
        # 清屏btn
        self.Bind(wx.EVT_BUTTON, self.button_action, wx.Button(self, 32, label=u'C', pos=(495, 55), size=(25, 25)))
        # 选择设备btn
        self.Bind(wx.EVT_BUTTON, self.button_action, wx.Button(self, 33, u'刷新设备', pos=(540, 10)))
        # 重启btn
        self.Bind(wx.EVT_BUTTON, self.button_action, wx.Button(self, 34, label=u'重启设备', pos=(370, 20)))
        # 开始录音
        self.Bind(wx.EVT_BUTTON, self.button_action, wx.Button(self, 36, label=u'开始录音', pos=(180, 258)))
        # 保存音频btn
        self.Bind(wx.EVT_BUTTON, self.button_action, wx.Button(self, 35, label=u'保存音频', pos=(420, 258)))
        self.FindWindowById(35).Enable(False)
        # 输出log
        self.txt_log = wx.TextCtrl(self, 41, pos=(190, 80), size=(330, 170),
                                   style=wx.TE_MULTILINE | wx.EXPAND | wx.TE_READONLY | wx.TE_RICH2)
        # 保存音频路径
        self.Bind(wx.EVT_TEXT, self.save_path, wx.TextCtrl(self, 24, value=r'd:\audio', pos=(270, 260), size=(140, -1)))
        # 开始录音
        self.cb_dev_lists = []
        for i in range(5):
            self.cb_dev_lists.append(
                wx.CheckBox(self, 60 + i, label=u'等待设备连接                ', pos=(540, 50 * (i + 1))))
            self.Bind(wx.EVT_CHECKBOX, self.active_devices, self.cb_dev_lists[i])

            combo_mod = wx.ComboBox(self, 40 + i, pos=(530, 20 + 50 * (i + 1)), size=(-1, -1), choices=cb_mod_list)
            combo_mod.SetValue(u'——')
            combo_mod.Bind(wx.EVT_COMBOBOX, self.set_single_mod)
            self.cb_mods_lists.append(combo_mod)

        self.refresh_devices()

    @staticmethod
    def save_path(event):
        global SAVE_RESULTS_PATH, SAVE_AUDIO
        txt = event.GetEventObject()
        if txt.GetId() == 23:
            SAVE_RESULTS_PATH = txt.GetValue()
        elif txt.GetId() == 24:
            SAVE_AUDIO = txt.GetValue()

    @staticmethod
    def set_options(event):
        global is_save_log, debug_mode
        _id = event.GetEventObject().GetId()
        cbs = event.GetEventObject()
        if cbs.IsChecked():
            if _id == 21:
                debug_mode = False
            elif _id == 22:
                is_save_log = True

        else:
            if _id == 21:
                debug_mode = True
            elif _id == 22:
                is_save_log = False

    def set_module(self, event):
        global CURRENT_MODULE, STOP_ALL, ACTIVE_DEVICES
        STOP_ALL = True
        mid = event.GetEventObject().GetId()
        if mid in child_mod:
            select = self.FindWindowById(mid * 2).GetSelection()
            if select == -1:
                select = 0
            CURRENT_MODULE = child_mod[mid][select]
        else:
            CURRENT_MODULE = parent_mod[mid]
        print(CURRENT_MODULE)

    def set_mode_tree(self, event):
        global CURRENT_MODULE
        tgs = event.GetEventObject().GetSelection()
        tid = event.GetEventObject().GetId()
        CURRENT_MODULE = child_mod[tid / 2][tgs]
        (self.FindWindowById(tid / 2)).SetValue(True)

        print(CURRENT_MODULE)

    @staticmethod
    def set_single_mod(event):
        global ACTIVE_MODULES
        index = event.GetEventObject().GetId() - 40
        tgs = event.GetEventObject().GetValue()
        ACTIVE_MODULES[DEVICES_ORDERED.index(index)] = tgs
        print(ACTIVE_MODULES)

    def button_action(self, event):
        global STOP_ALL
        btn = event.GetEventObject()
        bid = btn.GetId()
        # 开始按钮
        if bid == 31:
            if STOP_ALL:
                if len(ACTIVE_DEVICES) < 1:
                    self.txt_log.SetDefaultStyle(wx.TextAttr('RED'))
                    self.txt_log.write(u'没有连接设备！！！\n')
                    return
                self.txt_log.SetValue('')
                DATA.clear()
                DATA['osn'] = ''
                STOP_ALL = False
                btn.SetLabel(u'停止')
                self.FindWindowById(22).Enable(False)
                for no in range(len(ACTIVE_DEVICES)):
                    ThreadLogcat(self, no)
            else:
                STOP_ALL = True
                btn.SetLabel(u'开始')
                self.FindWindowById(22).Enable(True)

        # 清屏clear
        elif bid == 32:
            self.txt_log.SetValue('')
            for i, dev in enumerate(ACTIVE_DEVICES):
                cm = get_own_mod(i)
                print(cm)
                if cm in activities.keys():
                    stop = 'adb -s %s shell am force-stop %s' % (
                        dev, activities[cm].split('/')[0])
                    start = 'adb -s %s shell am start %s' % (dev, activities[cm])
                    os.popen(stop).close()
                    os.popen(start).close()
                    # 刷新设备按钮
            DATA.clear()
        elif bid == 33:
            STOP_ALL = True
            self.btn_start.SetLabel('')
            self.btn_start.SetLabel(u'开始')
            self.refresh_devices()
        # 重启设备
        elif bid == 34:
            answer = wx.MessageBox(u'确认重启设备？', u'请确认！', wx.YES_NO | wx.YES_DEFAULT | wx.ICON_EXCLAMATION)
            if answer == wx.YES:
                for dev in ACTIVE_DEVICES:
                    ThreadReboot(dev)
        # 保存音频
        elif bid == 35:
            self.FindWindowById(36).SetLabel(u'开始录音')
            btn.Enable(False)
            if len(ACTIVE_DEVICES) == 0:
                self.txt_log.SetDefaultStyle(wx.TextAttr('RED'))
                self.txt_log.write(u'<<<<<没有连接设备>>>>>\n')
                return
            root = wx.Dialog(self, 9999, title=u'正在导出,请稍等！', size=(-1, 300))
            root.Center()
            root.Show()
            self.FindWindowById(36).Enable(True)
            for no in range(len(ACTIVE_DEVICES)):
                os.popen(
                    'adb -s %s shell rm /sdcard/tencent/wecarspeech/data/dingdang/debug_save_wav.conf' %
                    ACTIVE_DEVICES[
                        no])
                pid = os.popen('adb -s %s shell ps | findstr speech' % ACTIVE_DEVICES[no]).readlines()[0].split()[1]
                os.popen('adb -s %s shell kill -9 %s' % (ACTIVE_DEVICES[no], pid))
                wx.StaticText(root, pos=(5, 45 + no * 40), label='dev%s:' % str(no))
                gauge = wx.Gauge(root, range=100, size=(300, 25), pos=(0, 40 + no * 40), style=wx.GA_HORIZONTAL)
                gauge.Centre(wx.HORIZONTAL)
                ThreadPullAud(gauge, no)

        # 开始录音
        elif bid == 36:
            btn.SetLabel(u'录音中')
            self.FindWindowById(35).Enable(True)
            for no in range(len(ACTIVE_DEVICES)):
                threading.Thread(target=self.start_record, args=(no,)).start()

    def active_devices(self, event):
        global ACTIVE_DEVICES, STOP_ALL, DEVICES_ORDERED, ACTIVE_MODULES
        STOP_ALL = True
        cb_mods = self.cb_mods_lists
        for c in cb_mods:
            c.SetSelection(len(cb_mod_list) - 1)
        ACTIVE_MODULES = [-1, -1, -1, -1, -1]
        self.btn_start.SetLabel(u'开始')
        cb = event.GetEventObject()
        index = cb.GetId() - 60
        cbd = event.GetEventObject().GetLabel()
        if cb.IsChecked():
            cb_mods[index].Enable(True)
            ACTIVE_DEVICES.append(cbd)
            DEVICES_ORDERED.append(index)
        else:
            cb_mods[index].Enable(False)
            ACTIVE_DEVICES.remove(cbd)
            DEVICES_ORDERED.remove(index)
        print(ACTIVE_DEVICES)

    def refresh_devices(self):
        global ACTIVE_DEVICES, DEVICES_ORDERED
        ACTIVE_DEVICES = []
        DEVICES_ORDERED = []
        if len(sys.argv) > 1:
            devices = sys.argv[1:]
        else:
            devices = get_device_list()
        cbs = self.cb_dev_lists
        cb_mods = self.cb_mods_lists
        for d in range(5):
            if d < len(devices):
                cbs[d].SetLabel(devices[d])
                cbs[d].Enable(True)
                cb_mods[d].Enable(True)
            else:
                cbs[d].SetLabel(u'等待设备连接                ')
                cbs[d].SetValue(False)
                cbs[d].Enable(False)
                cb_mods[d].Enable(False)
            if len(devices) == 1 and d == 0:
                cbs[0].SetValue(True)
                ACTIVE_DEVICES.append(cbs[0].GetLabel())
                DEVICES_ORDERED.append(0)
            else:
                cbs[d].SetValue(False)
            if cbs[d].GetValue():
                cb_mods[d].Enable(True)
            else:
                cb_mods[d].Enable(False)
        print(ACTIVE_DEVICES)

    def start_record(self, no):
        self.FindWindowById(36).Enable(False)
        os.popen('adb -s %s root' % ACTIVE_DEVICES[no])
        os.popen('adb -s %s shell rm /sdcard/tencent/wecarspeech/data/dingdang/tmp_wav/*' % ACTIVE_DEVICES[no])
        os.popen(
            'adb -s %s shell touch /sdcard/tencent/wecarspeech/data/dingdang/debug_save_wav.conf' % ACTIVE_DEVICES[no])
        pid = os.popen('adb -s %s shell ps | findstr speech' % ACTIVE_DEVICES[no]).readlines()[0].split()[1]
        os.popen('adb -s %s shell kill -9 %s' % (ACTIVE_DEVICES[no], pid))
        # self.FindWindowById(36).Enable(False)
        # self.sp[no] = subprocess.Popen('adb -s %s shell' % ACTIVE_DEVICES[no], stdin=subprocess.PIPE,
        #                                stdout=subprocess.PIPE, shell=True)
        # sp = self.sp[no]
        # sp.stdin.write('cd sdcard\n')
        # sp.stdin.write('rm voice.dat\n')
        # sp.stdin.write('rm speech8.dat\n')
        # sp.stdin.write('fm_fm1388\n')
        # time.sleep(1.5)
        # sp.stdin.write('e\n')
        # time.sleep(1.5)
        # sp.stdin.write('speech8.wav\n')
        # time.sleep(1.5)
        # sp.stdin.write('013478\n')
        # time.sleep(60)
        # sp.stdin.write('f\n')
        # time.sleep(2)
        # sp.stdin.write('q\n')


class MyApp(wx.App):
    def OnInit(self):
        MyFrame().Show(True)
        return True

    def OnExit(self):
        sys.exit()


class ThreadLogcat(threading.Thread):
    fm = ''

    def __init__(self, fm, no):
        threading.Thread.__init__(self)
        self.fm = fm
        self.no = no
        self.start()

    def run(self):
        global DATA
        DATA = {}
        # _start_d = get_device_list()[CURRENT_DEVICE]
        _d = ACTIVE_DEVICES[self.no]
        cm = get_own_mod(self.no)
        print(cm)
        os.popen('adb -s %s logcat -c' % _d).close()
        consume("adb -s %s logcat -v time" % _d, self.fm, str(self.no))


class ThreadPullAud(threading.Thread):
    def __init__(self, fm, no):
        super(ThreadPullAud, self).__init__()
        self.fm = fm
        self.no = no
        self.start()

    def run(self):
        cm = get_own_mod(self.no)
        print(cm)
        # if cm == AINEMO_LAUNCHER:
        #     from_path = 'data/log'
        # elif cm in (AINEMO_1S, AINEMO_1C, AINEMO_1L_demo):
        #     from_path = 'mnt/aud_rec'
        # elif cm == CW_box or cm == Max:
        #     from_path = 'data/local/aud_rec'
        # else:
        #     from_path = 'data/local/tmp/aud_rec'
        from_path = '/sdcard/tencent/wecarspeech/data/dingdang/tmp_wav'
        to_path = r'%s\%s' % (SAVE_AUDIO, ACTIVE_DEVICES[self.no])
        if not os.path.exists(to_path):
            os.makedirs(to_path)
        cmd = 'adb -s %s pull %s %s' % (ACTIVE_DEVICES[self.no], from_path, to_path)
        #
        process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   shell=True)
        stdout_queue = Queue()
        stdout_reader = AsynchronousFileReader(process.stdout, stdout_queue)
        stdout_reader.start()
        while not stdout_reader.eof():
            while not stdout_queue.empty():
                line = stdout_queue.get().decode("utf-8", errors="ignore")
                if line.find('building file list') != -1 or line.find('pulled') != -1 or line.find('?]') != -1:
                    continue
                try:
                    percent = int(line[line.find('[') + 1:line.find('%')])
                    self.fm.SetValue(percent)
                except ValueError as e:
                    print repr(e)
        process.stdout.close()
        process.kill()
        if 'pull_count' not in DATA:
            DATA['pull_count'] = 1
        else:
            DATA['pull_count'] += 1
        if DATA['pull_count'] == len(ACTIVE_DEVICES):
            L.acquire()
            time.sleep(1)
            self.fm.GetParent().Destroy()
            DATA.clear()
            L.release()
        self.merge()

    @staticmethod
    def merge():
        for dev in ACTIVE_DEVICES:
            header = []
            path = os.path.join(SAVE_AUDIO, dev, 'tmp_wav')
            for s in os.listdir(path):
                h = s[:s.find('_')]
                if h not in header:
                    header.append(h)
            for s in header:
                cmd_meg = 'type %s\\%s*.pcm >> %s\\total_%s.pcm' % (path, s, path, s)
                cmd_del = 'del %s\\%s*.pcm' % (path, s)
                os.system(cmd_meg)
                os.system(cmd_del)


class ThreadReboot(threading.Thread):
    def __init__(self, dev):
        super(ThreadReboot, self).__init__()
        self.dev = dev
        self.start()

    def run(self):
        if len(ACTIVE_DEVICES) == 0:
            return
        os.popen('adb -s %s reboot' % self.dev).close()


if __name__ == '__main__':
    app = MyApp()
    app.MainLoop()
