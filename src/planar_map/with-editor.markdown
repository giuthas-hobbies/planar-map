Here is the complete, updated application. 

To achieve this side-by-side layout without overlaying the graph, we will use a **`QSplitter`**. This allows the user to click and drag the divider between the network view and the markdown tools to adjust their proportions. 

We are also utilizing PyQt6's native `setMarkdown()` method within a `QTextBrowser`, which eliminates the need to install external markdown-parsing libraries.

### Updated Python Application (`main.py`)

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
                             QPlainTextEdit, QPushButton, QLabel)
from PyQt6.QtCore import Qt, QPointF, QLineF, QTimer, QRectF
from PyQt6.QtGui import QColor, QPen, QBrush, QPainter, QPainterPath, QKeySequence, QShortcut

class EditDialog(QDialog):
    """A generic dialog to create/edit nodes and edges."""
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
        self.source = source
        self.target = target
        self.source.add_edge(self)
        self.target.add_edge(self)
        
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.update_properties(properties)
        
        self.is_dimmed = False
        self.is_highlighted = False
        self.setZValue(-1)

    def update_properties(self, properties):
        self.base_color = QColor(properties.get('color', '#888888'))
        self.width = int(properties.get('width', 1))
        self.curvature = properties.get('curvature', 0.0)
        
        style_str = properties.get('style', 'solid').lower()
        self.style_str = style_str
        if style_str == 'dashed':
            self.style = Qt.PenStyle.DashLine
        elif style_str == 'dotted':
            self.style = Qt.PenStyle.DotLine
        else:
            self.style = Qt.PenStyle.SolidLine
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
            dx = self.target.pos().x() - self.source.pos().x()
            dy = self.target.pos().y() - self.source.pos().y()
            length = math.hypot(dx, dy)
            if length > 0:
                nx, ny = -dy / length, dx / length
                center_x = (self.source.pos().x() + self.target.pos().x()) / 2
                center_y = (self.source.pos().y() + self.target.pos().y()) / 2
                ctrl_x = center_x + nx * self.curvature
                ctrl_y = center_y + ny * self.curvature
                path.quadTo(QPointF(ctrl_x, ctrl_y), self.target.pos())
            else:
                path.lineTo(self.target.pos())
        return path

    def boundingRect(self):
        if not self.source or not self.target: return QRectF()
        path = self.get_path()
        return path.boundingRect().adjusted(-self.width-5, -self.width-5, self.width+5, self.width+5)

    def paint(self, painter, option, widget):
        if not self.source or not self.target: return

        path = self.get_path()
        draw_color = QColor(self.base_color)
        draw_width = self.width
        
        if self.isSelected():
            draw_color = QColor("#ffffff")
            draw_width += 2
        elif self.is_dimmed:
            draw_color.setAlpha(30)
        elif self.is_highlighted:
            draw_width += 1
            draw_color.setAlpha(255)
        else:
            draw_color.setAlpha(180)

        pen = QPen(draw_color, draw_width, self.style)
        painter.setPen(pen)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.drawPath(path)


