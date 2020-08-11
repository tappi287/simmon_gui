from qtpy.QtCore import QEasingCurve, QObject, QPropertyAnimation, QSize
from qtpy.QtWidgets import QPushButton, QWidget


class ExpandableWidget(QObject):
    def __init__(self, widget: QWidget, expand_btn: QPushButton=None):
        """ Method to add expandable widget functionality to a widget containing an collapsible widget

        :param widget: the widget which size will be changed
        :param expand_btn: the button which will toggle the expanded/collapsed state
        """
        super(ExpandableWidget, self).__init__(widget)

        self.widget = widget

        self.size_animation = QPropertyAnimation(self.widget, b'maximumSize')
        self.size_animation.setDuration(150)
        self.size_animation.setEasingCurve(QEasingCurve.OutCurve)
        self.size_animation.finished.connect(self.widget.updateGeometry)

        self.expand_toggle_btn = expand_btn or QPushButton(self)
        self.expand_toggle_btn.setCheckable(True)
        self.expand_toggle_btn.released.connect(self.expand_widget)

        self.org_resize = self.widget.resizeEvent
        self._initial_resize()

    def _initial_resize(self):
        if not self.expand_toggle_btn.isChecked():
            self.widget.setMaximumSize(QSize(self.widget.maximumWidth(), 0))

    def toggle_expand(self, immediate: bool=False):
        if self.expand_toggle_btn.isChecked():
            self.expand_toggle_btn.setChecked(False)
            self.expand_widget(immediate=immediate)
        else:
            self.expand_toggle_btn.setChecked(True)
            self.expand_widget(immediate=immediate)

    def expand_widget(self, immediate: bool=False):
        if self.expand_toggle_btn.isChecked():
            expand_height = self.widget.sizeHint().height()
        else:
            expand_height = 0

        expanded_size = QSize(self.widget.maximumWidth(), expand_height)

        self.size_animation.setStartValue(self.widget.size())
        self.size_animation.setEndValue(expanded_size)

        if immediate:
            self.widget.resize(expanded_size)
            self.widget.updateGeometry()
        else:
            self.size_animation.start()
