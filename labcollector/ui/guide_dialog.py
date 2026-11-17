"""Help > User guide: shows docs/USER_GUIDE.md, with its screenshots, inside the app."""

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QColor, QImage, QTextBlock, QTextBlockFormat, QTextCursor, QTextTable
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QTextBrowser, QVBoxLayout, QWidget

# The screenshots are saved at twice the size they're shown at, so they stay sharp on screens
# scaled to 125% or 150%. Wide ones are shrunk to fit the window, without sideways scrolling.
SCREENSHOT_SCALE = 2
PAGE_MARGIN = 28


class GuideDialog(QDialog):
    def __init__(self, guide: Path, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Lab Collector user guide")
        screen = self.screen().availableGeometry()  # fit small laptop screens too
        self.resize(min(1000, screen.width() - 40), min(800, screen.height() - 60))

        self.browser = QTextBrowser()
        if guide.exists():
            # Qt shows a .md file as formatted text; image paths in it are relative to the file.
            self.browser.setSource(QUrl.fromLocalFile(str(guide)))
            self._add_space(guide.parent)
        else:
            self.browser.setPlainText(f"The user guide wasn't found:\n{guide}")

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self.browser)
        layout.addWidget(buttons)

    def _add_space(self, folder: Path) -> None:
        """Qt shows Markdown tightly packed: add room around the text, headings and tables."""
        document = self.browser.document()
        document.setDocumentMargin(PAGE_MARGIN)
        # The room left for a picture: the window minus the page margins, scroll bar and frame.
        max_image_width = self.width() - 2 * PAGE_MARGIN - 60
        cursor = QTextCursor(document)
        block = document.begin()
        while block.isValid():
            has_image = self._show_images_at_normal_size(block, cursor, folder, max_image_width)
            spacing = block.blockFormat()
            if not has_image:  # extra line height under a picture would leave a big gap
                spacing.setLineHeight(
                    140, QTextBlockFormat.LineHeightTypes.ProportionalHeight.value
                )
            spacing.setBottomMargin(16 if has_image else 6)
            if spacing.headingLevel():
                spacing.setTopMargin(22 if spacing.headingLevel() <= 2 else 14)
            cursor.setPosition(block.position())
            cursor.setBlockFormat(spacing)
            block = block.next()

        for frame in document.rootFrame().childFrames():
            if isinstance(frame, QTextTable):
                table = frame.format()
                table.setCellPadding(6)
                table.setCellSpacing(0)
                table.setBorder(1)
                table.setBorderBrush(QColor("#d1d9e0"))
                table.setBorderCollapse(True)
                frame.setFormat(table)

    @staticmethod
    def _show_images_at_normal_size(
        block: QTextBlock, cursor: QTextCursor, folder: Path, max_width: int
    ) -> bool:
        """Show the block's 2x screenshots at normal size. Returns True if it has any."""
        has_image = False
        fragments = block.begin()
        while not fragments.atEnd():
            fragment = fragments.fragment()
            if fragment.charFormat().isImageFormat():
                has_image = True
                image = fragment.charFormat().toImageFormat()
                width = QImage(str(folder / image.name())).width()
                image.setWidth(min(width / SCREENSHOT_SCALE, max_width))
                cursor.setPosition(fragment.position())
                cursor.setPosition(
                    fragment.position() + fragment.length(), QTextCursor.MoveMode.KeepAnchor
                )
                cursor.setCharFormat(image)
            fragments += 1
        return has_image