class Node(QGraphicsItem):
    def __init__(self, node_id, label, graph_widget, md_file=""):
        super().__init__()
        self.id = node_id
        self.label = label
        self.md_file = md_file
        self.graph_widget = graph_widget
        self.edges = []
        self.new_pos = QPointF()
        
        self.radius = 12
        self.is_dimmed = False
        
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setAcceptHoverEvents(True)
        self.setCacheMode(QGraphicsItem.CacheMode.DeviceCoordinateCache)
        self.setZValue(1)

    def add_edge(self, edge):
        self.edges.append(edge)
        
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
            distance = line.length()
            if 0 < distance < 300:
                force = 500.0 / (distance * distance)
                xvel -= (line.dx() / distance) * force
                yvel -= (line.dy() / distance) * force

        for edge in self.edges:
            target_node = edge.target if edge.source == self else edge.source
            line = QLineF(self.pos(), target_node.pos())
            distance = line.length()
            if distance > 0:
                force = (distance - 100) * 0.02
                xvel += (line.dx() / distance) * force
                yvel += (line.dy() / distance) * force

        self.new_pos = self.pos() + QPointF(xvel, yvel)

    def advance_position(self):
        if self.new_pos == self.pos(): return False
        self.setPos(self.new_pos)
        return True

    def boundingRect(self):
        return QRectF(-self.radius-2, -self.radius-2, self.radius*2 + 54, self.radius*2 + 34)

    def paint(self, painter, option, widget):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        alpha = 50 if self.is_dimmed else 255
        
        node_color = QColor("#00bfff" if self.md_file else "#a9a9a9")
        node_color.setAlpha(alpha)
        painter.setBrush(QBrush(node_color))
        
        border_color = QColor("#ffff00" if self.isSelected() else ("#ffffff" if not self.is_dimmed else "transparent"))
        border_width = 3 if self.isSelected() else 1.5
        border_color.setAlpha(alpha if not self.is_dimmed else 0)
        painter.setPen(QPen(border_color, border_width))
        
        painter.drawEllipse(-self.radius, -self.radius, self.radius * 2, self.radius * 2)
        
        text_color = QColor("#ffffff")
        text_color.setAlpha(alpha)
        painter.setPen(text_color)
        metrics = painter.fontMetrics()
        text_width = metrics.horizontalAdvance(self.label)
        painter.drawText(-int(text_width/2), self.radius + 15, self.label)

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
        if self.md_file:
            self.graph_widget.main_window.load_markdown_editor(self.md_file)
        else:
            self.graph_widget.edit_selected()
        super().mouseDoubleClickEvent(event)


