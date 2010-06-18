# Copyright (c) 2010 AG Projects. See LICENSE for details.
#

from __future__ import with_statement

__all__ = ['Conference', 'SessionItem', 'SessionModel', 'SessionListView']

import cPickle as pickle

from PyQt4 import uic
from PyQt4.QtCore import Qt, QAbstractListModel, QByteArray, QEvent, QMimeData, QModelIndex, QSize, QStringList, QTimer, pyqtSignal
from PyQt4.QtGui  import QAction, QBrush, QColor, QDrag, QLinearGradient, QListView, QMenu, QPainter, QPen, QPixmap, QStyle, QStyledItemDelegate

from application.python.util import Null

from blink.resources import Resources
from blink.widgets.buttons import LeftSegment, MiddleSegment, RightSegment


class SessionItem(object):
    def __init__(self, name, uri, streams):
        self.name = name
        self.uri = uri
        self.streams = streams
        self.widget = Null
        self.conference = None
        self.type = None
        self.codec_info = ''
        self.tls = False
        self.srtp = False
        self.latency = 0
        self.packet_loss = 0

    def __reduce__(self):
        return (self.__class__, (self.name, self.uri, self.streams), None)

    def _get_conference(self):
        return self.__dict__['conference']

    def _set_conference(self, conference):
        old_conference = self.__dict__.get('conference', Null)
        if old_conference is conference:
            return
        if old_conference is not None:
            old_conference.remove_session(self)
        if conference is not None:
            conference.add_session(self)
        self.__dict__['conference'] = conference

    conference = property(_get_conference, _set_conference)
    del _get_conference, _set_conference

    def _get_type(self):
        return self.__dict__['type']

    def _set_type(self, value):
        if self.__dict__.get('type', Null) == value:
            return
        self.__dict__['type'] = value
        self.widget.stream_info_label.session_type = value

    type = property(_get_type, _set_type)
    del _get_type, _set_type

    def _get_codec_info(self):
        return self.__dict__['codec_info']

    def _set_codec_info(self, value):
        if self.__dict__.get('codec_info', None) == value:
            return
        self.__dict__['codec_info'] = value
        self.widget.stream_info_label.codec_info = value

    codec_info = property(_get_codec_info, _set_codec_info)
    del _get_codec_info, _set_codec_info

    def _get_tls(self):
        return self.__dict__['tls']

    def _set_tls(self, value):
        if self.__dict__.get('tls', None) == value:
            return
        self.__dict__['tls'] = value
        self.widget.tls_label.setVisible(bool(value))

    tls = property(_get_tls, _set_tls)
    del _get_tls, _set_tls

    def _get_srtp(self):
        return self.__dict__['srtp']

    def _set_srtp(self, value):
        if self.__dict__.get('srtp', None) == value:
            return
        self.__dict__['srtp'] = value
        self.widget.srtp_label.setVisible(bool(value))

    srtp = property(_get_srtp, _set_srtp)
    del _get_srtp, _set_srtp

    def _get_latency(self):
        return self.__dict__['latency']

    def _set_latency(self, value):
        if self.__dict__.get('latency', None) == value:
            return
        self.__dict__['latency'] = value
        self.widget.latency_label.value = value

    latency = property(_get_latency, _set_latency)
    del _get_latency, _set_latency

    def _get_packet_loss(self):
        return self.__dict__['packet_loss']

    def _set_packet_loss(self, value):
        if self.__dict__.get('packet_loss', None) == value:
            return
        self.__dict__['packet_loss'] = value
        self.widget.packet_loss_label.value = value

    packet_loss = property(_get_packet_loss, _set_packet_loss)
    del _get_packet_loss, _set_packet_loss


