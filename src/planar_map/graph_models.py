import os
import yaml
import math
import random
from typing import (
    Dict, Any, List, Optional, Tuple, Set, cast, TYPE_CHECKING
)
from PyQt6.QtWidgets import (
    QGraphicsView, QGraphicsScene, QGraphicsItem,
    QDialog, QFormLayout, QLineEdit, QDialogButtonBox,
    QMessageBox, QWidget, QStyleOptionGraphicsItem
)
from PyQt6.QtCore import Qt, QPointF, QLineF, QTimer, QRectF
from PyQt6.QtGui import QColor, QPen, QBrush, QPainter, QPainterPath

if TYPE_CHECKING:
    from main_window import MainWindow


class EditDialog(QDialog):
    """A generic dialog to create or edit properties of nodes and edges."""

    def __init__(
        self,
        fields: Dict[str, Any],
        title: str,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent=parent)
        self.setWindowTitle(title)
        self.layout = QFormLayout(parent=self)
        self.inputs: Dict[str, QLineEdit] = {}

        for field, default in fields.items():
            le = QLineEdit(str(default))
            self.layout.addRow(field, le)
            self.inputs[field] = le

        buttons = (
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        self.btns = QDialogButtonBox(buttons)
        self.btns.accepted.connect(self.accept)
        self.btns.rejected.connect(self.reject)
        self.layout.addWidget(self.btns)

    def get_data(self) -> Dict[str, str]:
        return {f: le.text() for f, le in self.inputs.items()}


class Edge(QGraphicsItem):
    """A visual representation of a connection between two Nodes."""

    def __init__(
        self,
        source: 'Node',
        target: 'Node',
        properties: Dict[str, Any]
    ) -> None:
        super().__init__()
        self.source = source
        self.target = target
        self.source.add_edge(edge=self)
        self.target.add_edge(edge=self)

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.update_properties(properties=properties)

        self.is_dimmed: bool = False
        self.is_highlighted: bool = False
        self.setZValue(-1)

    def update_properties(self, properties: Dict[str, Any]) -> None:
        self.base_color = QColor(properties.get('color', '#888888'))
        self.width = int(properties.get('width', 1))
        self.curvature = float(properties.get('curvature', 0.0))

        self.style_str = str(properties.get('style', 'solid')).lower()
        if self.style_str == 'dashed':
            self.style = Qt.PenStyle.DashLine
        elif self.style_str == 'dotted':
            self.style = Qt.PenStyle.DotLine
        else:
            self.style = Qt.PenStyle.SolidLine
        self.update()

    def remove(self) -> None:
        if self in self.source.edges:
            self.source.edges.remove(self)
        if self in self.target.edges:
            self.target.edges.remove(self)
        if self.scene():
            self.scene().removeItem(self)

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
        if not self.source or not self.target:
            return QRectF()
        path_rect = self.get_path().boundingRect()
        return path_rect.adjusted(
            -self.width - 5,
            -self.width - 5,
            self.width + 5,
            self.width + 5
        )

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: Optional[QWidget] = None
    ) -> None:
        if not self.source or not self.target:
            return
        draw_color = QColor(self.base_color)
        draw_width = self.width

        if self.isSelected():
            draw_color = QColor("#ffffff")
            draw_width += 2
        elif self.is_dimmed:
            draw_color.setAlpha(30)
        elif self.is_highlighted:
            draw_color.setAlpha(255)
        else:
            draw_color.setAlpha(180)

        painter.setPen(QPen(draw_color, draw_width, self.style))
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.drawPath(self.get_path())


