from tkinter import Tk, Frame, Label, Button, Entry, Scrollbar, Listbox, Text
from tkinter.scrolledtext import ScrolledText
from tkinter import END, HORIZONTAL
from tkinter.ttk import Progressbar, Combobox
from tkinter.messagebox import showerror, showinfo
from serial import Serial
from serial.tools.list_ports import comports
from threading import Thread
from serial.serialutil import SerialException


class App(Frame):
    def __init__(self):
        master = Tk()
        super().__init__(master)
        self.master = master
        self.x = 600
        self.y = 400

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
        btn_start.place(x=100, y=350, width=400, height=40)
        self.widgets["btn_start"] = btn_start

        # Combobox with label to select ports
        lb_ports = Label(self.master, text="Add a command to run")
        lb_ports.place(x=370, y=30)

        # Entry to write a command to be executed
        add_dx = 300
        entry_cmd = Entry(self.master, text="red", fg="green")
        entry_cmd.place(x=50 + add_dx, y=70, width=200, height=25)
        self.widgets["entry_cmd"] = entry_cmd

        # Button to add a command to be executed
        btn_addcmd = Button(self.master, text="Add", command=self.add_cmd)
        btn_addcmd.place(x=10 + add_dx, y=70)
        self.widgets["btn_addcmd"] = btn_addcmd

        scroll_dy = 100
        # List of commands to be executed
        scroll_cmdlist = Scrollbar(self.master)
        scroll_cmdlist.place(x=300, y=10 + scroll_dy, width=270, height=140)
        listbox_cmdlist = Listbox(self.master, yscrollcommand=scroll_cmdlist.set)
        listbox_cmdlist.place(x=300, y=30 + scroll_dy, width=270, height=100)
        scroll_cmdlist.config(command=listbox_cmdlist.yview)
        self.widgets["scroll_cmdlist"] = scroll_cmdlist
        self.widgets["lb_cmdlist"] = listbox_cmdlist

        # Button to clear listbox
        btn_clear = Button(self.master, text="Clear", command=self.clear_cmds)
        btn_clear.place(x=300, y=160 + scroll_dy, width=270, height=20)

        # Combobox with label to select ports
        lb_ports = Label(self.master, text="Settings")
        lb_ports.place(x=120, y=30)

        settings_dy = 75
        # Combobox with label to select ports
        lb_ports = Label(self.master, text="Select Port:")
        lb_ports.place(x=10, y=settings_dy)
        cb_ports = Combobox(self.master)
        cb_ports.place(x=130, y=settings_dy - 5, width=150, height=30)
        cb_ports["values"] = [port.name for port in comports()]
        cb_ports.current(0)
        self.widgets["cb_ports"] = cb_ports

        # Combobox with label to select ports
        lb_hostname = Label(self.master, text="Hostname of Device: ")
        lb_hostname.place(x=10, y=40 + settings_dy)
        # Entry to input hostname of router
        entry_rhostname = Entry(self.master, text="Router", fg="green")
        entry_rhostname.place(x=130, y=40 + settings_dy, width=150, height=25)
        self.widgets["entry_rhostname"] = entry_rhostname

        # Progressbar
        pb_progress = Progressbar(self.master, orient=HORIZONTAL, length=100, mode='determinate')
        pb_progress.place(x=10, y=450, width=self.x - 20, height=30)
        self.widgets["pb_progress"] = pb_progress

        # Console Log
        log_scroll_y = 140
        log_scroll_x = 12
        scroll_log = ScrolledText(self.master,
                                  width=30,
                                  height=8,
                                  font=("Courier New", 8),
                                  state="disabled"
                                  )
        scroll_log.place(x=log_scroll_x, y=10 + log_scroll_y, width=270, height=180)
        self.widgets["scroll_log"] = scroll_log
    # GUI ABOVE

    # LOGIC BELOW
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
        self.master.geometry(f"{self.x}x{self.y + 100}")
        total = len(self.commands) + 1
        complete = 0
        result = ""
        try:
            with Serial(self.get_port(), 9600, timeout=5) as ser:
                self.log("Establishing a connection with the router...")

                complete += 1
                self.progress = complete / total * 100
                self.widgets["pb_progress"]["value"] = int(self.progress)

                self.log("Entering exec mode...")
                self.write_cmd(ser, "enable")  # enter privilege exec mode
                self.write_cmd(ser, "terminal length 0")  # commands will not pause
                self.log("Entered exec mode")

                for cmd in self.commands:
                    self.log(f"Running command '{cmd}'")
                    result += self.read_until_end(ser, cmd)
                    complete += 1
                    self.progress = complete / total * 100
                    self.widgets["pb_progress"]["value"] = int(self.progress)

        except SerialException as err:
            self.log(f"Error: {err}\n*Cannot open multiple serial connections*")
            self.extracting = False
            return
        with open("config.txt", "w") as config:
            config.write(result)
        self.widgets["pb_progress"]["value"] = 0
        self.master.geometry(f"{self.x}x{self.y}")
        self.extracting = False
        self.log("==================\n"
                 "COMMANDS EXTRACTED\n"
                 "==================")

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
        timeout = 3
        router_name = self.widgets["entry_rhostname"].get()
        while line != f"{router_name}#" and timeout > 0:
            line = ser.readline().decode()
            self.log(f"Reading line: {line[:-2]}")
            if "!" not in line and line[:-2] != "":
                output += f"{line[:-2]}\n"  # get line without "\r\n"
            elif line[:-2] == "":
                timeout -= 1
        return output[:-6]  # clear "Route" bit at end

    def log(self, txt: str):
        print(txt)
        self.widgets["scroll_log"].config(state="normal") # for readonly
        self.widgets["scroll_log"].insert(END, txt + "\n")
        self.widgets["scroll_log"].config(state="disabled")
