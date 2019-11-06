# coding=utf-8
from __future__ import print_function
from Queue import Queue
from main.ids import *
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

from create_wakeup_report import Report
from search import MainSearch

reload(sys)
sys.setdefaultencoding('utf-8')
L = threading.Lock()
k = PyKeyboard()
STOP_ALL = True
debug_mode = False  # 调试模式，关闭结果上屏
is_save_log = True  # 保存日志
is_ap_wakeup = False  # 唤醒播测模式
is_ap_asr = False  # 识别播测
all_recognized = False  # 全部识别结束
is_pulling_audio = False  # 是否正在导出音频
isplaying = False  # 唤醒音频是否正在播放
finish_one = False  # 播测完成一人
save_log = r'd:\log'  # 日志文件夹
save_audio = r'd:\audio'  # 保存音频文件夹
ap_record_path = r'd:\wakeup'  # 保存唤醒音频主路径
wakeup_cur_single_audio_paths = r'd:\audio'  # 当前播放唤醒音频集路径
ap_wakeup_tot_count = 50  # 唤醒播测总次数

ACTIVE_DEVICES = []  # 激活的设备
DEVICES_ORDERED = []  # 设备的连接顺序
UNACTIVE_DEVICES = []  # 休眠的设备
ACTIVE_MODULES = [-1, -1, -1, -1, -1]  # 各设备的模式

S111 = 'S111'
S311 = 'S311'
S203EV = 'S203ev'

CURRENT_MODULE = S111  # 当前模式

cb_mod_list = [S111, S311, S203EV, u'——']

parent_mod = {
    # 10000: S111,
    #           10001: S311,
    #           10002: S203EV,
}

child_mod = {}
activities = {}
DATA = {}


def reset_data():
    for index in range(5):
        i = str(index)
        DATA['is_wakeup' + i] = False
        DATA['is_reced' + i] = False
        DATA['text' + i] = ''
        DATA['sn' + i] = []
        DATA['wakeup_count' + i] = 0


# 复制粘贴
def set_clipboard_text(t):
    w.OpenClipboard()
    w.EmptyClipboard()
    w.SetClipboardData(win32con.CF_TEXT, t.encode("gbk"))
    w.CloseClipboard()


def paste():
    k.press_key(k.control_l_key)
    time.sleep(0.08)
    k.tap_key('v')
    time.sleep(0.08)
    k.release_key(k.control_l_key)


def click(n):
    time.sleep(.05)
    k.tap_key(n)
    time.sleep(.05)


def auto_set(_no, _frame):
    global L
    L.acquire()
    try:
        threading.Thread(target=_as, args=(_no, _frame)).start()
    except Exception as e:
        _frame.txt_log.write(repr(e) + '\n')
    L.release()


def _as(no, frame):
    global all_recognized
    DATA['is_reced' + str(no)] = True
    DATA['is_wakeup' + str(no)] = False

    _text = DATA['text' + no]
    _sn = DATA['sn' + no]
    if _text.strip() is not '' and len(_text) != 0:
        frame.txt_log.write(_text + '\n')

    frame.txt_log.SetDefaultStyle(wx.TextAttr('BLUE'))
    for ele in _sn:
        frame.txt_log.write(ele + '\n')
    frame.txt_log.SetDefaultStyle(wx.TextAttr('BLACK'))

    for d in range(len(ACTIVE_DEVICES)):
        d = str(d)
        if DATA['text' + d] == '':
            return
    if not debug_mode:
        for s in range(len(ACTIVE_DEVICES)):
            s = str(s)
            set_clipboard_text(DATA['text' + s])
            paste()
            click(k.escape_key)
            for ele in DATA['sn' + s]:
                click(k.right_key)
                set_clipboard_text(ele)
                paste()
                click(k.escape_key)
            if int(s) == len(ACTIVE_DEVICES) - 1:
                click(k.down_key)
            else:
                click(k.right_key)
        for e in range(len(ACTIVE_DEVICES)):
            e = str(e)
            for _ in DATA['sn' + e]:
                click(k.left_key)
            if int(e) != len(ACTIVE_DEVICES) - 1:
                click(k.left_key)
    all_recognized = True
    for d in range(len(ACTIVE_DEVICES)):
        d = str(d)
        DATA['text' + d] = ''
        DATA['sn' + d] = []


def save_logcat(no):
    dev = ACTIVE_DEVICES[int(no)]
    t = time.strftime("%m-%d %H-%M-%S", time.localtime())
    date = time.strftime("%m-%d", time.localtime())
    dir_path = os.path.join(save_log, date)
    log_path = os.path.join(dir_path, '%s@%s.txt' % (t, dev))
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)
    f = open(log_path, 'w')
    return f


def write_wakeup(txt, no, *arg):
    global all_recognized
    L.acquire()
    all_recognized = False
    DATA['is_wakeup' + str(no)] = True
    DATA['is_reced' + str(no)] = False
    DATA['text' + str(no)] = ''
    DATA['sn' + str(no)] = []
    DATA['wakeup_count' + no] += 1
    t = time.strftime("%m-%d %H:%M:%S", time.localtime())
    msg = u'No%d 唤醒次数 %d   %s\n' % (int(no) + 1, DATA['wakeup_count' + no], t)
    txt.txt_log.write(msg)

    for d, dev in enumerate(ACTIVE_DEVICES):
        if is_ap_wakeup:
            threading.Thread(
                target=lambda: os.popen('adb -s %s shell input tap 100 100' % dev)).start()
    L.release()


