Here is the refactored application. I have separated the codebase into logical modules: `config.py` (for handling the YAML configuration), `graph_models.py` (for the graph canvas, nodes, and edges), `main_window.py` (for the Qt window and shortcut editor UI), and `main.py` (for the Click CLI entry point).

I've also integrated `QKeySequenceEdit`, which provides a native UI for recording key presses, making the shortcut editor highly intuitive.

### 1. Configuration Manager (`config.py`)

This file handles loading and saving the `config.yaml` file, ensuring defaults exist if the file is missing.

```python
import os
import yaml
from typing import Dict, Any

CONFIG_FILE = 'config.yaml'

DEFAULT_CONFIG: Dict[str, Any] = {
    'shortcuts': {
        'open_yaml': 'Ctrl+O',
        'create_node': 'Ctrl+N',
        'create_edge': 'Ctrl+E',
        'save_yaml': 'Ctrl+S',
        'delete_selected': 'Delete',
        'delete_selected_alt': 'Backspace',
        'edit_selected': 'Return',
        'export_graph': 'Ctrl+Shift+G',
        'export_markdown': 'Ctrl+Shift+M',
        'export_compilation': 'Ctrl+Shift+C',
        'edit_shortcuts': 'Ctrl+Shift+S'
    }
}

def load_config() -> Dict[str, Any]:
    """Loads the config file or creates it with defaults if it doesn't exist."""
    if not os.path.exists(CONFIG_FILE):
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG
        
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f) or {}
        
    # Ensure all default keys exist in case of a version update
    modified = False
    if 'shortcuts' not in config:
        config['shortcuts'] = {}
        
    for k, v in DEFAULT_CONFIG['shortcuts'].items():
        if k not in config['shortcuts']:
            config['shortcuts'][k] = v
            modified = True
            
    if modified:
        save_config(config)
        
    return config

def save_config(config: Dict[str, Any]) -> None:
    """Saves the configuration dictionary to the YAML file."""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        yaml.dump(config, f, sort_keys=False)
```

### 2. Graph Models & View (`graph_models.py`)

This file isolates the canvas logic, items, and physics processing.

