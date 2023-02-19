import sys, socket, time, subprocess
from pytube import YouTube
from PyQt6.QtWidgets import QApplication, QStatusBar, QWidget, QLabel, QLineEdit, QPushButton, QProgressBar, QComboBox, QMessageBox, QFileDialog, QVBoxLayout, QHBoxLayout
from PyQt6.QtGui import QIcon, QPixmap, QCursor
from PyQt6.QtCore import Qt, QDir, QThread, pyqtSignal
from urllib.request import urlopen
from datetime import timedelta

class ConnectionThread(QThread):
    con_response = pyqtSignal(bool)
    def run(self):
        while True:
            try:
                # check if the host is reachable
                con = socket.create_connection(('8.8.8.8', 53))
                con.close()
                self.con_response.emit(True)
            except OSError:
                self.con_response.emit(False)
            finally:
                # sleep for 3 seconds just to avoid overhead
                time.sleep(3)

# separate worker thread for background processing
class WorkerThread(QThread):
    worker_response = pyqtSignal(tuple)
    worker_err_response = pyqtSignal()
    def __init__(self, url):
        super(WorkerThread, self).__init__()
        self.url = url
    def run(self):
        try:
            yt = YouTube(self.url)
            pixmap = QPixmap()
            pixmap.loadFromData(urlopen(str(yt.thumbnail_url)).read())
            self.worker_response.emit((
                yt,
                pixmap,
                yt.title,
                yt.author,
                yt.length,
                yt.publish_date,
                # populate a list of progressive mp4 resolutions for the download options
                [f'{res.resolution} - {round(res.filesize/1.049e+6, 1)}MB' for res in yt.streams.filter(progressive='true', file_extension='mp4').order_by('resolution')]
            ))
        except:
            self.worker_err_response.emit()

class DownloadThread(QThread):
    download_response = pyqtSignal(int)
    download_complete = pyqtSignal(str)
    download_err = pyqtSignal()

    def __init__(self, yt, download_type, path):
        super(DownloadThread, self).__init__()
        self.yt = yt
        self.download_type = download_type
        self.path = path

    def run(self):
        def downloadProgress(stream, chunk, bytes_remaining):
            size = stream.filesize
            self.download_response.emit(int((float(abs(bytes_remaining-size)/size))*float(100)))
        # download complete callback to navigate user to download folder
        def downloadComplete(stream, location):
            self.download_complete.emit(location)
        try:
            self.yt.register_on_progress_callback(downloadProgress)
            self.yt.register_on_complete_callback(downloadComplete)
            if self.download_type == 'audio':
                self.yt.streams.get_audio_only().download(output_path=self.path, filename_prefix='[Audio] ')
            else:
                self.yt.streams.filter(progressive=True, file_extension='mp4').get_by_resolution(self.download_type).download(output_path=self.path, filename_prefix=f'[{self.download_type}] ')
        except:
            self.download_err.emit()

