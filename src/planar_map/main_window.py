import os
from typing import Optional, List
from PyQt6.QtWidgets import (
    QMainWindow, QSplitter, QWidget, QVBoxLayout,
    QTabWidget, QTextBrowser, QPlainTextEdit, QPushButton,
    QLabel, QFileDialog, QMessageBox, QDialog, QFormLayout,
    QDialogButtonBox, QKeySequenceEdit, QSlider, QGroupBox
)
from PyQt6.QtCore import Qt, QRectF, QUrl
from PyQt6.QtGui import (
    QAction,
    QColor, QPainter, QKeySequence, QShortcut, QPdfWriter,
    QPageSize, QPageLayout, QTextDocument, QTextCursor,
    QTextBlockFormat, QTextFormat, QTextImageFormat, QImage
)

from planar_map.entity_list_widget import EntityListWidget
from planar_map.graph_models import GraphWidget
from planar_map.config import load_config, save_config


class ShortcutEditorDialog(QDialog):
    """A dialog to edit keyboard shortcuts natively."""

    def __init__(
        self,
        config_data: dict,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent=parent)
        self.setWindowTitle("Edit Shortcuts")
        self.config_data = config_data
        self.layout = QFormLayout(parent=self)
        self.edits: dict[str, QKeySequenceEdit] = {}

        for action, shortcut in self.config_data['shortcuts'].items():
            edit = QKeySequenceEdit(QKeySequence(shortcut))
            label_name = action.replace('_', ' ').title()
            self.layout.addRow(label_name, edit)
            self.edits[action] = edit

        buttons = (
            QDialogButtonBox.StandardButton.Save |
            QDialogButtonBox.StandardButton.Cancel
        )
        self.btns = QDialogButtonBox(buttons)
        self.btns.accepted.connect(self.accept)
        self.btns.rejected.connect(self.reject)
        self.layout.addWidget(self.btns)

    def get_updated_shortcuts(self) -> dict:
        return {
            action: edit.keySequence().toString()
            for action, edit in self.edits.items()
        }


class PhysicsWidget(QGroupBox):
    """A widget containing sliders to adjust physics parameters."""

    def __init__(self, main_window: 'MainWindow') -> None:
        super().__init__(title="Physics Settings")
        self.main_window = main_window
        self.layout = QFormLayout(parent=self)

        r_force = int(self._get_conf(key='repulsion_force'))
        self.rep_force_slider = self._make_slider(
            min_val=0, max_val=20000, init_val=r_force
        )

        r_range = int(self._get_conf(key='repulsion_range'))
        self.rep_range_slider = self._make_slider(
            min_val=0, max_val=1000, init_val=r_range
        )

        a_force = int(self._get_conf(key='attraction_force') * 1000)
        self.attr_force_slider = self._make_slider(
            min_val=0, max_val=200, init_val=a_force
        )

        s_len = int(self._get_conf(key='spring_length'))
        self.spring_len_slider = self._make_slider(
            min_val=0, max_val=500, init_val=s_len
        )

        self.layout.addRow("Repulsion Force", self.rep_force_slider)
        self.layout.addRow("Repulsion Range", self.rep_range_slider)
        self.layout.addRow("Attraction Force", self.attr_force_slider)
        self.layout.addRow("Spring Length", self.spring_len_slider)

    def _get_conf(self, key: str) -> float:
        return float(self.main_window.config['physics'][key])

    def _make_slider(
        self, min_val: int, max_val: int, init_val: int
    ) -> QSlider:
        s = QSlider(orientation=Qt.Orientation.Horizontal)
        s.setMinimum(min_val)
        s.setMaximum(max_val)
        s.setValue(init_val)
        s.valueChanged.connect(self._on_change)
        return s

    def _on_change(self) -> None:
        phys = self.main_window.config['physics']
        phys['repulsion_force'] = float(self.rep_force_slider.value())
        phys['repulsion_range'] = float(self.rep_range_slider.value())
        phys['attraction_force'] = float(
            self.attr_force_slider.value() / 1000.0
        )
        phys['spring_length'] = float(self.spring_len_slider.value())

        save_config(config=self.main_window.config)
        self.main_window.graph_widget.update_physics_params()