class Node(QGraphicsItem):
    """A visual representation of a concept or markdown file."""

    def __init__(
        self,
        node_id: str,
        label: str,
        graph_widget: 'GraphWidget',
        md_file: str = ""
    ) -> None:
        super().__init__()
        self.id = node_id
        self.label = label
        self.md_file = md_file
        self.graph_widget = graph_widget
        self.edges: List['Edge'] = []
        self.new_pos = QPointF()
        self.radius: int = 12
        self.is_dimmed: bool = False

        flags = (
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
            QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.setFlags(flags)
        self.setAcceptHoverEvents(True)
        self.setCacheMode(QGraphicsItem.CacheMode.DeviceCoordinateCache)
        self.setZValue(1)

    def add_edge(self, edge: 'Edge') -> None:
        self.edges.append(edge)

    def remove(self) -> None:
        for edge in list(self.edges):
            edge.remove()
        if self.id in self.graph_widget.nodes_dict:
            del self.graph_widget.nodes_dict[self.id]
        if self.scene():
            self.scene().removeItem(self)

    def calculate_forces(self, nodes: List['Node']) -> None:
        if self.scene().mouseGrabberItem() == self:
            self.new_pos = self.pos()
            return
        xvel, yvel = 0.0, 0.0

        for node in nodes:
            if node == self:
                continue
            line = QLineF(self.pos(), node.pos())
            dist = line.length()
            if 0 < dist < 300:
                force = 500.0 / (dist * dist)
                xvel -= (line.dx() / dist) * force
                yvel -= (line.dy() / dist) * force

        for edge in self.edges:
            target = edge.target if edge.source == self else edge.source
            line = QLineF(self.pos(), target.pos())
            dist = line.length()
            if dist > 0:
                force = (dist - 100) * 0.02
                xvel += (line.dx() / dist) * force
                yvel += (line.dy() / dist) * force

        self.new_pos = self.pos() + QPointF(xvel, yvel)

    def advance_position(self) -> bool:
        if self.new_pos == self.pos():
            return False
        self.setPos(self.new_pos)
        return True

    def boundingRect(self) -> QRectF:
        return QRectF(
            -self.radius - 2,
            -self.radius - 2,
            self.radius * 2 + 54,
            self.radius * 2 + 34
        )

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: Optional[QWidget] = None
    ) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        alpha = 50 if self.is_dimmed else 255

        node_color = QColor("#00bfff" if self.md_file else "#a9a9a9")
        node_color.setAlpha(alpha)
        painter.setBrush(QBrush(node_color))

        if self.isSelected():
            border_color = QColor("#ffff00")
        else:
            border_color = QColor("#ffffff" if not self.is_dimmed else "none")

        border_color.setAlpha(alpha if not self.is_dimmed else 0)
        painter.setPen(QPen(border_color, 3 if self.isSelected() else 1.5))
        painter.drawEllipse(
            -self.radius,
            -self.radius,
            self.radius * 2,
            self.radius * 2
        )

        text_color = QColor("#ffffff")
        text_color.setAlpha(alpha)
        painter.setPen(text_color)
        metrics = painter.fontMetrics()
        offset_x = -int(metrics.horizontalAdvance(self.label) / 2)
        painter.drawText(offset_x, self.radius + 15, self.label)

    def itemChange(
        self,
        change: QGraphicsItem.GraphicsItemChange,
        value: Any
    ) -> Any:
        pos_change = QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged
        if change == pos_change:
            for edge in self.edges:
                edge.adjust()
        return super().itemChange(change, value)

    def hoverEnterEvent(self, event: Any) -> None:
        self.graph_widget.set_hover_state(active=self)
        main_win = self.graph_widget.main_window
        main_win.load_markdown_preview(filepath=self.md_file)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event: Any) -> None:
        self.graph_widget.clear_hover_state()
        super().hoverLeaveEvent(event)

    def mouseDoubleClickEvent(self, event: Any) -> None:
        if self.md_file:
            main_win = self.graph_widget.main_window
            main_win.load_markdown_editor(filepath=self.md_file)
        else:
            self.graph_widget.edit_selected()
        super().mouseDoubleClickEvent(event)


