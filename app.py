import sys, socket, time
from pytube import YouTube
from PyQt6.QtWidgets import QApplication, QStatusBar, QWidget, QLabel, QLineEdit, QPushButton, QProgressBar, QComboBox, QMessageBox, QVBoxLayout, QHBoxLayout
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtCore import Qt, QThread, pyqtSignal
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
                # emit available signal
                self.con_response.emit(True)
            except OSError:
                # emit unavailable signal
                self.con_response.emit(False)
            finally:
                # sleep for 3 seconds just to avoid overhead
                time.sleep(3)

# seperate worker thread for background processing and to avoid UI freez 
class WorkerThread(QThread):
    # setup response signal
    worker_response = pyqtSignal(tuple)
    # setup error signal
    worker_err_response = pyqtSignal()
    # additional parameter as url
    def __init__(self, url):
        # invoke the __init__ of super as well
        super(WorkerThread, self).__init__()
        self.url = url
    def run(self):
        try:
            yt = YouTube(self.url)
            # load thumbnail image
            pixmap = QPixmap()
            pixmap.loadFromData(urlopen(str(yt.thumbnail_url)).read())
            # emitting the response signal
            self.worker_response.emit((
                pixmap,
                yt.title,
                yt.author,
                yt.length,
                yt.publish_date,
                # populate a list of progressive mp4 resolutions for the download options
                [res.resolution for res in yt.streams.filter(progressive='true', file_extension='mp4').order_by('resolution')]
            ))
        except:
            # emitting the error signal
            self.worker_err_response.emit()

# download thread
class DownloadThread(QThread):
    # setup download signal
    download_response = pyqtSignal(str)
    def __init__(self, download_type):
        super(DownloadThread, self).__init__()
        self.download_type = download_type
    def run(self):
        self.download_response.emit(self.download_type)