def main_doing(_line, _module, _res_txt, no):
    if _module == S111:
        module_s111(_line, _res_txt, no)
    elif _module == S203EV:
        module_s203ev(_line, _res_txt, no)
    elif _module == S311:
        module_s311(_line, _res_txt, no)


def waiting_tts(frame, no):
    threading.Thread(target=_wt, args=(frame, no)).start()


def _wt(frame, no):
    start = time.time()
    has_tts = True
    while not DATA['is_reced' + no]:
        if time.time() - start > 1:
            has_tts = False
            break
    if not has_tts:
        DATA['sn' + no].append('null')
        auto_set(no, frame)


def module_s311(line, txt, no):
    if line.endswith('wakeup_Type:wordWakeup\n'):
        write_wakeup(txt, no)
    elif 'onSpeechResult' in line and u'最终结果' in line:
        print(line)
        line = str(line[line.find('{'):line.rfind('}') + 1])
        line = json.loads(line)
        DATA['text' + no] = line['text']
        waiting_tts(txt, no)
    elif 'TSSCallback onWakeupResult type:1' in line:
        if '"小安你好"' in line or '"召唤妲己"' in line or '"召唤李白"' in line or '"叮当叮当"' in line:
            return
        print(line)
        line = str(line[line.find('{'):line.rfind('}') + 1])
        line = json.loads(line)
        DATA['text' + no] = line['keyword']
        DATA['is_reced' + str(no)] = False
        waiting_tts(txt, no)
    elif '\"domain\"' in line and '\"intent\"' and DATA['sn' + no] == []:
        print(line)
        domain = line[line.find('\"domain\":\"') + 10:]
        domain = domain[:domain.find('\"')]
        intent = line[line.find('\"intent\":\"') + 10:]
        intent = intent[:intent.find('\"')]
        if domain == '':
            domain = 'N/A'
        if intent == '':
            intent = 'N/A'
        if len(domain) > 20 or len(intent) > 20:
            return
        print(domain)
        print(intent)
        DATA['sn' + no] = [domain, intent]
    # elif 'TryWordRepo' in line and ' domain ' in line and ' intent ' in line and DATA['sn' + no] == []:
    #     domain = line[line.find(' domain =') + 10:]
    #     domain = domain[:domain.find(',')]
    #     intent = line[line.find(' intent =') + 10:].rstrip('\r\r\n').rstrip('\r\n')
    #     if intent == '':
    #         intent = 'N/A'
    #     print(domain)
    #     print(intent)
    #     DATA['sn' + no] = [domain, intent]
    elif ':playTTS text' in line:
        print(line)
        tts = line[line.find('text:') + 5:line.rfind(',')]
        if DATA['text' + no] == '':
            DATA['text' + no] = 'null'
        DATA['sn' + no].append(tts)
        auto_set(no, txt)


def module_s111(line, txt, no):
    module_s311(line, txt, no)


def module_s203ev(line, txt, no):
    if line.endswith('wakeup_Type:wordWakeup\n'):
        write_wakeup(txt, no)
    elif 'onSpeechResult type:1' in line:
        print(line)
        line = str(line[line.find('{'):line.rfind('}') + 1])
        line = json.loads(line)
        DATA['text' + no] = line['text']
        waiting_tts(txt, no)
    elif 'TSSCallback onWakeupResult type:1' in line:
        if '"小安你好"' in line or '"召唤妲己"' in line or '"召唤李白"' in line or '"叮当叮当"' in line:
            return
        print(line)
        line = str(line[line.find('{'):line.rfind('}') + 1])
        line = json.loads(line)
        DATA['text' + no] = line['keyword']
        DATA['is_reced' + str(no)] = False
        waiting_tts(txt, no)
    elif '\"domain\"' in line and '\"intent\"' and DATA['sn' + no] == [] and '[b]' not in line:
        print(line)
        domain = line[line.find('\"domain\":\"') + 10:]
        domain = domain[:domain.find('\"')]
        intent = line[line.find('\"intent\":\"') + 10:]
        intent = intent[:intent.find('\"')]
        if intent == '':
            intent = 'N/A'
        print(domain)
        print(intent)
        DATA['sn' + no] = [domain, intent]
    elif 'TryWordRepo' in line and ' domain ' in line and ' intent ' in line and DATA['sn' + no] == []:
        domain = line[line.find(' domain =') + 10:]
        domain = domain[:domain.find(',')]
        intent = line[line.find(' intent =') + 10:].rstrip('\r\r\n').rstrip('\r\n')
        if intent == '':
            intent = 'N/A'
        print(domain)
        print(intent)
        DATA['sn' + no] = [domain, intent]
    elif ':playTTS text' in line:
        print(line)
        tts = line[line.find('text:') + 5:line.rfind(',')]
        if DATA['text' + no] == '':
            DATA['text' + no] = 'null'
        DATA['sn' + no].append(tts)
        auto_set(no, txt)