class Conference(object):
    def __init__(self):
        self.sessions = []

    def add_session(self, session):
        if self.sessions:
            self.sessions[-1].widget.conference_position = Top if len(self.sessions)==1 else Middle
            session.widget.conference_position = Bottom
        else:
            session.widget.conference_position = None
        session.widget.mute_button.show()
        self.sessions.append(session)

    def remove_session(self, session):
        session.widget.conference_position = None
        session.widget.mute_button.hide()
        self.sessions.remove(session)
        session_count = len(self.sessions)
        if session_count == 1:
            self.sessions[0].widget.conference_position = None
            self.sessions[0].widget.mute_button.hide()
        elif session_count > 1:
            self.sessions[0].widget.conference_position = Top
            self.sessions[-1].widget.conference_position = Bottom
            for sessions in self.sessions[1:-1]:
                session.widget.conference_position = Middle


# Positions for sessions in conferences.
#
class Top(object): pass
class Middle(object): pass
class Bottom(object): pass


ui_class, base_class = uic.loadUiType(Resources.get('session.ui'))

class SessionWidget(base_class, ui_class):
    def __init__(self, session, parent=None):
        super(SessionWidget, self).__init__(parent)
        with Resources.directory:
            self.setupUi(self)
        # add a left margin for the colored band
        self.address_layout.setContentsMargins(8, -1, -1, -1)
        self.stream_layout.setContentsMargins(8, -1, -1, -1)
        self.bottom_layout.setContentsMargins(8, -1, -1, -1)
        font = self.latency_label.font()
        font.setPointSizeF(self.status_label.fontInfo().pointSizeF() - 1)
        self.latency_label.setFont(font)
        font = self.packet_loss_label.font()
        font.setPointSizeF(self.status_label.fontInfo().pointSizeF() - 1)
        self.packet_loss_label.setFont(font)
        self.mute_button.type = LeftSegment
        self.hold_button.type = MiddleSegment
        self.record_button.type = MiddleSegment
        self.hangup_button.type = RightSegment
        self.selected = False
        self.drop_indicator = False
        self.conference_position = None
        self._disable_dnd = False
        self.setFocusProxy(parent)
        self.mute_button.hidden.connect(self._mute_button_hidden)
        self.mute_button.shown.connect(self._mute_button_shown)
        self.mute_button.pressed.connect(self._tool_button_pressed)
        self.hold_button.pressed.connect(self._tool_button_pressed)
        self.record_button.pressed.connect(self._tool_button_pressed)
        self.hangup_button.pressed.connect(self._tool_button_pressed)
        self.mute_button.hide()
        self.address_label.setText(session.name or session.uri)
        self.stream_info_label.session_type = session.type
        self.stream_info_label.codec_info = session.codec_info
        self.latency_label.value = session.latency
        self.packet_loss_label.value = session.packet_loss
        self.tls_label.setVisible(bool(session.tls))
        self.srtp_label.setVisible(bool(session.srtp))

    def _get_selected(self):
        return self.__dict__['selected']

    def _set_selected(self, value):
        if self.__dict__.get('selected', None) == value:
            return
        self.__dict__['selected'] = value
        self.update()

    selected = property(_get_selected, _set_selected)
    del _get_selected, _set_selected

    def _get_drop_indicator(self):
        return self.__dict__['drop_indicator']

    def _set_drop_indicator(self, value):
        if self.__dict__.get('drop_indicator', None) == value:
            return
        self.__dict__['drop_indicator'] = value
        self.update()

    drop_indicator = property(_get_drop_indicator, _set_drop_indicator)
    del _get_drop_indicator, _set_drop_indicator

    def _get_conference_position(self):
        return self.__dict__['conference_position']

    def _set_conference_position(self, value):
        if self.__dict__.get('conference_position', Null) == value:
            return
        self.__dict__['conference_position'] = value
        self.update()

    conference_position = property(_get_conference_position, _set_conference_position)
    del _get_conference_position, _set_conference_position

    def _mute_button_hidden(self):
        self.hold_button.type = LeftSegment

    def _mute_button_shown(self):
        self.hold_button.type = MiddleSegment

    def _tool_button_pressed(self):
        self._disable_dnd = True

    def mousePressEvent(self, event):
        self._disable_dnd = False
        super(SessionWidget, self).mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._disable_dnd:
            return
        super(SessionWidget, self).mouseMoveEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        rect = self.rect()

        # draw inner rect and border
        #
        if self.selected:
            background = QLinearGradient(0, 0, 10, 0)
            background.setColorAt(0.00, QColor('#75c0ff'))
            background.setColorAt(0.99, QColor('#75c0ff'))
            background.setColorAt(1.00, QColor('#ffffff'))
            painter.setBrush(QBrush(background))
            painter.setPen(QPen(QBrush(QColor('#606060' if self.conference_position is None else '#b0b0b0')), 2.0))
        elif self.conference_position is not None:
            background = QLinearGradient(0, 0, 10, 0)
            background.setColorAt(0.00, QColor('#95ff95'))
            background.setColorAt(0.99, QColor('#95ff95'))
            background.setColorAt(1.00, QColor('#ffffff'))
            painter.setBrush(QBrush(background))
            painter.setPen(QPen(QBrush(QColor('#b0b0b0')), 2.0))
        else:
            background = QLinearGradient(0, 0, 10, 0)
            background.setColorAt(0.00, QColor('#d0d0d0'))
            background.setColorAt(0.99, QColor('#d0d0d0'))
            background.setColorAt(1.00, QColor('#ffffff'))
            painter.setBrush(QBrush(background))
            painter.setPen(QPen(QBrush(QColor('#b0b0b0')), 2.0))
        painter.drawRoundedRect(rect.adjusted(2, 2, -2, -2), 3, 3)

        # for conferences extend the left marker over the whole conference
        #
        if self.conference_position is not None:
            painter.setPen(Qt.NoPen)
            left_rect = rect.adjusted(0, 0, 10-rect.width(), 0)
            if self.conference_position is Top:
                painter.drawRect(left_rect.adjusted(2, 5, 0, 5))
            elif self.conference_position is Middle:
                painter.drawRect(left_rect.adjusted(2, -5, 0, 5))
            elif self.conference_position is Bottom:
                painter.drawRect(left_rect.adjusted(2, -5, 0, -5))

        # draw outer border
        #
        if self.selected or self.drop_indicator:
            painter.setBrush(Qt.NoBrush)
            if self.drop_indicator:
                painter.setPen(QPen(QBrush(QColor('#dc3169')), 2.0))
            elif self.selected:
                painter.setPen(QPen(QBrush(QColor('#3075c0')), 2.0)) # or #2070c0 (next best look) or gray: #606060

            if self.conference_position is Top:
                painter.drawRoundedRect(rect.adjusted(2, 2, -2, 5), 3, 3)
                painter.drawRoundedRect(rect.adjusted(1, 1, -1, 5), 3, 3)
            elif self.conference_position is Middle:
                painter.drawRoundedRect(rect.adjusted(2, -5, -2, 5), 3, 3)
                painter.drawRoundedRect(rect.adjusted(1, -5, -1, 5), 3, 3)
            elif self.conference_position is Bottom:
                painter.drawRoundedRect(rect.adjusted(2, -5, -2, -2), 3, 3)
                painter.drawRoundedRect(rect.adjusted(1, -5, -1, -1), 3, 3)
            else:
                painter.drawRoundedRect(rect.adjusted(2, 2, -2, -2), 3, 3)
                painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 3, 3)
        elif self.conference_position is not None:
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(QBrush(QColor('#309030')), 2.0)) # or 237523, #2b8f2b
            if self.conference_position is Top:
                painter.drawRoundedRect(rect.adjusted(2, 2, -2, 5), 3, 3)
            elif self.conference_position is Middle:
                painter.drawRoundedRect(rect.adjusted(2, -5, -2, 5), 3, 3)
            elif self.conference_position is Bottom:
                painter.drawRoundedRect(rect.adjusted(2, -5, -2, -2), 3, 3)
            else:
                painter.drawRoundedRect(rect.adjusted(2, 2, -2, -2), 3, 3)

        painter.end()
        super(SessionWidget, self).paintEvent(event)


