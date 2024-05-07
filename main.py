import sys
from PyQt5.QtWidgets import QDateTimeEdit, QApplication, QWidget, QLabel, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout, QListWidget, QSplitter, QProgressBar, QTreeView, QMessageBox, QFileDialog
from PyQt5.QtWidgets import QSpacerItem, QSizePolicy
from PyQt5.QtGui import QStandardItemModel, QStandardItem, QFont
from PyQt5.QtCore import Qt, QVariant, QThread, pyqtSignal, QDateTime, QDate
import requests
import json
import yaml
import logging
import csv


class RequestWorker(QThread):
    progress = pyqtSignal(int, int)  # current page, total pages
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, base_url, headers, filter_layouts, token):
        super().__init__()
        self.base_url = base_url
        self.headers = headers
        self.filter_layouts = filter_layouts
        self.token = token
        self.running = True

    def run(self):
        current_page = 1
        total_pages = None
        all_data = []

        while self.running and (total_pages is None or current_page <= total_pages):
            payload = {}
            for layout in self.filter_layouts:
                if isinstance(layout[1], QLineEdit) and layout[1].text():
                    payload[f'filter[{layout[1].text()}]'] = layout[2].text()
                elif isinstance(layout[1], QDateTimeEdit):
                    start = layout[1].dateTime().toString(Qt.ISODate)
                    end = layout[2].dateTime().toString(Qt.ISODate)
                    payload['range[begin_at]'] = f"{start},{end}"

            payload.update({'page[number]': current_page, 'page[size]': 100})
            try:
                response = requests.get(self.base_url, headers=self.headers, params=payload)
                response.raise_for_status()
                new_data = response.json()

                if isinstance(new_data, dict):
                    new_data = [new_data]

                all_data.extend(new_data)

                if 'X-Total' in response.headers:
                    if total_pages is None:
                        total_pages = (int(response.headers['X-Total']) + 99) // 100
                else:
                    total_pages = 1

                self.progress.emit(current_page, total_pages)
                current_page += 1
            except requests.RequestException as e:
                self.error.emit(str(e))
                break

        if self.running:
            self.finished.emit(all_data)
        self.running = False


