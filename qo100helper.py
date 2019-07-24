#!/usr/bin/python
# A Hamlib QO-100 helper mess -GI7UGV

from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from socket import *

import time
import traceback, sys, re
import pulsectl
import signal, os

signal.signal(signal.SIGINT, signal.SIG_DFL)

class WorkerSignals(QObject):
    '''
    Defines the signals available from a running worker thread.

    Supported signals are:

    finished
        No data

    error
        `tuple` (exctype, value, traceback.format_exc() )

    result
        `object` data returned from processing, anything

    progress
        `int` indicating % progress

    '''
    finished = pyqtSignal()
    error = pyqtSignal(tuple)
    result = pyqtSignal(object)
    progress = pyqtSignal(int)

class Worker(QRunnable):
    '''
    Worker thread

    Inherits from QRunnable to handler worker thread setup, signals and wrap-up.

    :param callback: The function callback to run on this worker thread. Supplied args and 
                     kwargs will be passed through to the runner.
    :type callback: function
    :param args: Arguments to pass to the callback function
    :param kwargs: Keywords to pass to the callback function

    '''

    def __init__(self, fn, *args, **kwargs):
        super(Worker, self).__init__()

        # Store constructor arguments (re-used for processing)
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    @pyqtSlot()
    def run(self):
        '''
        Initialise the runner function with passed args, kwargs.
        '''

        # Retrieve args/kwargs here; and fire processing using them
        try:
            result = self.fn(*self.args, **self.kwargs)
        except:
            traceback.print_exc()
            exctype, value = sys.exc_info()[:2]
            self.signals.error.emit((exctype, value, traceback.format_exc()))
        else:
            self.signals.result.emit(result)  # Return the result of the processing
        finally:
            self.signals.finished.emit()  # Done