class YTdownloader(QWidget):
    def __init__(self):
        super().__init__()
        # setup some window specific things
        self.setWindowTitle('Youtube Downloader')
        self.setWindowIcon(QIcon('assets/yt-icon.ico'))
        self.setFixedSize(705, 334)

        # parent layout
        layout = QVBoxLayout()
        layout.setContentsMargins(15, 15, 15, 10)
        self.setLayout(layout)

        # top bar layout
        topBar = QHBoxLayout()

        # detail section
        detailSec = QHBoxLayout()
        metaSec = QVBoxLayout()

        # download section
        downloadSec = QHBoxLayout()
        downloadBtn = QVBoxLayout()

        # status bar
        self.statusBar = QStatusBar()

        # message box
        self.message = QMessageBox()

        # setting up widgets
        urlLabel = QLabel('URL: ')
        self.urlBox = QLineEdit()
        self.urlBox.setFocusPolicy(Qt.FocusPolicy.ClickFocus or Qt.FocusPolicy.NoFocus)
        self.urlBox.setPlaceholderText('Enter or paste video URL...')
        self.button = QPushButton('Get')
        self.button.setDefault(True)
        self.button.clicked.connect(self.getDetails)

        # thumbnail
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

        # progress bar
        self.progress_bar = QProgressBar()
        
        # download options
        self.download = QComboBox()
        self.download.setPlaceholderText('Download video')
        self.download.activated.connect(self.getVideo)
        self.download.setEnabled(False)

        # download audio button
        self.download_audio = QPushButton('Download audio')
        self.download_audio.clicked.connect(self.getAudio)
        self.download_audio.setEnabled(False)

        # add widgets and layouts
        topBar.addWidget(urlLabel)
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
        downloadSec.addLayout(downloadBtn)

        # add content to parent layout
        layout.addLayout(topBar)
        layout.addSpacing(20)
        layout.addLayout(detailSec)
        layout.addSpacing(5)
        layout.addLayout(downloadSec)
        layout.addWidget(self.statusBar)

        # setup a connection thread to keep checking internet connectivity
        self.connection = ConnectionThread()
        self.connection.start()

        # catch the connection response signal
        self.connection.con_response.connect(self.connection_slot)

    # connection slot
    def connection_slot(self, status):
        # get current message from status bar
        curMsg = self.statusBar.currentMessage()
        # connection succeeded
        if status:
            if curMsg == '🔴  Disconnected':
                self.statusBar.showMessage('🟢  Connection restored!', 3000)
            elif curMsg != '🟢  Connected':
                self.statusBar.showMessage('🟢  Connected')
        # connection failed
        elif curMsg == '🟢  Connected':
            self.statusBar.showMessage('🔴  Connection interrupted!', 3000)
        elif curMsg != '🔴  Disconnected': 
            self.statusBar.showMessage('🔴  Disconnected')

    # get button slot
    def getDetails(self):
        curMsg = self.statusBar.currentMessage()
        if curMsg == '🔴  Disconnected' or curMsg == '🔴  Connection interrupted!':
            self.message.critical(
                self,
                'Error',
                'Conection failed!\nAre you sure you\'re connected to internet ? '
            )
        elif self.button.text() == 'Get':
            self.button.setText('Fetching...')
            self.button.setDisabled(True)
            # setup a worker thread to keep UI responsive
            self.worker = WorkerThread(self.urlBox.text())
            self.worker.start()
            # catch the finished signal
            self.worker.finished.connect(self.finished_slot)
            # catch the response signal
            self.worker.worker_response.connect(self.response_slot)
            # catch the error signal
            self.worker.worker_err_response.connect(self.err_slot)

    # download video combo box slot
    def getVideo(self):
        self.message.critical(
                self,
                'Error',
                f'video got triggered {self.download.currentText()}'
        )

    # download audio button slot
    def getAudio(self):
        self.message.critical(
                self,
                'Error',
                'Audio got triggered'
        )
    
    # finished slot
    def finished_slot(self):
        print('Worker finished!')

    # response slot
    def response_slot(self, res):
        # set back the button text and enable it
        self.button.setText('Get')
        self.button.setDisabled(False)
        # set the actual thumbnail of requested video
        self.thumb.setPixmap(res[0])
        # slice the title if it is more than the limit
        if len(res[1]) > 50:
            self.title.setText(f'Title:  {res[1][:50]}...')
        else:
            self.title.setText(f'Title:  {res[1]}')
        # set leftover details
        self.author.setText(f'Author:  {res[2]}')
        self.length.setText('Duration:  {}'.format(str(timedelta(seconds=res[3]))))
        self.publish_date.setText(f'Published:  {res[4].strftime("%m/%d/%Y")}')
        # clear any previous items if any
        self.download.clear()
        # add resolutions as items to the download button and enable them
        self.download.addItems(['MP4 - ' + res for res in res[5]])
        self.download.setDisabled(False)
        self.download_audio.setDisabled(False)

    # error slot
    def err_slot(self):
        # show the warning message
        self.message.warning(
            self,
            'Warning',
            'Something went wrong!\nProbably a broken link or some restricted content... '
        )
        # set back the button text and enable it
        self.button.setText('Get')
        self.button.setDisabled(False)

if __name__ == '__main__':
    # instantiate the application
    app = QApplication(sys.argv)
    # setup a custom styleSheet
    app.setStyleSheet('''
        QWidget {
            font-size: 15px;
        }
        QStatusBar {
            font-size: 12px;
        }
        QLineEdit {
            border: none;
            border-bottom: 2px solid #808080;
            padding: 2px 5px;
            margin: 0 10px;
            background: transparent;
        }
        QPushButton {
            width: 125px;
            padding: 5.5px 0;
        }
        QComboBox {
            padding: 3px 30px 3px 45px;
        }
        QMessageBox QLabel {
            font-size: 13px;
        }
        QMessageBox QPushButton {
            width: auto;
            padding: 3px 20px;
        }
    ''')
    window = YTdownloader()
    # show the window at last
    window.show()

    sys.exit(app.exec())