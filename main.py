from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import time
import os
from colorama import Fore
import colorama

class MPRparser:
    def __init__(self, path, gg_gr_toggle):
        self.path = path
        self.line_array = []
        self.stop_in = 0
        self.saw_in = 0
        self.gs_reversed = False
        self.gg_gr_toggle = gg_gr_toggle

        with open(path, "r") as file:
            time.sleep(1.5)
            lines = file.readlines()
            for line in lines:
                self.line_array.append(line)

    def __repr__(self):
        return f"stop in: {self.stop_in}\nsaw in: {self.saw_in}\ngs reversed: {self.gs_reversed}"

    def parse(self):
        
        with open(self.path, "r") as file:
            lines = file.readlines()

            #NCSTOP
            idx = 0
            for line in lines:
                if "NCStop" in line:
                    self.stop_in = idx     
                    break
                idx+=1
            ###########################

            file.seek(0)
            lines = file.readlines()

            #SAW && GS_REVERSED
            idx = 0       
            for line in lines:

                if "Nuten" in line:
                    self.saw_in = idx+2 #added offset
                    
                    if self.saw_in > self.stop_in:
                        self.gs_reversed = True
                    break

                idx+=1
            #############################

            file.seek(0)
            lines = file.readlines()

            # Cancel GS_REVERSED if there's only SAW on the other side.
            after_stop_tmp = False
            more_than_saw = False

            for line in lines:
                if "<117" in line:
                    after_stop_tmp = True                
                elif after_stop_tmp and "<1" in line:
                    if not "109" in line and not "105" in line:
                        more_than_saw = True                  
                        break                         
            if not more_than_saw: self.gs_reversed = False
            ###############################

    def apply_flip_edits(self):

        if self.stop_in == 0: return

        line_array_tmp = []

        in_macro = False
        after_stop = False
        left_to_skip = 0
        in_block = False
      
        for line in self.line_array:
            #DP = Macro block child amount
            if "DP=" in line:
                left_to_skip = int(line.split('"')[1]) #don't ask again please.
                in_block = True
              
            elif "<1" in line and not "<100" in line and not "<101" in line:
                in_macro = True
            
            #doing things at the end of the macro
            elif line.strip() == "" or line.strip() == "!":

                #check if lines are after stop macro
                if not after_stop:
                    for i in line_array_tmp:
                        if "Stop" in i:
                            after_stop = True
                                  
                if in_macro and left_to_skip == 0 or in_block:
                    if after_stop == False:
                        if self.gs_reversed: line_array_tmp.append('??="gs=2"\n')
                        else: line_array_tmp.append('??="gs=1"\n')

                    elif after_stop == True:
                        if self.gs_reversed: line_array_tmp.append('??="gs=1"\n')
                        else: line_array_tmp.append('??="gs=2"\n')


                if left_to_skip > 0 and in_macro and not in_block:
                    left_to_skip -= 1

                in_block = False                                                                
                in_macro = False
               
            elif "LSL" in line:
                line_array_tmp.append('BM="LS"\n')
                line_array_tmp.append('TI="d/2+2"\n')
                #replace LSL with LS by skipping current line
                #maybe too hacky, but for now we'll leave it hanging for now
                continue 
                
            line_array_tmp.append(line)
            
    
        self.line_array = line_array_tmp
    
    def remove_macros(self):
        #remove useless crap like nc-stop and v.route
        in_stop_or_route = False
        line_array_tmp = []

        for line in self.line_array:

            if "NCStop" in line or "Vert. Route" in line:
                in_stop_or_route = True
                continue

            elif in_stop_or_route and line.strip() == "":
                in_stop_or_route = False
                continue
            
            if in_stop_or_route: continue
            
            line_array_tmp.append(line)

        self.line_array = line_array_tmp


    def apply_comment(self):
            if self.stop_in == 0: return

            flip = ""

            for line in self.line_array:
                if "KM" in line and "Y" in line:
                    flip = 'KM="!X"\n'               
                    break

                elif "KM" in line and "X" in line:
                    flip = 'KM="!Y"\n'               
                    break

            for i, line in enumerate(self.line_array):
                if 'km="ongaa"' in line.lower() and flip != "":
                    self.line_array[i] = flip
                    break

    def apply_19_25_through_drill(self):
        in_vertical = False
        is_through = False
        diam_index = 0

        for i, line in enumerate(self.line_array):

            if line == "\n":
                if diam_index != 0 and in_vertical and is_through:
                    if 19.0 <= float(self.line_array[diam_index].split('"')[1]) <= 25.0:
                        self.line_array[diam_index] = 'DU="10.0"\n'

                in_vertical = False
                is_through = False
                diam_index = 0

            elif "<102" and "Vert" in line:
                in_vertical = True

            elif "LSL" in line:
                is_through = True

            elif 'DU="' in line:
                diam_index = i

    def apply_gg_gr(self):
        there_is = False
        in_vertical = False

        #TI="18.000"
        gg_index = 0
        #DU="8.000"
        gr_index = 0

        for i, line in enumerate(self.line_array):

            if line == "\n":
                if gr_index != 0 and gg_index != 0 and in_vertical:
                    self.line_array[gg_index] = 'TI="gg"\n'
                    self.line_array[gr_index] = 'DU="gr"\n'
                    there_is = True

                in_vertical = False
                gg_index = 0
                gr_index = 0


            elif "<102" and "Vert" in line:
                in_vertical = True

            elif 'TI="18.000' in line:
                gg_index = i
            
            elif 'DU="8.000"' in line:
                gr_index = i

        #apply variables
        if not there_is: return

        in_variable_section = False
        line_array_tmp = []

        for i, line in enumerate(self.line_array):
            if line == "\n" and in_variable_section: 
                line_array_tmp.append('gg="18"\n')
                line_array_tmp.append('KM=""\n')
                line_array_tmp.append('gr="13.5"\n')
                line_array_tmp.append('KM=""\n')
                in_variable_section = False

            elif "[001" in line:
                in_variable_section = True
            
            line_array_tmp.append(line)
        
        self.line_array = line_array_tmp

    def apply_pocket(self):
        has_pocket = False #apply variable later if True
        in_pocket = False
        valid_la = False
        valid_br = False

        for i, line in enumerate(self.line_array):
            if line == "\n":
                in_pocket = False
                valid_br = False
                valid_la = False

            #circle pockets don't have dimensions, only radius.
            elif 'LA=".0"' in line:
                valid_la = True
            elif 'BR=".0"' in line:
                valid_br = True

            elif "<112" in line:
                in_pocket = True

            elif in_pocket and valid_la and valid_br and 'RD="' in line:
                radius = float(line.split('"')[1])
                self.line_array[i] = f'RD="(sk+{radius*2})/2"\n'
                has_pocket = True

        if not has_pocket:
            return

        in_variable_section = False
        line_array_tmp = []

        for i, line in enumerate(self.line_array):
            if line == "\n" and in_variable_section: 
                line_array_tmp.append('sk="0"\n')
                line_array_tmp.append('KM=""\n')
                in_variable_section = False

            elif "[001" in line:
                in_variable_section = True
            
            line_array_tmp.append(line)
        
        self.line_array = line_array_tmp

            

    def edit(self):
        self.apply_flip_edits() # GS1/GS2 and D/2+2
        self.apply_comment()
        self.remove_macros()

        if self.gg_gr_toggle:
            self.apply_gg_gr()

        self.apply_pocket()
        self.apply_19_25_through_drill()

        with open(self.path, 'w') as file:
            for line in self.line_array:
                file.write(line)

    def open(self):
        os.system(self.path)           

