from __future__ import unicode_literals
import os
import sys
import threading

from PyQt5 import QtCore, QtGui, QtWidgets, uic
from PyQt5.QtWidgets import QApplication, QFileDialog, QWidget
from PyQt5.QtCore import QStandardPaths, QEventLoop, pyqtSignal
from PyQt5.QtGui import QPalette, QColor

from DownloadMethods import Download


def res_path(rel: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)

def _system_theme():
    try:
        if sys.platform.startswith("win"):
            import winreg
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
            ) as k:
                val, _ = winreg.QueryValueEx(k, "AppsUseLightTheme")
                return "light" if int(val) == 1 else "dark"
    except Exception:
        pass

    pal = QApplication.instance().palette() if QApplication.instance() else QPalette()
    win = pal.color(QPalette.Window)
    lum = 0.2126 * win.redF() + 0.7152 * win.greenF() + 0.0722 * win.blueF()
    return "dark" if lum < 0.5 else "light"


class MainWindow(QtWidgets.QMainWindow):
    # >>> Thread-safe channels
    sig_progress = pyqtSignal(dict)           # payload from downloader
    sig_title    = pyqtSignal(str, object, object)  # title, idx, total
    sig_finish   = pyqtSignal(bool, str)      # success, message

    def __init__(self):
        super().__init__()
        uic.loadUi(res_path("Graphics.ui"), self)

        # Bind widgets
        self.label_top       = self.findChild(QtWidgets.QLabel,      "label")
        self.button_download = self.findChild(QtWidgets.QPushButton, "pushButton_3")
        self.check_video     = self.findChild(QtWidgets.QCheckBox,   "checkBox")
        self.input_url       = self.findChild(QtWidgets.QLineEdit,   "lineEdit_3")
        self.button_set      = self.findChild(QtWidgets.QPushButton, "pushButton_4")
        self.input_path      = self.findChild(QtWidgets.QLineEdit,   "lineEdit_4")
        self.radio_single    = self.findChild(QtWidgets.QRadioButton,"radioButton")
        self.radio_playlist  = self.findChild(QtWidgets.QRadioButton,"radioButton_2")
        self.themeButton     = self.findChild(QtWidgets.QPushButton, "themeButton")
        self.combo_quality   = self.findChild(QtWidgets.QComboBox,   "comboBox")
        self.label_done      = self.findChild(QtWidgets.QLabel,      "label_2")
        self.label_progress  = self.findChild(QtWidgets.QLabel,      "label_progress")
        self.progress_bar    = self.findChild(QtWidgets.QProgressBar,"progressBar")
        self.central         = self.findChild(QtWidgets.QWidget,     "centralwidget")

        # Window props
        self.setWindowTitle("Youtube Downloader")
        self.setFixedSize(592, 360) 

        # Be sure both labels can wrap/show fully
        self.label_done.setWordWrap(True)
        self.label_progress.setWordWrap(True)

        # Ensure stacking order: progress text sits above done label during downloads
        self.label_done.lower()
        self.label_progress.raise_()
        self.progress_bar.raise_()
        self.themeButton.raise_()

        # Initial state
        self.input_url.setPlaceholderText("Enter URL Here...")
        self.input_url.setText("")
        self.label_done.setText("")
        self.radio_single.setChecked(True)

        # THEME
        start_theme = _system_theme()
        for w in (self, self.central, self.statusBar(), self.menuBar()):
            if w:
                w.setProperty("theme", start_theme)
        self._apply_placeholder_palette(start_theme)
        self._repolish_theme_all()

        # Downloads folder
        downloads = QStandardPaths.writableLocation(QStandardPaths.DownloadLocation) \
                    or os.path.join(os.path.expanduser("~"), "Downloads")
        self.input_path.setText(downloads)

        # Progress row hidden initially
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("%p%")
        self.progress_bar.setTextVisible(True)
        self.progress_bar.hide()
        self.label_progress.hide()

        # Hand cursor on buttons
        pointing = QtGui.QCursor(QtCore.Qt.PointingHandCursor)
        for btn in (self.button_download, self.button_set, self.themeButton):
            btn.setCursor(pointing)

        # Signals/slots (thread-safe)
        self.sig_progress.connect(self._on_progress_gui)
        self.sig_title.connect(self._show_initial_title)
        self.sig_finish.connect(self._on_download_finished_gui)

        # Buttons
        self.button_download.clicked.connect(self.download_button)
        self.button_set.clicked.connect(self.set_button)
        self.themeButton.clicked.connect(self.toggle_theme)

        # State
        self.current_title = None
        self._saw_progress = False

        # >>> Place bottom widgets now and keep them placed on resize
        self._place_bottom_controls()

    # ---------- bottom controls placer ----------
    def _place_bottom_controls(self):
        """Anchor progress labels, bar and the Toggle Theme button."""
        cw = self.central or self.centralWidget()
        if not cw:
            return

        cw_w, cw_h = cw.width(), cw.height()

        # Layout constants
        margin_left       = 12
        margin_right      = 16
        bottom_margin     = 16
        gap_label_to_bar  = 6
        gap_bar_to_btn    = 8
        labels_height     = 44   # 2 lines at ~14pt without clipping

        # Lowest point of the middle row -> labels/bar never go above this
        lower_row_bottom = max(
            self.combo_quality.geometry().bottom(),
            self.button_download.geometry().bottom(),
            self.check_video.geometry().bottom(),
            self.radio_single.geometry().bottom(),
            self.radio_playlist.geometry().bottom(),
        )
        safe_top = lower_row_bottom + 12

        # --- Toggle Theme (bottom-right, with a small right margin)
        btn = self.themeButton
        btn_w = max(150, btn.sizeHint().width())
        btn_h = max(30,  btn.sizeHint().height())
        btn_x = max(0, cw_w - btn_w - margin_right)
        btn_y = max(0, cw_h - btn_h - bottom_margin)
        btn.setGeometry(btn_x, btn_y, btn_w, btn_h)

        # --- Progress bar (short & centered), always below the labels and above the button
        pb = self.progress_bar
        pb_h = max(14, pb.sizeHint().height())
        pb_w = 240
        # place above the button, but never so high that it would push labels into the form
        pb_y = min(btn_y - gap_bar_to_btn - pb_h,
                cw_h - bottom_margin - btn_h - gap_bar_to_btn - pb_h)
        pb_y = max(safe_top + labels_height + gap_label_to_bar, pb_y)
        pb_x = max(0, (cw_w - pb_w) // 2)
        pb.setGeometry(pb_x, pb_y, pb_w, pb_h)

        # --- Progress/Done labels directly above the bar (two lines wide)
        lab_y = max(safe_top, pb_y - labels_height - gap_label_to_bar)
        lab_x = margin_left
        lab_w = cw_w - (margin_left + margin_right)
        self.label_progress.setGeometry(lab_x, lab_y, lab_w, labels_height)
        self.label_done.setGeometry(lab_x, lab_y, lab_w, labels_height)

        # z-order so progress text is on top during downloads
        self.label_done.lower()
        self.label_progress.raise_()
        self.progress_bar.raise_()
        self.themeButton.raise_()


    def resizeEvent(self, e):
        super().resizeEvent(e)
        # place again after the window has its new size
        QtCore.QTimer.singleShot(0, self._place_bottom_controls)

    # ---------- Progress text helper ----------
    def _set_progress_text(self, text: str):
        # show full text in tooltip + status bar
        self.label_progress.setToolTip(text)
        if self.statusBar():
            self.statusBar().showMessage(text)
        # the label itself wraps to two lines (wordWrap enabled in .ui)
        self.label_progress.setText(text)

    # ---------- Theme helpers ----------
    def _apply_placeholder_palette(self, theme: str):
        placeholder = QColor("#888888") if theme == "light" else QColor("#bdbdbd")
        for le in (self.input_url, self.input_path):
            pal = le.palette()
            pal.setColor(QPalette.PlaceholderText, placeholder)
            le.setPalette(pal)

    def _repolish_theme_all(self):
        widgets = [self, self.central] + self.findChildren(QWidget)
        for w in widgets:
            try:
                s = w.style()
                s.unpolish(w); s.polish(w); w.update()
            except Exception:
                pass
        QApplication.processEvents(QEventLoop.AllEvents, 5)

    def toggle_theme(self):
        current = self.property("theme") or "light"
        new = "dark" if current == "light" else "light"
        for w in (self, self.central, self.statusBar(), self.menuBar()):
            if w:
                w.setProperty("theme", new)
        self._apply_placeholder_palette(new)
        self._repolish_theme_all()

    # ---------- UI actions ----------
    def set_button(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose download folder", self.input_path.text())
        if folder:
            self.input_path.setText(folder)

    def download_button(self):
        url = self.input_url.text().strip()
        save_path = self.input_path.text().strip()

        if not (url.startswith("http://") or url.startswith("https://")):
            QtWidgets.QMessageBox.warning(self, "Invalid URL", "Please paste a valid video/playlist URL.")
            return
        if not os.path.isdir(save_path):
            QtWidgets.QMessageBox.warning(self, "Invalid Folder", "Please choose an existing download folder.")
            return

        # Reset + show progress UI
        self.label_done.setText("")
        self.current_title = None
        self._saw_progress = False
        self._set_progress_text("Preparing…")
        self.label_progress.show()
        self.progress_bar.setValue(0)
        self.progress_bar.show()

        # Disable + busy cursor
        self.button_download.setEnabled(False)
        QApplication.setOverrideCursor(QtGui.QCursor(QtCore.Qt.BusyCursor))

        quality = self.combo_quality.currentText()
        playlist = self.radio_playlist.isChecked()
        video_format = self.check_video.isChecked()

        threading.Thread(
            target=self.download_thread,
            args=(url, save_path, quality, playlist, video_format),
            daemon=True,
        ).start()

    # ---------- Title helper (GUI thread) ----------
    @QtCore.pyqtSlot(str, object, object)
    def _show_initial_title(self, title, idx=None, total=None):
        self.current_title = (title or self.current_title or "").strip()
        prefix = f"Downloading {idx}/{total}" if (idx and total) else "Downloading"
        shown = self.current_title or "..."
        self._set_progress_text(f"{prefix} — {shown} (0%)")

    # ---------- Thread body ----------
    def download_thread(self, url, save_path, quality, playlist, video_format):
        try:
            # Early metadata -> show title quickly
            try:
                import yt_dlp as ydl
                probe = ydl.YoutubeDL({
                    "quiet": True,
                    "noplaylist": not playlist,
                    "extract_flat": "discard_in_playlist",
                    "skip_download": True
                }).extract_info(url, download=False)
                title, idx, total = None, None, None
                if probe.get("entries"):
                    entries = [e for e in (probe.get("entries") or []) if e]
                    if entries:
                        first = entries[0]
                        title = first.get("title") or first.get("fulltitle")
                        idx, total = 1, len(entries)
                else:
                    title = probe.get("title") or probe.get("fulltitle")
                if title:
                    self.sig_title.emit(title, idx, total)
            except Exception as e:
                print(f"[APP] Title probe failed: {e}", flush=True)

            # Download with thread-safe emitter
            def thread_safe_emit(payload: dict):
                self.sig_progress.emit(payload)

            downloader = Download(
                url, save_path, quality, playlist, video_format,
                progress_cb=thread_safe_emit
            )
            name = downloader.mp4_download() if video_format else downloader.mp3_download()
            self.sig_finish.emit(True, name)

        except Exception as e:
            self.sig_finish.emit(False, str(e))
        finally:
            QtCore.QTimer.singleShot(0, QtWidgets.QApplication.restoreOverrideCursor)

    # ---------- Progress + finish (GUI thread) ----------
    @QtCore.pyqtSlot(dict)
    def _on_progress_gui(self, payload: dict):
        self._saw_progress = True

        idx = payload.get("idx")
        total = payload.get("total")
        title = (payload.get("title") or "").strip()
        if title:
            self.current_title = title

        file_p = payload.get("file_percent")
        overall = payload.get("overall_percent")

        prefix = f"Downloading {idx}/{total}" if (idx and total) else "Downloading"
        shown_title = self.current_title or title or ""
        text = prefix + (f" — {shown_title}" if shown_title else "")
        if file_p is not None:
            text += f" ({file_p}%)"
        self._set_progress_text(text)

        self.progress_bar.setValue(int(overall if overall is not None else (file_p or 0)))

        # force paint on Windows (helps when stdout is spammy)
        self.progress_bar.repaint()
        QApplication.processEvents(QEventLoop.AllEvents, 5)

    @QtCore.pyqtSlot(bool, str)
    def _on_download_finished_gui(self, success: bool, message: str):
        QApplication.restoreOverrideCursor()
        self.button_download.setEnabled(True)

        if success:
            if not self._saw_progress:
                if not self.current_title and message:
                    self.current_title = message
                title = self.current_title or message or ""
                self._set_progress_text(f"Downloading — {title} (100%)")
                self.progress_bar.setValue(100)

            self.label_done.setText(f"{message}\nDownload Done!")
            self.label_done.show()
            self.label_progress.hide()
            self.progress_bar.hide()
            if self.statusBar():
                self.statusBar().clearMessage()
        else:
            self.label_done.setText(f"Error: {message}")
            self.label_done.show()
            self.label_progress.hide()
            self.progress_bar.hide()
            if self.statusBar():
                self.statusBar().clearMessage()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.setWindowIcon(QtGui.QIcon(res_path("YouTube.ico")))
    window.show()
    sys.exit(app.exec_())