class DraggedSessionWidget(base_class, ui_class):
    """Used to draw a dragged session item"""
    def __init__(self, session_widget, parent=None):
        super(DraggedSessionWidget, self).__init__(parent)
        with Resources.directory:
            self.setupUi(self)
        # add a left margin for the colored band
        self.address_layout.setContentsMargins(8, -1, -1, -1)
        self.stream_layout.setContentsMargins(8, -1, -1, -1)
        self.bottom_layout.setContentsMargins(8, -1, -1, -1)
        self.mute_button.hide()
        self.hold_button.hide()
        self.record_button.hide()
        self.hangup_button.hide()
        self.tls_label.hide()
        self.srtp_label.hide()
        self.latency_label.hide()
        self.packet_loss_label.hide()
        self.duration_label.hide()
        self.stream_info_label.setText(u'')
        self.address_label.setText(session_widget.address_label.text())
        self.selected = session_widget.selected
        self.in_conference = session_widget.conference_position is not None
        if self.in_conference:
            self.status_label.setText(u'Drop outside the conference to detach')
        else:
            self.status_label.setText(u'Drop over a session to conference them')


    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        if self.in_conference:
            background = QLinearGradient(0, 0, 10, 0)
            background.setColorAt(0.00, QColor('#95ff95'))
            background.setColorAt(0.99, QColor('#95ff95'))
            background.setColorAt(1.00, QColor('#f8f8f8'))
            painter.setBrush(QBrush(background))
            painter.setPen(QPen(QBrush(QColor('#309030')), 2.0))
        elif self.selected:
            background = QLinearGradient(0, 0, 10, 0)
            background.setColorAt(0.00, QColor('#75c0ff'))
            background.setColorAt(0.99, QColor('#75c0ff'))
            background.setColorAt(1.00, QColor('#f8f8f8'))
            painter.setBrush(QBrush(background))
            painter.setPen(QPen(QBrush(QColor('#3075c0')), 2.0))
        else:
            background = QLinearGradient(0, 0, 10, 0)
            background.setColorAt(0.00, QColor('#d0d0d0'))
            background.setColorAt(0.99, QColor('#d0d0d0'))
            background.setColorAt(1.00, QColor('#f8f8f8'))
            painter.setBrush(QBrush(background))
            painter.setPen(QPen(QBrush(QColor('#808080')), 2.0))
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 3, 3)
        painter.end()
        super(DraggedSessionWidget, self).paintEvent(event)

