import sys, socket, time
from pytube import YouTube
from PyQt6.QtWidgets import QApplication, QStatusBar, QWidget, QLabel, QLineEdit, QPushButton, QTextEdit, QVBoxLayout, QHBoxLayout
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtCore import QThread, pyqtSignal
from urllib.request import urlopen
from datetime import timedelta

class ConnectionThread(QThread):
    con_response = pyqtSignal(bool)
    def run(self):
        while True:
            try:
                # check if the host is reachable
                con = socket.create_connection(("8.8.8.8", 53))
                con.close()
                # emit available signal
                self.con_response.emit(True)
                continue
            except OSError:
                pass
            finally:
                # sleep for 3 seconds just to avoid overhead
                time.sleep(3)
            # emit unavailable signal
            self.con_response.emit(False)

# seperate worker thread for background processing and to avoid UI freez 
class WorkerThread(QThread):
    # setup response signal
    worker_response = pyqtSignal(tuple)
    # additional parameter as url
    def __init__(self, url):
        # invoke the __init__ of super as well
        super(WorkerThread, self).__init__()
        self.url = url
    def run(self):
        try:
            yt = YouTube(self.url)
            # emitting the response signal
            # self.worker_response.emit(str(yt.streams.filter(progressive='true', file_extension='mp4')))
            self.worker_response.emit((yt.thumbnail_url, yt.title, yt.author, yt.length, yt.publish_date))
        except Exception as ex:
            pass
            # emitting the response signal
            # self.worker_response.emit('Enter valid url!','','','','')

class YTdownloader(QWidget):
    def __init__(self):
        super().__init__()
        # setup some window specific things
        self.setWindowTitle('Youtube Downloader')
        self.setWindowIcon(QIcon('assets/yt-icon.ico'))
        self.resize(700, 400)

        # parent layout
        layout = QVBoxLayout()
        self.setLayout(layout)

        # top bar layout
        topBar = QHBoxLayout()

        # detail section
        detailSec = QHBoxLayout()
        metaSec = QVBoxLayout()

        # status bar
        self.statusBar = QStatusBar()

        # widgets
        urlLabel = QLabel('URL: ')
        self.urlBox = QLineEdit()
        button = QPushButton('&Get')
        button.clicked.connect(self.getDetails)
        self.output = QTextEdit()

        pixmap = QPixmap('assets\placeholder.jpg')
        self.thumb = QLabel()
        self.thumb.setFixedSize(250, 141)
        self.thumb.setScaledContents(True)
        self.thumb.setPixmap(pixmap)

        self.title = QLabel('Title: ')
        self.author = QLabel('Author: ')
        self.length = QLabel('Duration: ')
        self.publish_date = QLabel('Published: ')

        # add widgets and layouts
        topBar.addWidget(urlLabel)
        topBar.addWidget(self.urlBox)
        topBar.addWidget(button)

        metaSec.addWidget(self.title)
        metaSec.addWidget(self.author)
        metaSec.addWidget(self.length)
        metaSec.addWidget(self.publish_date)
        detailSec.addWidget(self.thumb)
        detailSec.addLayout(metaSec)

        # add content to parent layout
        layout.addLayout(topBar)
        layout.addLayout(detailSec)
        layout.addWidget(self.output)
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
            if curMsg == '🔴 Disconnected':
                self.statusBar.showMessage('🟢 Connection restored!', 3000)
            elif curMsg != '🟢 Connected':
                self.statusBar.showMessage('🟢 Connected')
        # connection failed
        elif curMsg == '🟢 Connected':
            self.statusBar.showMessage('🔴 Connection interrupted!', 3000)
        elif curMsg != '🔴 Disconnected': 
            self.statusBar.showMessage('🔴 Disconnected')

    # get button slot
    def getDetails(self):
        # setup a worker thread to keep UI responsive
        self.worker = WorkerThread(self.urlBox.text())
        self.worker.start()
        # catch the finished signal
        self.worker.finished.connect(self.finished_slot)
        # catch the response signal
        self.worker.worker_response.connect(self.response_slot)
        self.output.setText('Button clicked !')
    
    # finished slot
    def finished_slot(self):
        print('Worker finished!')

    # response slot
    def response_slot(self, res):
        pixmap = QPixmap()
        pixmap.loadFromData(urlopen(str(res[0])).read())
        self.thumb.setPixmap(pixmap)
        if len(res[1]) > 50:
            self.title.setText(f'Title:  {res[1][:50]}...')
        else:
            self.title.setText(f'Title:  {res[1]}')
        self.author.setText(f'Author:  {res[2]}')
        self.length.setText('Duration:  {}'.format(str(timedelta(seconds=res[3]))))
        self.publish_date.setText(f'Published:  {res[4].strftime("%m/%d/%Y")}')
        #self.output.setText(res)

if __name__ == '__main__':
    # app = QApplication([])
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
    ''')
    window = YTdownloader()
    # show the window at last
    window.show()

    sys.exit(app.exec())