class MyHandler(FileSystemEventHandler):
    def __init__(self):
        self.last_modified = ""
        self.konvertuoti_file_path = "//Path_to_PC/Konvertuoti/2025"
        self.konvertuoti_txt = "ongaa_s.txt"
        self.gg_gr_toggle = True

    def get_code(self):
        base = self.last_modified.split('.')[0]
        value = base.split('_')[-1]
        return value

    def on_created(self, event):
        self.handle_mpr(event)

    def on_modified(self, event):
        self.handle_mpr(event)

    def handle_mpr(self, event):
        if not event.is_directory and self.last_modified != event.src_path:

            self.last_modified = event.src_path
            mpr = MPRparser(event.src_path, gg_gr_toggle = self.gg_gr_toggle)
            mpr.parse()
            mpr.edit()
            mpr.open()
            #self.last_modified =" "
            self.update_screen()
            #self.handle_konvertuoti()

    def update_screen(self):
        os.system('cls')
        print("Paskutinis koregavimas: " + self.last_modified + Fore.YELLOW + " (R - panaikinti)")

        if self.gg_gr_toggle:
            print(Fore.GREEN + "GG GR įjungtas (Q - išjungti)")
        if not self.gg_gr_toggle:
            print(Fore.RED + "GG GR išjungtas (Q - įjungti)")
        
from pynput import keyboard
from functools import partial
import win32gui

# Get the title of the active window
def get_active_window_title():
    window = win32gui.GetForegroundWindow()
    return win32gui.GetWindowText(window)
        
def on_key_press(event_handler, key):
    if get_active_window_title() != "Windows PowerShell": return
    try:
        if key.char == 'q':

            if event_handler.gg_gr_toggle == True:
                event_handler.gg_gr_toggle = False
            else:
                event_handler.gg_gr_toggle = True

        elif key.char == 'r':
            event_handler.last_modified = ""

        event_handler.update_screen()

    except Exception:
        pass


if __name__ == "__main__":
    path = "."  # Directory to monitor (current directory in this case)
    event_handler = MyHandler()
    observer = Observer()
    observer.schedule(event_handler, "C:\\tmp", recursive=True)
    observer.start()

    colorama.init(autoreset=True)

    event_handler.update_screen()

    listener = keyboard.Listener(on_press=partial(on_key_press, event_handler))
    listener.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
