from aqt.qt import (
    QDialog,
    QListWidgetItem,
    QShortcut,
)
from aqt.sound import play
from PyQt5 import QtCore, QtGui, QtWidgets
from typing import IO, Any, Callable, Dict, Iterable, List, Optional, Tuple, Union
#from .forms import soundselector


class Ui_Dialog(object):
    def setupUi(self, Dialog):
        Dialog.setObjectName("Dialog")
        Dialog.resize(200, 180)
        self.verticalLayout = QtWidgets.QVBoxLayout(Dialog)
        self.verticalLayout.setObjectName("verticalLayout")
        self.label = QtWidgets.QLabel(Dialog)
        font = QtGui.QFont()
        font.setBold(False)
        font.setItalic(True)
        font.setWeight(50)
        self.label.setFont(font)
        self.label.setWordWrap(True)
        self.label.setObjectName("label")
        self.verticalLayout.addWidget(self.label)
        self.soundList = QtWidgets.QListWidget(Dialog)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.soundList.sizePolicy().hasHeightForWidth())
        self.soundList.setSizePolicy(sizePolicy)
        self.soundList.setResizeMode(QtWidgets.QListView.Fixed)
        self.soundList.setObjectName("soundList")
        self.verticalLayout.addWidget(self.soundList)
        self.buttonBox = QtWidgets.QDialogButtonBox(Dialog)
        self.buttonBox.setOrientation(QtCore.Qt.Horizontal)
        self.buttonBox.setStandardButtons(QtWidgets.QDialogButtonBox.Cancel|QtWidgets.QDialogButtonBox.Save)
        self.buttonBox.setCenterButtons(True)
        self.buttonBox.setObjectName("buttonBox")
        self.verticalLayout.addWidget(self.buttonBox)

        Dialog.setWindowTitle("Pronunciation selector")
        self.label.setText("Select, double-click or press a number(0-9) to play the audio.")
        self.buttonBox.accepted.connect(Dialog.accept)
        self.buttonBox.rejected.connect(Dialog.reject)
        QtCore.QMetaObject.connectSlotsByName(Dialog)

    def retranslateUi(self, Dialog):
        _translate = QtCore.QCoreApplication.translate
        Dialog.setWindowTitle("Pronunciation selector")
        self.label.setText("Select, double-click or press a number(0-9) to play the audio.")

class SoundDialog(QDialog):
    """
    This dialog is used to select the correct sound
    """

    def __init__(self, mw, sounds, users):
        self.mw = mw
        self.sounds = sounds
        self.users = users
        self.selected = 0
        super().__init__(self.mw)
        self.form = Ui_Dialog()
        self.form.setupUi(self)
        self.form.soundList.currentRowChanged.connect(self._onSoundItemSelected)
        self.form.soundList.itemDoubleClicked.connect(self._onSoundDoubleClicked)
        # shortcuts
        for key, key_func in [
            ("0", lambda: self.onKey(0)),
            ("1", lambda: self.onKey(1)),
            ("2", lambda: self.onKey(2)),
            ("3", lambda: self.onKey(3)),
            ("4", lambda: self.onKey(4)),
            ("5", lambda: self.onKey(5)),
            ("6", lambda: self.onKey(6)),
            ("7", lambda: self.onKey(7)),
            ("8", lambda: self.onKey(8)),
            ("9", lambda: self.onKey(9)),
        ]:
            QShortcut(key, self, activated=key_func)
        self._setupList()


    def onKey(self, idx):
        """
        Handles the shortcuts
        """
        cur_row = self.form.soundList.currentRow()
        next_row = min(idx, len(self.sounds) - 1)
        self.form.soundList.setCurrentRow(next_row)

        # if the selection didn't change, play the sound again
        if next_row == cur_row:
            snd = self.sounds[next_row]
            play(snd)


    def wait_for_result(self):
        """
        Shows the dialog and blocks
        """
        return self.exec_()


    def _onSoundDoubleClicked(self):
        """
        Plays the sound on double click
        """
        row_int = self.form.soundList.selectedIndexes()[0].row()
        snd = self.sounds[row_int]
        play(snd)


    def _setupList(self):
        """
        Fills the list with sounds
        """
        lst = self.form.soundList
        for idx, (_sound, user) in enumerate(zip(self.sounds, self.users)):
            QListWidgetItem(f"{idx}. {user}", lst)
        lst.reset()


    def _onSoundItemSelected(self, row_int: int) -> None:
        """
        Play sound when selection changed
        """
        try:
            self.selected = row_int
            snd = self.sounds[row_int]
            play(snd)
        except IndexError:
            return
        return
