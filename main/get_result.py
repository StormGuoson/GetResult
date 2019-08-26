# -*- coding: utf-8-*-
from Queue import Queue
from ids import *
import os
import subprocess
import sys
import threading
import time
import json
import mp3play
import win32clipboard as w
import win32con
import wx
from pykeyboard import PyKeyboard

from main.search import MainSearch

reload(sys)
sys.setdefaultencoding('utf-8')
k = PyKeyboard()
L = threading.Lock()

STOP_ALL = True
debug_mode = False  # 调试模式，关闭结果上屏
is_save_log = False  # 保存日志
is_wakeup_bc = False  # 唤醒播测模式
save_result = r'd:\log'  # 日志文件夹
save_audio = r'd:\audio'  # 保存音频文件夹
wakeup_audio_path = ''  # 唤醒音频路径
wakeup_bc_tot_count = 5  # 唤醒播测总次数
wakeup_bc_cur_count = 0  # 唤醒播测当前播放次数
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
    if _text is not '':
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


def save_log(no):
    dev = ACTIVE_DEVICES[int(no)]
    log_path = os.path.join(save_result, '%s.txt' % str(dev))
    if not os.path.exists(save_result):
        os.makedirs(save_result)
    f = open(log_path, 'a+')
    return f


def write_wakeup(txt, no, *arg):
    L.acquire()
    DATA['is_wakeup' + str(no)] = True
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
        # DATA['sn' + no] = ''
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
    cb_mods_lists = []  # 单个设备模式
    cb_dev_lists = []  # 设备list
    sp = [None, None, None]

    def __init__(self):
        wx.Frame.__init__(self, None, -1, 'GG -- ver:20190823', size=(730, 350),
                          style=wx.DEFAULT_FRAME_STYLE | wx.STAY_ON_TOP)
        self.Centre()
        self.init_ele()

        self.refresh_devices()

    def init_ele(self):
        cb_lists = [wx.CheckBox(self, id_cb_copy_xls, label=u'上屏', pos=(10, 10)),
                    wx.CheckBox(self, id_cb_save_log, label=u'保存日志', pos=(10, 40)),
                    wx.CheckBox(self, id_cb_wakeup_broadcast, label=u'唤醒播测', pos=(10, 40))
                    ]
        cb_lists[0].SetValue(True)
        for cb in cb_lists:
            self.Bind(wx.EVT_CHECKBOX, self.set_options, cb)
        self.Bind(wx.EVT_TEXT, self.save_path,
                  wx.TextCtrl(self, id_tc_save_log_path, value=r'd:\log', pos=(10, 60)))
        self.Bind(wx.EVT_TEXT, self.save_path,
                  wx.TextCtrl(self, id_tc_save_wakeup_result_path, pos=(10, 60)))

        self.FindWindowById(id_tc_save_log_path).Show(False)
        self.FindWindowById(id_cb_save_log).Show(False)

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
        self.btn_start = wx.Button(self, id_btn_start, label=u'开始', pos=(200, 20))
        self.Bind(wx.EVT_BUTTON, self.button_action, self.btn_start)
        # 清屏btn
        self.Bind(wx.EVT_BUTTON, self.button_action,
                  wx.Button(self, id_btn_clear, label=u'C', pos=(495, 55), size=(25, 25)))
        # 刷新设备btn
        self.Bind(wx.EVT_BUTTON, self.button_action,
                  wx.Button(self, id_btn_refresh_devices, u'刷新设备', pos=(540, 10)))
        # 重启btn
        self.Bind(wx.EVT_BUTTON, self.button_action,
                  wx.Button(self, id_btn_reboot, label=u'重启设备', pos=(370, 20)))
        # 开始录音
        self.Bind(wx.EVT_BUTTON, self.button_action,
                  wx.Button(self, id_btn_start_record, label=u'开始录音', pos=(180, 258)))
        # 保存音频btn
        self.Bind(wx.EVT_BUTTON, self.button_action,
                  wx.Button(self, id_btn_save_record, label=u'保存音频', pos=(420, 258)))
        self.FindWindowById(id_btn_save_record).Enable(False)

        # 输出log
        self.txt_log = wx.TextCtrl(self, id_tc_log_view, pos=(190, 80), size=(330, 170),
                                   style=wx.TE_MULTILINE | wx.EXPAND | wx.TE_READONLY | wx.TE_RICH2)
        # 保存音频路径
        self.Bind(wx.EVT_TEXT, self.save_path,
                  wx.TextCtrl(self, id_tc_save_record_path, value=r'd:\audio', pos=(270, 260), size=(140, -1)))
        for i in range(5):
            self.cb_dev_lists.append(
                wx.CheckBox(self, 1000 + i, label=u'等待设备连接                ', pos=(540, 50 * (i + 1))))
            self.Bind(wx.EVT_CHECKBOX, self.active_devices, self.cb_dev_lists[i])

            combo_mod = wx.ComboBox(self, 2000 + i, pos=(530, 20 + 50 * (i + 1)), size=(-1, -1), choices=cb_mod_list)
            combo_mod.SetValue(u'——')
            combo_mod.Bind(wx.EVT_COMBOBOX, self.set_single_mod)
            self.cb_mods_lists.append(combo_mod)

    @staticmethod
    def save_path(event):
        global save_result, save_audio
        txt = event.GetEventObject()
        if txt.GetId() == id_tc_save_log_path:
            save_result = txt.GetValue()
        elif txt.GetId() == id_tc_save_record_path:
            save_audio = txt.GetValue()

    def set_options(self, event):
        global is_save_log, debug_mode, is_wakeup_bc
        _id = event.GetEventObject().GetId()
        cbs = event.GetEventObject()
        if cbs.IsChecked():
            if _id == id_cb_copy_xls:
                debug_mode = False
            elif _id == id_cb_save_log:
                is_save_log = True
            elif _id == id_cb_wakeup_broadcast:
                is_wakeup_bc = True
        else:
            if _id == id_cb_copy_xls:
                debug_mode = True
            elif _id == id_cb_save_log:
                is_save_log = False
            elif _id == id_cb_wakeup_broadcast:
                is_wakeup_bc = False

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
        index = event.GetEventObject().GetId() - 2000
        tgs = event.GetEventObject().GetValue()
        ACTIVE_MODULES[DEVICES_ORDERED.index(index)] = tgs
        print(ACTIVE_MODULES)

    def button_action(self, event):
        global STOP_ALL, wakeup_audio_path
        btn = event.GetEventObject()
        bid = btn.GetId()
        # 开始按钮
        if bid == id_btn_start:
            wakeup_audio_path = self.FindWindowById(id_tc_save_wakeup_result_path).GetValue()
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
                self.FindWindowById(id_cb_save_log).Enable(False)
                if is_wakeup_bc:
                    wakeup_audio_path = MainSearch(self.FindWindowById(id_tc_save_wakeup_result_path).GetValue(),
                                                   r'[\S\s]+.mp3').start().get_files()[
                        0]
                    WakeupBroadcast(wakeup_bc_tot_count, self)
                for no in range(len(ACTIVE_DEVICES)):
                    ThreadLogcat(self, no)
            else:
                STOP_ALL = True
                btn.SetLabel(u'开始')
                self.FindWindowById(id_cb_save_log).Enable(True)
        # 清屏clear
        elif bid == id_btn_clear:
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
        # 刷新设备
        elif bid == id_btn_refresh_devices:
            STOP_ALL = True
            self.btn_start.SetLabel('')
            self.btn_start.SetLabel(u'开始')
            self.refresh_devices()

        # 重启设备
        elif bid == id_btn_reboot:
            answer = wx.MessageBox(u'确认重启设备？', u'请确认！', wx.YES_NO | wx.YES_DEFAULT | wx.ICON_EXCLAMATION)
            if answer == wx.YES:
                for dev in ACTIVE_DEVICES:
                    ThreadReboot(dev)
        # 保存音频
        elif bid == id_btn_save_record:
            self.save_record()

        # 开始录音
        elif bid == id_btn_start_record:
            btn.SetLabel(u'录音中')
            self.FindWindowById(id_btn_save_record).Enable(True)
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
        index = cb.GetId() - 1000
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
        self.FindWindowById(id_btn_start_record).Enable(False)
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

    def save_record(self):
        self.FindWindowById(id_btn_start_record).SetLabel(u'开始录音')
        self.FindWindowById(id_btn_save_record).Enable(False)
        if len(ACTIVE_DEVICES) == 0:
            self.txt_log.SetDefaultStyle(wx.TextAttr('RED'))
            self.txt_log.write(u'<<<<<没有连接设备>>>>>\n')
            return
        root = wx.Dialog(self, id_dialog_pulling_record, title=u'正在导出,请稍等！', size=(-1, 300))
        root.Center()
        root.Show()
        self.FindWindowById(id_btn_start_record).Enable(True)
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
        to_path = r'%s\%s' % (save_audio, ACTIVE_DEVICES[self.no])
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
        # self.merge()

    @staticmethod
    def merge():
        for dev in ACTIVE_DEVICES:
            header = []
            path = os.path.join(save_audio, dev, 'tmp_wav')
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


