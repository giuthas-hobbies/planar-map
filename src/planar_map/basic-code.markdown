Here is the fully updated code. To accommodate multiple edges between the same two nodes without them overlapping, we can use **quadratic Bézier curves**. We also introduce **hover events** that highlight the active node and its direct connections while dimming the rest of the network, completing that signature Obsidian feel.

### 1. Updated YAML File (`graph.yaml`)
Let's add a second edge between "Main" and "A" to test the new multiple-edge curving feature.

```yaml
nodes:
  - id: "Main"
    label: "Core Idea"
  - id: "A"
    label: "Concept A"
  - id: "B"
    label: "Concept B"
  - id: "C"
    label: "Concept C"

edges:
  - source: "Main"
    target: "A"
    color: "#7b61ff" # Obsidian purple
    style: "solid"
    width: 2
  - source: "Main" # Second connection between Main and A
    target: "A"
    color: "#00bfff" # Deep sky blue
    style: "dashed"
    width: 2
  - source: "Main"
    target: "B"
    color: "#ff5555" # Red
    style: "dashed"
    width: 2
  - source: "A"
    target: "B"
    color: "#55ff55" # Green
    style: "dotted"
    width: 1
  - source: "Main"
    target: "C"
    color: "#888888" # Gray
    style: "solid"
    width: 1
```

### 2. Updated Python Application (`main.py`)
This script now calculates curvature for duplicate edges and manages scene-wide hover states.