del ui_class, base_class


class SessionDelegate(QStyledItemDelegate):
    size_hint = QSize(200, 62)

    def __init__(self, parent=None):
        super(SessionDelegate, self).__init__(parent)

    def createEditor(self, parent, options, index):
        session = index.model().data(index, Qt.DisplayRole)
        session.widget = SessionWidget(session, parent)
        return session.widget

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)

    def paint(self, painter, option, index):
        session = index.model().data(index, Qt.DisplayRole)
        if session.widget.size() != option.rect.size():
            # For some reason updateEditorGeometry only receives the peak value
            # of the size that the widget ever had, so it will never shrink it.
            session.widget.resize(option.rect.size())

    def sizeHint(self, option, index):
        return self.size_hint


class SessionModel(QAbstractListModel):
    sessionAdded = pyqtSignal(SessionItem)
    sessionRemoved = pyqtSignal(SessionItem)

    # The MIME types we accept in drop operations, in the order they should be handled
    accepted_mime_types = ['application/x-blink-session-list', 'application/x-blink-contact-list']

    def __init__(self, parent=None):
        super(SessionModel, self).__init__(parent)
        self.sessions = []
        self.main_window = parent
        self.session_list = parent.session_list

    def flags(self, index):
        if index.isValid():
            return QAbstractListModel.flags(self, index) | Qt.ItemIsDropEnabled | Qt.ItemIsDragEnabled | Qt.ItemIsEditable
        else:
            return QAbstractListModel.flags(self, index)

    def rowCount(self, parent=QModelIndex()):
        return len(self.sessions)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or role != Qt.DisplayRole:
            return None
        return self.sessions[index.row()]

    def supportedDropActions(self):
        return Qt.CopyAction | Qt.MoveAction

    def mimeTypes(self):
        return QStringList(['application/x-blink-session-list'])

    def mimeData(self, indexes):
        mime_data = QMimeData()
        sessions = [self.sessions[index.row()] for index in indexes if index.isValid()]
        if sessions:
            mime_data.setData('application/x-blink-session-list', QByteArray(pickle.dumps(sessions)))
        return mime_data

    def dropMimeData(self, mime_data, action, row, column, parent_index):
        # this is here just to keep the default Qt DnD API happy
        # the custom handler is in handleDroppedData
        return False

    def handleDroppedData(self, mime_data, action, index):
        if action == Qt.IgnoreAction:
            return True

        for mime_type in self.accepted_mime_types:
            if mime_data.hasFormat(mime_type):
                name = mime_type.replace('/', ' ').replace('-', ' ').title().replace(' ', '')
                handler = getattr(self, '_DH_%s' % name)
                return handler(mime_data, action, index)
        else:
            return False

    def _DH_ApplicationXBlinkSessionList(self, mime_data, action, index):
        session_list = self.session_list
        selection_model = session_list.selectionModel()
        selection_mode = session_list.selectionMode()
        session_list.setSelectionMode(session_list.NoSelection)
        source = self.session_list.dragged_session
        target = self.sessions[index.row()] if index.isValid() else None
        if source.conference is None:
            # the dragged session is not in a conference yet
            if target is None:
                return False
            source_selected = source.widget.selected
            target_selected = target.widget.selected
            if target.conference is not None:
                self._remove_session(source)
                position = self.sessions.index(target.conference.sessions[-1]) + 1
                self.beginInsertRows(QModelIndex(), position, position)
                self.sessions.insert(position, source)
                self.endInsertRows()
                session_list.openPersistentEditor(self.index(position))
                source.conference = target.conference
                source_index = self.index(position)
                if source_selected:
                    selection_model.select(source_index, selection_model.Select)
                elif target_selected:
                    source.widget.selected = True
                session_list.scrollTo(source_index, session_list.EnsureVisible) # or PositionAtBottom
            else:
                source_row = self.sessions.index(source)
                target_row = index.row()
                first, last = (source, target) if source_row < target_row else (target, source)
                self._remove_session(source)
                self._remove_session(target)
                self.beginInsertRows(QModelIndex(), 0, 1)
                self.sessions[0:0] = [first, last]
                self.endInsertRows()
                session_list.openPersistentEditor(self.index(0))
                session_list.openPersistentEditor(self.index(1))
                conference = Conference()
                first.conference = conference
                last.conference = conference
                if source_selected:
                    selection_model.select(self.index(self.sessions.index(source)), selection_model.Select)
                elif target_selected:
                    selection_model.select(self.index(self.sessions.index(target)), selection_model.Select)
                session_list.scrollToTop()
        else:
            # the dragged session is in a conference
            if target is not None and target.conference is source.conference:
                return False
            conference = source.conference
            if len(conference.sessions) == 2:
                conference_selected = source.widget.selected
                first, last = conference.sessions
                sibling = first if source is last else last
                source.conference = None
                sibling.conference = None
                self._remove_session(first)
                self._remove_session(last)
                self._add_session(first)
                self._add_session(last)
                if conference_selected:
                    selection_model.select(self.index(self.sessions.index(sibling)), selection_model.ClearAndSelect)
                session_list.scrollToBottom()
            else:
                selected_index = selection_model.selectedIndexes()[0]
                if self.sessions[selected_index.row()] is source:
                    sibling = (session for session in source.conference.sessions if session is not source).next()
                    selection_model.select(self.index(self.sessions.index(sibling)), selection_model.ClearAndSelect)
                source.conference = None
                self._remove_session(source)
                self._add_session(source)
                position = self.sessions.index(conference.sessions[0])
                session_list.scrollTo(self.index(position), session_list.PositionAtCenter)
        session_list.setSelectionMode(selection_mode)
        return True

    def _DH_ApplicationXBlinkContactList(self, mime_data, action, index):
        return False

    def _add_session(self, session):
        position = len(self.sessions)
        self.beginInsertRows(QModelIndex(), position, position)
        self.sessions.append(session)
        self.session_list.openPersistentEditor(self.index(position))
        self.endInsertRows()

    def _remove_session(self, session):
        position = self.sessions.index(session)
        self.beginRemoveRows(QModelIndex(), position, position)
        del self.sessions[position]
        self.endRemoveRows()

    def addSession(self, session):
        if session in self.sessions:
            return
        self._add_session(session)
        self.sessionAdded.emit(session)

    def removeSession(self, session):
        if session not in self.sessions:
            return
        self._remove_session(session)
        self.sessionRemoved.emit(session)

    def test(self):
        self.addSession(SessionItem('Dan Pascu', 'dan@umts.ro', []))
        self.addSession(SessionItem('Lucian Stanescu', 'luci@umts.ro', []))
        self.addSession(SessionItem('Adrian Georgescu', 'adi@umts.ro', []))
        self.addSession(SessionItem('Saul Ibarra', 'saul@umts.ro', []))
        self.addSession(SessionItem('Tijmen de Mes', 'tijmen@umts.ro', []))
        self.addSession(SessionItem('Test Call', '3333@umts.ro', []))
        conference = Conference()
        self.sessions[0].conference = conference
        self.sessions[1].conference = conference
        conference = Conference()
        self.sessions[2].conference = conference
        self.sessions[3].conference = conference
        session = self.sessions[0]
        session.type, session.codec_info = 'HD Audio', 'speex 32kHz'
        session.tls, session.srtp, session.latency, session.packet_loss = True,  True,  100, 20
        session = self.sessions[1]
        session.type, session.codec_info = 'HD Audio', 'speex 32kHz'
        session.tls, session.srtp, session.latency, session.packet_loss = True,  True,   80, 20
        session = self.sessions[2]
        session.type, session.codec_info = 'HD Audio', 'speex 32kHz'
        session.tls, session.srtp, session.latency, session.packet_loss = True,  False, 150,  0
        session = self.sessions[3]
        session.type, session.codec_info = 'HD Audio', 'speex 32kHz'
        session.tls, session.srtp, session.latency, session.packet_loss = False, False, 180, 20
        session = self.sessions[4]
        session.type, session.codec_info = 'Video', 'H.264 512kbit, PCM 8kHz'
        session.tls, session.srtp, session.latency, session.packet_loss = True,  True,    0,  0
        session = self.sessions[5]
        session.type, session.codec_info = 'Audio', 'PCM 8kHz'
        session.tls, session.srtp, session.latency, session.packet_loss = True,  True,  540, 50


