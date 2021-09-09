from tkinter import Tk, Frame, Button, Entry, Scrollbar, Listbox
from tkinter import END
from tkinter.messagebox import showerror
from serial import Serial
from threading import Thread
from time import time


class App(Frame):
    def __init__(self):
        master = Tk()
        super().__init__(master)
        self.master = master
        self.x = 400
        self.y = 200

        self.widgets = []
        self.init_basic()
        self.init_widgets()

        self.commands = []
        self.progress = 0
        self.extracting = False

    def init_basic(self):
        self.master.title("Config-puller")
        self.master.iconbitmap("router.ico")
        self.master.geometry(f"{self.x}x{self.y}")
        self.master.resizable(False, False)

    def init_widgets(self):
        btn_start = Button(self.master, text="Extract", command=self.extract)
        btn_start.place(x=10, y=40, width=190, height=150)

        entry_cmd = Entry(self.master, text="red", fg="blue")
        entry_cmd.place(x=50, y=10, width=150, height=25)

        btn_addcmd = Button(self.master, text="add", command=self.add_cmd)
        btn_addcmd.place(x=10, y=10)

        scroll_cmdlist = Scrollbar(self.master)
        scroll_cmdlist.place(x=250, y=10, width=120, height=180)
        listbox_cmdlist = Listbox(self.master, yscrollcommand=scroll_cmdlist.set)
        listbox_cmdlist.place(x=250, y=30, width=120, height=140)
        scroll_cmdlist.config(command=listbox_cmdlist.yview)

        self.widgets += [btn_start, entry_cmd, btn_addcmd, listbox_cmdlist]

    def add_cmd(self):
        cmd = self.widgets[1].get()
        self.commands.append(cmd)
        self.widgets[1].delete(0, last=len(cmd))
        self.widgets[-1].insert(END, cmd)

    def extract(self):
        self.progress = 0
        if not self.extracting:
            self.extracting = True
            extr_thread = Thread(target=self._extract, daemon=True)
            extr_thread.start()
        else:
            showerror(title="Error", message="You are already in the process of extracting")

    def _extract(self):
        total = len(self.commands)
        complete = 0
        result = ""
        with Serial("COM1", 9600, timeout=5) as ser:
            print("Establishing a connection with the router")
            ready = self.wait_until_ready(ser)
            if not ready:
                showerror(title="Error", message="Not able to enter privilege exec mode")
                self.extracting = False
                return
            print('Router ready')
            self.write_cmd(ser, "enable")  # enter privilege exec mode
            self.write_cmd(ser, "terminal length 0")  # commands will not pause
            for cmd in self.commands:
                print(f"starting {cmd}")
                result += self.read_until_end(ser, cmd)
                complete += 1
                self.progress = complete/total * 100
                print(f"{self.progress}%")
        with open("config.txt", "w") as config:
            config.write(result)
        self.extracting = False

    def write_cmd(self, ser: Serial, cmd: str):
        cmd = f"{cmd}\n".encode()  # Console parseable
        ser.write(cmd)

    def read_until_end(self, ser: Serial, cmd: str) -> str:
        self.write_cmd(ser, cmd)
        output = ""
        line = ""
        while line != "Router#":
            line = ser.readline().decode()
            if "!" not in line and line[:-2] != "":
                output += f"{line[:-2]}\n"  # get line without "\r\n"
        return output[:-6]  # clear "Route" bit at end

    def wait_until_ready(self, ser: Serial, timeout: int = 60):  # waits for the router to enter privilege exec mode
        init_time = time()
        self.write_cmd(ser, "\r")  # newline to startup device
        count = 0
        while True:
            line = ser.readline().decode()
            if count > 1:  # after the initial dialogue, lines begin to look like line="", so after we get two blank lines we know the router has probably booted in user exec
                return True
            elif line == "":
                count += 1
            elif time() > init_time + timeout:  # 60 seconds have passed so the router hasn't booted correctly
                return False
            elif "Router" in line and len(
                    line) > 9:  # if the router is currently in a mode above priv exec, return to priv exec and begin
                self.write_cmd(ser, "end")
                return True
            elif "Would you like to enter the initial configuration dialog? [yes/no]:" in line:
                self.write_cmd(ser, "no")
            else:
                count = 0