class Ui_MainWindow(object):

    txrxOffset = 10057500000 # Difference between rx & tx 
    rxHost = "localhost" # expecting rx to be 10498
    rxPort = 7356
    txHost = "localhost" # expecting 432.
    txPort = 4568
    soundcardName = 'HyperX Virtual Surround Sound Analogue Stereo' # Get sound card name from list with output from below script

    #pulseDev = 1 	# Audio sink in pulse to mute, list devs with: 
			# import pulsectl 
			# pulse = pulsectl.Pulse('my-client-name') 
			# for x in pulse.sink_list() :
			#  print x 
    pulse = pulsectl.Pulse('my-client-name')
    pulseDev = 0
    rxFreq = 0
    txFreq = 0
    syncRxReq = 0
    syncRxFreq = 0
    syncTxReq = 0
    syncTxFreq = 0
    offsetHz = 0
    pttSet = 0 # 0 = no change, 1 = request ptt on, 2 = request ptt off

    for x in pulse.sink_list() :
        if re.search(soundcardName, str(x)) :
	    break
        pulseDev = pulseDev+1;

    def setupUi(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(759, 284)
        MainWindow.setFixedSize(MainWindow.size())
        self.centralWidget = QWidget(MainWindow)
        self.centralWidget.setObjectName("centralWidget")
        self.offsetLbl1 = QLabel(self.centralWidget)
        self.offsetLbl1.setGeometry(QRect(30, 170, 101, 31))
        font = QFont()
        font.setPointSize(17)
        self.offsetLbl1.setFont(font)
        self.offsetLbl1.setObjectName("offsetLbl1")
        self.txLabel = QLabel(self.centralWidget)
        self.txLabel.setGeometry(QRect(480, 0, 231, 31))
        font = QFont()
        font.setPointSize(17)
        self.txLabel.setFont(font)
        self.txLabel.setObjectName("txLabel")
        self.rxLabel = QLabel(self.centralWidget)
        self.rxLabel.setGeometry(QRect(60, 0, 231, 31))
        font = QFont()
        font.setPointSize(17)
        self.rxLabel.setFont(font)
        self.rxLabel.setObjectName("rxLabel")
        self.offsetLbl2 = QLabel(self.centralWidget)
        self.offsetLbl2.setGeometry(QRect(140, 170, 51, 31))
        font = QFont()
        font.setPointSize(17)
        self.offsetLbl2.setFont(font)
        self.offsetLbl2.setLayoutDirection(Qt.LeftToRight)
        self.offsetLbl2.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)
        self.offsetLbl2.setObjectName("offsetLbl2")
        self.syncRxButton = QPushButton(self.centralWidget)
        self.syncRxButton.setGeometry(QRect(340, 120, 85, 27))
        self.syncRxButton.setObjectName("syncRxButton")
        self.syncRxButton.clicked.connect(self.syncRx) # Added
        self.muteButton = QPushButton(self.centralWidget)
        self.muteButton.setGeometry(QRect(330, 170, 101, 71))
        font = QFont()
        font.setPointSize(13)
        self.muteButton.setFont(font)
        self.muteButton.setCheckable(True)
        self.muteButton.setObjectName("muteButton")
        self.muteButton.clicked.connect(self.setMute) # Added
        self.offsetSlider = QSlider(self.centralWidget)
        self.offsetSlider.setGeometry(QRect(10, 210, 311, 18))
        self.offsetSlider.setMinimum(-500)
        self.offsetSlider.setMaximum(500)
        self.offsetSlider.setSingleStep(10)
        self.offsetSlider.setOrientation(Qt.Horizontal)
        self.offsetSlider.setTickPosition(QSlider.TicksBelow)
        self.offsetSlider.setTickInterval(100)
        self.offsetSlider.setObjectName("offsetSlider")
        self.offsetSlider.valueChanged.connect(self.offsetChange) # Added
        self.lcdTx = QLCDNumber(self.centralWidget)
        self.lcdTx.setGeometry(QRect(440, 40, 311, 121))
        self.lcdTx.setDigitCount(8)
        self.lcdTx.setObjectName("lcdTx")
        self.lcdRx = QLCDNumber(self.centralWidget)
        self.lcdRx.setGeometry(QRect(10, 40, 311, 121))
        self.lcdRx.setDigitCount(8)
        self.lcdRx.setObjectName("lcdRx")
        self.syncTxButton = QPushButton(self.centralWidget)
        self.syncTxButton.setGeometry(QRect(340, 40, 85, 27))
        self.syncTxButton.setObjectName("syncTxButton")
        self.syncTxButton.clicked.connect(self.syncTx) # Added
        self.linkButton = QPushButton(self.centralWidget)
        self.linkButton.setGeometry(QRect(340, 80, 85, 27))
        self.linkButton.setCheckable(True) # Added
        self.linkButton.setObjectName("linkButton")
        self.linkButton.clicked.connect(self.linkTx) # Added
        self.pttButton = QPushButton(self.centralWidget)
        self.pttButton.setGeometry(QRect(440, 170, 301, 71))
        font = QFont()
        font.setPointSize(27)
        self.pttButton.setFont(font)
        self.pttButton.setCheckable(True)
        self.pttButton.setObjectName("pttButton")
        self.pttButton.clicked.connect(self.setPtt) # Added

        self.offsetLbl3 = QLabel(self.centralWidget)
        self.offsetLbl3.setGeometry(QRect(200, 170, 71, 31))
        font = QFont()
        font.setPointSize(17)
        self.offsetLbl3.setFont(font)
        self.offsetLbl3.setObjectName("offsetLbl3")
        MainWindow.setCentralWidget(self.centralWidget)
        self.mainToolBar = QToolBar(MainWindow)
        self.mainToolBar.setObjectName("mainToolBar")
        MainWindow.addToolBar(Qt.TopToolBarArea, self.mainToolBar)
        self.statusBar = QStatusBar(MainWindow)
        self.statusBar.setObjectName("statusBar")
        MainWindow.setStatusBar(self.statusBar)

        self.retranslateUi(MainWindow)
        QMetaObject.connectSlotsByName(MainWindow)

        self.threadpool = QThreadPool()

        rxWorker = Worker(self.connRx)
        self.threadpool.start(rxWorker)

        txWorker = Worker(self.connTx)
        self.threadpool.start(txWorker)

    def retranslateUi(self, MainWindow):
        _translate = QCoreApplication.translate
        MainWindow.setWindowTitle(_translate("MainWindow", "QO-100 Hamlib Helper"))
        self.offsetLbl1.setText(_translate("MainWindow", "RX Offset"))
        self.txLabel.setText(_translate("MainWindow", "  Transmit 2400."))
        self.rxLabel.setText(_translate("MainWindow", " Receive 10498."))
        self.offsetLbl2.setText(_translate("MainWindow", "0"))
        self.syncRxButton.setText(_translate("MainWindow", "<< SYNC  "))
        self.muteButton.setText(_translate("MainWindow", "Mute On TX"))
        self.syncTxButton.setText(_translate("MainWindow", "  SYNC >>"))
        self.linkButton.setText(_translate("MainWindow", "<< LINK >>"))
        self.pttButton.setText(_translate("MainWindow", "PTT"))
        self.offsetLbl3.setText(_translate("MainWindow", "Hz"))

    def setMute(self): # Added
        if self.pttButton.isChecked():
            if self.muteButton.isChecked():
                self.pulse.mute(self.pulse.sink_list()[self.pulseDev], True)  
            else:
                self.pulse.mute(self.pulse.sink_list()[self.pulseDev], False)

    def setPtt(self): # Added, need to allow easier configuration and setting by name
        if self.pttButton.isChecked():
            self.pttButton.setStyleSheet("background-color: red; border-radius: 1px;")
            if (self.muteButton.isChecked()):
                self.pulse.mute(self.pulse.sink_list()[self.pulseDev], True)
            self.pttSet = 1 # request ptt on
        else:
            self.pttButton.setStyleSheet("background-color: light grey")
            if (self.muteButton.isChecked()):
                self.pulse.mute(self.pulse.sink_list()[self.pulseDev], False)            
            self.pttSet = 2 # request ptt off, 0 = no change
        #print ("Mute: %d" % self.isMuted)

    def offsetChange(self):
        self.offsetHz = int(round(self.offsetSlider.value(), -1))
        self.offsetLbl2.setText(str(self.offsetHz))

    def syncTx(self):
        #print ("sync Tx Txold: %d Rxnow: %d" % (int(self.txFreq), int(self.rxFreq)))
        shortF=self.txFreq[3:] # strip leading three, 432 here
        self.lcdTx.display(shortF[:3] + "." + shortF[3:]) # display xxx.xxx 
        self.txFreq = str((int(self.rxFreq) - self.txrxOffset))
        self.syncTxFreq = str((int(self.rxFreq) - self.txrxOffset))
        self.syncTxReq = 1

    def syncRx(self):
        shortF=self.rxFreq[5:] # strip leading three, 10368 here
        self.lcdRx.display(shortF[:3] + "." + shortF[3:]) # display xxx.xxx
        self.rxFreq = str((int(self.txFreq) + self.txrxOffset))
        self.syncRxFreq = str((int(self.txFreq) + self.txrxOffset))
        self.syncRxReq = 1
                
    def linkTx(self):
        if self.linkButton.isChecked():
            #print "linking"
            self.syncTxButton.setEnabled(False)
            self.syncRxButton.setEnabled(False)
            self.linkButton.setStyleSheet("background-color: red; border-radius: 1px;")
        else:
            #print "unlinking"
            self.syncTxButton.setEnabled(True)
            self.syncRxButton.setEnabled(True)
            self.linkButton.setStyleSheet("background-color: light grey;")

    def connRx(self):
        try:
            connSock = socket(AF_INET, SOCK_STREAM)
            connSock.connect((self.rxHost, self.rxPort))
            while 1:
                time.sleep(0.1)
                if (self.syncRxReq):
                    #connSock.send('F %s' % self.rxFreq)
                    connSock.send('F %s' % self.syncRxFreq)
                    self.syncRxReq = 0
                else:
                    connSock.send('f\n')
                output = connSock.recv(100)
                if not ( re.match(r'^[0-9]+$', str(output)) ): # change to not that or RPRT0
                    #print ("Unexpected non frequency response from hamlib: " + str(output)) # not strictly true F does this
                    continue
                self.rxFreq = str(output)
                #print ('RX Frequency offset: %d read: %d real: %d' % (self.offsetHz, int(self.rxFreq), (int(self.rxFreq) + self.offsetHz)))
                shortF=self.rxFreq[5:] # strip leading three, 10368 here
                self.lcdRx.display(shortF[:3] + "." + shortF[3:]) # display xxx.xxx
                #print shortF[:3] + "." + shortF[3:]
                #self.lcdRx.display(self.rxFreq)
            ConnSock.close()
        except:
            print ('Could not connect to Rx.')
            os._exit(1)

    def connTx(self): # ****** make sure turns PTT off when program exits? ********
        try:
            connSock = socket(AF_INET, SOCK_STREAM)
            connSock.connect((self.txHost, self.txPort))
            while 1:
                time.sleep(0.1)
                if (self.syncTxReq):
                    #print ("TX Sync requested %s" % self.syncTxFreq)
                    connSock.send('F %s\n' % self.syncTxFreq)
                    self.syncTxReq = 0
                elif (self.pttSet == 1):
                    #print ("PTT ON REQUESTED")
                    connSock.send("T 1\n")
                    self.pttSet = 0
                elif (self.pttSet == 2):
                    #print ("PTT OFF REQUESTED")
                    connSock.send('T 0\n') 
                    self.pttSet = 0
                elif (self.linkButton.isChecked()): 
                    newTx = int(self.rxFreq) - self.txrxOffset
                    if (int(self.txFreq) != newTx):
                        #print ("Not equal, sync %d to %d" %(int(self.txFreq), newTx))
                        connSock.send('F %s\n' % newTx)
                        self.txFreq = str(newTx)
                    else:
                        connSock.send('f\n')
                else:
                    connSock.send('f\n')
                output = connSock.recv(100)
                
                if not ( re.match(r'^[0-9]+$', str(output)) ):
                    #print ("Unexpected non frequency response from hamlib: " + str(output))
                    continue
                
                self.txFreq = str(output)
                #print ('TX Frequency offset: %d read: %d real: %d' % (self.offsetHz, int(self.txFreq), (int(self.txFreq) + self.offsetHz)))
                shortF=self.txFreq[3:] # strip leading three, 432 here
                self.lcdTx.display(shortF[:3] + "." + shortF[3:]) # display xxx.xxx
                #print shortF[:3] + "." + shortF[3:]
                #self.lcdTx.display(self.txFreq)  
            ConnSock.close()
        except:
            print ('Could not connect to Tx.')
            os._exit(1)
            
if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)
    MainWindow = QMainWindow()
    ui = Ui_MainWindow()
    ui.setupUi(MainWindow)
    MainWindow.show()
    sys.exit(app.exec_())
