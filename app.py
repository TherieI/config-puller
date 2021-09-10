from tkinter import Tk, Frame, Label, Button, Entry, Scrollbar, Listbox
from tkinter import END, HORIZONTAL
from tkinter.ttk import Progressbar, Combobox
from tkinter.messagebox import showerror, showinfo
from serial import Serial
from serial.tools.list_ports import comports
from threading import Thread
from time import time


class App(Frame):
    def __init__(self):
        master = Tk()
        super().__init__(master)
        self.master = master
        self.x = 400
        self.y = 200

        self.widgets = {}
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
        # Button to execute commands in a router terminal
        btn_start = Button(self.master, text="Extract", command=self.extract)
        btn_start.place(x=10, y=100, width=190, height=90)
        self.widgets["btn_start"] = btn_start

        # Entry to write a command to be executed
        entry_cmd = Entry(self.master, text="red", fg="green")
        entry_cmd.place(x=50, y=70, width=150, height=25)
        self.widgets["entry_cmd"] = entry_cmd

        # Button to add a command to be executed
        btn_addcmd = Button(self.master, text="Add", command=self.add_cmd)
        btn_addcmd.place(x=10, y=70)
        self.widgets["btn_addcmd"] = btn_addcmd

        # List of commands to be executed
        scroll_cmdlist = Scrollbar(self.master)
        scroll_cmdlist.place(x=250, y=10, width=120, height=140)
        listbox_cmdlist = Listbox(self.master, yscrollcommand=scroll_cmdlist.set)
        listbox_cmdlist.place(x=250, y=30, width=120, height=100)
        scroll_cmdlist.config(command=listbox_cmdlist.yview)
        self.widgets["scroll_cmdlist"] = scroll_cmdlist
        self.widgets["lb_cmdlist"] = listbox_cmdlist

        # Button to clear listbox
        btn_clear = Button(self.master, text="Clear", command=self.clear_cmds)
        btn_clear.place(x=250, y=160, width=120, height=20)

        # Combobox with label to select ports
        lb_ports = Label(self.master, text="Select Port:")
        lb_ports.place(x=10, y=15)
        cb_ports = Combobox(self.master)
        cb_ports.place(x=90, y=10, width=110, height=30)
        cb_ports["values"] = [port.name for port in comports()]
        cb_ports.current(0)
        self.widgets["cb_ports"] = cb_ports

        # Progressbar
        pb_progress = Progressbar(self.master, orient=HORIZONTAL, length=100, mode='determinate')
        pb_progress.place(x=10, y=240, width=self.x-20, height=30)
        self.widgets["pb_progress"] = pb_progress

    def add_cmd(self):
        cmd = self.widgets["entry_cmd"].get()
        self.commands.append(cmd)
        self.widgets["entry_cmd"].delete(0, last=len(cmd))
        self.widgets["lb_cmdlist"].insert(END, cmd)

    def clear_cmds(self):
        self.widgets["lb_cmdlist"].delete(0, END)
        self.commands = []

    def extract(self):
        if len(self.commands) <= 0:
            showerror(title="Error", message="You don't have any commands to run")
        elif not self.extracting:
            self.progress = 0
            self.extracting = True
            extr_thread = Thread(target=self._extract, daemon=True)
            extr_thread.start()
        else:
            showerror(title="Error", message="You are already in the process of extracting")

    def _extract(self):
        self.master.geometry(f"{self.x}x{self.y+100}")
        total = len(self.commands) + 1
        complete = 0
        result = ""
        with Serial(self.get_port(), 9600, timeout=5) as ser:
            print("Establishing a connection with the router")
            ready = self.wait_until_ready(ser)
            if not ready:
                showerror(title="Error", message="Not able to enter privilege exec mode")
                self.master.geometry(f"{self.x}x{self.y}")
                self.extracting = False
                return
            print('Router ready')

            complete += 1
            self.progress = complete / total * 100
            self.widgets["pb_progress"]["value"] = int(self.progress)

            self.write_cmd(ser, "enable")  # enter privilege exec mode
            self.write_cmd(ser, "terminal length 0")  # commands will not pause
            for cmd in self.commands:
                print(f"starting {cmd}")
                result += self.read_until_end(ser, cmd)
                complete += 1
                self.progress = complete/total * 100
                self.widgets["pb_progress"]["value"] = int(self.progress)
                print(f"{self.progress}%")

        with open("config.txt", "w") as config:
            config.write(result)
        self.widgets["pb_progress"]["value"] = 0
        self.master.geometry(f"{self.x}x{self.y}")
        self.extracting = False
        showinfo(title="Build complete", message="Commands extracted")

    def get_port(self) -> str:
        port = self.widgets["cb_ports"].get()
        ports = [port.name for port in comports()]
        if port not in ports:
            showerror(title="Error", message=f"That port does not exist, defaulting to {ports[0]}")
            self.widgets["cb_ports"].current(0)
            return ports[0]
        return port

    def write_cmd(self, ser: Serial, cmd: str):
        cmd = f"{cmd}\n".encode()  # Console parseable
        ser.write(cmd)

    def read_until_end(self, ser: Serial, cmd: str) -> str:
        self.write_cmd(ser, cmd)
        output = ""
        line = ""
        while line != "Router#":
            # print(f"{line=}")
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