class YTdownloader(QWidget):
    def __init__(self):
        super().__init__()
        self.isFetching = False
        self.isDownloading = False

        self.outputPath = f'{QDir.homePath()}/videos'

        # setup some window specific things
        self.setWindowTitle('YouTube Downloader')
        self.setWindowIcon(QIcon('assets/yt-icon.ico'))
        self.setFixedSize(705, 343)

        # parent layout
        layout = QVBoxLayout()
        layout.setContentsMargins(15, 15, 15, 10)
        self.setLayout(layout)

        topBar = QHBoxLayout()

        detailSec = QHBoxLayout()
        metaSec = QVBoxLayout()

        downloadSec = QHBoxLayout()
        downloadBtn = QVBoxLayout()

        self.outputBtn = QPushButton('📂  Output Path')
        self.outputBtn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.outputBtn.setToolTip(self.outputPath)
        self.outputBtn.clicked.connect(self.setOutputPath)

        self.statusBar = QStatusBar()

        self.message = QMessageBox()

        # setting up widgets
        self.urlBox = QLineEdit()
        self.urlBox.setPlaceholderText('🔍 Enter or paste video URL...')
        self.button = QPushButton('Get')
        self.button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.button.clicked.connect(self.getDetails)

        pixmap = QPixmap('assets\placeholder.jpg')
        self.thumb = QLabel()
        self.thumb.setFixedSize(250, 141)
        self.thumb.setScaledContents(True)
        self.thumb.setPixmap(pixmap)

        # detail widgets
        self.title = QLabel('Title: ')
        self.author = QLabel('Author: ')
        self.length = QLabel('Duration: ')
        self.publish_date = QLabel('Published: ')

        self.progress_bar = QProgressBar()
        
        self.download = QComboBox()
        self.download.setPlaceholderText('Download Video')
        self.download.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.download.activated.connect(lambda: self.getContent(0))
        self.download.setEnabled(False)

        self.download_audio = QPushButton('Download Audio')
        self.download_audio.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.download_audio.clicked.connect(lambda: self.getContent(1))
        self.download_audio.setEnabled(False)

        topBar.addWidget(self.urlBox)
        topBar.addWidget(self.button)

        # detail section
        metaSec.addWidget(self.title)
        metaSec.addWidget(self.author)
        metaSec.addWidget(self.length)
        metaSec.addWidget(self.publish_date)
        detailSec.addWidget(self.thumb)
        detailSec.addSpacing(20)
        detailSec.addLayout(metaSec)

        # download section
        downloadBtn.addWidget(self.download)
        downloadBtn.addWidget(self.download_audio)
        downloadSec.addWidget(self.progress_bar)
        downloadSec.addSpacing(10)
        downloadSec.addLayout(downloadBtn)

        self.statusBar.setSizeGripEnabled(False)
        self.statusBar.addPermanentWidget(self.outputBtn)

        layout.addLayout(topBar)
        layout.addSpacing(20)
        layout.addLayout(detailSec)
        layout.addSpacing(5)
        layout.addLayout(downloadSec)
        layout.addWidget(self.statusBar)

        # setup a connection thread to keep checking internet connectivity
        self.connection = ConnectionThread()
        self.connection.start()

        self.connection.con_response.connect(self.connection_slot)

    def connection_slot(self, status):
        curMsg = self.statusBar.currentMessage()
        if status:
            if curMsg == '🔴  Disconnected':
                self.statusBar.showMessage('🟢  Connection restored!', 3000)
            elif curMsg != '🟢  Connected':
                self.statusBar.showMessage('🟢  Connected')
        elif curMsg == '🟢  Connected':
            self.statusBar.showMessage('🔴  Connection interrupted!', 3000)
        elif curMsg != '🔴  Disconnected': 
            self.statusBar.showMessage('🔴  Disconnected')

    def setOutputPath(self):
        path = str(QFileDialog.getExistingDirectory(self, "Select Output Directory"))
        if path:
            self.outputPath = path
            self.outputBtn.setToolTip(path)

    def getDetails(self):
        curMsg = self.statusBar.currentMessage()
        if curMsg == '🔴  Disconnected' or curMsg == '🔴  Connection interrupted!':
            self.message.critical(
                self,
                'Error',
                'Connection failed!\nAre you sure you\'re connected to the internet ? '
            )
        elif self.button.text() == 'Get':
            self.button.setText('Stop')
            # indicate progress bar as busy
            self.progress_bar.setRange(0, 0)
            self.isFetching = True
            self.worker = WorkerThread(self.urlBox.text())
            self.worker.start()
            self.worker.finished.connect(self.finished_slot)
            self.worker.worker_response.connect(self.response_slot)
            self.worker.worker_err_response.connect(self.err_slot)
        elif self.button.text() == 'Stop':
            if self.isFetching:
                self.worker.terminate()
                self.button.setText('Get')
            elif self.isDownloading:
                self.download_thread.terminate()
                self.message.information(
                    self,
                    'Interrupted',
                    'Download interrupted!\nThe process was aborted while the file was being downloaded... '
                )
                self.progress_bar.reset()

    # download options slot
    def getContent(self, id):
        if self.isFetching:
            self.message.warning(
                self,
                'Warning',
                'Please wait!\nWait while the details are being fetched... '
            )
        else:
            self.download.setDisabled(True)
            self.download_audio.setDisabled(True)
            self.isDownloading = True
            self.button.setText('Stop')
            if id == 0:
                self.download_thread = DownloadThread(self.yt, self.download.currentText()[:4], self.outputPath)
            else:
                self.download_thread = DownloadThread(self.yt, 'audio', self.outputPath)
            self.download_thread.start()
            self.download_thread.finished.connect(self.download_finished_slot)
            self.download_thread.download_response.connect(self.download_response_slot)
            self.download_thread.download_complete.connect(self.download_complete_slot)
            self.download_thread.download_err.connect(self.download_err_slot)

    # handling enter key for get/stop button
    def keyPressEvent(self, event):
        self.urlBox.setFocus()
        if event.key() == Qt.Key.Key_Enter.value or event.key() == Qt.Key.Key_Return.value:
            self.getDetails()

    def finished_slot(self):
        self.progress_bar.setRange(0, 100)
        self.isFetching = False

    def response_slot(self, res):
        self.button.setText('Get')
        # save the yt object for speeding up download
        self.yt = res[0]
        self.thumb.setPixmap(res[1])
        if len(res[2]) > 50:
            self.title.setText(f'Title:  {res[2][:50]}...')
        else:
            self.title.setText(f'Title:  {res[2]}')
        self.author.setText(f'Author:  {res[3]}')
        self.length.setText(f'Duration:  {timedelta(seconds=res[4])}')
        self.publish_date.setText(f'Published:  {res[5].strftime("%d/%m/%Y")}')
        # clear any previous items if any
        self.download.clear()
        self.download.addItems([item for item in res[6]])
        self.download.setDisabled(False)
        self.download_audio.setDisabled(False)

    def err_slot(self):
        self.message.warning(
            self,
            'Warning',
            'Something went wrong!\nProbably a broken link or some restricted content... '
        )
        self.button.setText('Get')

    def download_finished_slot(self):
        self.button.setText('Get')
        self.download.setDisabled(False)
        self.download_audio.setDisabled(False)
        self.isDownloading = False
        self.progress_bar.reset()

    def download_response_slot(self, per):
        self.progress_bar.setValue(per)
        # adjust the font color to maintain the contrast
        if per > 52:
            self.progress_bar.setStyleSheet('QProgressBar { color: #fff }')
        else:
            self.progress_bar.setStyleSheet('QProgressBar { color: #000 }')
    
    def download_complete_slot(self, location):
        location = QDir.toNativeSeparators(location)
        if self.message.information(
            self,
            'Downloaded',
            f'Download complete!\nFile was successfully downloaded to :\n{location}\n\nOpen the downloaded file now ?',
            QMessageBox.StandardButtons.Open,
            QMessageBox.StandardButtons.Cancel
        ) is QMessageBox.StandardButtons.Open: subprocess.Popen(f'explorer /select,{location}')

    def download_err_slot(self):
        self.message.critical(
            self,
            'Error',
            'Error!\nSomething unusual happened and was unable to download...'
        )

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyleSheet('''
        * {
            background-color: #fff;
        }
        QWidget {
            font-size: 15px;
            border-radius: 4px;
        }
        QToolTip {
            padding: 4px; 
            border: 1px solid #bababa;
        }
        QStatusBar {
            font-size: 13px;
        }
        QStatusBar QPushButton {
            background-color: none;
            font-family: 'Segoe UI Symbol';
            padding: 0 40px;
            color: #333;
        }
        QStatusBar QPushButton:hover {
            background-color: none;
            color: #0078d4;
        }
        QLineEdit {
            padding: 4px 10px;
            margin-right: 10px;
            border: 2px solid #bababa;
            font-size: 16px;
            font-family: 'Segoe UI Symbol';
            selection-background-color: #0078d4;
        }
        QLineEdit:hover {
            border-color: #808080;
        }
        QLineEdit:focus {
            border-color: #0078d4;
        }
        QMenu {
            border: 1px solid #bababa;
            padding: 5px;
        }
        QMenu::item {
            padding: 3px 25px;
            border-radius: 4px; 
        }
        QMenu::item:selected {
            color: #fff;
            background-color: #0078d4;
        }
        QPushButton {
            width: 125px;
            padding: 7px 0;
            color: #fff;
            border: none;
            background-color: #0078d4;
        }
        QPushButton:hover, QComboBox:hover {
            background-color: #00599d;
        }
        QPushButton:pressed, QComboBox:pressed {
            background-color: #00477c;
        }
        QPushButton:disabled, QComboBox:disabled {
            background-color: #77b7e9;
        }
        QComboBox {
            padding: 5.5px 30px 5.5px 45px;
            color: #fff;
            border: none;
            background-color: #0078d4;
        }
        QComboBox::drop-down {
            border-radius: 0;
        }
        QComboBox:on {
            border-bottom-left-radius: 0;
            border-bottom-right-radius: 0;
        }
        QComboBox QAbstractItemView {
            border-radius: 0;
            outline: 0;
        }
        QComboBox QAbstractItemView::item {
            height: 33px;
            padding-left: 42px;
            background-color: #fff;
        }
        QComboBox QAbstractItemView::item:selected {
            background-color: #0078d4;
        }
        QProgressBar {
            text-align: center;
        }
        QProgressBar::chunk {
            background: #0078d4;
            border-radius: 4px;
        }
        QMessageBox QLabel {
            font-size: 13px;
        }
        QMessageBox QPushButton {
            width: 50px;
            padding: 6px 25px;
        }
    ''')
    window = YTdownloader()
    window.show()

    sys.exit(app.exec())
