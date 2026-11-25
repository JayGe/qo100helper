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
import subprocess, array

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

    #txrxOffset = 10057500000 # Difference between rx & tx 
    #txrxOffsetFixed = 10057500300 # Difference between rx & tx 
    txrxOffsetFixed = 10057499900 # Difference between rx & tx 

    txrxOffset = txrxOffsetFixed
    #txrxOffset = 10057500080 # Difference between rx & tx 
    #txrxOffset = 10057500030 # Difference between rx & tx 
    #txrxOffset = 10057500050 # Difference between rx & tx 
    #txrxOffset = 10057498000 # Difference between rx & tx 
    #txrxOffset = 10057499950 # Difference between rx & tx 
    #txrxOffset = 10057499930 # Difference between rx & tx 
    #txrxOffset = 10057499900 # Difference between rx & tx 
    #txrxOffset = 10057499990 # Difference between rx & tx 
    #txrxOffset = 10057500950 # Difference between rx & tx  # RTL +650 Hz
    #txrxOffset = 10057500250 # Difference between rx & tx  # RTL +650 Hz
    #txrxOffset = 10057500700 # Difference between rx & tx  # RTL +650 Hz
    rxHost = "localhost" # expecting rx to be 10498
    rxPort = 7357 # gqrx
    txHost = "localhost" # expecting 432.
    txPort = 4597 # 9700
    #txPort = 4568 # 9700
    soundcardName = 'Built-in Audio Analogue Stereo'  # audio sink muted on TX (gqrx RX audio plays here)
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

    # ---- Receive-only drift calibration against the QO-100 NB CW beacon -------
    # CAL measures where the LNB / IF / SDR chain actually puts the narrowband CW
    # beacon NOW, and corrects only the CHANGE since the baseline below was taken.
    # The absolute RX<->TX relationship therefore stays whatever you hand-tuned
    # into txrxOffsetFixed - CAL only removes drift between sessions, which is the
    # real failure mode. Nothing here ever touches PTT, the transmitter or the amp.
    beaconHz = 10489500664     # BASELINE: measured apparent position of the NB CW
                               # beacon on 2026-11-25, with the hand-tuned alignment
                               # already in use. Agreed to 0.42 Hz from three dial
                               # positions 1.5 kHz apart; CW ident ~50% duty.
                               # This is deliberately a measured baseline and NOT a
                               # claim about the beacon's published frequency, so no
                               # unverified LO or band-plan number can pull the TX
                               # off. Two ways to use it:
                               #   - delete cal.conf -> next CAL re-baselines here
                               #     (do that after you re-align by hand)
                               #   - if you confirm the beacon's true frequency from
                               #     AMSAT-DL, put it here and CAL becomes absolute
    calPlaceHz = 1500          # park the beacon here in the USB audio passband.
                               # USB audio = RF - dial, so the dial goes BELOW it
    calSeconds = 8.0           # capture length; the beacon idents, so give it time
    calMinSep = 40.0           # a rival this close is keying sideband, not a rival
    calRivalRatio = 0.4        # a rival this strong means "do not guess"
    calKeyFrame = 0.2          # detection frame: >= one Morse element so a keyed
    calKeyHop = 0.05           # carrier appears undiluted in at least one frame
    calRefineHz = 25.0         # +/- Hz around the detected carrier for fine tuning
    calSettle = 0.8            # let gqrx re-lock before capturing / restoring
    calFs = 48000              # capture rate
    calDecim = 6               # 48k -> 8k, keeps the 1.5k tone well inside Nyquist
    calSearch = 250            # +/- Hz searched around calPlaceHz. Covers the
                               # operator's stated drift ("a couple of hundred Hz")
                               # and is deliberately SMALLER than the 390 Hz
                               # spacing to a persistent carrier measured below the
                               # beacon: at 400 that rival sat inside the band and
                               # CAL correctly refused every run as ambiguous. If
                               # CAL ever reports two carriers, do not widen this
                               # past the rival - re-baseline on a cleaner carrier.
                               # Tone stays in gqrx's 100-3500 Hz passband.
    calMinSnr = 15.0           # peak / band-noise-median. Measured with margin: the
                               # real beacon gives 94-220x even while keyed, whereas
                               # a false lock on a stray digimode carrier measured
                               # 4.7x. 4.0 let that false lock through - do not go
                               # back there.
    calMaxDelta = 1000         # refuse a correction larger than this: past ordinary
                               # drift, something else changed (gqrx ppm, LNB, or a
                               # fresh hand alignment) and needs re-baselining.
    # Reference only, not used to compute anything: 2.4GHz up-converter LO confirmed
    # by the operator as exactly 1968.000 MHz, NB transponder shift 8089.5 MHz.
    autoOffsetHz = 0           # correction applied by the CAL button (signed Hz)
    txMinHz = 432050000        # IC-9700 IF limits for the NB uplink (432 MHz IF
    txMaxHz = 432300000        # + 1968 MHz up-converter = 2400.050-2400.300 MHz)
    txRefuseShown = -1         # last off-band target already reported, to not spam
    sockTimeout = 5.0          # seconds before a silent gqrx/rigctld link counts
                               # as dead. Without it recv() blocks forever: the
                               # thread neither raises nor updates, so the RX LCD
                               # and the LINK chase keep working from a stale
                               # frequency and nothing anywhere looks wrong.
    rxLinkDown = False         # only say "restored" after we said "lost", so the
    txLinkDown = False         # status bar never claims a recovery that never
    pttLinkDown = False        # followed a failure
    calLastDrift = 0
    calBusy = False
    calTuneReq = 0
    calTuneFreq = "0"
    calSavedRx = "0"
    calSavedTx = "0"
    calText = "CAL RX (beacon)"
    calConfPath = os.path.expanduser("~/.config/qo100helper/cal.conf")

    for x in pulse.sink_list() :
        if re.search(soundcardName, getattr(x, 'description', '')) :
            break
        pulseDev = pulseDev+1;

    def setupUi(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(759, 320)
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

        self.calButton = QPushButton(self.centralWidget)
        self.calButton.setGeometry(QRect(300, 4, 150, 26))
        font = QFont()
        font.setPointSize(11)
        self.calButton.setFont(font)
        self.calButton.setObjectName("calButton")
        self.calButton.clicked.connect(self.startCalibrate) # Added

        self.autoLbl = QLabel(self.centralWidget)
        self.autoLbl.setGeometry(QRect(160, 252, 200, 24))
        font = QFont()
        font.setPointSize(11)
        self.autoLbl.setFont(font)
        self.autoLbl.setLayoutDirection(Qt.LeftToRight)
        self.autoLbl.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)
        self.autoLbl.setObjectName("autoLbl")

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

        # "Amp On TX" was a toolbar action. As a widget it can take the space
        # under the offset slider, which frees the top of the window for the CAL
        # button - the bottom row was being clipped at this window size.
        self.ampAction = QCheckBox("Amp On TX", self.centralWidget)
        self.ampAction.setGeometry(QRect(10, 250, 140, 26))
        self.ampAction.setObjectName("ampAction")
        MainWindow.removeToolBar(self.mainToolBar)
        self.statusBar = QStatusBar(MainWindow)
        self.statusBar.setObjectName("statusBar")
        MainWindow.setStatusBar(self.statusBar)

        self.retranslateUi(MainWindow)
        QMetaObject.connectSlotsByName(MainWindow)

        self.threadpool = QThreadPool()

        self.loadCalConf()      # pick up the last CAL before the rigs start talking
        self.txrxOffset = self.desiredOffset()
        self.updateAutoLabel()

        rxWorker = Worker(self.connRx)
        self.threadpool.start(rxWorker)

        txWorker = Worker(self.connTx)
        self.threadpool.start(txWorker)

        pttWorker = Worker(self.connPtt)
        self.threadpool.start(pttWorker)

    def retranslateUi(self, MainWindow):
        _translate = QCoreApplication.translate
        MainWindow.setWindowTitle(_translate("MainWindow", "QO-100 Hamlib Helper"))
        self.offsetLbl1.setText(_translate("MainWindow", "TX Offset"))
        self.txLabel.setText(_translate("MainWindow", "  Transmit 2400."))
        self.rxLabel.setText(_translate("MainWindow", " Receive 10498."))
        self.offsetLbl2.setText(_translate("MainWindow", "0"))
        self.syncRxButton.setText(_translate("MainWindow", "<< SYNC  "))
        self.muteButton.setText(_translate("MainWindow", "Mute On TX"))
        self.syncTxButton.setText(_translate("MainWindow", "  SYNC >>"))
        self.linkButton.setText(_translate("MainWindow", "<< LINK >>"))
        self.pttButton.setText(_translate("MainWindow", "PTT"))
        self.offsetLbl3.setText(_translate("MainWindow", "Hz"))
        self.calButton.setText(_translate("MainWindow", self.calText))
        self.autoLbl.setText("auto 0 Hz")

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

    # ---------- receive-only RX calibration ----------
    # The slider can only express 10 Hz steps (round(x, -1)), so the calibration
    # result is kept separately as a precise integer trim and summed with it:
    #     txrxOffset = fixed + auto - manual

    def desiredOffset(self):
        return int(self.txrxOffsetFixed) + int(self.autoOffsetHz) - int(self.offsetHz)

    def updateAutoLabel(self):
        try:
            self.autoLbl.setText("auto %+d Hz" % self.autoOffsetHz)
        except:
            pass

    def loadCalConf(self):
        try:
            f = open(self.calConfPath)
            txt = f.read()
            f.close()
            m = re.search(r'autoOffsetHz\s*=\s*(-?\d+)', txt)
            if m:
                self.autoOffsetHz = int(m.group(1))
                m = re.search(r'driftHz\s*=\s*(-?\d+)', txt)
                if m:
                    self.calLastDrift = int(m.group(1))
                print ("Loaded calibration: auto %+d Hz from %s" % (self.autoOffsetHz, self.calConfPath))
        except:
            pass # no calibration saved yet, that's fine

    def saveCalConf(self):
        try:
            d = os.path.dirname(self.calConfPath)
            if not os.path.isdir(d):
                os.makedirs(d)
            f = open(self.calConfPath, "w")
            f.write("# Written by the CAL button in qo100helper.py\n")
            f.write("# Drift correction for LNB / IF / SDR receive-chain wander,\n")
            f.write("# measured against the QO-100 narrowband CW beacon baseline.\n")
            f.write("# Receive-only: nothing in this file causes a transmission.\n")
            f.write("# Delete this file to re-baseline after a hand alignment.\n")
            f.write("beaconBaselineHz = %d\n" % self.beaconHz)
            f.write("driftHz = %d\n" % self.calLastDrift)
            f.write("autoOffsetHz = %d\n" % self.autoOffsetHz)
            f.write("txrxOffsetNominal = %d\n" % self.txrxOffsetFixed)
            f.write("time = %s\n" % time.strftime("%Y-%m-%d %H:%M:%S"))
            f.close()
        except Exception as msg:
            print ("Could not write %s: %s" % (self.calConfPath, msg))

    def requestRxTune(self, freq):
        # Handed to connRx, which owns the only socket to gqrx - no second client,
        # so we never fight it or WSJT-X for the receiver.
        self.calTuneFreq = str(freq)
        self.calTuneReq = 1

    def captureAudio(self, seconds):
        sink = None
        for s in self.pulse.sink_list():
            if re.search(self.soundcardName, getattr(s, 'description', '') or ''):
                sink = s
                break
        if sink is None:
            raise RuntimeError("audio sink '%s' not found" % self.soundcardName)
        if str(getattr(sink, 'mute', 0)) in ('True', '1'):
            raise RuntimeError("audio sink is muted - clear Mute On TX before calibrating")
        cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error",
               "-f", "pulse", "-i", str(sink.name) + ".monitor",
               "-t", "%.2f" % seconds, "-ac", "1", "-ar", str(self.calFs),
               "-f", "s16le", "-"]
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           timeout=int(seconds) + 25)
        if p.returncode != 0:
            raise RuntimeError("audio capture failed: %s" % p.stderr.decode()[-200:])
        a = array.array('h')
        a.frombytes(p.stdout)
        if len(a) < int(self.calFs * seconds * 0.5):
            raise RuntimeError("only got %d audio samples" % len(a))
        return a

    def toneEstimate(self, samples):
        # Two stages, because the NB beacon is CW-keyed and a single transform
        # cannot both find it and measure it:
        #
        # 1. DETECT on short frames (>= one Morse element), taking the per-bin
        #    MAXIMUM across them. A DFT peak scales with the carrier's duty cycle
        #    *inside the window*, so one long FFT showed the beacon at ~50% of its
        #    true level and a steady rival 397 Hz below it won the search - the
        #    real 2026-11-25 wrong answer. Short frames catch a key-on element at
        #    full amplitude, so carriers are compared on true strength.
        # 2. MEASURE with one long zero-padded FFT, but only in a narrow window
        #    around the carrier stage 1 picked, using log-parabolic interpolation.
        #    Short frames alone give only 5 Hz resolution.
        #
        # Deliberately NOT a sweep of discrete probe frequencies either: with a
        # T-second window the leakage pattern has nulls every 1/T Hz, so a probe
        # grid at a multiple of that spacing can read a tone as exactly ZERO.
        import numpy as np
        d = self.calDecim
        fs = float(self.calFs)
        x = np.asarray(samples, dtype=np.float64)
        x = x[:(len(x) // d) * d].reshape(-1, d).mean(axis=1) # box-car decimate
        fs /= d
        x = x - x.mean()
        frame = int(fs * self.calKeyFrame)
        hop = int(fs * self.calKeyHop)
        if frame < 32 or hop < 1 or len(x) < frame + hop:
            raise RuntimeError("capture too short for framing")
        nfft = 1
        while nfft < frame * 8:
            nfft *= 2
        w = np.hanning(frame)
        pool = np.zeros(nfft // 2 + 1)
        for i in range(0, len(x) - frame + 1, hop):
            pool = np.maximum(pool, np.abs(np.fft.rfft(x[i:i + frame] * w, nfft)))
        fr = np.fft.rfftfreq(nfft, 1.0 / fs)
        band = np.where((fr >= self.calPlaceHz - self.calSearch) &
                        (fr <= self.calPlaceHz + self.calSearch))[0]
        if len(band) < 8:
            raise RuntimeError("search band above Nyquist - reduce calPlaceHz/calSearch")
        k = int(band[int(np.argmax(pool[band]))])
        peak = float(pool[k])
        coarsef = float(fr[k])
        noise = float(np.median(pool[band])) + 1e-15
        snr = peak / noise
        # SNR gate first: with nothing in the band the band median IS the peak
        # area, and every peak looks like a rival. Say "not found", not "ambiguous".
        if snr < self.calMinSnr:
            return coarsef, peak, snr
        # Ambiguity guard, judged on the keying-robust pooled spectrum: a second
        # carrier of comparable strength elsewhere in the band makes picking the
        # strongest a coin toss. Refuse instead of guessing.
        rivals = [j for j in band if abs(float(fr[j]) - coarsef) > self.calMinSep
                  and float(pool[j]) > self.calRivalRatio * peak]
        if rivals:
            near = min(rivals, key=lambda j: abs(float(fr[j]) - coarsef))
            raise RuntimeError("two carriers of comparable strength in the search band (%.1f Hz and %.1f Hz) - refusing to guess" % (coarsef, float(fr[near])))
        # Stage 2: fine measurement of the already-identified carrier.
        nfft2 = 1
        while nfft2 < len(x) * 8:
            nfft2 *= 2
        sp2 = np.abs(np.fft.rfft(x * np.hanning(len(x)), nfft2))
        fr2 = np.fft.rfftfreq(nfft2, 1.0 / fs)
        win = np.where((fr2 >= coarsef - self.calRefineHz) &
                       (fr2 <= coarsef + self.calRefineHz))[0]
        if len(win) < 8:
            return coarsef, peak, snr
        k2 = int(win[int(np.argmax(sp2[win]))])
        if k2 < 1 or k2 + 1 >= len(sp2):
            return coarsef, peak, snr
        la = np.log(max(float(sp2[k2 - 1]), 1e-30))
        lb = np.log(max(float(sp2[k2]), 1e-30))
        lc = np.log(max(float(sp2[k2 + 1]), 1e-30))
        denom = la - 2.0 * lb + lc
        delta = 0.0 if denom == 0 else max(-1.0, min(1.0, 0.5 * (la - lc) / denom))
        peakf = float(fr2[k2] + delta * (fs / nfft2))
        return peakf, peak, snr

    def startCalibrate(self):
        if self.calBusy:
            self.statusBar.showMessage("Calibration already running")
            return
        if self.pttButton.isChecked():
            self.statusBar.showMessage("Release PTT before calibrating")
            return
        savedRx = str(self.rxFreq)
        if not re.match(r'^[0-9]+$', savedRx):
            self.statusBar.showMessage("Receiver not answering - cannot calibrate")
            return
        self.calBusy = True      # also suspends the LINK chase so the TX never follows the beacon
        self.calSavedRx = savedRx
        self.calSavedTx = str(self.txFreq)
        self.calButton.setEnabled(False)
        self.calButton.setText("CALibrating")
        self.statusBar.showMessage("Measuring %.3f MHz beacon..." % (self.beaconHz / 1e6))
        self.requestRxTune(self.beaconHz - self.calPlaceHz) # USB: dial below the beacon
        w = Worker(self.runCalibrate, savedRx)
        w.signals.result.connect(self.calFinished)
        w.signals.error.connect(self.calFailed)
        self.threadpool.start(w)

    def runCalibrate(self, savedRx):
        try:
            time.sleep(self.calSettle)               # gqrx re-lock
            samples = self.captureAudio(self.calSeconds)
            result = self.toneEstimate(samples)
        finally:
            self.requestRxTune(savedRx)              # always put the RX back
            self.waitRxRestored(savedRx)             # and make sure it actually got there
        return result

    def waitRxRestored(self, savedRx, limit=5.0):
        # connTx releases the LINK chase as soon as calFinished clears calBusy,
        # and the chase follows self.rxFreq. requestRxTune only *asks* connRx to
        # retune, so a fixed sleep leaves a window where the chase resumes with
        # the CAL listening frequency still in rxFreq - which parks the
        # transmitter on the beacon's uplink counterpart, 2399.999 MHz, well
        # outside the band. Wait for the receiver to read the saved frequency
        # back, so the chase can only ever resume from where the operator left it.
        t0 = time.time()
        while time.time() - t0 < limit:
            if str(self.rxFreq) == str(savedRx):
                return True
            time.sleep(0.1)
        print ("CAL WARNING: receiver did not read back %s within %.0fs" % (savedRx, limit))
        return False

    def calFinished(self, result):
        freq, mag, snr = result
        self.calBusy = False
        self.calButton.setEnabled(True)
        self.calButton.setText(self.calText)
        if snr < self.calMinSnr:
            self.statusBar.showMessage("CAL: beacon not found - best peak %.1fx noise at %.1f Hz, need %.0fx. Raise gqrx audio output / check the beacon is in view" % (snr, freq, self.calMinSnr))
            return
        drift = int(round(freq - self.calPlaceHz))
        if abs(drift) > self.calMaxDelta:
            self.statusBar.showMessage("CAL REFUSED: %.0f Hz from the baseline is beyond calMaxDelta. Something other than drift changed (gqrx ppm, LNB, or a new hand alignment) - delete cal.conf to re-baseline" % drift)
            return
        # txrxOffset must move by exactly the amount the beacon moved, same sign:
        # the baseline was taken with this offset already correct, so any further
        # apparent motion of the beacon is pure receive-chain drift.
        self.calLastDrift = drift
        self.autoOffsetHz = drift
        self.txrxOffset = self.desiredOffset()
        self.saveCalConf()
        self.updateAutoLabel()
        self.statusBar.showMessage("CAL: beacon %+d Hz from baseline (SNR %.0fx) -> offset %d (%+d Hz). Beacon now reads %+d Hz. TX follows only if LINK/sync is on" % (drift, snr, self.txrxOffset, drift, drift))

    def calFailed(self, errtuple):
        self.calBusy = False
        self.calButton.setEnabled(True)
        self.calButton.setText(self.calText)
        self.statusBar.showMessage("CAL failed: %s" % str(errtuple[1]))
        print ("".join(traceback.format_exception(*errtuple)))

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
            #print ("linking")
            self.syncTxButton.setEnabled(False)
            self.syncRxButton.setEnabled(False)
            self.linkButton.setStyleSheet("background-color: red; border-radius: 1px;")
        else:
            #print ("unlinking")
            self.syncTxButton.setEnabled(True)
            self.syncRxButton.setEnabled(True)
            self.linkButton.setStyleSheet("background-color: light grey;")

    def connRx(self):
        # Survive a dropped gqrx remote connection. gqrx serves ONE remote
        # client, so anything that briefly takes the slot - a diagnostic script,
        # a gqrx restart, a hiccup - lands in the bare except below, which used
        # to call os._exit(1). That killed the whole helper silently, stopping
        # PTT and amp supervision mid-session and leaving the transmitter
        # stranded wherever it last pointed. Retry instead.
        while 1:
            try:
                self.connRxOnce()
            except:
                print ("RX link lost: %s" % traceback.format_exc().splitlines()[-1])
                self.statusBar.showMessage("Receiver link lost - retrying every second")
                self.rxLinkDown = True
                time.sleep(1.0)

    def connRxOnce(self):
        try:
            connSock = socket(AF_INET, SOCK_STREAM)
            connSock.connect((self.rxHost, self.rxPort))
            connSock.settimeout(self.sockTimeout)
            if self.rxLinkDown:
                self.rxLinkDown = False
                self.statusBar.showMessage("Receiver link restored")
            while 1:
                time.sleep(0.1)
                if (self.calTuneReq): # CAL wants the receiver somewhere specific
                    connSock.send(('F %s\n' % self.calTuneFreq).encode())
                    self.calTuneReq = 0
                    try:
                        connSock.settimeout(1.0)
                        connSock.recv(100)
                        connSock.settimeout(self.sockTimeout)
                    except:
                        pass
                    continue
                if (self.syncRxReq):
                    #connSock.send('F %s' % self.rxFreq)
                    sendString = ('F %s' % self.syncRxFreq)
                    connSock.send(sendString.encode())
                    #connSock.send('F %s'.encode() % self.syncRxFreq)
                    self.syncRxReq = 0
                else:
                    connSock.send('f\n'.encode())
                output = connSock.recv(100).decode()
                if str(output).startswith('RPRT'): # ack of an F command, not a frequency
                    continue
                if not ( re.match(r'^[0-9]+$', str(output)) ): # change to not that or RPRT0
                    print ("Unexpected non frequency response from hamlib: " + str(output)) # not strictly true F does this
                    continue
                self.rxFreq = str(output)
                #print ('RX Frequency offset: %d read: %d real: %d' % (self.offsetHz, int(self.rxFreq), (int(self.rxFreq) + self.offsetHz)))
                #print ('TXRX Offset:%d With Adjust: %d' % (self.txrxOffset, int(self.txrxOffset - self.offsetHz)) )
                shortF=self.rxFreq[5:] # strip leading three, 10368 here
                self.lcdRx.display(shortF[:3] + "." + shortF[3:]) # display xxx.xxx
                #print shortF[:3] + "." + shortF[3:]
                #self.lcdRx.display(self.rxFreq)
            ConnSock.close()
        except:
            try:
                connSock.close()
            except:
                pass
            raise

    def connTx(self): # ****** make sure turns PTT off when program exits? ********
        # Same retry policy as connRx: losing rigctld must not end the program,
        # or the amp could stay keyed with nobody watching. Forcing txFreq to an
        # impossible value makes the chase re-send the wanted frequency as soon
        # as the link is back, rather than trusting a pre-outage reading.
        while 1:
            try:
                self.connTxOnce()
            except:
                print ("TX link lost: %s" % traceback.format_exc().splitlines()[-1])
                self.statusBar.showMessage("Transmitter link lost - retrying every second")
                self.txLinkDown = True
                self.txFreq = "0"
                time.sleep(1.0)

    def connTxOnce(self):
        try:
            connSock = socket(AF_INET, SOCK_STREAM)
            connSock.connect((self.txHost, self.txPort))
            connSock.settimeout(self.sockTimeout)
            if self.txLinkDown:
                self.txLinkDown = False
                self.statusBar.showMessage("Transmitter link restored")
            while 1:
                time.sleep(0.1)
                wantOffset = self.desiredOffset() # nominal + CAL trim - slider
                if (wantOffset != self.txrxOffset): # Adjust TX offset if changed in GUI or by CAL
                    self.txrxOffset = wantOffset
                if (self.syncTxReq):
                    #print ("TX Sync requested %s" % self.syncTxFreq)
                    sendString=('F %s\n' % self.syncTxFreq)
                    connSock.send(sendString.encode())
                    self.syncTxReq = 0
                elif (self.pttSet == 1):
                    #print ("PTT ON REQUESTED")
                    connSock.send("T 1\n".encode())
                    os.system("(/usr/bin/mosquitto_pub -h 192.168.0.201 -t '/radio/amp/set2' -m 'ON')")
                    self.pttSet = 0
                elif (self.pttSet == 2):
                    #print ("PTT OFF REQUESTED")
                    connSock.send('T 0\n'.encode())
                    os.system("(/usr/bin/mosquitto_pub -h 192.168.0.201 -t '/radio/amp/set2' -m 'OFF')")
                    self.pttSet = 0
                elif (self.linkButton.isChecked() and not self.calBusy): # CAL suspends the chase so the TX never follows the beacon
                    newTx = int(self.rxFreq) - self.txrxOffset
                    if not (self.txMinHz <= newTx <= self.txMaxHz):
                        # The NB downlink reaches below the transponder's translated
                        # passband: the CW beacons around 10489.500 MHz map to
                        # 2399.999 MHz, which is outside the uplink entirely. Parked
                        # there by hand - or by CAL - the tracker would otherwise
                        # drive the transmitter off-band and leave it there. Refuse
                        # to follow, keep the last in-band frequency, say so once.
                        if newTx != self.txRefuseShown:
                            self.txRefuseShown = newTx
                            print ("TX chase refused: %.6f MHz outside the NB uplink (RX %.6f)" % (newTx / 1e6, int(self.rxFreq) / 1e6))
                            self.statusBar.showMessage("TX chase HELD: %.6f MHz is outside the NB uplink - move the RX into 10489.550-10489.800" % (newTx / 1e6))
                        connSock.send('f\n'.encode())
                    elif (int(self.txFreq) != newTx):
                        #print ("Not equal, sync %d to %d" %(int(self.txFreq), newTx))
                        sendString = ('F %s\n'% newTx)
                        connSock.send(sendString.encode())
                        self.txFreq = str(newTx)
                    else:
                        connSock.send('f\n'.encode())
                else:
                    connSock.send('f\n'.encode())
                output = connSock.recv(100).decode()
                
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
            try:
                connSock.close()
            except:
                pass
            raise

    def connPtt(self):
        # Same retry policy as connRx/connTx. This one matters most: if the
        # thread dies, "Amp On TX" silently stops keying the amp in step with
        # the rig and nothing anywhere says so.
        while 1:
            try:
                self.connPttOnce()
            except:
                print ("Amp keying link lost: %s" % traceback.format_exc().splitlines()[-1])
                self.statusBar.showMessage("Amp keying link lost - retrying every second")
                self.pttLinkDown = True
                time.sleep(1.0)

    def connPttOnce(self):
        # Follow the rig PTT state and key the amp via MQTT when "Amp On TX" is checked.
        try:
            connSock = socket(AF_INET, SOCK_STREAM)
            connSock.connect((self.txHost, self.txPort))
            connSock.settimeout(self.sockTimeout)
            if self.pttLinkDown:
                self.pttLinkDown = False
                self.statusBar.showMessage("Amp keying link restored")
            last = None
            while 1:
                time.sleep(0.2)
                if not self.ampAction.isChecked():
                    last = None
                    continue
                connSock.send('t\n'.encode())
                output = connSock.recv(100).decode().strip()
                ptt = 1 if output == '1' else 0
                if ptt != last:
                    last = ptt
                    os.system("(/usr/bin/mosquitto_pub -h 192.168.0.201 -t '/radio/amp/set2' -m '%s')" % ('ON' if ptt else 'OFF'))
                    if self.muteButton.isChecked():
                        self.pulse.mute(self.pulse.sink_list()[self.pulseDev], bool(ptt))
        except:
            try:
                connSock.close()
            except:
                pass
            raise


if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)
    MainWindow = QMainWindow()
    ui = Ui_MainWindow()
    ui.setupUi(MainWindow)
    MainWindow.show()
    sys.exit(app.exec_())