class WakeupBroadcast(threading.Thread):
    def __init__(self, wakeup_tot_count, main_frame):
        super(WakeupBroadcast, self).__init__()
        self.wakeup_tot_count = wakeup_tot_count
        self.frame = main_frame
        self.cur_time = 1
        self.stream = ''
        self.t = ''
        self.start()

    @staticmethod
    def _play(p):
        p.play()

    def run(self):
        global wakeup_bc_cur_count, STOP_ALL
        wakeup_bc_cur_count = 0
        print ACTIVE_DEVICES
        for no in range(len(ACTIVE_DEVICES)):
            DATA['is_wakeup' + str(no)] = True
        time.sleep(5)
        p = mp3play.load(wakeup_audio_path)
        while self.cur_time <= self.wakeup_tot_count:
            if STOP_ALL:
                break
            if not p.isplaying():
                self._play(p)
                self.judge_wakeup(self.t)
                self.t = time.strftime("%m-%d %H:%M:%S", time.localtime())
                self.update_cur_wakeup_count()
        time.sleep(p.seconds() + 3)
        self.judge_wakeup(self.t)
        p.stop()
        STOP_ALL = True
        self.finish_bc()

    # 判断是否唤醒
    def judge_wakeup(self, t):
        for no in range(len(ACTIVE_DEVICES)):
            if 'is_wakeup' + str(no) not in DATA.keys():
                DATA['is_wakeup' + str(no)] = True
            if not DATA['is_wakeup' + str(no)]:
                self.write_nwp_time(ACTIVE_DEVICES[no], wakeup_bc_cur_count, t)
            DATA['is_wakeup' + str(no)] = False

    # 记录未唤醒时间点
    @staticmethod
    def write_nwp_time(device, no_wakeup_time, t):
        path = os.path.join(wakeup_audio_path[:wakeup_audio_path.rfind('\\')], device)
        if not os.path.exists(path):
            os.mkdir(path)
        with open(os.path.join(path, 'wakeup_result.txt'), 'a+') as f:
            f.write(u'%s 第%s次未唤醒\n' % (t, str(no_wakeup_time)))

    # 更新总唤醒次数
    def update_cur_wakeup_count(self):
        global wakeup_bc_cur_count
        wakeup_bc_cur_count += 1
        self.frame.txt_log.SetDefaultStyle(wx.TextAttr('BLACK'))
        self.frame.txt_log.write(u'当前播放唤醒词次数: %s\n' % str(wakeup_bc_cur_count))
        self.cur_time += 1

    def finish_bc(self):
        for no in range(len(ACTIVE_DEVICES)):
            if 'wakeup_count' + str(no) not in DATA:
                DATA['wakeup_count' + str(no)] = 0
            msg = u'设备%s 唤醒次数:%s,唤醒率:%s%%' % (
                ACTIVE_DEVICES[no], str(DATA['wakeup_count' + str(no)]),
                str(DATA['wakeup_count' + str(no)] * 100.00 / wakeup_bc_tot_count))
            self.frame.txt_log.write(msg + '\n')
            path = os.path.join(wakeup_audio_path[:wakeup_audio_path.rfind('\\')], ACTIVE_DEVICES[no])
            with open(os.path.join(path, 'wakeup_result.txt'), 'a+') as f:
                f.write('<<<<<<<finished>>>>>>>>\n')
                msg = u'播放总次数:%s,%s' % (str(wakeup_bc_tot_count), msg[msg.find(u'唤醒'):])
                f.write(msg + '\n')
                f.write('\n')


if __name__ == '__main__':
    app = MyApp()
    app.MainLoop()