class MainWindow(QMainWindow):
    """Main application window holding the split layout (Graph / Markdown)."""

    def __init__(self, yaml_file: str) -> None:
        super().__init__()
        self.setWindowTitle(f"Obsidian Network - {yaml_file}")
        self.setMinimumSize(1000, 600)

        # Load config FIRST so the widgets can read the defaults
        self.config = load_config()

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.setCentralWidget(self.splitter)

        self.graph_widget = GraphWidget(
            yaml_file=yaml_file,
            main_window=self
        )
        self.splitter.addWidget(self.graph_widget)

        self.right_panel = QWidget()
        self.right_layout = QVBoxLayout(self.right_panel)

        self.file_label = QLabel(
            "Hover over a node to preview, double-click to edit."
        )
        self.file_label.setStyleSheet("font-weight: bold; color: #aaaaaa;")
        self.right_layout.addWidget(self.file_label)

        self.md_tabs = QTabWidget()
        self.md_preview = QTextBrowser()
        self.md_editor = QPlainTextEdit()

        # ... (keep existing md_preview and md_editor styles here) ...

        self.md_tabs.addTab(self.md_preview, "Preview")
        self.md_tabs.addTab(self.md_editor, "Editor")

        self.right_splitter = QSplitter(orientation=Qt.Orientation.Vertical)
        self.right_splitter.addWidget(self.md_tabs)

        self.entity_list = EntityListWidget(main_window=self)
        self.right_splitter.addWidget(self.entity_list)
        self.right_layout.addWidget(self.right_splitter)

        self.save_btn = QPushButton(text="Save Markdown Document")
        # ... (keep existing save_btn styles and connections here) ...
        self.right_layout.addWidget(self.save_btn)

        # ADD THE PHYSICS WIDGET AT THE BOTTOM OF THE RIGHT PANEL
        self.physics_widget = PhysicsWidget(main_window=self)
        self.right_layout.addWidget(self.physics_widget)

        self.splitter.addWidget(self.right_panel)
        self.splitter.setSizes([700, 300])

        self.current_md_file: Optional[str] = None
        self.active_shortcuts: List[QShortcut] = []

        self.apply_shortcuts()
        self._setup_menus()

        # Populate the tree widget with the loaded graph data
        self.entity_list.refresh_data()

    def _setup_menus(self) -> None:
        """Creates the main application menu bar and maps commands."""
        menu_bar = self.menuBar()

        # File Menu
        m_file = menu_bar.addMenu("File")

        a_open = QAction(text="Open YAML", parent=self)
        a_open.triggered.connect(slot=self.open_yaml)
        m_file.addAction(a_open)

        a_save = QAction(text="Save YAML", parent=self)
        a_save.triggered.connect(slot=self.graph_widget.save_yaml)
        m_file.addAction(a_save)

        m_file.addSeparator()

        a_short = QAction(text="Edit Shortcuts", parent=self)
        a_short.triggered.connect(slot=self.open_shortcut_editor)
        m_file.addAction(a_short)

        # Edit Menu
        m_edit = menu_bar.addMenu("Edit")

        a_cnode = QAction(text="Create Node", parent=self)
        a_cnode.triggered.connect(slot=self.graph_widget.create_node)
        m_edit.addAction(a_cnode)

        a_cedge = QAction(text="Create Edge", parent=self)
        a_cedge.triggered.connect(slot=self.graph_widget.create_edge)
        m_edit.addAction(a_cedge)

        m_edit.addSeparator()

        a_esel = QAction(text="Edit Selected", parent=self)
        a_esel.triggered.connect(slot=self.graph_widget.edit_selected)
        m_edit.addAction(a_esel)

        a_dsel = QAction(text="Delete Selected", parent=self)
        a_dsel.triggered.connect(slot=self.graph_widget.delete_selected)
        m_edit.addAction(a_dsel)

        # Export Menu
        m_export = menu_bar.addMenu("Export")

        a_egraph = QAction(text="Export Graph PDF", parent=self)
        a_egraph.triggered.connect(slot=self.export_graph_pdf)
        m_export.addAction(a_egraph)

        a_emd = QAction(text="Export Markdown PDF", parent=self)
        a_emd.triggered.connect(slot=self.export_markdown_pdf)
        m_export.addAction(a_emd)

        a_ecomp = QAction(text="Export Compilation PDF", parent=self)
        a_ecomp.triggered.connect(slot=self.export_compilation_pdf)
        m_export.addAction(a_ecomp)

    def open_shortcut_editor(self) -> None:
        dialog = ShortcutEditorDialog(config_data=self.config, parent=self)
        if dialog.exec():
            new_shortcuts = dialog.get_updated_shortcuts()
            self.config['shortcuts'].update(new_shortcuts)
            save_config(config=self.config)
            self.apply_shortcuts()
            QMessageBox.information(
                self,
                "Success",
                "Shortcuts updated successfully!"
            )

    def apply_shortcuts(self) -> None:
        for shortcut in self.active_shortcuts:
            shortcut.setEnabled(False)
            shortcut.deleteLater()
        self.active_shortcuts.clear()

        s = self.config.get('shortcuts', {})

        bindings = {
            'open_yaml': self.open_yaml,
            'create_node': self.graph_widget.create_node,
            'create_edge': self.graph_widget.create_edge,
            'save_yaml': self.graph_widget.save_yaml,
            'delete_selected': self.graph_widget.delete_selected,
            'delete_selected_alt': self.graph_widget.delete_selected,
            'edit_selected': self.graph_widget.edit_selected,
            'export_graph': self.export_graph_pdf,
            'export_markdown': self.export_markdown_pdf,
            'export_compilation': self.export_compilation_pdf,
            'edit_shortcuts': self.open_shortcut_editor
        }

        for action, func in bindings.items():
            key_seq = s.get(action)
            if key_seq:
                shortcut = QShortcut(QKeySequence(key_seq), self)
                shortcut.activated.connect(func)
                self.active_shortcuts.append(shortcut)

    def open_yaml(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            parent=self,
            caption="Open Graph YAML",
            directory="",
            filter="YAML Files (*.yaml *.yml)"
        )
        if filename:
            self.graph_widget.yaml_file = filename
            self.graph_widget.scene.clear()
            self.graph_widget.nodes_dict.clear()
            self.graph_widget.load_yaml()
            title = f"Obsidian Network - {os.path.basename(p=filename)}"
            self.setWindowTitle(title)

    def load_markdown_preview(self, filepath: str) -> None:
        if not filepath:
            self.md_preview.clear()
            self.file_label.setText("No markdown file assigned.")
            return
        self.md_tabs.setCurrentIndex(0)
        if os.path.exists(path=filepath):
            with open(file=filepath, mode='r', encoding='utf-8') as f:
                self.md_preview.setMarkdown(f.read())
            self.file_label.setText(f"Previewing: {filepath}")
        else:
            self.md_preview.setMarkdown(
                f"### {filepath} doesn't exist yet.\n\n"
                "Double-click the node to create and edit it."
            )
            self.file_label.setText(f"Missing File: {filepath}")

    def load_markdown_editor(self, filepath: str) -> None:
        if not filepath:
            return
        self.current_md_file = filepath
        self.md_tabs.setCurrentIndex(1)
        self.file_label.setText(f"Editing: {filepath}")

        base = os.path.basename(p=filepath).replace('.md', '')
        content = f"# {base}\n\nStart typing your ideas here..."
        if os.path.exists(path=filepath):
            with open(file=filepath, mode='r', encoding='utf-8') as f:
                content = f.read()
        self.md_editor.setPlainText(content)
        self.md_editor.setFocus()

    def save_markdown(self) -> None:
        if self.current_md_file:
            with open(
                file=self.current_md_file, mode='w', encoding='utf-8'
            ) as f:
                f.write(self.md_editor.toPlainText())
            self.md_preview.setMarkdown(self.md_editor.toPlainText())
            self.file_label.setText(f"Saved: {self.current_md_file}")

    def export_graph_pdf(self) -> None:
        filename, _ = QFileDialog.getSaveFileName(
            parent=self,
            caption="Export Graph to PDF",
            directory="graph.pdf",
            filter="PDF Files (*.pdf)"
        )
        if not filename:
            return

        writer = QPdfWriter(filename)
        writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        writer.setPageOrientation(QPageLayout.Orientation.Landscape)

        painter = QPainter(writer)
        target_rect = QRectF(0, 0, writer.width(), writer.height())
        source_rect = self.graph_widget.scene.itemsBoundingRect().adjusted(
            -50, -50, 50, 50
        )

        self.graph_widget.scene.render(
            painter,
            target_rect,
            source_rect,
            Qt.AspectRatioMode.KeepAspectRatio
        )
        painter.end()
        QMessageBox.information(
            self, "Success", f"Graph exported to {filename}"
        )

    def export_markdown_pdf(self) -> None:
        exists = self.current_md_file and os.path.exists(
            path=self.current_md_file
        )
        if not exists:
            QMessageBox.warning(
                self,
                "Warning",
                "No active/saved markdown file selected in the panel."
            )
            return

        filename, _ = QFileDialog.getSaveFileName(
            parent=self,
            caption="Export Markdown to PDF",
            directory=f"{self.current_md_file}.pdf",
            filter="PDF Files (*.pdf)"
        )
        if not filename:
            return

        writer = QPdfWriter(filename)
        writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))

        doc = QTextDocument()
        with open(
            file=self.current_md_file, mode='r', encoding='utf-8'
        ) as f:
            doc.setMarkdown(f.read())
        doc.print(writer)

        QMessageBox.information(
            self, "Success", f"Document exported to {filename}"
        )

    def export_compilation_pdf(self) -> None:
        filename, _ = QFileDialog.getSaveFileName(
            parent=self,
            caption="Export Compilation",
            directory="compilation.pdf",
            filter="PDF Files (*.pdf)"
        )
        if not filename:
            return

        writer = QPdfWriter(filename)
        writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))

        source_rect = self.graph_widget.scene.itemsBoundingRect().adjusted(
            -50, -50, 50, 50
        )
        if source_rect.isEmpty():
            source_rect = QRectF(0, 0, 800, 600)

        img_width = 2400
        img_height = int(img_width * source_rect.height() /
                         source_rect.width())
        image = QImage(img_width, img_height, QImage.Format.Format_ARGB32)
        image.fill(QColor("#1e1e1e"))

        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.graph_widget.scene.render(
            painter,
            QRectF(image.rect()),
            source_rect
        )
        painter.end()

        master_doc = QTextDocument()
        res_type = QTextDocument.ResourceType.ImageResource
        master_doc.addResource(res_type, QUrl("mydata://graph.png"), image)
        cursor = QTextCursor(master_doc)

        img_format = QTextImageFormat()
        img_format.setName("mydata://graph.png")
        img_format.setWidth(750)
        cursor.insertImage(img_format)

        md_files = set(
            node.md_file for node in self.graph_widget.nodes_dict.values()
            if node.md_file and os.path.exists(path=node.md_file)
        )
        sorted_files = sorted(list(md_files))

        for md_file in sorted_files:
            block_format = QTextBlockFormat()
            page_break = QTextFormat.PageBreakFlag.PageBreak_AlwaysBefore
            block_format.setPageBreakPolicy(page_break)
            cursor.insertBlock(block_format)

            with open(file=md_file, mode='r', encoding='utf-8') as f:
                content = f.read()

            temp_doc = QTextDocument()
            temp_doc.setMarkdown(content)
            cursor.insertHtml(temp_doc.toHtml())

        master_doc.print(writer)
        QMessageBox.information(
            self, "Success", f"Compilation exported to {filename}"
        )