```python
import os
import yaml
import math
from typing import Dict, Any, List, Optional, Tuple, Set, cast, TYPE_CHECKING
from PyQt6.QtWidgets import (QGraphicsView, QGraphicsScene, QGraphicsItem, 
                             QDialog, QFormLayout, QLineEdit, QDialogButtonBox, 
                             QMessageBox, QWidget, QStyleOptionGraphicsItem)
from PyQt6.QtCore import Qt, QPointF, QLineF, QTimer, QRectF
from PyQt6.QtGui import QColor, QPen, QBrush, QPainter, QPainterPath

if TYPE_CHECKING:
    from main_window import MainWindow

class EditDialog(QDialog):
    """A generic dialog to create or edit properties of nodes and edges."""
    def __init__(self, fields: Dict[str, Any], title: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.layout = QFormLayout(self)
        self.inputs: Dict[str, QLineEdit] = {}
        
        for field, default in fields.items():
            le = QLineEdit(str(default))
            self.layout.addRow(field, le)
            self.inputs[field] = le
            
        self.btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.btns.accepted.connect(self.accept)
        self.btns.rejected.connect(self.reject)
        self.layout.addWidget(self.btns)

    def get_data(self) -> Dict[str, str]:
        return {f: le.text() for f, le in self.inputs.items()}


class Edge(QGraphicsItem):
    """A visual representation of a connection between two Nodes."""
    def __init__(self, source: 'Node', target: 'Node', properties: Dict[str, Any]) -> None:
        super().__init__()
        self.source = source
        self.target = target
        self.source.add_edge(self)
        self.target.add_edge(self)
        
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.update_properties(properties)
        
        self.is_dimmed: bool = False
        self.is_highlighted: bool = False
        self.setZValue(-1)

    def update_properties(self, properties: Dict[str, Any]) -> None:
        self.base_color = QColor(properties.get('color', '#888888'))
        self.width = int(properties.get('width', 1))
        self.curvature = float(properties.get('curvature', 0.0))
        
        self.style_str = str(properties.get('style', 'solid')).lower()
        if self.style_str == 'dashed': self.style = Qt.PenStyle.DashLine
        elif self.style_str == 'dotted': self.style = Qt.PenStyle.DotLine
        else: self.style = Qt.PenStyle.SolidLine
        self.update()

    def remove(self) -> None:
        if self in self.source.edges: self.source.edges.remove(self)
        if self in self.target.edges: self.target.edges.remove(self)
        if self.scene(): self.scene().removeItem(self)

    def adjust(self) -> None:
        self.prepareGeometryChange()

    def get_path(self) -> QPainterPath:
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

    def boundingRect(self) -> QRectF:
        if not self.source or not self.target: return QRectF()
        return self.get_path().boundingRect().adjusted(-self.width-5, -self.width-5, self.width+5, self.width+5)

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: Optional[QWidget] = None) -> None:
        if not self.source or not self.target: return
        draw_color = QColor(self.base_color)
        draw_width = self.width
        
        if self.isSelected(): draw_color, draw_width = QColor("#ffffff"), draw_width + 2
        elif self.is_dimmed: draw_color.setAlpha(30)
        elif self.is_highlighted: draw_width, draw_color.setAlpha(255)
        else: draw_color.setAlpha(180)

        painter.setPen(QPen(draw_color, draw_width, self.style))
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.drawPath(self.get_path())


class Node(QGraphicsItem):
    """A visual representation of a concept or markdown file in the graph."""
    def __init__(self, node_id: str, label: str, graph_widget: 'GraphWidget', md_file: str = "") -> None:
        super().__init__()
        self.id = node_id
        self.label = label
        self.md_file = md_file
        self.graph_widget = graph_widget
        self.edges: List['Edge'] = []
        self.new_pos = QPointF()
        self.radius: int = 12
        self.is_dimmed: bool = False
        
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsMovable | 
                      QGraphicsItem.GraphicsItemFlag.ItemIsSelectable | 
                      QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setAcceptHoverEvents(True)
        self.setCacheMode(QGraphicsItem.CacheMode.DeviceCoordinateCache)
        self.setZValue(1)

    def add_edge(self, edge: 'Edge') -> None:
        self.edges.append(edge)
        
    def remove(self) -> None:
        for edge in list(self.edges): edge.remove()
        if self.id in self.graph_widget.nodes_dict:
            del self.graph_widget.nodes_dict[self.id]
        if self.scene(): self.scene().removeItem(self)

    def calculate_forces(self, nodes: List['Node']) -> None:
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
                xvel -= (line.dx() / dist) * force
                yvel -= (line.dy() / dist) * force

        for edge in self.edges:
            target_node = edge.target if edge.source == self else edge.source
            line = QLineF(self.pos(), target_node.pos())
            dist = line.length()
            if dist > 0:
                force = (dist - 100) * 0.02
                xvel += (line.dx() / dist) * force
                yvel += (line.dy() / dist) * force
                
        self.new_pos = self.pos() + QPointF(xvel, yvel)

    def advance_position(self) -> bool:
        if self.new_pos == self.pos(): return False
        self.setPos(self.new_pos)
        return True

    def boundingRect(self) -> QRectF:
        return QRectF(-self.radius-2, -self.radius-2, self.radius*2 + 54, self.radius*2 + 34)

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: Optional[QWidget] = None) -> None:
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
        metrics = painter.fontMetrics()
        painter.drawText(-int(metrics.horizontalAdvance(self.label)/2), self.radius + 15, self.label)

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value: Any) -> Any:
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            for edge in self.edges: edge.adjust()
        return super().itemChange(change, value)

    def hoverEnterEvent(self, event: Any) -> None:
        self.graph_widget.set_hover_state(self)
        self.graph_widget.main_window.load_markdown_preview(self.md_file)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event: Any) -> None:
        self.graph_widget.clear_hover_state()
        super().hoverLeaveEvent(event)
        
    def mouseDoubleClickEvent(self, event: Any) -> None:
        if self.md_file: 
            self.graph_widget.main_window.load_markdown_editor(self.md_file)
        else: 
            self.graph_widget.edit_selected()
        super().mouseDoubleClickEvent(event)


class GraphWidget(QGraphicsView):
    """The primary canvas view that holds and manages the graph scene."""
    def __init__(self, yaml_file: str, main_window: 'MainWindow') -> None:
        super().__init__()
        self.yaml_file = yaml_file
        self.main_window = main_window
        self.scene = QGraphicsScene(self)
        self.scene.setItemIndexMethod(QGraphicsScene.ItemIndexMethod.NoIndex)
        self.setScene(self.scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setBackgroundBrush(QColor("#1e1e1e"))
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        
        self.nodes_dict: Dict[str, Node] = {}
        self.load_yaml()

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_physics)
        self.timer.start(1000 // 60)

    def load_yaml(self) -> None:
        if not os.path.exists(self.yaml_file): return
        with open(self.yaml_file, 'r', encoding='utf-8') as file: 
            data = yaml.safe_load(file) or {}

        import random
        for n in data.get('nodes', []):
            node = Node(n['id'], n.get('label', n['id']), self, n.get('md_file', ''))
            self.nodes_dict[n['id']] = node
            self.scene.addItem(node)
            node.setPos(random.randint(-100, 100), random.randint(-100, 100))

        edge_pairs: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
        for e in data.get('edges', []):
            pair = tuple(sorted([str(e.get('source')), str(e.get('target'))]))
            pair_key = cast(Tuple[str, str], pair)
            edge_pairs.setdefault(pair_key, []).append(e)

        for pair, edges_list in edge_pairs.items(): 
            self._apply_curvature_and_create_edges(pair, edges_list)

    def _apply_curvature_and_create_edges(self, pair: Tuple[str, str], edges_list: List[Dict[str, Any]]) -> None:
        total_edges = len(edges_list)
        for i, e_data in enumerate(edges_list):
            src, tgt = e_data.get('source'), e_data.get('target')
            if src in self.nodes_dict and tgt in self.nodes_dict:
                offset = ((i - (total_edges - 1) / 2.0) * 35.0) if total_edges > 1 else 0.0
                if src != pair[0]: offset = -offset
                e_data['curvature'] = offset
                self.scene.addItem(Edge(self.nodes_dict[src], self.nodes_dict[tgt], e_data))

    def save_yaml(self) -> None:
        data: Dict[str, List[Dict[str, Any]]] = {'nodes': [], 'edges': []}
        for node in self.nodes_dict.values():
            nd = {'id': node.id, 'label': node.label}
            if node.md_file: nd['md_file'] = node.md_file
            data['nodes'].append(nd)
            
        for item in self.scene.items():
            if isinstance(item, Edge):
                data['edges'].append({
                    'source': item.source.id, 
                    'target': item.target.id, 
                    'color': item.base_color.name(), 
                    'width': item.width, 
                    'style': item.style_str
                })
        with open(self.yaml_file, 'w', encoding='utf-8') as f: 
            yaml.dump(data, f, sort_keys=False)

    def create_node(self) -> None:
        dialog = EditDialog({'id': 'NewNode', 'label': 'New Concept', 'md_file': ''}, "Create Node", self)
        if dialog.exec() and (data := dialog.get_data()):
            if data['id'] in self.nodes_dict: 
                QMessageBox.warning(self, "Error", "Node ID exists!")
                return
            node = Node(data['id'], data['label'], self, data['md_file'])
            self.nodes_dict[data['id']] = node
            self.scene.addItem(node)
            node.setPos(self.mapToScene(self.viewport().rect().center()))

    def create_edge(self) -> None:
        selected = [i for i in self.scene.selectedItems() if isinstance(i, Node)]
        if len(selected) != 2: 
            QMessageBox.information(self, "Info", "Select exactly 2 nodes.")
            return
            
        dialog = EditDialog({'color': '#888888', 'width': '1', 'style': 'solid'}, "Create Edge", self)
        if dialog.exec():
            data = dialog.get_data()
            data['source'], data['target'] = selected[0].id, selected[1].id
            pair = tuple(sorted([selected[0].id, selected[1].id]))
            pair_key = cast(Tuple[str, str], pair)
            
            edges = [i for i in self.scene.items() if isinstance(i, Edge) and tuple(sorted([i.source.id, i.target.id])) == pair]
            edge_data_list = [{'source': e.source.id, 'target': e.target.id, 'color': e.base_color.name(), 'width': e.width, 'style': e.style_str} for e in edges] + [data]
            
            for e in edges: e.remove()
            self._apply_curvature_and_create_edges(pair_key, edge_data_list)

    def edit_selected(self) -> None:
        sel = self.scene.selectedItems()
        if not sel: return
        
        if isinstance(sel[0], Node):
            dialog = EditDialog({'label': sel[0].label, 'md_file': sel[0].md_file}, f"Edit: {sel[0].id}", self)
            if dialog.exec():
                data = dialog.get_data()
                sel[0].label, sel[0].md_file = data['label'], data['md_file']
                sel[0].update()
        elif isinstance(sel[0], Edge):
            dialog = EditDialog({'color': sel[0].base_color.name(), 'width': str(sel[0].width), 'style': sel[0].style_str}, "Edit Edge", self)
            if dialog.exec():
                sel[0].update_properties(dialog.get_data())

    def delete_selected(self) -> None:
        for item in self.scene.selectedItems():
            if isinstance(item, Edge): item.remove()
        for item in self.scene.selectedItems():
            if isinstance(item, Node): item.remove()

    def set_hover_state(self, active: Node) -> None:
        conn: Set[Node] = {active}
        for e in active.edges:
            conn.update([e.source, e.target])
            e.is_dimmed, e.is_highlighted = False, True
            
        for n in self.nodes_dict.values(): 
            n.is_dimmed = n not in conn
            
        for i in self.scene.items():
            if isinstance(i, Edge) and i not in active.edges: 
                i.is_dimmed, i.is_highlighted = True, False
        self.scene.update()

    def clear_hover_state(self) -> None:
        for i in self.scene.items(): 
            if hasattr(i, 'is_dimmed'): i.is_dimmed = False
            if hasattr(i, 'is_highlighted'): i.is_highlighted = False
        self.scene.update()

    def update_physics(self) -> None:
        nodes = list(self.nodes_dict.values())
        for n in nodes: n.calculate_forces(nodes)
        for n in nodes: n.advance_position()
```