class FileReader(threading.Thread):

    def __init__(self, fd, queue):
        assert isinstance(queue, Queue)
        assert callable(fd.readline)
        threading.Thread.__init__(self)
        self._fd = fd
        self._queue = queue

    def run(self):
        for line in iter(self._fd.readline, ''):
            self._queue.put(line.replace('\r\r\n', '\n').replace('\r\n', '\n'))

    def eof(self):
        return not self.is_alive() and self._queue.empty()


def consume(command, frame, no):
    print(command)
    global STOP_ALL, L
    time.sleep(float(no) / 10.0 * 3)
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               shell=True)
    stdout_queue = Queue()
    stdout_reader = FileReader(process.stdout, stdout_queue)
    stdout_reader.start()
    stderr_queue = Queue()
    stderr_reader = FileReader(process.stderr, stderr_queue)
    stderr_reader.start()
    frame.txt_log.write(('No%s_' % str(int(no) + 1)) + ACTIVE_DEVICES[int(no)] + u' <<<开始>>>' + '\n')
    _mod = get_own_mod(no)
    log = None
    if is_save_log:
        log = save_logcat(no)
    while not stdout_reader.eof() or not stderr_reader.eof():
        if STOP_ALL:
            print('stop')
            L.acquire()
            frame.btn_start.SetLabel(u'开始')
            frame.txt_log.write(('No%s' % str(int(no) + 1)) + u' <<<停止>>>' + '\n')
            L.release()
            break
        while not stdout_queue.empty():
            line = stdout_queue.get().decode("utf-8", errors="ignore")
            try:
                if is_save_log:
                    log.write(line)
                main_doing(line, _mod, frame, no)
            except IndexError as e:
                frame.txt_log.SetDefaultStyle(wx.TextAttr('RED'))
                frame.txt_log.write(repr(e))
                frame.txt_log.SetDefaultStyle(wx.TextAttr('BLACK'))
        while not stderr_queue.empty():
            line = stderr_queue.get().decode("utf-8", errors="ignore")
            L.acquire()
            frame.txt_log.SetDefaultStyle(wx.TextAttr('RED'))
            frame.txt_log.write(line)
            frame.txt_log.SetDefaultStyle(wx.TextAttr('BLACK'))
            L.release()
            if 'replaced' in line:
                continue
            print('Received line on standard error: ' + repr(line))
            frame.txt_log.SetDefaultStyle(wx.TextAttr('RED'))
            frame.txt_log.write(repr(line))
            frame.txt_log.SetDefaultStyle(wx.TextAttr('BLACK'))
            STOP_ALL = True
            frame.btn_start.SetLabel(u'开始')
        # Sleep a bit before asking the readers again.
        try:
            time.sleep(.1)
        except KeyboardInterrupt:
            pass

    if is_save_log:
        log.close()
    frame.FindWindowById(id_cb_save_log).Enable(True)
    frame.FindWindowById(id_cb_ap_wakeup).Enable(True)
    frame.FindWindowById(id_cb_ap_asr).Enable(True)
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
    L.acquire()
    try:
        frame.txt_log.SetDefaultStyle(wx.TextAttr('RED'))
        frame.txt_log.write(ACTIVE_DEVICES[int(no)] + u' <<<断开连接>>>' + '\n')
        frame.txt_log.SetDefaultStyle(wx.TextAttr('BLACK'))
    except IndexError as e:
        print(repr(e))
    frame.act_refresh_devices()
    L.release()


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
        wx.Frame.__init__(self, None, -1, 'GG -- ver:20191021', size=(730, 350),
                          style=wx.DEFAULT_FRAME_STYLE | wx.STAY_ON_TOP)
        self.Centre()
        self.init_ele()
        reset_data()
        # self.FindWindowById(id_tc_save_log_path).Show(False)
        self.FindWindowById(id_cb_save_log).Show(False)
        self.FindWindowById(id_tc_ap_audio_path).Enable(False)
        self.FindWindowById(id_tc_ap_wakeup_tot_count).Enable(False)
        # time.sleep(.1)
        self.act_refresh_devices()

    def init_ele(self):
        cb_lists = [wx.CheckBox(self, id_cb_copy_xls, label=u'上屏', pos=(10, 10)),
                    wx.CheckBox(self, id_cb_save_log, label=u'保存日志', pos=(10, 40)),
                    wx.CheckBox(self, id_cb_ap_wakeup, label=u'唤醒播测', pos=(10, 40)),
                    wx.CheckBox(self, id_cb_ap_asr, label=u'识别播测', pos=(10, 70))
                    ]
        cb_lists[0].SetValue(True)
        cb_lists[1].SetValue(True)
        for cb in cb_lists:
            self.Bind(wx.EVT_CHECKBOX, self.set_options, cb)
        self.Bind(wx.EVT_TEXT, self.save_path,
                  wx.TextCtrl(self, id_tc_save_log_path, value=r'd:\log', pos=(273, 260), size=(140, -1)))
        wx.StaticText(self, label=u'音频路径', pos=(10, 100))
        self.Bind(wx.EVT_TEXT, self.save_path,
                  wx.TextCtrl(self, id_tc_ap_audio_path, ap_record_path, pos=(85, 95),
                              size=(100, -1)))
        wx.StaticText(self, label=u'循环次数', pos=(90, 40))
        self.Bind(wx.EVT_TEXT, self.save_path,
                  wx.TextCtrl(self, id_tc_ap_wakeup_tot_count, str(ap_wakeup_tot_count), pos=(145, 36),
                              size=(40, -1)))
        # 保存音频路径
        # self.Bind(wx.EVT_TEXT, self.save_path,
        #           wx.TextCtrl(self, id_tc_save_record_path, value=r'd:\audio', pos=(273, 260), size=(140, -1)))
        # 选择模式
        index = 0
        for key, value in parent_mod.items():
            if key == S111:
                rb = wx.RadioButton(self, key, label=value, pos=(10, 140), style=wx.RB_GROUP)
            else:
                rb = wx.RadioButton(self, key, label=value, pos=(10, 140 + (index * 30)))
            self.Bind(wx.EVT_RADIOBUTTON, self.set_module, rb)
            index += 1
        if parent_mod:
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
        # self.Bind(wx.EVT_BUTTON, self.button_action,
        #           wx.Button(self, id_btn_start_record, label=u'开始录音', pos=(180, 258)))
        # 保存音频btn
        # self.Bind(wx.EVT_BUTTON, self.button_action,
        #           wx.Button(self, id_btn_save_record, label=u'保存音频', pos=(420, 258)))
        # 清除日志
        self.Bind(wx.EVT_BUTTON, self.button_action,
                  wx.Button(self, id_btn_clear_log, label=u'清除日志', pos=(180, 258)))
        # 保存Xlog
        self.Bind(wx.EVT_BUTTON, self.button_action,
                  wx.Button(self, id_btn_save_log, label=u'保存Xlog', pos=(420, 258)))
        # 输出log
        self.txt_log = wx.TextCtrl(self, id_tc_log_view, pos=(190, 80), size=(330, 170),
                                   style=wx.TE_MULTILINE | wx.EXPAND | wx.TE_READONLY | wx.TE_RICH2)

        for i in range(5):
            self.cb_dev_lists.append(
                wx.CheckBox(self, 1000 + i, label=u'等待设备连接                ', pos=(540, 50 * (i + 1))))
            self.FindWindowById(1000 + i).Enable(False)
            self.Bind(wx.EVT_CHECKBOX, self.active_devices, self.cb_dev_lists[i])

            combo_mod = wx.ComboBox(self, 2000 + i, pos=(530, 20 + 50 * (i + 1)), size=(-1, -1), choices=cb_mod_list)
            combo_mod.SetValue(u'——')
            combo_mod.Enable(False)
            combo_mod.Bind(wx.EVT_COMBOBOX, self.set_single_mod)
            self.cb_mods_lists.append(combo_mod)

    @staticmethod
    def save_path(event):
        global save_log, save_audio
        txt = event.GetEventObject()
        if txt.GetId() == id_tc_save_log_path:
            save_log = txt.GetValue()
        elif txt.GetId() == id_tc_save_record_path:
            save_audio = txt.GetValue()

    def set_options(self, event):
        global is_save_log, debug_mode, is_ap_wakeup, is_ap_asr
        _id = event.GetEventObject().GetId()
        cbs = event.GetEventObject()
        if cbs.IsChecked():
            if _id == id_cb_copy_xls:
                debug_mode = False
            elif _id == id_cb_save_log:
                is_save_log = True
            elif _id == id_cb_ap_wakeup:
                is_ap_wakeup = True
                is_ap_asr = False

                self.FindWindowById(id_tc_ap_wakeup_tot_count).Enable(True)
                self.FindWindowById(id_tc_ap_audio_path).Enable(True)
                self.FindWindowById(id_tc_ap_wakeup_tot_count).SetFocus()
                self.FindWindowById(id_cb_ap_asr).SetValue(False)
            elif _id == id_cb_ap_asr:
                is_ap_asr = True
                is_ap_wakeup = False
                self.FindWindowById(id_cb_ap_wakeup).SetValue(False)
                self.FindWindowById(id_tc_ap_audio_path).Enable(True)
                self.FindWindowById(id_tc_ap_wakeup_tot_count).Enable(False)
        else:
            if _id == id_cb_copy_xls:
                debug_mode = True
            elif _id == id_cb_save_log:
                is_save_log = False
            elif _id == id_cb_ap_wakeup:
                is_ap_wakeup = False
                self.FindWindowById(id_tc_ap_wakeup_tot_count).Enable(False)
                self.FindWindowById(id_tc_ap_audio_path).Enable(False)

            elif _id == id_cb_ap_asr:
                is_ap_asr = False
                self.FindWindowById(id_tc_ap_audio_path).Enable(False)

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
        global STOP_ALL, wakeup_cur_single_audio_paths, ap_wakeup_tot_count, ap_record_path
        btn = event.GetEventObject()
        bid = btn.GetId()
        # 开始按钮
        if bid == id_btn_start:
            self.act_start()
        # 清屏clear
        elif bid == id_btn_clear:
            self.act_clear()
        # 刷新设备
        elif bid == id_btn_refresh_devices:
            self.act_refresh_devices()
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
            self.start_record()
        #  清除日志
        elif bid == id_btn_clear_log:
            self.act_clear_log()
        # 保存日志
        elif bid == id_btn_save_log:
            print('save log')
            self.act_save_log()

    @staticmethod
    def act_clear_log():
        answer = wx.MessageBox(u'确认清除腾讯日志？', u'请确认！', wx.YES_NO | wx.YES_DEFAULT | wx.ICON_EXCLAMATION)
        if answer != wx.YES:
            return
        # for no, dev in enumerate(ACTIVE_DEVICES):
        # cm = get_own_mod(no)
        # if cm == S111:
        #     pass
        # elif cm == S311:
        threading.Thread(target=tool.clear_s311_log).start()

    @staticmethod
    def act_save_log():
        for no, dev in enumerate(ACTIVE_DEVICES):
            # cm = get_own_mod(no)
            # if cm == S111:
            #     pass
            # elif cm == S311:
            threading.Thread(target=tool.save_s311_log).start()

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

    def act_start(self):
        global STOP_ALL, wakeup_cur_single_audio_paths, ap_wakeup_tot_count, ap_record_path, reports
        if STOP_ALL:
            if len(ACTIVE_DEVICES) < 1:
                self.txt_log.SetDefaultStyle(wx.TextAttr('RED'))
                self.txt_log.SetValue('')
                self.txt_log.write(u'没有连接设备！！！\n')
                self.txt_log.SetDefaultStyle(wx.TextAttr('BLACK'))
                return
            try:
                self.txt_log.SetValue('')
                reset_data()
                STOP_ALL = False
                self.sras()
                self.FindWindowById(id_btn_start).SetLabel(u'停止')
                self.FindWindowById(id_cb_save_log).Enable(False)
                self.FindWindowById(id_cb_ap_wakeup).Enable(False)
                self.FindWindowById(id_cb_ap_asr).Enable(False)
                ap_record_path = self.FindWindowById(id_tc_ap_audio_path).GetValue()
                for no in range(len(ACTIVE_DEVICES)):
                    ThreadLogcat(self, no)
                if is_ap_wakeup:
                    reports = []
                    for dev in ACTIVE_DEVICES:
                        rp = Report(ap_record_path, dev)
                        reports.append(rp)
                        threading.Thread(target=rp.check_sys_info).start()
                    ap_wakeup_tot_count = int(self.FindWindowById(id_tc_ap_wakeup_tot_count).GetValue())
                    MultiAPW(ap_record_path, self)
                    # paths = os.listdir(main_path)
                    # for path in paths:
                    #     path = os.path.join(main_path, path)
                    #     wakeup_cur_single_audio_paths = MainSearch(path, r'[\S\s]+.MP3').start().get_files()
                    #     WakeupBroadcast(self)
                    #     threading.Thread(target=self.auto_repeat_pull_audio).start()

                elif is_ap_asr:
                    AudioPlayAsr()
            except WindowsError:
                STOP_ALL = True
                self.txt_log.SetDefaultStyle(wx.TextAttr('RED'))
                self.txt_log.SetValue('')
                self.txt_log.write(u'没有找到音频！！！\n')
                self.txt_log.SetDefaultStyle(wx.TextAttr('BLACK'))
        else:
            STOP_ALL = True
            self.FindWindowById(id_btn_start).SetLabel(u'开始')
            self.FindWindowById(id_cb_save_log).Enable(True)

    def act_clear(self):
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
        reset_data()

    def sras(self):
        threading.Thread(target=self._save_record_after_stop).start()

    def _save_record_after_stop(self):
        while not STOP_ALL:
            pass
        if is_ap_wakeup:
            time.sleep(1.5)
            self.save_record()

    def act_refresh_devices(self):
        threading.Thread(target=self._ard).start()

    def _ard(self):
        global ACTIVE_DEVICES, DEVICES_ORDERED, STOP_ALL
        STOP_ALL = True
        self.btn_start.SetLabel(u'开始')
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

    # def auto_repeat_pull_audio(self):
    #     global is_pulling_audio
    #     first = True
    #     last_ts = 0
    #     while not STOP_ALL and not finish_one:
    #         if first:
    #             last_ts = time.time()
    #             first = False
    #             self.txt_log.write(u'开启录音中，播放倒计时30s\n')
    #             self.start_record()
    #             self.delay_play()
    #         elif time.time() - last_ts > 3600:
    #             last_ts = time.time()
    #             is_pulling_audio = True
    #             while isplaying:
    #                 pass
    #             self.save_record()
    #             while is_pulling_audio:
    #                 pass
    #             self.txt_log.write(u'开启录音中，播放倒计时30s\n')
    #             self.start_record()
    #             self.delay_play()

    def delay_play(self):
        threading.Thread(target=self._delay_play).start()

    @staticmethod
    def _delay_play():
        global is_pulling_audio
        time.sleep(30)
        is_pulling_audio = False

    def start_record(self):
        threading.Thread(target=self._start_record).start()

    def _start_record(self):
        global is_pulling_audio
        is_pulling_audio = True
        for no in range(len(ACTIVE_DEVICES)):
            os.popen('adb -s %s root' % ACTIVE_DEVICES[no])
            os.popen('adb -s %s shell rm /sdcard/tencent/wecarspeech/data/dingdang/tmp_wav/*' % ACTIVE_DEVICES[no])
            os.popen(
                'adb -s %s shell touch /sdcard/tencent/wecarspeech/data/dingdang/debug_save_wav.conf' % ACTIVE_DEVICES[
                    no])
            try:
                pid = os.popen('adb -s %s shell ps | findstr speech' % ACTIVE_DEVICES[no]).readlines()[0].split()[1]
                os.popen('adb -s %s shell kill -9 %s' % (ACTIVE_DEVICES[no], pid))
            except IndexError as e:
                print(repr(e))
                self.txt_log.write(u'未发现语音服务，无法录音')
                return
        self.FindWindowById(id_btn_start_record).SetLabel(u'录音中')
        # self.FindWindowById(id_btn_save_record).Enable(True)
        self.FindWindowById(id_btn_start_record).Enable(False)
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
        global is_pulling_audio
        is_pulling_audio = True
        # t1 = threading.Thread(target=self._save_record)
        # t1.start()
        self._save_record()

    def _save_record(self):
        global is_pulling_audio
        path = wakeup_cur_single_audio_paths[0]
        self.FindWindowById(id_btn_start_record).SetLabel(u'开始录音')
        # self.FindWindowById(id_btn_save_record).Enable(False)
        if len(ACTIVE_DEVICES) == 0:
            self.txt_log.SetDefaultStyle(wx.TextAttr('RED'))
            self.txt_log.write(u'<<<<<没有连接设备>>>>>\n')
            self.txt_log.SetDefaultStyle(wx.TextAttr('BLACK'))
            return
        root = wx.Dialog(self, id_dialog_pulling_record, title=u'正在导出,请稍等！', size=(-1, 300))
        root.Center()
        root.Show()
        self.FindWindowById(id_btn_start_record).Enable(True)
        for no in range(len(ACTIVE_DEVICES)):
            gauge = wx.Gauge(root, range=100, size=(300, 25), pos=(0, 40 + no * 40), style=wx.GA_HORIZONTAL)
            gauge.Centre(wx.HORIZONTAL)
            os.popen(
                'adb -s %s shell rm /sdcard/tencent/wecarspeech/data/dingdang/debug_save_wav.conf' %
                ACTIVE_DEVICES[
                    no])
            pid = os.popen('adb -s %s shell ps | findstr speech' % ACTIVE_DEVICES[no]).readlines()[0].split()[1]
            os.popen('adb -s %s shell kill -9 %s' % (ACTIVE_DEVICES[no], pid))
            ThreadPullAud(gauge, no)
            # else:
            #     cm = get_own_mod(no)
            #     print(cm)
            #     from_path = '/sdcard/tencent/wecarspeech/data/dingdang/tmp_wav/'
            #     to_path = r'%s\%s' % (save_audio, ACTIVE_DEVICES[no])
            #     if is_wakeup_bc:
            #         p = path[:path.rfind('\\')]
            #         p = p[p.rfind('\\') + 1:]
            #         to_path = os.path.join(save_audio, p, ACTIVE_DEVICES[no])
            #     if not os.path.exists(to_path):
            #         os.makedirs(to_path)
            #     cmd = 'adb -s %s pull %s %s' % (ACTIVE_DEVICES[no], from_path, to_path)
            #     process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            #                                shell=True)
            #     stdout_queue = Queue()
            #     stdout_reader = AsynchronousFileReader(process.stdout, stdout_queue)
            #     stdout_reader.start()
            #     while not stdout_reader.eof():
            #         while not stdout_queue.empty():
            #             line = stdout_queue.get().decode("utf-8", errors="ignore")
            #             if line.find('building file list') != -1 or line.find('pulled') != -1 or line.find('?]') != -1:
            #                 continue
            #             try:
            #                 percent = int(line[line.find('[') + 1:line.find('%')])
            #                 gauge.SetValue(percent)
            #             except ValueError as e:
            #                 print repr(e)
            #     process.stdout.close()
            #     process.kill()
            #     if 'pull_count' not in DATA:
            #         DATA['pull_count'] = 1
            #     else:
            #         DATA['pull_count'] += 1
            #     if DATA['pull_count'] == len(ACTIVE_DEVICES):
            #         DATA['pull_count'] = 0
            #         L.acquire()
            #         time.sleep(1)
            #         is_pulling_audio = False
            #         root.Destroy()
            #         if not is_wakeup_bc:
            #             DATA.clear()
            #         L.release()


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
        # _start_d = get_device_list()[CURRENT_DEVICE]
        _d = ACTIVE_DEVICES[self.no]
        cm = get_own_mod(self.no)
        print(cm)
        os.popen('adb -s %s logcat -c' % _d).close()
        # consume("adb -s %s logcat -v threadtime -b main -b system -b events" % _d, self.fm, str(self.no))
        consume("adb -s %s logcat -v time" % _d, self.fm, str(self.no))


