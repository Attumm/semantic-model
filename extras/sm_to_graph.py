import json
import sys

from semantic_model import dsm_looper


def get_color(item):
    n = len(item)
    return COLORS[n % len(COLORS)]


class Node():
    DN = {}
    head = None

    def __init__(self, val, dn):
        self.val = val
        self.nodes = []
        self.dn = dn
        Node.DN[dn] = self

    def connect(self, node):
        self.nodes.append(node)

    @classmethod
    def get_node(cls, dn):
        return cls.DN[dn]

    @classmethod
    def loop_over(cls):
        return cls.head.loop()

    def loop(self):
        print('-'.join(self.dn), self.val)
        for n in self.nodes:
            n.loop()
        print()

LABELS = {}
COLORS = [
         "black",
         "red",
         "green",
         "yellow",
         "blue",
         "purple",
         "pink",
         ]
DN = []


def get_color(item):
    n = len(item)
    return COLORS[n % len(COLORS)]


def load_dns(model, dn):
    if len(dn) >= 1:
        DN.append(dn)
    return model


if __name__ == "__main__":
    filename = sys.argv[sys.argv.index('-f')+1] if '-f' in sys.argv else None
    if filename is not None:
        dsm_model = json.load(open("example/example_file.json"))
    else:
        data = sys.stdin.read()
        #data = input()
        dsm_model = json.loads(data)

    result = dsm_looper(load_dns, dsm_model)
    font = "ubuntu"
    print("digraph G {")
    print("rankdir=LR;")
    print(f'node [shape=rectangle width=3 fontname="{font}"];')
    print(f'graph [fontname = "{font}"]');
    print(f'edge [fontname = "{font}"]');
    node = Node("dsm_model", "()")
    Node.head = node
    print("DN:", DN)
    for i, item in enumerate(DN, start=2):
        node = Node(i, str(item))
        parent_dn = "()" if len(item) == 1 else str(item[:-1])
        parent_node = Node.get_node(str(item[:-1]))
        parent_node.connect(node)

    for i, item in enumerate(DN, start=2):
        LABELS[str(item)] = i
        label = item[0] if len(item) == 1 else item[-1]
        print(f'\t{i} [label="{label}", style=filled color={get_color(item)}];')

    SEEN = set()
    for i, item in enumerate(DN, start=2):
        parent_dn = "()" if len(item) == 1 else str(item[:-1])
        if parent_dn in SEEN:
            continue
        node = Node.get_node(parent_dn)
        for n in node.nodes:
            print(f"{node.val} -> {n.val} [penwidth=1, arrowhead=none];")
        SEEN.add(parent_dn)

    print("}")

