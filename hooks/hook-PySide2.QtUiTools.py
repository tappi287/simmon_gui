# Loading *.ui files from PySide2.QtUiTools will fail in freezed app
# from PySide2.QtUiTools.QUiLoader depends on QtXml
import logging

logger = logging.getLogger('user_hooks_logger')

hiddenimports = ["PySide2.QtXml", "PySide2.QtPrintSupport"]
logger.info('Included PySide2 QtUiTools hidden modules %s', hiddenimports)