class ThreadPullAud(threading.Thread):
    def __init__(self, gauge, no):
        super(ThreadPullAud, self).__init__()
        self.fm = gauge
        self.no = no
        self.start()

    def run(self):
        global is_pulling_audio
        cm = get_own_mod(self.no)
        print(cm)
        from_path = '/sdcard/tencent/wecarspeech/data/dingdang/tmp_wav/'
        to_path = r'%s\%s' % (save_audio, ACTIVE_DEVICES[self.no])
        if not os.path.exists(to_path):
            os.makedirs(to_path)
        cmd = 'adb -s %s pull %s %s' % (ACTIVE_DEVICES[self.no], from_path, to_path)
        process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   shell=True)
        stdout_queue = Queue()
        stdout_reader = FileReader(process.stdout, stdout_queue)
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
                    print(repr(e))
        process.stdout.close()
        process.kill()
        if 'pull_count' not in DATA:
            DATA['pull_count'] = 1
        else:
            DATA['pull_count'] += 1
        if DATA['pull_count'] == len(ACTIVE_DEVICES):
            L.acquire()
            DATA['pull_count'] = 0
            is_pulling_audio = False
            time.sleep(1)
            self.fm.GetParent().Destroy()
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


class MultiAPW(threading.Thread):
    def __init__(self, main_path, frame):
        super(MultiAPW, self).__init__()
        self.main_path = main_path
        self.frame = frame
        self.start()

    def run(self):
        global wakeup_cur_single_audio_paths, STOP_ALL
        # self.frame.start_record()
        # self.frame.txt_log.write(u'开启录音中，播放倒计时30s\n')
        # self.frame.delay_play()
        paths = os.listdir(self.main_path)
        for path in paths:
            if os.path.isfile(os.path.join(self.main_path, path)):
                paths.remove(path)
        print(paths)
        for path in paths:
            path = os.path.join(self.main_path, path)
            wakeup_cur_single_audio_paths = MainSearch(path, r'[\S\s]+.MP3').start().get_files()
            if len(wakeup_cur_single_audio_paths) == 0:
                continue
            AudioPlayWakeup(self.frame)
            # self.frame.auto_repeat_pull_audio()
            time.sleep(1)
            while not finish_one:
                pass
            if STOP_ALL:
                break
        STOP_ALL = True
        time.sleep(1)
        for no in range(len(ACTIVE_DEVICES)):
            reports[no].parser_wakeup_txt()
            reports[no].write_excel()