### 3. Main Window & Editor UI (`main_window.py`)

This file handles the main UI layout, PDF exporting, and introduces the `ShortcutEditorDialog` allowing users to edit shortcuts via `QKeySequenceEdit`.

```python
import os
from typing import Optional, List
from PyQt6.QtWidgets import (QMainWindow, QSplitter, QWidget, QVBoxLayout, 
                             QTabWidget, QTextBrowser, QPlainTextEdit, QPushButton, 
                             QLabel, QFileDialog, QMessageBox, QDialog, QFormLayout, 
                             QDialogButtonBox, QKeySequenceEdit)
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import (QColor, QPainter, QKeySequence, QShortcut, QPdfWriter, 
                         QPageSize, QPageLayout, QTextDocument, QTextCursor, 
                         QTextBlockFormat, QTextFormat, QTextImageFormat, QImage)

from graph_models import GraphWidget
from config import load_config, save_config

class ShortcutEditorDialog(QDialog):
    """A dialog to edit keyboard shortcuts natively."""
    def __init__(self, config_data: dict, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit Shortcuts")
        self.config_data = config_data
        self.layout = QFormLayout(self)
        self.edits: dict[str, QKeySequenceEdit] = {}

        for action, current_shortcut in self.config_data['shortcuts'].items():
            edit = QKeySequenceEdit(QKeySequence(current_shortcut))
            # Format label name nicely
            label_name = action.replace('_', ' ').title()
            self.layout.addRow(label_name, edit)
            self.edits[action] = edit

        self.btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.btns.accepted.connect(self.accept)
        self.btns.rejected.connect(self.reject)
        self.layout.addWidget(self.btns)

    def get_updated_shortcuts(self) -> dict:
        """Extracts the new shortcuts from the editors."""
        return {action: edit.keySequence().toString() for action, edit in self.edits.items()}

class MainWindow(QMainWindow):
    """The main application window holding the split layout (Graph / Markdown)."""
    def __init__(self, yaml_file: str) -> None:
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
        
        self.current_md_file: Optional[str] = None
        self.active_shortcuts: List[QShortcut] = []
        
        self.config = load_config()
        self.apply_shortcuts()

    def open_shortcut_editor(self) -> None:
        """Opens the shortcut editor dialog, saves changes, and re-applies."""
        dialog = ShortcutEditorDialog(self.config, self)
        if dialog.exec():
            new_shortcuts = dialog.get_updated_shortcuts()
            self.config['shortcuts'].update(new_shortcuts)
            save_config(self.config)
            self.apply_shortcuts()
            QMessageBox.information(self, "Success", "Shortcuts updated successfully!")

    def apply_shortcuts(self) -> None:
        """Clears existing shortcuts and re-binds them based on config."""
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
        filename, _ = QFileDialog.getOpenFileName(self, "Open Graph YAML", "", "YAML Files (*.yaml *.yml)")
        if filename:
            self.graph_widget.yaml_file = filename
            self.graph_widget.scene.clear()
            self.graph_widget.nodes_dict.clear()
            self.graph_widget.load_yaml()
            self.setWindowTitle(f"Obsidian Network - {os.path.basename(filename)}")

    def load_markdown_preview(self, filepath: str) -> None:
        if not filepath:
            self.md_preview.clear()
            self.file_label.setText("No markdown file assigned to this node.")
            return
        self.md_tabs.setCurrentIndex(0)
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f: 
                self.md_preview.setMarkdown(f.read())
            self.file_label.setText(f"Previewing: {filepath}")
        else:
            self.md_preview.setMarkdown(f"### {filepath} doesn't exist yet.\n\nDouble-click the node to create and edit it.")
            self.file_label.setText(f"Missing File: {filepath}")

    def load_markdown_editor(self, filepath: str) -> None:
        if not filepath: return
        self.current_md_file = filepath
        self.md_tabs.setCurrentIndex(1)
        self.file_label.setText(f"Editing: {filepath}")
        
        content = f"# {os.path.basename(filepath).replace('.md', '')}\n\nStart typing your ideas here..."
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f: 
                content = f.read()
        self.md_editor.setPlainText(content)
        self.md_editor.setFocus()

    def save_markdown(self) -> None:
        if self.current_md_file:
            with open(self.current_md_file, 'w', encoding='utf-8') as f: 
                f.write(self.md_editor.toPlainText())
            self.md_preview.setMarkdown(self.md_editor.toPlainText())
            self.file_label.setText(f"Saved: {self.current_md_file}")

    def export_graph_pdf(self) -> None:
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

    def export_markdown_pdf(self) -> None:
        if not self.current_md_file or not os.path.exists(self.current_md_file):
            QMessageBox.warning(self, "Warning", "No active/saved markdown file selected in the panel.")
            return
            
        filename, _ = QFileDialog.getSaveFileName(self, "Export Markdown to PDF", f"{self.current_md_file}.pdf", "PDF Files (*.pdf)")
        if not filename: return
        
        writer = QPdfWriter(filename)
        writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        
        doc = QTextDocument()
        with open(self.current_md_file, 'r', encoding='utf-8') as f:
            doc.setMarkdown(f.read())
        doc.print(writer)
        
        QMessageBox.information(self, "Success", f"Document exported to {filename}")

    def export_compilation_pdf(self) -> None:
        filename, _ = QFileDialog.getSaveFileName(self, "Export Compilation", "compilation.pdf", "PDF Files (*.pdf)")
        if not filename: return

        writer = QPdfWriter(filename)
        writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        
        source_rect = self.graph_widget.scene.itemsBoundingRect().adjusted(-50, -50, 50, 50)
        if source_rect.isEmpty(): source_rect = QRectF(0, 0, 800, 600)
        
        img_width = 2400 
        img_height = int(img_width * source_rect.height() / source_rect.width())
        image = QImage(img_width, img_height, QImage.Format.Format_ARGB32)
        image.fill(QColor("#1e1e1e")) 
        
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.graph_widget.scene.render(painter, QRectF(image.rect()), source_rect)
        painter.end()

        master_doc = QTextDocument()
        master_doc.addResource(QTextDocument.ResourceType.ImageResource, QUrl("mydata://graph.png"), image)
        cursor = QTextCursor(master_doc)
        
        img_format = QTextImageFormat()
        img_format.setName("mydata://graph.png")
        img_format.setWidth(750) 
        cursor.insertImage(img_format)

        md_files = set(node.md_file for node in self.graph_widget.nodes_dict.values() if node.md_file and os.path.exists(node.md_file))
        sorted_files = sorted(list(md_files))

        for md_file in sorted_files:
            block_format = QTextBlockFormat()
            block_format.setPageBreakPolicy(QTextFormat.PageBreakFlag.PageBreak_AlwaysBefore)
            cursor.insertBlock(block_format)
            
            with open(md_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
            temp_doc = QTextDocument()
            temp_doc.setMarkdown(content)
            cursor.insertHtml(temp_doc.toHtml())

        master_doc.print(writer)
        QMessageBox.information(self, "Success", f"Compilation exported to {filename}")
```

### 4. Entry Point (`main.py`)

This file is now extremely lean, importing dependencies and handling the Click CLI.

```python
import sys
import click
from PyQt6.QtWidgets import QApplication
from main_window import MainWindow

@click.command()
@click.option('--file', '-f', default='graph.yaml', help='The YAML file to load and save the graph data.')
def main(file: str) -> None:
    """Launch the Obsidian-style Network Graph Application."""
    app = QApplication(sys.argv)
    window = MainWindow(file)
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
```