class IntraAPIClient(QWidget):
    def __init__(self):
        super().__init__()
        self.config = self.load_config()
        self.token = None
        self.running = False
        self.current_json_data = []
        self.filter_layouts = []
        self.payload_entries = []
        self.init_ui()

    def load_config(self):
        with open('config.yml', 'r') as cfg_stream:
            return yaml.load(cfg_stream, Loader=yaml.BaseLoader)

    def export_data(self):
        file_name, _ = QFileDialog.getSaveFileName(self, "Save File")
        if file_name:
            file_name += ".csv"
            if file_name.endswith('.csv'):
                self.export_to_csv(file_name)

    def export_to_csv(self, file_name):
        with open(file_name, 'w', newline='') as file:
            writer = csv.writer(file)
            headers = [self.model.horizontalHeaderItem(i).text() for i in range(self.model.columnCount())]
            writer.writerow(headers)
            for row in range(self.model.rowCount()):
                row_data = [self.model.item(row, col).text() for col in range(self.model.columnCount())]
                writer.writerow(row_data)


    def init_ui(self):
        self.setWindowTitle('IntraAPIClient')
        self.setGeometry(10, 10, 1600, 800)
        main_layout = QVBoxLayout()

        # Splitter
        splitter = QSplitter(Qt.Horizontal)
        # Request frame
        self.setup_request_frame(splitter)
        # Response frame
        self.setup_response_frame(splitter)

        splitter.setSizes([200, 1400])
        main_layout.addWidget(splitter)
        self.setLayout(main_layout)


    def setup_request_frame(self, splitter):
        self.request_frame = QWidget()
        layout = QVBoxLayout()

        # Spacing and margins
        layout.setSpacing(5)
        layout.setContentsMargins(10, 10, 10, 10) 

        self.client_id_entry = QLineEdit(self.config['intra']['client'])
        self.client_secret_entry = QLineEdit(self.config['intra']['secret'])
        self.endpoint_entry = QLineEdit()

        layout.addWidget(QLabel("Client ID:"))
        layout.addWidget(self.client_id_entry)
        layout.addWidget(QLabel("Client Secret:"))
        layout.addWidget(self.client_secret_entry)
        layout.addWidget(QPushButton("Authenticate", clicked=self.authenticate))

        # Adding spacer
        spacer = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)
        layout.addItem(spacer)

        layout.addWidget(QLabel("API Endpoint:"))
        layout.addWidget(self.endpoint_entry)
        layout.addWidget(QPushButton("Add Filter", clicked=self.add_filter_field))
        layout.addWidget(QPushButton("Add Date Range", clicked=self.add_date_range_field))


        spacer = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)
        layout.addItem(spacer)

        layout.addWidget(QPushButton("Send Request", clicked=self.send_request))
        self.progress = QProgressBar()
        layout.addWidget(self.progress)
        layout.addWidget(QPushButton("Cancel Request", clicked=self.stop_request))

        # Optional: Add a stretch at the bottom to push all widgets up
        layout.addStretch(1)
        export_button = QPushButton("Export", clicked=self.export_data)
        layout.addWidget(export_button)

        self.request_frame.setLayout(layout)
        splitter.addWidget(self.request_frame)



    def setup_response_frame(self, splitter):
        self.response_frame = QWidget()
        layout = QHBoxLayout()

        self.json_keys_listbox = QListWidget()
        self.json_keys_listbox.setSelectionMode(QListWidget.MultiSelection)
        self.json_keys_listbox.itemSelectionChanged.connect(self.on_key_select)

        self.data_table = QTreeView()
        self.model = QStandardItemModel()
        self.data_table.setModel(self.model)
        self.data_table.setSortingEnabled(True)

        layout.addWidget(self.json_keys_listbox, 1)
        layout.addWidget(self.data_table, 3)

        self.response_frame.setLayout(layout)
        splitter.addWidget(self.response_frame)




    def authenticate(self):
        url = 'https://api.intra.42.fr/oauth/token'
        data = {
            'grant_type': 'client_credentials',
            'client_id': self.client_id_entry.text(),
            'client_secret': self.client_secret_entry.text()
        }
        try:
            response = requests.post(url, data=data)
            response.raise_for_status()
            self.token = response.json()['access_token']
            QMessageBox.information(self, "Authentication", "Authentication Successful!")
        except requests.RequestException as e:
            QMessageBox.critical(self, "Authentication", f"Failed to authenticate: {e}")


    def send_request(self):
        if not self.token:
            QMessageBox.critical(self, "Error", "Authenticate first!")
            return
        self.json_keys_listbox.clear()
        self.model.clear()
        print(f'https://api.intra.42.fr/v2/{self.endpoint_entry.text()}')
        self.worker = RequestWorker(
            base_url=f'https://api.intra.42.fr/v2/{self.endpoint_entry.text()}',
            headers={'Authorization': f'Bearer {self.token}'},
            filter_layouts=self.filter_layouts,
            token=self.token
        )
        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.handle_finished)
        self.worker.error.connect(self.handle_error)
        self.worker.start()


    def update_progress(self, current_page, total_pages):
        self.progress.setMaximum(total_pages)
        self.progress.setValue(current_page)


    def handle_finished(self, data):
        self.current_json_data = data
        #(data)
        self.update_json_keys_listbox(data)


    def handle_error(self, message):
        QMessageBox.critical(self, "Request Failed", message)


    def stop_request(self):
        if self.worker.isRunning():
            self.worker.stop()


    def add_date_range_field(self):
        date_range_layout = QHBoxLayout()

        small_font = QFont()
        small_font.setPointSize(10)

        start_date_time_edit = QDateTimeEdit(self)
        start_date_time_edit.setCalendarPopup(True)
        start_date_time_edit.setDateTime(QDateTime.currentDateTime())
        start_date_time_edit.setDisplayFormat("yyyy-MM-dd HH:mm")
        start_date_time_edit.setFixedWidth(150)
        start_date_time_edit.setFont(small_font)

        end_date_time_edit = QDateTimeEdit(self)
        end_date_time_edit.setCalendarPopup(True)
        end_date_time_edit.setDateTime(QDateTime.currentDateTime().addDays(1))
        end_date_time_edit.setDisplayFormat("yyyy-MM-dd HH:mm")
        end_date_time_edit.setFixedWidth(150)
        end_date_time_edit.setFont(small_font)

        delete_btn = QPushButton("X")
        delete_btn.setFont(small_font)
        delete_btn.clicked.connect(lambda: self.remove_filter_field(date_range_layout))

        date_range_layout.addWidget(start_date_time_edit)
        date_range_layout.addWidget(QLabel(" to "))
        date_range_layout.addWidget(end_date_time_edit)
        date_range_layout.addWidget(delete_btn)

        self.request_frame.layout().insertLayout(7, date_range_layout)
        self.filter_layouts.append((date_range_layout, start_date_time_edit, end_date_time_edit))




    def add_filter_field(self):
        # Jorizontal layout
        filter_layout = QHBoxLayout()

        # Key and value input
        key_edit = QLineEdit()
        key_edit.setPlaceholderText("Key")
        value_edit = QLineEdit()
        value_edit.setPlaceholderText("Value")

        # Delete button
        delete_btn = QPushButton("X")
        delete_btn.clicked.connect(lambda: self.remove_filter_field(filter_layout))

        # Add widgets
        filter_layout.addWidget(key_edit)
        filter_layout.addWidget(value_edit)
        filter_layout.addWidget(delete_btn)


        self.request_frame.layout().insertLayout(6, filter_layout)
        self.filter_layouts.append((filter_layout, key_edit, value_edit))


    def remove_filter_field(self, layout):
        layout.setEnabled(False)
        for i in reversed(range(layout.count())): 
            widget = layout.itemAt(i).widget()
            if widget is not None:
                widget.deleteLater()
        layout.deleteLater()
        self.filter_layouts = [(lay, key, val) for lay, key, val in self.filter_layouts if lay != layout]


    def on_key_select(self):
        self.update_data_table()


    from PyQt5.QtCore import QDateTime, QDate

    def update_data_table(self):
        selected_keys = [item.text() for item in self.json_keys_listbox.selectedItems()]
        self.model.clear()
        self.model.setHorizontalHeaderLabels(selected_keys)

        date_fields = ['begin at', 'end at']

        for data in self.current_json_data:
            row = []
            for key in selected_keys:
                value = data.get(key, '')
                if key in date_fields:
                    print(key)
                    try:
                        # Formatting not working as for now
                        datetime_value = QDateTime.fromString(value, "yyyy-MM-ddTHH:mm:ssZ")
                        formatted_date = datetime_value.toString("dd/MM/yyyy HH:mm")
                        item = QStandardItem(formatted_date)
                        print(item)
                    except Exception as e:
                        print(f"Error parsing date: {e}")
                        item = QStandardItem(value)  # Use original value if parsing fails
                elif isinstance(value, (int, float)):
                    item = QStandardItem()
                    item.setData(value, Qt.DisplayRole)
                else:
                    item = QStandardItem(str(value))
                row.append(item)
            self.model.appendRow(row)




    def update_json_keys_listbox(self, json_data):
        unique_keys = set()
     #   print(json_data)
        for item in json_data:
            if isinstance(item, dict):
                unique_keys.update(item.keys())
            else:
                continue
        self.json_keys_listbox.clear()
        self.json_keys_listbox.addItems(sorted(unique_keys))



if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = IntraAPIClient()
    ex.show()
    sys.exit(app.exec_())