class AudioPlayWakeup(threading.Thread):
    def __init__(self, main_frame):
        global finish_one
        super(AudioPlayWakeup, self).__init__()
        self.frame = main_frame
        self.t = ''
        self.person = ''
        self.wakeup_bc_cur_count = 1
        finish_one = False
        self.start()

    def run(self):
        global finish_one, isplaying
        self.wakeup_bc_cur_count = 1
        plays = []
        time.sleep(2)
        person2 = wakeup_cur_single_audio_paths[0].replace(ap_record_path, '')
        self.person = person2[1:person2.rfind('\\')]
        L.acquire()
        while is_pulling_audio:
            continue
        self.frame.txt_log.write(u'开始播放 %s\n' % self.person)
        L.release()
        for p in wakeup_cur_single_audio_paths:
            plays.append(mp3play.load(p))
        while self.wakeup_bc_cur_count <= ap_wakeup_tot_count:
            if STOP_ALL:
                return
            for i, p in enumerate(plays):
                if STOP_ALL:
                    return
                if self.wakeup_bc_cur_count > ap_wakeup_tot_count:
                    break
                isplaying = p.isplaying()
                # if not isplaying:
                if is_pulling_audio:
                    continue
                p.play()
                self.t = time.strftime("%m-%d %H:%M:%S", time.localtime())
                L.acquire()
                self.update_cur_wakeup_count()
                L.release()
                time.sleep(p.seconds() + .1)
                self.judge_wakeup(self.t)
        # time.sleep(2)
        for p in plays:
            p.stop()
        finish_one = True
        self.finish_bc(wakeup_cur_single_audio_paths[0])
        # self.frame.save_record()

    # 判断是否唤醒
    def judge_wakeup(self, t):
        for no in range(len(ACTIVE_DEVICES)):
            if 'is_wakeup' + str(no) not in DATA.keys():
                DATA['is_wakeup' + str(no)] = False
            if not DATA['is_wakeup' + str(no)]:
                self.write_nwp_time(ACTIVE_DEVICES[no], self.wakeup_bc_cur_count - 1, t)
            DATA['is_wakeup' + str(no)] = False

    # 记录未唤醒时间点
    @staticmethod
    def write_nwp_time(device, no_wakeup_time, t):
        path = wakeup_cur_single_audio_paths[0]
        p = path[:path.rfind('\\')]
        p = p[p.rfind('\\') + 1:]
        path = os.path.join(ap_record_path, device, p)
        if not os.path.exists(path):
            os.makedirs(path)

        if not os.path.exists(path):
            os.makedirs(path)
        with open(os.path.join(path, 'wakeup_result.txt'), 'a+') as f:
            f.write(u'%s 第%s次未唤醒\n' % (t, str(no_wakeup_time)))

    # 更新总唤醒次数
    def update_cur_wakeup_count(self):
        self.frame.txt_log.write(u'当前播放唤醒词次数: %s\n' % str(self.wakeup_bc_cur_count))
        self.wakeup_bc_cur_count += 1

    def finish_bc(self, path):
        for no in range(len(ACTIVE_DEVICES)):
            if 'wakeup_count' + str(no) not in DATA:
                DATA['wakeup_count' + str(no)] = 0
            msg = u'设备%s 唤醒次数:%s,唤醒率:%s%%' % (
                ACTIVE_DEVICES[no], str(DATA['wakeup_count' + str(no)]),
                str(DATA['wakeup_count' + str(no)] * 100.00 / ap_wakeup_tot_count))
            self.frame.txt_log.write(msg + '\n')
            # path = os.path.join(path[:path.rfind('\\')],
            #                     ACTIVE_DEVICES[no])
            p = path[:path.rfind('\\')]
            p = p[p.rfind('\\') + 1:]
            path = os.path.join(ap_record_path, ACTIVE_DEVICES[no], p)
            if not os.path.exists(path):
                os.makedirs(path)
            path = os.path.join(path, 'wakeup_result.txt')
            reports[no].put_wakeup_txt(self.person, path)
            with open(path, 'a+') as f:
                f.write('<<<<<<<finished>>>>>>>>\n')
                msg = u'播放总次数:%s,%s' % (str(self.wakeup_bc_cur_count - 1), msg[msg.find(u'唤醒'):])
                f.write(msg + '\n')
                f.write('\n')
            DATA['wakeup_count' + str(no)] = 0
            reports[no].put_wakeup_txt(self.person, path)