class GraphWidget(QGraphicsView):
    def __init__(self, yaml_file, main_window):
        super().__init__()
        self.yaml_file = yaml_file
        self.main_window = main_window # Reference to the main window to trigger UI changes
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
        if not os.path.exists(self.yaml_file):
            return
        with open(self.yaml_file, 'r') as file:
            data = yaml.safe_load(file) or {}

        import random
        for n_data in data.get('nodes', []):
            node = Node(n_data['id'], n_data.get('label', n_data['id']), self, n_data.get('md_file', ''))
            self.nodes_dict[n_data['id']] = node
            self.scene.addItem(node)
            node.setPos(random.randint(-100, 100), random.randint(-100, 100))

        edge_pairs = {}
        for e_data in data.get('edges', []):
            pair = tuple(sorted([e_data.get('source'), e_data.get('target')]))
            edge_pairs.setdefault(pair, []).append(e_data)

        for pair, edges_list in edge_pairs.items():
            self._apply_curvature_and_create_edges(pair, edges_list)

    def _apply_curvature_and_create_edges(self, pair, edges_list):
        total_edges = len(edges_list)
        for i, e_data in enumerate(edges_list):
            source_id = e_data.get('source')
            target_id = e_data.get('target')
            if source_id in self.nodes_dict and target_id in self.nodes_dict:
                offset = ((i - (total_edges - 1) / 2.0) * 35.0) if total_edges > 1 else 0.0
                if source_id != pair[0]: offset = -offset
                e_data['curvature'] = offset
                edge = Edge(self.nodes_dict[source_id], self.nodes_dict[target_id], e_data)
                self.scene.addItem(edge)

    def save_yaml(self):
        data = {'nodes': [], 'edges': []}
        for node in self.nodes_dict.values():
            nd = {'id': node.id, 'label': node.label}
            if node.md_file: nd['md_file'] = node.md_file
            data['nodes'].append(nd)
            
        for item in self.scene.items():
            if isinstance(item, Edge):
                data['edges'].append({
                    'source': item.source.id, 'target': item.target.id,
                    'color': item.base_color.name(), 'width': item.width, 'style': item.style_str
                })
                
        with open(self.yaml_file, 'w') as file:
            yaml.dump(data, file, sort_keys=False)

    def create_node(self):
        dialog = EditDialog({'id': 'NewNode', 'label': 'New Concept', 'md_file': ''}, "Create Node", self)
        if dialog.exec():
            data = dialog.get_data()
            if data['id'] in self.nodes_dict:
                QMessageBox.warning(self, "Error", "Node ID already exists!")
                return
            node = Node(data['id'], data['label'], self, data['md_file'])
            self.nodes_dict[data['id']] = node
            self.scene.addItem(node)
            node.setPos(self.mapToScene(self.viewport().rect().center()))

    def create_edge(self):
        selected = [item for item in self.scene.selectedItems() if isinstance(item, Node)]
        if len(selected) != 2:
            QMessageBox.information(self, "Info", "Please select exactly 2 nodes to connect.")
            return
            
        dialog = EditDialog({'color': '#888888', 'width': '1', 'style': 'solid'}, "Create Edge", self)
        if dialog.exec():
            data = dialog.get_data()
            data['source'] = selected[0].id
            data['target'] = selected[1].id
            pair = tuple(sorted([selected[0].id, selected[1].id]))
            
            existing_edges = [item for item in self.scene.items() 
                              if isinstance(item, Edge) and 
                              tuple(sorted([item.source.id, item.target.id])) == pair]
            
            edge_data_list = [{'source': e.source.id, 'target': e.target.id, 
                               'color': e.base_color.name(), 'width': e.width, 
                               'style': e.style_str} for e in existing_edges]
            edge_data_list.append(data)
            
            for e in existing_edges: e.remove()
            self._apply_curvature_and_create_edges(pair, edge_data_list)

    def edit_selected(self):
        selected = self.scene.selectedItems()
        if not selected: return
        item = selected[0]
        
        if isinstance(item, Node):
            dialog = EditDialog({'label': item.label, 'md_file': item.md_file}, f"Edit Node: {item.id}", self)
            if dialog.exec():
                data = dialog.get_data()
                item.label = data['label']
                item.md_file = data['md_file']
                item.update()
                
        elif isinstance(item, Edge):
            dialog = EditDialog({'color': item.base_color.name(), 'width': str(item.width), 'style': item.style_str}, "Edit Edge", self)
            if dialog.exec():
                item.update_properties(dialog.get_data())

    def delete_selected(self):
        for item in self.scene.selectedItems():
            if isinstance(item, Edge): item.remove()
        for item in self.scene.selectedItems():
            if isinstance(item, Node): item.remove()

    def set_hover_state(self, active_node):
        connected = {active_node}
        for edge in active_node.edges:
            connected.add(edge.source)
            connected.add(edge.target)
            edge.is_dimmed = False
            edge.is_highlighted = True
        for node in self.nodes_dict.values():
            node.is_dimmed = node not in connected
        for item in self.scene.items():
            if isinstance(item, Edge):
                if item.source == active_node or item.target == active_node:
                    item.is_dimmed, item.is_highlighted = False, True
                else:
                    item.is_dimmed, item.is_highlighted = True, False
        self.scene.update()

    def clear_hover_state(self):
        for item in self.scene.items():
            if hasattr(item, 'is_dimmed'): item.is_dimmed = False
            if hasattr(item, 'is_highlighted'): item.is_highlighted = False
        self.scene.update()

    def update_physics(self):
        nodes = list(self.nodes_dict.values())
        for node in nodes: node.calculate_forces(nodes)
        for node in nodes: node.advance_position()