class GraphWidget(QGraphicsView):
    """The primary canvas view that holds and manages the graph scene."""

    def __init__(self, yaml_file: str, main_window: 'MainWindow') -> None:
        super().__init__()
        self.yaml_file = yaml_file
        self.main_window = main_window
        self.scene = QGraphicsScene(parent=self)
        index_method = QGraphicsScene.ItemIndexMethod.NoIndex
        self.scene.setItemIndexMethod(index_method)
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
        if not os.path.exists(path=self.yaml_file):
            return
        with open(file=self.yaml_file, mode='r', encoding='utf-8') as f:
            data = yaml.safe_load(stream=f) or {}

        for n in data.get('nodes', []):
            node_id = n['id']
            label = n.get('label', node_id)
            md_file = n.get('md_file', '')
            node = Node(
                node_id=node_id,
                label=label,
                graph_widget=self,
                md_file=md_file
            )
            self.nodes_dict[node_id] = node
            self.scene.addItem(node)
            node.setPos(random.randint(-100, 100), random.randint(-100, 100))

        edge_pairs: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
        for e in data.get('edges', []):
            src, tgt = str(e.get('source')), str(e.get('target'))
            pair = tuple(sorted([src, tgt]))
            pair_key = cast(Tuple[str, str], pair)
            edge_pairs.setdefault(pair_key, []).append(e)

        for pair, edges_list in edge_pairs.items():
            self._apply_curvature_and_create_edges(
                pair=pair,
                edges_list=edges_list
            )

    def _apply_curvature_and_create_edges(
        self,
        pair: Tuple[str, str],
        edges_list: List[Dict[str, Any]]
    ) -> None:
        total_edges = len(edges_list)
        for i, e_data in enumerate(iterable=edges_list):
            src = e_data.get('source')
            tgt = e_data.get('target')
            if src in self.nodes_dict and tgt in self.nodes_dict:
                offset = 0.0
                if total_edges > 1:
                    offset = (i - (total_edges - 1) / 2.0) * 35.0
                if src != pair[0]:
                    offset = -offset
                e_data['curvature'] = offset
                edge = Edge(
                    source=self.nodes_dict[src],
                    target=self.nodes_dict[tgt],
                    properties=e_data
                )
                self.scene.addItem(edge)

    def save_yaml(self) -> None:
        data: Dict[str, List[Dict[str, Any]]] = {'nodes': [], 'edges': []}
        for node in self.nodes_dict.values():
            nd = {'id': node.id, 'label': node.label}
            if node.md_file:
                nd['md_file'] = node.md_file
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
        with open(file=self.yaml_file, mode='w', encoding='utf-8') as f:
            yaml.dump(data=data, stream=f, sort_keys=False)

    def create_node(self) -> None:
        fields = {'id': 'NewNode', 'label': 'New Concept', 'md_file': ''}
        dialog = EditDialog(fields=fields, title="Create Node", parent=self)
        if dialog.exec() and (data := dialog.get_data()):
            if data['id'] in self.nodes_dict:
                QMessageBox.warning(self, "Error", "Node ID exists!")
                return
            node = Node(
                node_id=data['id'],
                label=data['label'],
                graph_widget=self,
                md_file=data['md_file']
            )
            self.nodes_dict[data['id']] = node
            self.scene.addItem(node)
            center = self.mapToScene(self.viewport().rect().center())
            node.setPos(center)

    def create_edge(self) -> None:
        selected = [
            i for i in self.scene.selectedItems()
            if isinstance(i, Node)
        ]
        if len(selected) != 2:
            QMessageBox.information(self, "Info", "Select exactly 2 nodes.")
            return

        fields = {'color': '#888888', 'width': '1', 'style': 'solid'}
        dialog = EditDialog(fields=fields, title="Create Edge", parent=self)
        if dialog.exec():
            data = dialog.get_data()
            data['source'] = selected[0].id
            data['target'] = selected[1].id
            pair = tuple(sorted([selected[0].id, selected[1].id]))
            pair_key = cast(Tuple[str, str], pair)

            edges = [
                i for i in self.scene.items()
                if isinstance(i, Edge)
                and tuple(sorted([i.source.id, i.target.id])) == pair
            ]
            edge_data_list = [
                {
                    'source': e.source.id,
                    'target': e.target.id,
                    'color': e.base_color.name(),
                    'width': e.width,
                    'style': e.style_str
                } for e in edges
            ]
            edge_data_list.append(data)

            for e in edges:
                e.remove()

            self._apply_curvature_and_create_edges(
                pair=pair_key,
                edges_list=edge_data_list
            )

    def edit_selected(self) -> None:
        sel = self.scene.selectedItems()
        if not sel:
            return

        if isinstance(sel[0], Node):
            fields = {'label': sel[0].label, 'md_file': sel[0].md_file}
            title = f"Edit: {sel[0].id}"
            dialog = EditDialog(fields=fields, title=title, parent=self)
            if dialog.exec():
                data = dialog.get_data()
                sel[0].label = data['label']
                sel[0].md_file = data['md_file']
                sel[0].update()
        elif isinstance(sel[0], Edge):
            fields = {
                'color': sel[0].base_color.name(),
                'width': str(sel[0].width),
                'style': sel[0].style_str
            }
            dialog = EditDialog(fields=fields, title="Edit Edge", parent=self)
            if dialog.exec():
                sel[0].update_properties(properties=dialog.get_data())

    def delete_selected(self) -> None:
        for item in self.scene.selectedItems():
            if isinstance(item, Edge):
                item.remove()
        for item in self.scene.selectedItems():
            if isinstance(item, Node):
                item.remove()

    def set_hover_state(self, active: Node) -> None:
        conn: Set[Node] = {active}
        for e in active.edges:
            conn.update([e.source, e.target])
            e.is_dimmed = False
            e.is_highlighted = True

        for n in self.nodes_dict.values():
            n.is_dimmed = n not in conn

        for i in self.scene.items():
            if isinstance(i, Edge) and i not in active.edges:
                i.is_dimmed = True
                i.is_highlighted = False
        self.scene.update()

    def clear_hover_state(self) -> None:
        for i in self.scene.items():
            if hasattr(i, 'is_dimmed'):
                i.is_dimmed = False
            if hasattr(i, 'is_highlighted'):
                i.is_highlighted = False
        self.scene.update()

    def update_physics(self) -> None:
        nodes = list(self.nodes_dict.values())
        for n in nodes:
            n.calculate_forces(nodes=nodes)
        for n in nodes:
            n.advance_position()