```python
import sys
import yaml
import math
from PyQt6.QtWidgets import (QApplication, QGraphicsView, QGraphicsScene, 
                             QGraphicsItem, QMainWindow)
from PyQt6.QtCore import Qt, QPointF, QLineF, QTimer, QRectF, QSizeF
from PyQt6.QtGui import QColor, QPen, QBrush, QPainter, QPainterPath

class Edge(QGraphicsItem):
    def __init__(self, source, target, properties):
        super().__init__()
        self.source = source
        self.target = target
        self.source.add_edge(self)
        self.target.add_edge(self)
        
        # Parse edge properties
        self.base_color = QColor(properties.get('color', '#888888'))
        self.width = properties.get('width', 1)
        self.curvature = properties.get('curvature', 0.0)
        
        # State properties for hover effects
        self.is_dimmed = False
        self.is_highlighted = False
        
        style_str = properties.get('style', 'solid').lower()
        if style_str == 'dashed':
            self.style = Qt.PenStyle.DashLine
        elif style_str == 'dotted':
            self.style = Qt.PenStyle.DotLine
        else:
            self.style = Qt.PenStyle.SolidLine
            
        self.setZValue(-1)

    def adjust(self):
        self.prepareGeometryChange()

    def get_path(self):
        """Calculates straight line or bezier curve based on curvature"""
        path = QPainterPath(self.source.pos())
        line = QLineF(self.source.pos(), self.target.pos())
        
        if self.curvature == 0.0:
            path.lineTo(self.target.pos())
        else:
            # Calculate a control point perpendicular to the center of the line
            dx = self.target.pos().x() - self.source.pos().x()
            dy = self.target.pos().y() - self.source.pos().y()
            length = math.hypot(dx, dy)
            
            if length > 0:
                # Normal vector (-dy, dx) normalized
                nx = -dy / length
                ny = dx / length
                
                center_x = (self.source.pos().x() + self.target.pos().x()) / 2
                center_y = (self.source.pos().y() + self.target.pos().y()) / 2
                
                ctrl_x = center_x + nx * self.curvature
                ctrl_y = center_y + ny * self.curvature
                
                path.quadTo(QPointF(ctrl_x, ctrl_y), self.target.pos())
            else:
                path.lineTo(self.target.pos())
                
        return path

    def boundingRect(self):
        if not self.source or not self.target:
            return QRectF()
        # The bounding rect must encompass the curve's path, plus edge width padding
        path = self.get_path()
        return path.boundingRect().adjusted(-self.width-2, -self.width-2, self.width+2, self.width+2)

    def paint(self, painter, option, widget):
        if not self.source or not self.target:
            return

        path = self.get_path()

        # Apply hover styling
        draw_color = QColor(self.base_color)
        draw_width = self.width
        
        if self.is_dimmed:
            draw_color.setAlpha(30) # Heavy fade
        elif self.is_highlighted:
            draw_width += 1 # Slightly thicker when highlighted
            draw_color.setAlpha(255)
        else:
            draw_color.setAlpha(180) # Normal state is slightly transparent

        pen = QPen(draw_color, draw_width, self.style)
        painter.setPen(pen)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.drawPath(path)


class Node(QGraphicsItem):
    def __init__(self, node_id, label, graph_widget):
        super().__init__()
        self.id = node_id
        self.label = label
        self.graph_widget = graph_widget
        self.edges = []
        self.new_pos = QPointF()
        
        self.radius = 12
        self.is_dimmed = False
        
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setAcceptHoverEvents(True) # Enable hover events
        self.setCacheMode(QGraphicsItem.CacheMode.DeviceCoordinateCache)
        self.setZValue(1)

    def add_edge(self, edge):
        self.edges.append(edge)

    def calculate_forces(self, nodes):
        if self.scene().mouseGrabberItem() == self:
            self.new_pos = self.pos()
            return

        xvel = 0.0
        yvel = 0.0
        
        for node in nodes:
            if node == self:
                continue
            line = QLineF(self.pos(), node.pos())
            distance = line.length()
            if distance > 0 and distance < 300:
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
        if self.new_pos == self.pos():
            return False
        self.setPos(self.new_pos)
        return True

    def boundingRect(self):
        return QRectF(-self.radius, -self.radius, 
                      self.radius * 2 + 50, self.radius * 2 + 30)

    def paint(self, painter, option, widget):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        alpha = 50 if self.is_dimmed else 255
        
        # Node circle
        node_color = QColor("#a9a9a9")
        node_color.setAlpha(alpha)
        painter.setBrush(QBrush(node_color))
        
        border_color = QColor("#ffffff" if not self.is_dimmed else "transparent")
        border_color.setAlpha(alpha if not self.is_dimmed else 0)
        painter.setPen(QPen(border_color, 1.5))
        
        painter.drawEllipse(-self.radius, -self.radius, self.radius * 2, self.radius * 2)
        
        # Label text
        text_color = QColor("#ffffff")
        text_color.setAlpha(alpha)
        painter.setPen(text_color)
        metrics = painter.fontMetrics()
        text_width = metrics.horizontalAdvance(self.label)
        painter.drawText(-int(text_width/2), self.radius + 15, self.label)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            for edge in self.edges:
                edge.adjust()
        return super().itemChange(change, value)

    def hoverEnterEvent(self, event):
        self.graph_widget.set_hover_state(self)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.graph_widget.clear_hover_state()
        super().hoverLeaveEvent(event)


class GraphWidget(QGraphicsView):
    def __init__(self, yaml_file):
        super().__init__()
        self.scene = QGraphicsScene(self)
        self.scene.setItemIndexMethod(QGraphicsScene.ItemIndexMethod.NoIndex)
        self.setScene(self.scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setBackgroundBrush(QColor("#1e1e1e"))
        self.setMinimumSize(800, 600)

        self.nodes_dict = {}
        self.load_yaml(yaml_file)

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_physics)
        self.timer.start(1000 // 60)

    def load_yaml(self, filepath):
        try:
            with open(filepath, 'r') as file:
                data = yaml.safe_load(file)
        except Exception as e:
            print(f"Error loading YAML: {e}")
            return

        import random
        # 1. Create Nodes
        for n_data in data.get('nodes', []):
            node = Node(n_data['id'], n_data.get('label', n_data['id']), self)
            self.nodes_dict[n_data['id']] = node
            self.scene.addItem(node)
            node.setPos(random.randint(-100, 100), random.randint(-100, 100))

        # 2. Group edges by node pairs to calculate curvatures
        edge_pairs = {}
        for e_data in data.get('edges', []):
            pair = tuple(sorted([e_data.get('source'), e_data.get('target')]))
            if pair not in edge_pairs:
                edge_pairs[pair] = []
            edge_pairs[pair].append(e_data)

        # 3. Create Edges with applied curvature
        for pair, edges_list in edge_pairs.items():
            total_edges = len(edges_list)
            for i, e_data in enumerate(edges_list):
                source_id = e_data.get('source')
                target_id = e_data.get('target')
                
                if source_id in self.nodes_dict and target_id in self.nodes_dict:
                    # Calculate curve spread. If 1 edge, curvature is 0. 
                    # If multiple, space them out by 35 pixels.
                    offset = 0.0
                    if total_edges > 1:
                        offset = (i - (total_edges - 1) / 2.0) * 35.0
                    
                    # Ensure curve goes the right way regardless of source/target order
                    if source_id != pair[0]:
                        offset = -offset
                        
                    e_data['curvature'] = offset
                    
                    edge = Edge(self.nodes_dict[source_id], self.nodes_dict[target_id], e_data)
                    self.scene.addItem(edge)

    def set_hover_state(self, active_node):
        """Dims all items except the active node and its direct connections."""
        connected_nodes = {active_node}
        
        # Identify connected items
        for edge in active_node.edges:
            connected_nodes.add(edge.source)
            connected_nodes.add(edge.target)
            edge.is_dimmed = False
            edge.is_highlighted = True

        # Dim nodes
        for node in self.nodes_dict.values():
            node.is_dimmed = node not in connected_nodes

        # Dim edges
        for item in self.scene.items():
            if isinstance(item, Edge):
                # Only highlight edges directly connected to the active node
                if item.source == active_node or item.target == active_node:
                    item.is_dimmed = False
                    item.is_highlighted = True
                else:
                    item.is_dimmed = True
                    item.is_highlighted = False
                    
        self.scene.update()

    def clear_hover_state(self):
        """Resets all items to their default visible state."""
        for item in self.scene.items():
            if hasattr(item, 'is_dimmed'):
                item.is_dimmed = False
            if hasattr(item, 'is_highlighted'):
                item.is_highlighted = False
        self.scene.update()

    def update_physics(self):
        nodes = list(self.nodes_dict.values())
        for node in nodes:
            node.calculate_forces(nodes)
        for node in nodes:
            node.advance_position()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Obsidian Style Network Graph - Advanced")
        self.graph_widget = GraphWidget('graph.yaml')
        self.setCentralWidget(self.graph_widget)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
```

### Key Changes Breakdown:

* **Bézier Curvature Logic:** In `GraphWidget.load_yaml`, the script now groups edges based on the node pairs they connect (ignoring direction). It counts how many edges share that same pair and assigns an `offset` multiplier to each. The `Edge` class reads this and uses `QPainterPath.quadTo()` to draw a smooth curve that arches outward by `offset` pixels perpendicular to the center of the line.
* **Hover Events (`hoverEnterEvent` / `hoverLeaveEvent`):** By setting `self.setAcceptHoverEvents(True)` on the `Node`, the mouse can now trigger state changes. 
* **State Management (`is_dimmed` / `is_highlighted`):** When you mouse over a node, it commands the `GraphWidget` to loop over the scene. Anything directly touching the active node stays bright (and edges get a tiny width boost via `is_highlighted`), while everything else receives an `is_dimmed` flag, dropping their opacity to fade them into the background.