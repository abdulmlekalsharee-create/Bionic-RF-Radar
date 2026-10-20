import sys
import serial
import numpy as np
from scipy.signal import butter, filtfilt
from sklearn.decomposition import PCA
import pyqtgraph as pg
from pyqtgraph.Qt import QtWidgets, QtCore
import threading
import collections

# ================= Main settings =================
PORT = 'COM11'        # serial port of the ESP32 receiver (change to yours)
BAUD_RATE = 921600
FS = 100.0            # sampling rate (100 packets/second)
WINDOW_SIZE = 500     # analysis window (5 seconds)

# Buffer holding the most recent phase vectors
phase_buffer = collections.deque(maxlen=WINDOW_SIZE)

# ================= 1. Signal processing (DSP) =================

def sanitize_phase(csi_complex):
    """ Remove the linear phase trend caused by timing offsets between transmitter and receiver """
    raw_phase = np.angle(csi_complex)
    unwrapped = np.unwrap(raw_phase)
    n = len(unwrapped)
    indices = np.arange(n)
    slope = (unwrapped[-1] - unwrapped[0]) / (n - 1)
    offset = np.mean(unwrapped)
    return unwrapped - (slope * indices) - offset

def butter_bandpass_filter(data, lowcut, highcut, fs, order=2):
    """ Zero-phase IIR Butterworth band-pass filter """
    nyq = 0.5 * fs
    b, a = butter(order, [lowcut/nyq, highcut/nyq], btype='band')
    return filtfilt(b, a, data)

# ================= 2. Serial link (reader thread) =================

def serial_worker():
    """ Read CSI lines from the ESP32 in a background thread """
    try:
        ser = serial.Serial(PORT, BAUD_RATE, timeout=1)
        print(f"Radar Online. Listening on {PORT}...")
        while True:
            line = ser.readline().decode('utf-8', errors='ignore').strip()
            if line.startswith("RSSI:") and "DATA:" in line:
                try:
                    data_str = line.split("DATA:")[1]
                    raw_nums = list(map(int, filter(None, data_str.split(','))))
                    csi_complex = [complex(raw_nums[i+1], raw_nums[i]) for i in range(0, len(raw_nums)-1, 2)]
                    clean_phase = sanitize_phase(np.array(csi_complex))
                    phase_buffer.append(clean_phase)
                except Exception:
                    pass
    except Exception as e:
        print(f"Serial Error: {e}")

threading.Thread(target=serial_worker, daemon=True).start()

# ================= 3. GUI =================

app = QtWidgets.QApplication(sys.argv)
win = pg.GraphicsLayoutWidget(show=True, title="Bionic RF Radar - Dual Vital Signs Monitor")
win.resize(1100, 750)
win.setBackground('#050505')

# Plot for the respiration and heartbeat waveforms
p1 = win.addPlot(title="<span style='color: #FFFFFF; font-size: 13pt;'>Real-Time Vital Signs (Time Domain)</span>")
p1.showGrid(x=True, y=True, alpha=0.2)
curve_resp = p1.plot(pen=pg.mkPen('#00FF00', width=2), name="Respiration") # respiration (green)
curve_heart = p1.plot(pen=pg.mkPen('#FF0055', width=1.5), name="Heartbeat") # heartbeat (red)

# Text readouts (RR and HR)
rr_text = pg.TextItem(text="RESP (RR): --", color='#00FF00', anchor=(0, 0))
hr_text = pg.TextItem(text="HEART (HR): --", color='#FF0055', anchor=(1, 0))
rr_text.setFont(pg.QtGui.QFont("Arial", 22, pg.QtGui.QFont.Bold))
hr_text.setFont(pg.QtGui.QFont("Arial", 22, pg.QtGui.QFont.Bold))
p1.addItem(rr_text)
p1.addItem(hr_text)

win.nextRow()

# Frequency-spectrum (FFT) plot
p2 = win.addPlot(title="<span style='color: #00FFFF; font-size: 13pt;'>Frequency Spectrum (FFT Analysis)</span>")
p2.showGrid(x=True, y=True, alpha=0.2)
p2.setXRange(0, 2.5) 
curve_fft = p2.plot(pen='c', fillLevel=0, brush=(0, 255, 255, 50))

pca = PCA(n_components=1)

def update_gui():
    """ Refresh the display with the newest data (20 times per second) """
    if len(phase_buffer) == WINDOW_SIZE:
        window_data = np.array(phase_buffer)
        
        try:
            pc1 = pca.fit_transform(window_data).flatten()
        except Exception:
            return
            
        # 1. Respiration band-pass (0.15-0.50 Hz)

        resp_signal = butter_bandpass_filter(pc1, lowcut=0.15, highcut=0.5, fs=FS)
        
        # 2. Heartbeat band-pass (0.80-2.00 Hz)
        heart_signal = butter_bandpass_filter(pc1, lowcut=0.8, highcut=2.0, fs=FS)
        
        # Amplify the heartbeat waveform (display only) so it stays visible next to the larger respiration waveform
        heart_display = heart_signal * 5.0 
        
        # Update the time-domain plot
        curve_resp.setData(resp_signal)
        curve_heart.setData(heart_display)
        
        # Full-spectrum FFT
        fft_vals = np.abs(np.fft.rfft(pc1))
        fft_freqs = np.fft.rfftfreq(WINDOW_SIZE, d=1.0/FS)
        fft_vals[0] = 0 
        
        # Respiration frequency from the FFT peak
        resp_fft_vals = np.abs(np.fft.rfft(resp_signal))
        resp_peak_idx = np.argmax(resp_fft_vals[1:]) + 1
        rr_bpm = fft_freqs[resp_peak_idx] * 60.0
        
        # Heart-rate frequency from the FFT peak
        heart_fft_vals = np.abs(np.fft.rfft(heart_signal))
        heart_peak_idx = np.argmax(heart_fft_vals[1:]) + 1
        hr_bpm = fft_freqs[heart_peak_idx] * 60.0
        
        # Update the text readouts
        if 8 <= rr_bpm <= 30:
            rr_text.setText(f"RESP (RR): {rr_bpm:.1f} RPM", color='#00FF00')
        else:
            rr_text.setText("RESP (RR): --", color='#555555')
            
        if 50 <= hr_bpm <= 120:
            hr_text.setText(f"HEART (HR): {hr_bpm:.0f} BPM", color='#FF0055')
        else:
            hr_text.setText("HEART (HR): --", color='#555555')
            
        curve_fft.setData(fft_freqs, fft_vals)

timer = QtCore.QTimer()
timer.timeout.connect(update_gui)
timer.start(50)

if __name__ == '__main__':
    sys.exit(app.exec_())