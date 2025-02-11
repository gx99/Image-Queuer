import os
import sys
from pathlib import Path
import shelve
import random

from PyQt5 import QtCore, QtGui
from PyQt5.uic.uiparser import QtWidgets
from PyQt5.QtWidgets import *
from PyQt5.QtTest import QTest

import resources_config
from main_window import Ui_MainWindow
from session_display import Ui_session_display
from check_update import Version
os.chdir(os.path.abspath(os.path.dirname(sys.argv[0])))

CURRENT_VERSION = '0.3.4'
# Contrast on buttons now WCAG AAA
# New hotkeys added: Ctrl+Enter: start session, Esc: close window, Enter: add entry, F: open files... full list in the README
# Randomization will now be handled as a toggle, and will be loaded up along with the recent session settings
# BUGFIX break.png now adequately handled
# Some code housekeeping

class MainApp(QMainWindow, Ui_MainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.current_version = CURRENT_VERSION
        self.setWindowTitle(f'Reference Practice v{self.current_version}')
        self.session_schedule = {}
        self.has_break = False
        self.valid_file_types = ['.bmp','.jpg','.jpeg','.png']
        self.schedule = []
        self.total_time = 0
        self.total_images = 0
        self.selection = {'folders':[],'files':[]}

        # Buttons for selection
        self.add_folder.clicked.connect(self.open_folder)
        self.clear_items.clicked.connect(self.remove_items)
        self.randomize_selection.clicked.connect(self.display_random_status)
        self.remove_duplicates.clicked.connect(self.remove_dupes)

        # Buttons for preset
        self.add_entry.clicked.connect(self.append_schedule)
        self.save_preset.clicked.connect(self.save)
        self.delete_preset.clicked.connect(self.delete)
        self.preset_loader_box.currentIndexChanged.connect(self.load)

        # Buttons for table
        self.remove_entry.clicked.connect(self.remove_row)
        self.move_entry_up.clicked.connect(self.move_up)
        self.move_entry_down.clicked.connect(self.move_down)
        self.reset_table.clicked.connect(self.remove_rows)
        
        # Shortcuts
        # Ctrl+Enter to start session
        self.return_shortcut = QShortcut(QtGui.QKeySequence('Ctrl+Return'), self)
        self.return_shortcut.activated.connect(self.start_session)
        self.enter_shortcut = QShortcut(QtGui.QKeySequence('Ctrl+Enter'), self)
        self.enter_shortcut.activated.connect(self.start_session)
        # Escape to close window
        self.escape_shortcut = QShortcut(QtGui.QKeySequence('Escape'), self)
        self.escape_shortcut.activated.connect(self.close)
        # Add entry
        self.add_shortcut_return = QShortcut(QtGui.QKeySequence('Return'), self)
        self.add_shortcut_return.activated.connect(self.append_schedule)
        self.add_shortcut_enter = QShortcut(QtGui.QKeySequence('Enter'), self)
        self.add_shortcut_enter.activated.connect(self.append_schedule)

        self.init_preset()
        self.load_recent()
        self.check_version()
        self.entry_table.itemChanged.connect(self.update_total)
        self.dialog_buttons.accepted.connect(self.start_session)

    def display_random_status(self):
        if self.randomize_selection.isChecked():
            self.selected_items.setText(f'Randomization on!')
        else:
            self.selected_items.setText(f'Randomization off!')
        QTest.qWait(2000)
        self.display_status()

    #region Functions for user input
    #region Select Items
    def open_files(self):
        selected_files = QFileDialog().getOpenFileNames()
        checked_files = self.check_files(selected_files[0])
        self.selection['files'].extend(checked_files['valid_files'])
        self.selected_items.setText(f'{len(checked_files["valid_files"])} file(s) added!')
        if len(checked_files['invalid_files']) > 0:
            self.selected_items.append(f'{len(checked_files["invalid_files"])} file(s) not added. Supported file types: {", ".join(self.valid_file_types)}.')
            QTest.qWait(2000)
        QTest.qWait(3000)
        self.display_status()

    def open_folder(self):
        """
        Calls on self.check_files to check each file in the user selected directories
        Saves folder paths, and file names
        Displays message of result
        
        """
        # Subclassed QFileDialog
        selected_dir = FileDialog()
        if selected_dir.exec():
            # Example of result
            # ['D:/Files/Documents/Programming/Projects/Image Displayer/image_displayer/atest2', 'D:/Files/Documents/Programming/Projects/Image Displayer/image_displayer/atest1']
            total_valid_files = 0
            total_invalid_files = 0
            self.selected_items.clear()
            for directory in selected_dir.selectedFiles():
                checked_files = self.check_files(os.listdir(directory))
                total_valid_files += len(checked_files['valid_files'])
                total_invalid_files += len(checked_files['invalid_files'])
                if directory not in self.selection['folders']:
                    self.selection['folders'].append(directory)
                for file in checked_files['valid_files']:
                    self.selection['files'].append(f'{directory}/{file}')
            self.selected_items.append(f'{total_valid_files} file(s) added from {len(selected_dir.selectedFiles())} folders!')
            if total_invalid_files > 0:
                self.selected_items.append(f'{total_invalid_files} file(s) not added. Supported file types: {", ".join(self.valid_file_types)}. Does not add folders.')
                QTest.qWait(3000)
            QTest.qWait(4000)
            self.display_status()
            return
        self.selected_items.setText(f'0 folder(s) added!')
        QTest.qWait(2000)
        self.display_status()

    def check_files(self, files):
        """Checks if files are supported file types"""
        res = {'valid_files':[],'invalid_files':[]}
        for file in files:
            if file[-4:].lower() not in self.valid_file_types:
                res['invalid_files'].append(file)
            else:
                res['valid_files'].append(file)
        return res

    def remove_items(self):
        """Clears entire selection"""
        self.selection['files'].clear()
        self.selection['folders'].clear()
        self.selected_items.setText(f'All files and folders cleared!')
        QTest.qWait(2000)
        self.display_status()

    def remove_dupes(self):
        """
        Iterates through user selection of files while keeping seen files 
        in memory
        If a file has already been seen, it is deleted from the selection
        """
        self.duplicates = []
        files = []
        i = len(self.selection['files'])
        while i > 0:
            i -= 1
            if os.path.basename(self.selection['files'][i]) in files:
                self.duplicates.append(self.selection['files'].pop(i))
            else:
                files.append(os.path.basename(self.selection['files'][i]))
        self.selected_items.setText(f'Removed {len(self.duplicates)} duplicates!')
        QTest.qWait(2000)
        self.display_status()

    def display_status(self):
        """Displays amount of files, and folders selected"""
        self.selected_items.setText(f'{len(self.selection["files"])} total files added from {len(self.selection["folders"])} folder(s).')

    def load_recent(self):
        """
        Loads most recent session settings:
        Selected items
        Preset
        Randomization
        Removes breaks in case entire program closed during a session
        Displays status
        """
        if os.path.exists(r'.\recent'):
            try:
                os.chdir(r'.\recent')
                recent = shelve.open('recent')
                keys = list(recent['recent'].keys())
                for key in keys:
                    self.selection[key] = recent['recent'][key]
                self.preset_loader_box.setCurrentIndex(recent['recent_preset'])
                self.randomize_selection.setChecked(recent['randomized'])
                recent.close()
                os.chdir(r'..\\')
            except:
                print('load_recent error')
                print(os.getcwd())
                os.chdir(os.path.abspath(os.path.dirname(sys.argv[0])))
                return
            self.remove_breaks()
            self.display_status()
            self.selected_items.append(f'Recent session settings loaded!')
            self.update_total()
            if not self.is_valid_session():
                return

    #endregion

    #region Session Settings
    def append_schedule(self):
        """
        Adds entry information as a new row in the schedule
        Resets scrollboxes to 0
        Updates total amount
        """
        entry = []
        self.table_entries = self.entry_table.rowCount()+1
        entry.append(self.table_entries)
        images = self.set_number_of_images.value()
        entry.append(images)
        duration = self.set_minutes.value()*60 + self.set_seconds.value()
        entry.append(duration)
        self.set_number_of_images.setValue(0)
        self.set_minutes.setValue(0)
        self.set_seconds.setValue(0)
        row = self.entry_table.rowCount()
        self.entry_table.insertRow(row)
        for column, item in enumerate(entry):
            item = QTableWidgetItem(str(item))
            item.setTextAlignment(4)
            self.entry_table.setItem(row, column, item)
        self.update_total()

    def remove_row(self):
        row = self.entry_table.currentRow()
        if row == self.entry_table.rowCount()-1:
            last = True
        self.entry_table.removeRow(row)
        for i in range(row, self.entry_table.rowCount()):
            item = QTableWidgetItem(str(i+1))
            item.setTextAlignment(4)
            self.entry_table.setItem(i,0,item)
        try:
            if last:
                self.entry_table.setCurrentCell(row-1,0)
        except:
            self.entry_table.setCurrentCell(row,0)
        self.update_total()

    def move_up(self):
        row = self.entry_table.currentRow()
        if row == 0:
            return
        self.entry_table.setCurrentCell(row,0)
        for column in range(self.entry_table.columnCount()):
            if column == 0:
                continue
            try:
                current, above = QTableWidgetItem(self.entry_table.item(row,column).text()),QTableWidgetItem(self.entry_table.item(row-1,column).text())
            except:
                self.selected_items.append('\nSelect a row in the table!')
                QTest.qWait(2000)
                self.display_status()
                return
            current.setTextAlignment(4)
            above.setTextAlignment(4)
            self.entry_table.setItem(row,column,above)
            self.entry_table.setItem(row-1,column,current)
        self.entry_table.setCurrentCell(row-1,0)

    def move_down(self):
        row = self.entry_table.currentRow()
        if row == self.entry_table.rowCount() - 1:
            return
        self.entry_table.setCurrentCell(row,0)
        for column in range(self.entry_table.columnCount()):
            if column == 0:
                continue
            try:
                current, below = QTableWidgetItem(self.entry_table.item(row,column).text()), QTableWidgetItem(self.entry_table.item(row+1,column).text())
            except:
                self.selected_items.append('\nSelect a row in the table!')
                QTest.qWait(2000)
                self.display_status()
                return
            current.setTextAlignment(4)
            below.setTextAlignment(4)
            self.entry_table.setItem(row+1,column,current)
            self.entry_table.setItem(row,column,below)
        self.entry_table.setCurrentCell(row+1,0)

    #Clears the schedule of its entries
    def remove_rows(self):
        for i in range(self.entry_table.rowCount()):
            self.entry_table.removeRow(0)
        self.update_total()

    def randomize_items(self):
        copy = self.selection['files'].copy()
        randomized_items = []
        while len(copy) > 0:
            random_index = random.randint(0,len(copy)-1)
            randomized_items.append(copy.pop(random_index))
        self.selection['files'] = randomized_items
        self.display_status()

    def update_total(self):
        # Adds a row for total if it's empty
        if self.total_table.rowCount() < 1:
            self.total_table.insertRow(0)

        total = QTableWidgetItem('Total')
        total.setTextAlignment(4)
        self.total_table.setItem(0,0,total)

        # Number of images
        self.total_images = 0
        for row in range(self.entry_table.rowCount()):
            try:
                self.total_images += int(self.entry_table.item(row,1).text())
            except:
                return
        total_images = QTableWidgetItem(str(self.total_images))
        total_images.setTextAlignment(4)
        self.total_table.setItem(0,1,total_images)

        # Total time
        self.total_time = 0
        for row in range(self.entry_table.rowCount()):
            try:
                if int(self.entry_table.item(row,1).text()) > 0:
                    self.total_time += int(self.entry_table.item(row,2).text())*int(self.entry_table.item(row,1).text())
                else:
                    self.total_time += int(self.entry_table.item(row,2).text())
            except:
                return
        total_time = QTableWidgetItem(self.format_seconds(self.total_time))
        total_time.setTextAlignment(4)
        self.total_table.setItem(0,2,total_time)

    def format_seconds(self, sec):
        hrs = int(sec/3600)
        self.hrs_list = list(str(hrs))
        if len(self.hrs_list) == 1 or self.hrs_list[0] == "0":
            self.hrs_list.insert(0,'0')

        mins = int((sec/3600 - hrs) * 60)
        self.mins_list = list(str(mins))
        if len(self.mins_list) == 1 or self.mins_list[0] == "0":
            self.mins_list.insert(0,'0')

        self.secs = list(str(int((((sec/3600 - hrs) * 60) - mins) * 60)))
        if len(self.secs) == 1 or self.secs[0] == "0":
            self.secs.insert(0,'0')
        return f'{self.hrs_list[0]}{self.hrs_list[1]}:{self.mins_list[0]}{self.mins_list[1]}:{self.secs[0]}{self.secs[1]}'
    #endregion

    #region Presets
    def init_preset(self):
        self.presets = {}
        # If the presets folder does not exist in file directory, then create it and create shelve files there
        if not os.path.exists(r'.\presets'):
            os.mkdir(r'.\presets')
            os.chdir(r'.\presets')
            preset = shelve.open('preset')
            preset.close()
            os.chdir(r'..\\')
        # Load data from preset files then update presets
        else:
            try:
                os.chdir(r'.\presets')
                temp = shelve.open('preset')
                preset_list = list(temp.keys())
                for preset in preset_list:
                    self.presets[preset] = temp[preset]
                temp.close()
                os.chdir(r'..\\')
                self.update_presets() 
            except:
                print('init_preset error')
                print(os.getcwd())
                os.chdir(os.path.abspath(os.path.dirname(sys.argv[0])))

    def update_presets(self):
        self.preset_loader_box.clear()
        self.preset_names = []
        for p in [*self.presets]:
            if p not in self.preset_names:
                self.preset_names.append(p)
        self.preset_loader_box.addItems(self.preset_names)
        self.update_total()

    def save(self):
        if self.entry_table.rowCount() == 0:
            self.selected_items.setText(f'Cannot save an empty schedule!')
            QTest.qWait(4000)
            self.display_status()
            return

        preset_name = self.preset_loader_box.currentText()

        if preset_name == '':
            self.selected_items.setText(f'Cannot save an empty name!')
            QTest.qWait(5500)
            self.display_status()
            return
        tmppreset = {}

        # Get table entries
        for row in range(self.entry_table.rowCount()):
            tmppreset[row] = []
            for column in range(self.entry_table.columnCount()):
                tmppreset[row].append(self.entry_table.item(row,column).text())

        # Save preset to file
        os.chdir(r'.\presets')
        preset = shelve.open('preset')
        preset[preset_name] = tmppreset
        preset.close()
        os.chdir(r'..\\')

        # Load preset to new name
        self.selected_items.setText(f'{preset_name} saved!')
        if self.preset_loader_box.currentText() not in [*self.presets]:
            self.presets[preset_name] = tmppreset
            self.update_presets()
            self.preset_loader_box.setCurrentIndex(self.preset_loader_box.count()-1)
        else:
            self.presets[preset_name] = tmppreset
        QTest.qWait(3000)
        self.display_status()

    def delete(self):
        preset_name = self.preset_loader_box.currentText()
        if preset_name == '':
            self.selected_items.setText(f'Cannot delete an empty field!')
            QTest.qWait(4000)
            self.display_status()
            return
        os.chdir(r'.\presets')
        preset = shelve.open('preset')
        del preset[preset_name]
        preset.close()
        os.chdir(r'..\\')
        del self.presets[preset_name]
        self.selected_items.setText(f'{preset_name} deleted!')
        self.preset_loader_box.removeItem(self.preset_loader_box.currentIndex())
        QTest.qWait(2000)
        self.display_status()

    def load(self):
        preset_name = self.preset_loader_box.currentText()
        if preset_name not in [*self.presets]:
            self.preset_loader_box.removeItem(self.preset_loader_box.currentIndex())
            self.preset_loader_box.clearEditText()
            self.remove_rows()
            return
        self.remove_rows()
        self.presets[preset_name]
        rows = list(self.presets[preset_name].keys())
        columns = list(self.presets[preset_name][0])
        for row in range(len(rows)):
            self.entry_table.insertRow(row)
            for column in range(len(columns)):
                item = QTableWidgetItem(self.presets[preset_name][row][column])
                item.setTextAlignment(4)
                self.entry_table.setItem(row, column, item)

    #endregion
    #endregion
    #region Start Session
    def start_session(self):
        """
        Grabs schedule, checks for valid session, checks for empty schedule,
        grabs randomization setting, save 'recent', insert break.png, 
        shows session window
        self.selection['files'] => images to display
        self.session_schedule => schedule
        """
        self.grab_schedule()

        if not self.is_valid_session():
            return

        if len(self.session_schedule) == 0:
            self.selected_items.setText(f'Schedule cannot be empty.')
            QTest.qWait(3000)
            self.display_status()
            return

        if self.randomize_selection.isChecked():
            self.randomize_items()

        #saves to recent folder
        self.save_to_recent()
        self.insert_breaks()
        self.display = SessionDisplay(schedule=self.session_schedule, items=self.selection['files'])
        self.display.closed.connect(self.session_closed)
        self.display.show()

    def session_closed(self):
        """Removes breaks, and displays status"""
        self.remove_breaks()
        self.display_status()
        self.selected_items.append(f'Recent session settings saved!')

    def is_valid_session(self):
        """
        Checks if all files exist and 
        if there are enough images for the schedule
        """
        # Count scheduled images
        self.total_scheduled_images = 0
        for entry in [*self.session_schedule]:
            self.total_scheduled_images += int(self.session_schedule[entry][1])

        # Check if file exists
        for file in self.selection['files']:
            file_path = Path(file)
            if not file_path.is_file():
                self.selection['files'].remove(file)
                self.selected_items.setText(f'{os.path.basename(file)} not found!')
                self.selected_items.append(f'Has the location or file name been changed?')
                self.selected_items.append(f'Image removed from selection. {len(self.selection["files"])} total files.')
                self.selected_items.append(f'Previous directory: \n{os.path.dirname(file)}')
                return False

        # Check if there are enough selected images for the schedule
        if self.total_scheduled_images <= len(self.selection['files']):
            return True

        self.selected_items.setText(f'Not enough images selected. Add more images, or schedule fewer images.')
        QTest.qWait(4000)
        self.display_status()
        return False

    def insert_breaks(self):
        """Adds the break image as specified by the schedule"""
        if self.has_break:
            #add break image at appropriate index
            current_index = 0
            for entry in [*self.session_schedule]:
                if self.session_schedule[entry][1] == '0':
                    self.selection['files'].insert(current_index, ":/break/break.png")
                    continue
                current_index += int(self.session_schedule[entry][1])

    def remove_breaks(self):
        """Removes breaks images from the selection of files"""
        i = len(self.selection['files'])
        while i > 0:
            i -= 1
            if os.path.basename(self.selection['files'][i]) == 'break.png':
                self.selection['files'].pop(i)

    def grab_schedule(self):
        """Builds self.session_schedule with data from the schedule"""
        for row in range(self.entry_table.rowCount()):
            self.session_schedule[row] = []
            for column in range(self.entry_table.columnCount()):
                if self.entry_table.item(row,column).text() == '0':
                    self.has_break = True
                self.session_schedule[row].append(self.entry_table.item(row,column).text())

    def save_to_recent(self):
        """Saves current selection, selected preset, and randomization setting"""
        self.recent = {}
        if not os.path.exists(r'.\recent'):
            os.mkdir(r'.\recent')
        os.chdir(r'.\recent')
        file = shelve.open('recent')
        file['recent'] = self.selection
        file['recent_preset'] = self.preset_loader_box.currentIndex()
        file['randomized'] = self.randomize_selection.isChecked()
        file.close()
        os.chdir(r'..\\')
    #endregion

    #region Updates
    def check_version(self):
        """
        Checks if the current version is the newest one. If not, an update 
        notice is displayed in the display
        """
        current_version = Version(self.current_version)
        if not current_version.is_newest():
            
            update_type = current_version.update_type()
            if type(update_type) == str:
                self.selected_items.append(f'\n{update_type} update available!')
                content = current_version.content()
                self.selected_items.append(f'v{current_version.newest_version}\n{content}')
    #endregion


class SessionDisplay(QWidget, Ui_session_display):
    closed = QtCore.pyqtSignal()
    def __init__(self, schedule=None, items=None):
        super().__init__()
        self.setupUi(self)
        self.schedule = schedule
        # self.setWindowFlags(
        #     QtCore.Qt.Window |
        #     QtCore.Qt.CustomizeWindowHint |
        #     QtCore.Qt.WindowTitleHint |
        #     QtCore.Qt.WindowMinMaxButtonsHint |
        #     QtCore.Qt.WindowCloseButtonHint |
        #     QtCore.Qt.WindowStaysOnTopHint
        #     )
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.countdown)
        self.timer.start(500)
        self.pause_timer.clicked.connect(self.pause)
        self.add_30.clicked.connect(self.add_30_seconds)
        self.add_60.clicked.connect(self.add_60_seconds)
        self.entry = {'current':0,'total':[*self.schedule][-1]+1, 'amount of items':int(self.schedule[0][1]), 'time':int(self.schedule[0][2])}
        self.playlist = items
        self.playlist_position = 0
        self.installEventFilter(self)
        self.load_entry()
        self.previous_image.clicked.connect(self.previous_playlist_position)
        self.next_image.clicked.connect(self.load_next_image)
        self.restart.clicked.connect(self.restart_timer)
        self.stop_session.clicked.connect(self.close)

    def closeEvent(self, event):
        self.timer.stop()
        self.closed.emit()
        event.accept()

    #region Session processing functions
    def eventFilter(self, source, event):
        if (source is self and event.type() == QtCore.QEvent.Resize):
            self.image_display.setPixmap(self.image.scaled(self.size(),aspectRatioMode=1))
        return super(SessionDisplay, self).eventFilter(source, event)

    def load_entry(self):
        if self.entry['current'] >= self.entry['total']:
            self.timer.stop()
            self.timer_display.setText(f'Last image!')
            return
        self.entry['time'] = int(self.schedule[self.entry['current']][2])
        self.timer.stop()
        self.time_seconds = self.entry['time']
        self.timer.start(500)
        self.entry['amount of items'] = int(self.schedule[self.entry['current']][1])-1
        self.display_image()

    def load_next_image(self):
        if self.entry['current'] >= self.entry['total']:
            return
        if self.entry['amount of items'] == 0:
            self.entry['current'] += 1
            self.playlist_position += 1
            self.load_entry()
        else:
            self.timer.stop()
            self.time_seconds = self.entry['time']
            self.timer.start(500)
            self.update_timer_display()
            self.playlist_position += 1
            self.entry['amount of items'] -= 1
            self.display_image()

    def display_image(self):
        #last image
        if self.playlist_position > len(self.playlist):
            self.timer.stop()
            self.timer_display.setText(f'Last image!')

        else:
            if self.entry['amount of items'] == -1 or os.path.basename(self.playlist[self.playlist_position]) == 'break.png':
                self.entry['amount of items'] = 0
                self.setWindowTitle('Break')
                self.session_info.setText('Break')
                self.image = QtGui.QPixmap(self.playlist[self.playlist_position])
                self.image_display.setPixmap(self.image.scaled(self.size(),aspectRatioMode=1))
                return
            self.setWindowTitle(os.path.basename(self.playlist[self.playlist_position]))
            self.image = QtGui.QPixmap(self.playlist[self.playlist_position])
            self.image_display.setPixmap(self.image.scaled(self.size(),aspectRatioMode=1))
            self.session_info.setText(f'Entry: {self.entry["current"]+1}/{self.entry["total"]} Image: {int(self.schedule[self.entry["current"]][1])-self.entry["amount of items"]}/{int(self.schedule[self.entry["current"]][1])}')

    def previous_playlist_position(self):
        #first image
        if self.playlist_position == 0:
            self.time_seconds = self.entry['time']
            self.update_timer_display()
            self.timer.stop()
            self.timer_display.setText('First image! Restarting timer...')
            QTest.qWait(1000)
            self.timer.start(500)
            self.load_entry()
            return

        self.playlist_position -= 1
        # end of entries
        if self.entry['current'] >= self.entry['total']:
            self.playlist_position -= 1
            self.entry['current'] = [*self.schedule][-1]
            self.timer.stop()
            self.entry['time'] = int(self.schedule[self.entry['current']][2])
            self.time_seconds = int(self.schedule[self.entry['current']][2])
            self.timer.start(500)
            self.entry['amount of items'] = 1
            self.display_image()
            return
        # at the beginning of a new entry
        if self.entry['amount of items']+1 == int(self.schedule[self.entry['current']][1]) or self.session_info.text() == 'Break':
            self.entry['current'] -= 1
            self.timer.stop()
            self.entry['time'] = int(self.schedule[self.entry['current']][2])
            self.time_seconds = self.entry['time']
            self.timer.start(500)
            self.entry['amount of items'] = 0
            self.display_image()
            return
        self.entry['amount of items'] += 1
        self.time_seconds = self.entry['time']
        self.update_timer_display()
        self.display_image()
    #endregion

    #region Timer functions
    def format_seconds(self, sec):
        min = int(sec/60)
        sec = int(self.time_seconds-(min*60))
        return f'{min}:{sec}'

    def countdown(self):
        self.update_timer_display()
        if self.time_seconds == 0:
            QTest.qWait(500)
            self.load_next_image()
            return
        self.time_seconds -= 0.5

    def update_timer_display(self):
        hr = int(self.time_seconds/3600)
        self.hr_list = list(str(hr))
        if len(self.hr_list) == 1 or self.hr_list[0] == "0":
            self.hr_list.insert(0,'0')

        min = int((self.time_seconds/3600 - hr) * 60)
        self.min_list = list(str(min))
        if len(self.min_list) == 1 or self.min_list[0] == "0":
            self.min_list.insert(0,'0')

        self.sec = list(str(int((((self.time_seconds/3600 - hr) * 60) - min) * 60)))
        if len(self.sec) == 1 or self.sec[0] == "0":
            self.sec.insert(0,'0')

        return self.timer_display.setText(f'{self.hr_list[0]}{self.hr_list[1]}:{self.min_list[0]}{self.min_list[1]}:{self.sec[0]}{self.sec[1]}')

    def pause(self):
        if self.timer.isActive():
            self.timer.stop()
            self.timer_display.setText(f'Paused {self.hr_list[0]}{self.hr_list[1]}:{self.min_list[0]}{self.min_list[1]}:{self.sec[0]}{self.sec[1]}')
            QTest.qWait(20)
        else:
            self.timer_display.setText(f'{self.hr_list[0]}{self.hr_list[1]}:{self.min_list[0]}{self.min_list[1]}:{self.sec[0]}{self.sec[1]}')
            self.timer.start(500)

    def add_30_seconds(self):
        self.time_seconds += 30
        self.update_timer_display()

    def add_60_seconds(self):
        self.time_seconds += 60
        self.update_timer_display()

    def restart_timer(self):
        self.time_seconds = int(self.schedule[self.entry['current']][2])
    #endregion


#Subclass to enable multifolder selection.
class FileDialog(QFileDialog):
    def __init__(self, *args, **kwargs):
        super(FileDialog,self).__init__(*args, **kwargs)
        self.setOption(QFileDialog.DontUseNativeDialog, True)
        self.setFileMode(QFileDialog.Directory)
        self.setOption(QFileDialog.ShowDirsOnly, True)
        self.findChildren(QListView)[0].setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.findChildren(QTreeView)[0].setSelectionMode(QAbstractItemView.ExtendedSelection)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    view = MainApp()
    view.show()
    sys.exit(app.exec())