class AudioPlayAsr(threading.Thread):
    def __init__(self):
        super(AudioPlayAsr, self).__init__()
        self.wakeup_word = os.path.join(ap_record_path, 'wakeup\\wp.MP3').encode('gbk')
        self.query_path = os.path.join(ap_record_path, 'query').encode('gbk')
        self.query_list = []
        self.set_query()
        self.start()

    def run(self):
        global STOP_ALL
        self.play()
        STOP_ALL = True

    def set_query(self):
        search = MainSearch(self.query_path).start()
        self.query_list = search.get_files()

    def play_wakeup(self):
        if STOP_ALL:
            return
        for dev in ACTIVE_DEVICES:
            os.popen('adb -s %s shell input tap 300 50' % dev)
        p = mp3play.load(self.wakeup_word)
        p.play()
        time.sleep(p.seconds() + .3)
        for no in range(len(ACTIVE_DEVICES)):
            if not DATA['is_wakeup' + str(no)]:
                self.play_wakeup()
                break

    @staticmethod
    def play_query(query):
        if STOP_ALL:
            return
        p = mp3play.load(query)
        p.play()
        time.sleep(p.seconds() + .1)
        while not all_recognized:
            continue

    def play(self):
        for query in self.query_list:
            if STOP_ALL:
                return
            self.play_wakeup()
            self.play_query(query)