class ContextMenuActions(object):
    pass


class SessionListView(QListView):
    def __init__(self, parent=None):
        super(SessionListView, self).__init__(parent)
        self.setItemDelegate(SessionDelegate(self))
        self.setDropIndicatorShown(False)
        self.actions = ContextMenuActions()
        self.dragged_session = None
        self._pressed_position = None
        self._pressed_index = None

    def setModel(self, model):
        selection_model = self.selectionModel() or Null
        selection_model.selectionChanged.disconnect(self._selection_changed)
        super(SessionListView, self).setModel(model)
        self.selectionModel().selectionChanged.connect(self._selection_changed)

    def _selection_changed(self, selected, deselected):
        model = self.model()
        for session in (model.data(index) for index in deselected.indexes()):
            if session.conference is not None:
                for sibling in session.conference.sessions:
                    sibling.widget.selected = False
            else:
                session.widget.selected = False
        for session in (model.data(index) for index in selected.indexes()):
            if session.conference is not None:
                for sibling in session.conference.sessions:
                    sibling.widget.selected = True
            else:
                session.widget.selected = True

    def contextMenuEvent(self, event):
        pass

    def mousePressEvent(self, event):
        self._pressed_position = event.pos()
        self._pressed_index = self.indexAt(self._pressed_position)
        super(SessionListView, self).mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self._pressed_position = None
        self._pressed_index = None
        super(SessionListView, self).mouseReleaseEvent(event)

    def selectionCommand(self, index, event=None):
        selection_model = self.selectionModel()
        if self.selectionMode() == self.NoSelection:
            return selection_model.NoUpdate
        elif not index.isValid() or event is None:
            return selection_model.NoUpdate
        elif event.type() == QEvent.MouseButtonPress and not selection_model.selectedIndexes():
            return selection_model.ClearAndSelect
        elif event.type() in (QEvent.MouseButtonPress, QEvent.MouseMove):
            return selection_model.NoUpdate
        elif event.type() == QEvent.MouseButtonRelease:
            return selection_model.ClearAndSelect
        else:
            return super(SessionListView, self).selectionCommand(index, event)

    def startDrag(self, supported_actions):
        if self._pressed_index is not None and self._pressed_index.isValid():
            model = self.model()
            self.dragged_session = model.data(self._pressed_index)
            rect = self.visualRect(self._pressed_index)
            rect.adjust(1, 1, -1, -1)
            pixmap = QPixmap(rect.size())
            pixmap.fill(Qt.transparent)
            widget = DraggedSessionWidget(self.dragged_session.widget, None)
            widget.resize(rect.size())
            widget.render(pixmap)
            drag = QDrag(self)
            drag.setPixmap(pixmap)
            drag.setMimeData(model.mimeData([self._pressed_index]))
            drag.setHotSpot(self._pressed_position - rect.topLeft())
            drag.exec_(supported_actions, Qt.CopyAction)
            self.dragged_session = None
            self._pressed_position = None
            self._pressed_index = None

    def dragEnterEvent(self, event):
        event_source = event.source()
        accepted_mime_types = set(self.model().accepted_mime_types)
        provided_mime_types = set(str(x) for x in event.mimeData().formats())
        acceptable_mime_types = accepted_mime_types & provided_mime_types
        if not acceptable_mime_types:
            event.ignore() # no acceptable mime types found
        elif event_source is not self and 'application/x-blink-session-list' in provided_mime_types:
            event.ignore() # we don't handle drops for blink sessions from other sources
        else:
            if event_source is self:
                event.setDropAction(Qt.MoveAction)
            event.accept()
            self.setState(self.DraggingState)

    def dragLeaveEvent(self, event):
        super(SessionListView, self).dragLeaveEvent(event)
        for session in self.model().sessions:
            session.widget.drop_indicator = False

    def dragMoveEvent(self, event):
        super(SessionListView, self).dragMoveEvent(event)
        if event.source() is self:
            event.setDropAction(Qt.MoveAction)

        model = self.model()

        for session in model.sessions:
            session.widget.drop_indicator = False

        for mime_type in model.accepted_mime_types:
            if event.provides(mime_type):
                index = self.indexAt(event.pos())
                rect = self.visualRect(index)
                session = self.model().data(index)
                name = mime_type.replace('/', ' ').replace('-', ' ').title().replace(' ', '')
                handler = getattr(self, '_DH_%s' % name)
                handler(event, index, rect, session)
                break
        else:
            event.ignore()

    def dropEvent(self, event):
        model = self.model()
        if event.source() is self:
            event.setDropAction(Qt.MoveAction)
        for session in self.model().sessions:
            session.widget.drop_indicator = False
        if model.handleDroppedData(event.mimeData(), event.dropAction(), self.indexAt(event.pos())):
            event.accept()
        super(SessionListView, self).dropEvent(event)

    def _DH_ApplicationXBlinkSessionList(self, event, index, rect, session):
        dragged_session = self.dragged_session
        if not index.isValid():
            model = self.model()
            rect = self.viewport().rect()
            rect.setTop(self.visualRect(model.index(len(model.sessions)-1)).bottom())
            if dragged_session.conference is not None:
                event.accept(rect)
            else:
                event.ignore(rect)
        else:
            conference = dragged_session.conference or Null
            if dragged_session is session or session in conference.sessions:
                event.ignore(rect)
            else:
                if dragged_session.conference is None:
                    if session.conference is not None:
                        for sibling in session.conference.sessions:
                            sibling.widget.drop_indicator = True
                    else:
                        session.widget.drop_indicator = True
                event.accept(rect)

    def _DH_ApplicationXBlinkContactList(self, event, index, rect, session):
        model = self.model()
        if not index.isValid():
            rect = self.viewport().rect()
            rect.setTop(self.visualRect(model.index(len(model.sessions)-1)).bottom())
            event.ignore(rect)
        else:
            event.accept(rect)
            if session.conference is not None:
                for sibling in session.conference.sessions:
                    sibling.widget.drop_indicator = True
            else:
                session.widget.drop_indicator = True


