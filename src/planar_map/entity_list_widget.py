from typing import Any, Dict
from PyQt6.QtWidgets import QTreeWidget, QTreeWidgetItem
from PyQt6.QtCore import Qt


class EntityListWidget(QTreeWidget):
    """
    A resizable tree widget listing nodes and edges with editable fields.

    Parameters
    ----------
    main_window : Any
        A reference to the application's main window.
    """

    def __init__(self, main_window: Any) -> None:
        super().__init__()
        self.main_window = main_window
        self.setHeaderLabels(["Entity / Property", "Value"])
        self.itemChanged.connect(slot=self._on_item_changed)
        self._is_updating: bool = False

    def refresh_data(self) -> None:
        """
        Populate the tree widget with the current nodes and edges.

        Clears the current list and rebuilds it based on the data
        present in the main window's graph widget.
        """
        self._is_updating = True
        self.clear()

        graph = self.main_window.graph_widget

        # Setup Nodes Root
        nodes_root = QTreeWidgetItem(self, ["Nodes", ""])
        nodes_root.setExpanded(True)

        for n_id, node in graph.nodes_dict.items():
            n_item = QTreeWidgetItem(nodes_root, [f"Node: {n_id}", ""])
            n_item.setExpanded(True)

            # Label field
            l_item = QTreeWidgetItem(n_item, ["Label", node.label])
            self._make_editable(
                item=l_item, obj_type="node", obj_id=n_id, field="label"
            )

            # Markdown File field
            m_item = QTreeWidgetItem(n_item, ["MD File", node.md_file])
            self._make_editable(
                item=m_item, obj_type="node", obj_id=n_id, field="md_file"
            )

        # Setup Edges Root
        edges_root = QTreeWidgetItem(self, ["Edges", ""])
        edges_root.setExpanded(True)

        for edge in graph.edges:
            e_id = f"{edge.source.id} -> {edge.target.id}"
            e_item = QTreeWidgetItem(edges_root, [f"Edge: {e_id}", ""])
            e_item.setExpanded(True)

            # Color field
            c_item = QTreeWidgetItem(e_item, ["Color", edge.base_color.name()])
            self._make_editable(
                item=c_item, obj_type="edge", obj_id=e_id, field="color"
            )

            # Width field
            w_item = QTreeWidgetItem(e_item, ["Width", str(edge.width)])
            self._make_editable(
                item=w_item, obj_type="edge", obj_id=e_id, field="width"
            )

        # Resize columns to fit contents
        self.resizeColumnToContents(0)
        self._is_updating = False

    def _make_editable(
        self, item: QTreeWidgetItem, obj_type: str, obj_id: str, field: str
    ) -> None:
        """
        Set item flags to editable and store metadata for callbacks.

        Parameters
        ----------
        item : QTreeWidgetItem
            The tree item to make editable.
        obj_type : str
            The type of object ('node' or 'edge').
        obj_id : str
            The unique identifier of the object.
        field : str
            The specific property field this item represents.
        """
        flags = item.flags() | Qt.ItemFlag.ItemIsEditable
        item.setFlags(flags)

        meta = {"type": obj_type, "id": obj_id, "field": field}
        item.setData(0, Qt.ItemDataRole.UserRole, meta)

    def _on_item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        """
        Handle updates when the user edits a value in the tree.

        Parameters
        ----------
        item : QTreeWidgetItem
            The item that was edited.
        column : int
            The column index that was edited.
        """
        if self._is_updating or column != 1:
            return

        meta: Dict[str, str] = item.data(0, Qt.ItemDataRole.UserRole)
        if not meta:
            return

        new_val = item.text(1)
        graph = self.main_window.graph_widget

        if meta["type"] == "node":
            node = graph.nodes_dict.get(meta["id"])
            if node:
                if meta["field"] == "label":
                    node.update_data(label=new_val, md_file=node.md_file)
                elif meta["field"] == "md_file":
                    node.update_data(label=node.label, md_file=new_val)

        elif meta["type"] == "edge":
            # Match edge by its string representation
            for edge in graph.edges:
                e_id = f"{edge.source.id} -> {edge.target.id}"
                if e_id == meta["id"]:
                    props = {
                        "color": edge.base_color.name(),
                        "width": str(edge.width),
                        "style": edge.style_str
                    }
                    props[meta["field"]] = new_val
                    edge.update_properties(properties=props)
                    break
