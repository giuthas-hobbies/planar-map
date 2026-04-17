Here is the complete, updated application. 

We have added the native `QPdfWriter` and `QTextDocument` classes to handle generating multi-page PDFs directly within PyQt6, without needing any external PDF libraries.

### 1. Updated Python Application (`main.py`)

```python
import sys
import os
import yaml
import math
import click
from PyQt6.QtWidgets import (QApplication, QGraphicsView, QGraphicsScene, 
                             QGraphicsItem, QMainWindow, QDialog, QFormLayout, 
                             QLineEdit, QDialogButtonBox, QMessageBox, QSplitter,
                             QWidget, QVBoxLayout, QTabWidget, QTextBrowser, 
                             QPlainTextEdit, QPushButton, QLabel, QFileDialog)
from PyQt6.QtCore import Qt, QPointF, QLineF, QTimer, QRectF, QUrl
from PyQt6.QtGui import (QColor, QPen, QBrush, QPainter, QPainterPath, QKeySequence, 
                         QShortcut, QPdfWriter, QPageSize, QPageLayout, QTextDocument, 
                         QTextCursor, QTextBlockFormat, QTextFormat, QTextImageFormat, QImage)

class EditDialog(QDialog):
    def __init__(self, fields, title, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.layout = QFormLayout(self)
        self.inputs = {}
        for field, default in fields.items():
            le = QLineEdit(str(default))
            self.layout.addRow(field, le)
            self.inputs[field] = le
        self.btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.btns.accepted.connect(self.accept)
        self.btns.rejected.connect(self.reject)
        self.layout.addWidget(self.btns)

    def get_data(self):
        return {f: le.text() for f, le in self.inputs.items()}


class Edge(QGraphicsItem):
    def __init__(self, source, target, properties):
        super().__init__()
        self.source, self.target = source, target
        self.source.add_edge(self)
        self.target.add_edge(self)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.update_properties(properties)
        self.is_dimmed, self.is_highlighted = False, False
        self.setZValue(-1)

    def update_properties(self, properties):
        self.base_color = QColor(properties.get('color', '#888888'))
        self.width = int(properties.get('width', 1))
        self.curvature = properties.get('curvature', 0.0)
        self.style_str = properties.get('style', 'solid').lower()
        if self.style_str == 'dashed': self.style = Qt.PenStyle.DashLine
        elif self.style_str == 'dotted': self.style = Qt.PenStyle.DotLine
        else: self.style = Qt.PenStyle.SolidLine
        self.update()

    def remove(self):
        if self in self.source.edges: self.source.edges.remove(self)
        if self in self.target.edges: self.target.edges.remove(self)
        self.scene().removeItem(self)

    def adjust(self):
        self.prepareGeometryChange()

    def get_path(self):
        path = QPainterPath(self.source.pos())
        if self.curvature == 0.0:
            path.lineTo(self.target.pos())
        else:
            dx, dy = self.target.pos().x() - self.source.pos().x(), self.target.pos().y() - self.source.pos().y()
            length = math.hypot(dx, dy)
            if length > 0:
                nx, ny = -dy / length, dx / length
                center_x, center_y = (self.source.pos().x() + self.target.pos().x()) / 2, (self.source.pos().y() + self.target.pos().y()) / 2
                path.quadTo(QPointF(center_x + nx * self.curvature, center_y + ny * self.curvature), self.target.pos())
            else:
                path.lineTo(self.target.pos())
        return path

    def boundingRect(self):
        if not self.source or not self.target: return QRectF()
        return self.get_path().boundingRect().adjusted(-self.width-5, -self.width-5, self.width+5, self.width+5)

    def paint(self, painter, option, widget):
        if not self.source or not self.target: return
        draw_color, draw_width = QColor(self.base_color), self.width
        
        if self.isSelected(): draw_color, draw_width = QColor("#ffffff"), draw_width + 2
        elif self.is_dimmed: draw_color.setAlpha(30)
        elif self.is_highlighted: draw_width, draw_color.setAlpha(255)
        else: draw_color.setAlpha(180)

        painter.setPen(QPen(draw_color, draw_width, self.style))
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.drawPath(self.get_path())


class Node(QGraphicsItem):
    def __init__(self, node_id, label, graph_widget, md_file=""):
        super().__init__()
        self.id, self.label, self.md_file, self.graph_widget = node_id, label, md_file, graph_widget
        self.edges, self.new_pos, self.radius, self.is_dimmed = [], QPointF(), 12, False
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsMovable | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setAcceptHoverEvents(True)
        self.setCacheMode(QGraphicsItem.CacheMode.DeviceCoordinateCache)
        self.setZValue(1)

    def add_edge(self, edge): self.edges.append(edge)
        
    def remove(self):
        for edge in list(self.edges): edge.remove()
        del self.graph_widget.nodes_dict[self.id]
        self.scene().removeItem(self)

    def calculate_forces(self, nodes):
        if self.scene().mouseGrabberItem() == self:
            self.new_pos = self.pos()
            return
        xvel, yvel = 0.0, 0.0
        for node in nodes:
            if node == self: continue
            line = QLineF(self.pos(), node.pos())
            dist = line.length()
            if 0 < dist < 300:
                force = 500.0 / (dist * dist)
                xvel -= (line.dx() / dist) * force; yvel -= (line.dy() / dist) * force

        for edge in self.edges:
            target_node = edge.target if edge.source == self else edge.source
            line = QLineF(self.pos(), target_node.pos())
            dist = line.length()
            if dist > 0:
                force = (dist - 100) * 0.02
                xvel += (line.dx() / dist) * force; yvel += (line.dy() / dist) * force
        self.new_pos = self.pos() + QPointF(xvel, yvel)

    def advance_position(self):
        if self.new_pos == self.pos(): return False
        self.setPos(self.new_pos); return True

    def boundingRect(self):
        return QRectF(-self.radius-2, -self.radius-2, self.radius*2 + 54, self.radius*2 + 34)

    def paint(self, painter, option, widget):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        alpha = 50 if self.is_dimmed else 255
        node_color = QColor("#00bfff" if self.md_file else "#a9a9a9")
        node_color.setAlpha(alpha)
        painter.setBrush(QBrush(node_color))
        
        border_color = QColor("#ffff00" if self.isSelected() else ("#ffffff" if not self.is_dimmed else "transparent"))
        border_color.setAlpha(alpha if not self.is_dimmed else 0)
        painter.setPen(QPen(border_color, 3 if self.isSelected() else 1.5))
        painter.drawEllipse(-self.radius, -self.radius, self.radius * 2, self.radius * 2)
        
        text_color = QColor("#ffffff")
        text_color.setAlpha(alpha)
        painter.setPen(text_color)
        painter.drawText(-int(painter.fontMetrics().horizontalAdvance(self.label)/2), self.radius + 15, self.label)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            for edge in self.edges: edge.adjust()
        return super().itemChange(change, value)

    def hoverEnterEvent(self, event):
        self.graph_widget.set_hover_state(self)
        self.graph_widget.main_window.load_markdown_preview(self.md_file)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.graph_widget.clear_hover_state()
        super().hoverLeaveEvent(event)
        
    def mouseDoubleClickEvent(self, event):
        if self.md_file: self.graph_widget.main_window.load_markdown_editor(self.md_file)
        else: self.graph_widget.edit_selected()
        super().mouseDoubleClickEvent(event)


class GraphWidget(QGraphicsView):
    def __init__(self, yaml_file, main_window):
        super().__init__()
        self.yaml_file, self.main_window = yaml_file, main_window
        self.scene = QGraphicsScene(self)
        self.scene.setItemIndexMethod(QGraphicsScene.ItemIndexMethod.NoIndex)
        self.setScene(self.scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setBackgroundBrush(QColor("#1e1e1e"))
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.nodes_dict = {}
        self.load_yaml()

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_physics)
        self.timer.start(1000 // 60)

    def load_yaml(self):
        if not os.path.exists(self.yaml_file): return
        with open(self.yaml_file, 'r') as file: data = yaml.safe_load(file) or {}

        import random
        for n in data.get('nodes', []):
            node = Node(n['id'], n.get('label', n['id']), self, n.get('md_file', ''))
            self.nodes_dict[n['id']] = node
            self.scene.addItem(node)
            node.setPos(random.randint(-100, 100), random.randint(-100, 100))

        edge_pairs = {}
        for e in data.get('edges', []):
            edge_pairs.setdefault(tuple(sorted([e.get('source'), e.get('target')])), []).append(e)

        for pair, edges_list in edge_pairs.items(): self._apply_curvature_and_create_edges(pair, edges_list)

    def _apply_curvature_and_create_edges(self, pair, edges_list):
        total_edges = len(edges_list)
        for i, e_data in enumerate(edges_list):
            src, tgt = e_data.get('source'), e_data.get('target')
            if src in self.nodes_dict and tgt in self.nodes_dict:
                offset = ((i - (total_edges - 1) / 2.0) * 35.0) if total_edges > 1 else 0.0
                if src != pair[0]: offset = -offset
                e_data['curvature'] = offset
                self.scene.addItem(Edge(self.nodes_dict[src], self.nodes_dict[tgt], e_data))

    def save_yaml(self):
        data = {'nodes': [], 'edges': []}
        for node in self.nodes_dict.values():
            nd = {'id': node.id, 'label': node.label}
            if node.md_file: nd['md_file'] = node.md_file
            data['nodes'].append(nd)
        for item in self.scene.items():
            if isinstance(item, Edge):
                data['edges'].append({'source': item.source.id, 'target': item.target.id, 'color': item.base_color.name(), 'width': item.width, 'style': item.style_str})
        with open(self.yaml_file, 'w') as f: yaml.dump(data, f, sort_keys=False)

    def create_node(self):
        if EditDialog({'id': 'NewNode', 'label': 'New Concept', 'md_file': ''}, "Create Node", self).exec() and (data := dialog.get_data()):
            if data['id'] in self.nodes_dict: return QMessageBox.warning(self, "Error", "Node ID exists!")
            node = Node(data['id'], data['label'], self, data['md_file'])
            self.nodes_dict[data['id']] = node; self.scene.addItem(node)
            node.setPos(self.mapToScene(self.viewport().rect().center()))

    def create_edge(self):
        selected = [i for i in self.scene.selectedItems() if isinstance(i, Node)]
        if len(selected) != 2: return QMessageBox.information(self, "Info", "Select exactly 2 nodes.")
        dialog = EditDialog({'color': '#888888', 'width': '1', 'style': 'solid'}, "Create Edge", self)
        if dialog.exec():
            data = dialog.get_data(); data['source'], data['target'] = selected[0].id, selected[1].id
            pair = tuple(sorted([selected[0].id, selected[1].id]))
            edges = [i for i in self.scene.items() if isinstance(i, Edge) and tuple(sorted([i.source.id, i.target.id])) == pair]
            edge_data_list = [{'source': e.source.id, 'target': e.target.id, 'color': e.base_color.name(), 'width': e.width, 'style': e.style_str} for e in edges] + [data]
            for e in edges: e.remove()
            self._apply_curvature_and_create_edges(pair, edge_data_list)

    def edit_selected(self):
        if not (sel := self.scene.selectedItems()): return
        if isinstance(sel[0], Node):
            if EditDialog({'label': sel[0].label, 'md_file': sel[0].md_file}, f"Edit: {sel[0].id}", self).exec():
                data = dialog.get_data(); sel[0].label, sel[0].md_file = data['label'], data['md_file']; sel[0].update()
        elif isinstance(sel[0], Edge):
            if EditDialog({'color': sel[0].base_color.name(), 'width': str(sel[0].width), 'style': sel[0].style_str}, "Edit Edge", self).exec():
                sel[0].update_properties(dialog.get_data())

    def delete_selected(self):
        for item in self.scene.selectedItems():
            if isinstance(item, Edge): item.remove()
        for item in self.scene.selectedItems():
            if isinstance(item, Node): item.remove()

    def set_hover_state(self, active):
        conn = {active}
        for e in active.edges:
            conn.update([e.source, e.target]); e.is_dimmed, e.is_highlighted = False, True
        for n in self.nodes_dict.values(): n.is_dimmed = n not in conn
        for i in self.scene.items():
            if isinstance(i, Edge) and i not in active.edges: i.is_dimmed, i.is_highlighted = True, False
        self.scene.update()

    def clear_hover_state(self):
        for i in self.scene.items(): i.is_dimmed, i.is_highlighted = False, False
        self.scene.update()

    def update_physics(self):
        nodes = list(self.nodes_dict.values())
        for n in nodes: n.calculate_forces(nodes)
        for n in nodes: n.advance_position()


class MainWindow(QMainWindow):
    def __init__(self, yaml_file):
        super().__init__()
        self.setWindowTitle(f"Obsidian Network - {yaml_file}")
        self.setMinimumSize(1000, 600)
        
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.setCentralWidget(self.splitter)
        
        self.graph_widget = GraphWidget(yaml_file, self)
        self.splitter.addWidget(self.graph_widget)
        
        self.right_panel = QWidget()
        self.right_layout = QVBoxLayout(self.right_panel)
        
        self.file_label = QLabel("Hover over a node to preview, double-click to edit.")
        self.file_label.setStyleSheet("font-weight: bold; color: #aaaaaa;")
        self.right_layout.addWidget(self.file_label)
        
        self.md_tabs = QTabWidget()
        self.md_preview = QTextBrowser()
        self.md_editor = QPlainTextEdit()
        
        self.md_preview.setStyleSheet("background-color: #2b2b2b; color: #e0e0e0; font-size: 14px; padding: 10px;")
        self.md_editor.setStyleSheet("background-color: #1e1e1e; color: #ffffff; font-family: Consolas, monospace; font-size: 14px; padding: 10px;")
        
        self.md_tabs.addTab(self.md_preview, "Preview")
        self.md_tabs.addTab(self.md_editor, "Editor")
        self.right_layout.addWidget(self.md_tabs)
        
        self.save_btn = QPushButton("Save Markdown Document")
        self.save_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 8px; font-weight: bold;")
        self.save_btn.clicked.connect(self.save_markdown)
        self.right_layout.addWidget(self.save_btn)
        
        self.splitter.addWidget(self.right_panel)
        self.splitter.setSizes([700, 300])
        
        self.current_md_file = None
        self.setup_shortcuts()

    def load_markdown_preview(self, filepath):
        if not filepath:
            self.md_preview.clear(); self.file_label.setText("No markdown file assigned to this node.")
            return
        self.md_tabs.setCurrentIndex(0)
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f: self.md_preview.setMarkdown(f.read())
            self.file_label.setText(f"Previewing: {filepath}")
        else:
            self.md_preview.setMarkdown(f"### {filepath} doesn't exist yet.\n\nDouble-click the node to create and edit it.")
            self.file_label.setText(f"Missing File: {filepath}")

    def load_markdown_editor(self, filepath):
        if not filepath: return
        self.current_md_file = filepath
        self.md_tabs.setCurrentIndex(1)
        self.file_label.setText(f"Editing: {filepath}")
        
        content = f"# {os.path.basename(filepath).replace('.md', '')}\n\nStart typing your ideas here..."
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f: content = f.read()
        self.md_editor.setPlainText(content)
        self.md_editor.setFocus()

    def save_markdown(self):
        if self.current_md_file:
            with open(self.current_md_file, 'w', encoding='utf-8') as f: f.write(self.md_editor.toPlainText())
            self.md_preview.setMarkdown(self.md_editor.toPlainText())
            self.file_label.setText(f"Saved: {self.current_md_file}")

    # --- PDF EXPORT METHODS ---
    def export_graph_pdf(self):
        filename, _ = QFileDialog.getSaveFileName(self, "Export Graph to PDF", "graph.pdf", "PDF Files (*.pdf)")
        if not filename: return
        
        writer = QPdfWriter(filename)
        writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        writer.setPageOrientation(QPageLayout.Orientation.Landscape)
        
        painter = QPainter(writer)
        target_rect = QRectF(0, 0, writer.width(), writer.height())
        source_rect = self.graph_widget.scene.itemsBoundingRect().adjusted(-50, -50, 50, 50)
        
        self.graph_widget.scene.render(painter, target_rect, source_rect, Qt.AspectRatioMode.KeepAspectRatio)
        painter.end()
        QMessageBox.information(self, "Success", f"Graph exported to {filename}")

    def export_markdown_pdf(self):
        if not self.current_md_file or not os.path.exists(self.current_md_file):
            return QMessageBox.warning(self, "Warning", "No active/saved markdown file selected in the panel.")
            
        filename, _ = QFileDialog.getSaveFileName(self, "Export Markdown to PDF", f"{self.current_md_file}.pdf", "PDF Files (*.pdf)")
        if not filename: return
        
        writer = QPdfWriter(filename)
        writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        
        # Render markdown to a hidden document and print it
        doc = QTextDocument()
        with open(self.current_md_file, 'r', encoding='utf-8') as f:
            doc.setMarkdown(f.read())
        doc.print(writer)
        
        QMessageBox.information(self, "Success", f"Document exported to {filename}")

    def export_compilation_pdf(self):
        filename, _ = QFileDialog.getSaveFileName(self, "Export Compilation", "compilation.pdf", "PDF Files (*.pdf)")
        if not filename: return

        # 1. Setup PDF Writer
        writer = QPdfWriter(filename)
        writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        
        # 2. Capture High-Res Graph Image for the Title Page
        source_rect = self.graph_widget.scene.itemsBoundingRect().adjusted(-50, -50, 50, 50)
        if source_rect.isEmpty(): source_rect = QRectF(0, 0, 800, 600)
        
        img_width = 2400 # High res for printing
        img_height = int(img_width * source_rect.height() / source_rect.width())
        image = QImage(img_width, img_height, QImage.Format.Format_ARGB32)
        image.fill(QColor("#1e1e1e")) # Obsidian background
        
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.graph_widget.scene.render(painter, QRectF(image.rect()), source_rect)
        painter.end()

        # 3. Create Master Document
        master_doc = QTextDocument()
        master_doc.addResource(QTextDocument.ResourceType.ImageResource, QUrl("mydata://graph.png"), image)
        cursor = QTextCursor(master_doc)
        
        # Insert scaled graph image
        img_format = QTextImageFormat()
        img_format.setName("mydata://graph.png")
        img_format.setWidth(750) # Fit nicely on A4 logical width
        cursor.insertImage(img_format)

        # 4. Gather and Sort linked Markdown files alphabetically
        md_files = set(node.md_file for node in self.graph_widget.nodes_dict.values() if node.md_file and os.path.exists(node.md_file))
        sorted_files = sorted(list(md_files))

        # 5. Append Markdown to Master Doc
        for md_file in sorted_files:
            # Force a Page Break
            block_format = QTextBlockFormat()
            block_format.setPageBreakPolicy(QTextFormat.PageBreakFlag.PageBreak_AlwaysBefore)
            cursor.insertBlock(block_format)
            
            with open(md_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Convert raw Markdown string via a temporary document, then append to cursor
            temp_doc = QTextDocument()
            temp_doc.setMarkdown(content)
            cursor.insertHtml(temp_doc.toHtml())

        # 6. Final Print execution
        master_doc.print(writer)
        QMessageBox.information(self, "Success", f"Compilation exported to {filename}")

    def setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+N"), self).activated.connect(self.graph_widget.create_node)
        QShortcut(QKeySequence("Ctrl+E"), self).activated.connect(self.graph_widget.create_edge)
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self.graph_widget.save_yaml)
        QShortcut(QKeySequence("Delete"), self).activated.connect(self.graph_widget.delete_selected)
        QShortcut(QKeySequence("Backspace"), self).activated.connect(self.graph_widget.delete_selected)
        QShortcut(QKeySequence("Return"), self).activated.connect(self.graph_widget.edit_selected)
        
        # New PDF Export Shortcuts
        QShortcut(QKeySequence("Ctrl+Shift+G"), self).activated.connect(self.export_graph_pdf)
        QShortcut(QKeySequence("Ctrl+Shift+M"), self).activated.connect(self.export_markdown_pdf)
        QShortcut(QKeySequence("Ctrl+Shift+C"), self).activated.connect(self.export_compilation_pdf)

@click.command()
@click.option('--file', '-f', default='graph.yaml', help='The YAML file to load and save the graph data.')
def main(file):
    app = QApplication([])
    window = MainWindow(file)
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
```

### New Keybindings

* **`Ctrl+Shift+G`**: Exports the entire visual network graph as a Landscape A4 PDF.
* **`Ctrl+Shift+M`**: Exports whichever Markdown file is currently active/previewed in the right-hand panel as a standard PDF document. 
* **`Ctrl+Shift+C`**: Compiles the ultimate "Book" export. The app internally renders a high-resolution snapshot of the graph and places it on page 1. It then dynamically fetches every valid `.md` file attached to your nodes, sorts them alphabetically by filename, injects page-breaks between them, and prints them out directly sequentially.