ui_class, base_class = uic.loadUiType(Resources.get('incoming_dialog.ui'))

class IncomingDialog(base_class, ui_class):
    def __init__(self, parent=None):
        super(IncomingDialog, self).__init__(parent)
        with Resources.directory:
            self.setupUi(self)
        font = self.username_label.font()
        font.setPointSizeF(self.uri_label.fontInfo().pointSizeF() + 3)
        font.setFamily("Sans Serif")
        self.username_label.setFont(font)
        font = self.note_label.font()
        font.setPointSizeF(self.uri_label.fontInfo().pointSizeF() - 1)
        self.note_label.setFont(font)
        self.reject_mode = 'ignore'
        self.busy_button.released.connect(self._set_busy_mode)
        self.reject_button.released.connect(self._set_reject_mode)
        for stream in self.streams:
            stream.toggled.connect(self._update_accept_button)
            stream.hidden.connect(self._update_streams_layout)
            stream.shown.connect(self._update_streams_layout)
        self.desktopsharing_stream.hidden.connect(self.desktopsharing_label.hide)
        self.desktopsharing_stream.shown.connect(self.desktopsharing_label.show)
        for stream in self.streams:
            stream.hide()

    @property
    def streams(self):
        return (self.audio_stream, self.chat_stream, self.desktopsharing_stream, self.video_stream)

    @property
    def accepted_streams(self):
        return [stream for stream in self.streams if stream.in_use and stream.accepted]

    def _set_busy_mode(self):
        self.reject_mode = 'busy'

    def _set_reject_mode(self):
        self.reject_mode = 'reject'

    def _update_accept_button(self):
        was_enabled = self.accept_button.isEnabled()
        self.accept_button.setEnabled(len(self.accepted_streams) > 0)
        if self.accept_button.isEnabled() != was_enabled:
            self.accept_button.setFocus()

    def _update_streams_layout(self):
        if len([stream for stream in self.streams if stream.in_use]) > 1:
            self.audio_stream.active = True
            self.chat_stream.active = True
            self.desktopsharing_stream.active = True
            self.video_stream.active = True
            self.note_label.setText(u'To refuse a stream click its icon')
        else:
            self.audio_stream.active = False
            self.chat_stream.active = False
            self.desktopsharing_stream.active = False
            self.video_stream.active = False
            if self.audio_stream.in_use:
                self.note_label.setText(u'Audio call')
            elif self.chat_stream.in_use:
                self.note_label.setText(u'Chat session')
            elif self.video_stream.in_use:
                self.note_label.setText(u'Video call')
            elif self.desktopsharing_stream.in_use:
                self.note_label.setText(u'Desktop sharing request')
            else:
                self.note_label.setText(u'')
        self._update_accept_button()

del ui_class, base_class
