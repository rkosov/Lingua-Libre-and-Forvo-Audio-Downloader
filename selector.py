from aqt.qt import *

from PyQt5 import QtCore, QtGui, QtWidgets


class Ui_Dialog(object):
    def setupUi(self, Dialog):
        Dialog.setObjectName("Dialog")
        Dialog.resize(350, 250)
        self.verticalLayout = QtWidgets.QVBoxLayout(Dialog)
        self.verticalLayout.setObjectName("verticalLayout")
        self.label = QtWidgets.QLabel(Dialog)
        font = QtGui.QFont()
        font.setBold(True)
        font.setWeight(75)
        self.label.setFont(font)
        self.label.setObjectName("label")
        self.verticalLayout.addWidget(self.label)
        self.selectionList = QtWidgets.QListWidget(Dialog)
        self.selectionList.setResizeMode(QtWidgets.QListView.Fixed)
        self.selectionList.setObjectName("selectionList")
        self.verticalLayout.addWidget(self.selectionList)
        self.buttonBox = QtWidgets.QDialogButtonBox(Dialog)
        self.buttonBox.setOrientation(QtCore.Qt.Horizontal)
        self.buttonBox.setStandardButtons(QtWidgets.QDialogButtonBox.Cancel|QtWidgets.QDialogButtonBox.Ok)
        self.buttonBox.setCenterButtons(True)
        self.buttonBox.setObjectName("buttonBox")
        self.verticalLayout.addWidget(self.buttonBox)

        Dialog.setWindowTitle("Configuration Selection")
        self.label.setText("Please select a configuration:")
        self.buttonBox.accepted.connect(Dialog.accept)
        self.buttonBox.rejected.connect(Dialog.reject)
        QtCore.QMetaObject.connectSlotsByName(Dialog)

    def retranslateUi(self, Dialog):
        _translate = QtCore.QCoreApplication.translate
        Dialog.setWindowTitle(_("Configuration Selection"))
        self.label.setText(_("Please select a configuration:"))


class SelectDialog(QDialog):
    """
    This dialog is used to select an item from a list
    """

    def __init__(self, mw, items):
        self.mw = mw
        self.items = items
        self.selected = 0
        super().__init__(self.mw)
        self.form = Ui_Dialog()
        self.form.setupUi(self)
        self.form.selectionList.currentRowChanged.connect(self._onItemSelected)
        self._setupList()

    def wait_for_result(self):
        """
        Shows the dialog and blocks
        """
        return self.exec_()

    def _setupList(self):
        """
        Fills the list with items
        """
        lst = self.form.selectionList
        for item in self.items:
            QListWidgetItem(item, lst)
        lst.reset()

    def _onItemSelected(self, row_int: int) -> None:
        """
        Remember the selection
        """
        self.selected = row_int