class Tools(object):
    def __init__(self):
        pass

    def save_s311_log(self):
        cmds = [
            'data/anr',
            'sdcard/btsnoop_hci.log',
            'data/logger',
            'data/tombstones',
            'data/system/dropbox',
            'sdcard/tencent/wecarnavi/log',
            'sdcard/tencent/wecarspeech/log',
            'sdcard/WTLog'
        ]
        for dev in ACTIVE_DEVICES:
            path = os.path.join(save_log, dev)
            if not os.path.exists(path):
                os.makedirs(path)

            self.system('adb -s %s pull' % dev, cmds, path)

    def clear_s311_log(self):
        cmds = ['/data/anr/*',
                '/sdcard/btsnoop_hci.log',
                '/data/logger/*',
                '/data/tombstones/*',
                '/data/system/dropbox/*',
                '/sdcard/tencent/wecarnavi/log/*',
                '/sdcard/tencent/wecarspeech/log/*',
                ]
        for dev in ACTIVE_DEVICES:
            self.popen('adb -s %s shell rm -rf' % dev, cmds)
            os.popen('adb -s %s shell setprop debug.sys.logger.running 0' % dev).close()
            os.popen('adb -s %s shell rm -rf /sdcard/WTLog/main/*' % dev).close()
            os.popen('adb -s %s shell rm -rf /data/media/btsnoop.log' % dev).close()
            os.popen('adb -s %s shell setprop debug.sys.logger.running 1' % dev).close()
            pid = os.popen('adb -s %s shell ps | findstr speech' % dev).readlines()[0].split()[1]
            os.popen('adb -s %s shell kill -9 %s' % (dev, pid))

    def popen(self, header, cmds, tail=None):
        for cmd in cmds:
            os.popen(header + ' ' + cmd + ' ' + tail).close()

    def system(self, header, cmds, tail=None):
        for cmd in cmds:
            if 'wecarnavi' in cmd:
                os.system(header + ' ' + cmd + ' ' + tail + '\\' + 'wecarnavi')
            elif 'wecarspeech' in cmd:
                os.system(header + ' ' + cmd + ' ' + tail + '\\' + 'wecarspeech')
            else:
                os.system(header + ' ' + cmd + ' ' + tail)


if __name__ == '__main__':
    reports = []
    tool = Tools()
    app = MyApp()
    app.MainLoop()