class MainWindow(QMainWindow):
    def __init__(self, yaml_file):
        super().__init__()
        self.setWindowTitle(f"Obsidian Network - {yaml_file}")
        self.setMinimumSize(1000, 600)
        
        # 1. Main Splitter Layout
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.setCentralWidget(self.splitter)
        
        # 2. Graph Widget (Left side)
        self.graph_widget = GraphWidget(yaml_file, self)
        self.splitter.addWidget(self.graph_widget)
        
        # 3. Markdown Editor/Renderer Panel (Right side)
        self.right_panel = QWidget()
        self.right_layout = QVBoxLayout(self.right_panel)
        
        self.file_label = QLabel("Hover over a node to preview, double-click to edit.")
        self.file_label.setStyleSheet("font-weight: bold; color: #aaaaaa;")
        self.right_layout.addWidget(self.file_label)
        
        self.md_tabs = QTabWidget()
        self.md_preview = QTextBrowser()
        self.md_editor = QPlainTextEdit()
        
        # Style the Markdown text areas
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
        self.splitter.setSizes([700, 300]) # 70% Graph, 30% Text
        
        self.current_md_file = None
        self.setup_shortcuts()

    def load_markdown_preview(self, filepath):
        """Called automatically when hovering over a node."""
        if not filepath:
            self.md_preview.clear()
            self.file_label.setText("No markdown file assigned to this node.")
            return

        self.md_tabs.setCurrentIndex(0) # Switch to preview tab
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            self.md_preview.setMarkdown(content)
            self.file_label.setText(f"Previewing: {filepath}")
        else:
            self.md_preview.setMarkdown(f"### {filepath} doesn't exist yet.\n\nDouble-click the node to create and edit it.")
            self.file_label.setText(f"Missing File: {filepath}")

    def load_markdown_editor(self, filepath):
        """Called automatically when double-clicking a node with an assigned markdown file."""
        if not filepath:
            return
            
        self.current_md_file = filepath
        self.md_tabs.setCurrentIndex(1) # Switch to Editor tab
        self.file_label.setText(f"Editing: {filepath}")
        
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
        else:
            # Starter template for new files
            content = f"# {os.path.basename(filepath).replace('.md', '')}\n\nStart typing your ideas here..."
            
        self.md_editor.setPlainText(content)
        self.md_editor.setFocus()

    def save_markdown(self):
        """Saves the current text in the editor to the file system."""
        if self.current_md_file:
            with open(self.current_md_file, 'w', encoding='utf-8') as f:
                f.write(self.md_editor.toPlainText())
            
            # Immediately update the preview with the newly saved content
            self.md_preview.setMarkdown(self.md_editor.toPlainText())
            self.file_label.setText(f"Saved: {self.current_md_file}")

    def setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+N"), self).activated.connect(self.graph_widget.create_node)
        QShortcut(QKeySequence("Ctrl+E"), self).activated.connect(self.graph_widget.create_edge)
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self.graph_widget.save_yaml)
        QShortcut(QKeySequence("Delete"), self).activated.connect(self.graph_widget.delete_selected)
        QShortcut(QKeySequence("Backspace"), self).activated.connect(self.graph_widget.delete_selected)
        QShortcut(QKeySequence("Return"), self).activated.connect(self.graph_widget.edit_selected)

@click.command()
@click.option('--file', '-f', default='graph.yaml', help='The YAML file to load and save the graph data.')
def main(file):
    """Launch the Obsidian-style Network Graph."""
    app = QApplication([])
    window = MainWindow(file)
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
```

### Changes Made:
* **The UI Splitter:** The `MainWindow` now creates a split window using `QSplitter`. You can freely drag the bar between the Graph View and the Markdown Editor to resize them.
* **The Right-Hand Panel:** Features a tabbed widget (`QTabWidget`). 
    * **Preview Tab:** Renders standard Markdown strings into readable formatted text (headers, bolding, lists, etc.) using `QTextBrowser`'s native `.setMarkdown()` function.
    * **Editor Tab:** Uses a raw `QPlainTextEdit` for writing the markdown syntax directly, stylized with a monospaced font.
* **Dynamic Linking:** * When you **Hover** your mouse over a blue node, the right panel automatically shifts to the *Preview* tab, pulls the node's linked file from your computer, and renders it.
    * When you **Double-Click** a blue node, the right panel automatically shifts to the *Editor* tab, loads the underlying markdown text so you can rewrite it, and snaps your keyboard focus directly into the textbox.
    * Clicking **Save Markdown Document** commits your changes back into the `.md` file, and instantly updates the preview window.