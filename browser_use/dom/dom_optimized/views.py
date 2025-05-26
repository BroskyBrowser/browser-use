import json
from typing import (
	Any,
	Callable,
	Dict,
	List,
	Optional,
)


class DOMNode:
	"""
	Base node for any node in the DOM tree.
	"""

	def __init__(self, node_id: int, backend_node_id: int, frame_id: str):
		# CDP node identifier
		self.node_id: int = node_id
		# CDP backend node identifier
		self.backend_node_id: int = backend_node_id
		# CDP frame identifier
		self.frame_id: str = frame_id
		# Pointer to parent node (None for root)
		self.parent: Optional['DOMElementNode'] = None

	def is_element(self) -> bool:
		return isinstance(self, DOMElementNode)

	def is_text(self) -> bool:
		return isinstance(self, DOMTextNode)


class DOMElementNode(DOMNode):
	"""
	Node that represents an HTML element, with tag, attributes,
	computed styles and list of children.
	"""

	def __init__(
		self,
		node_id: int,
		backend_node_id: int,
		frame_id: str,
		tag: str,
		attributes: Optional[Dict[str, str]] = None,
		text_content: Optional[str] = None,
	):
		super().__init__(node_id, backend_node_id, frame_id)
		# Tag name, e.g. "div", "span", "a", etc.
		self.tag: str = tag.lower()
		# Attributes as they come from HTML: id, class, href, onclick…
		self.attributes: Dict[str, str] = attributes or {}
		# Direct text content (only for elements that contain text)
		self.text_content: str = text_content or ''
		# Children in order
		self.children: List[DOMNode] = []
		# Computed styles or data (e.g. display, visibility, boundingBox…)
		self.computed_styles: Dict[str, Any] = {}
		# Other useful properties (e.g. scrollHeight, clientHeight…)
		self.computed_properties: Dict[str, Any] = {}
		# Bounding box from layout data
		self.bounding_box: Optional[Dict[str, float]] = None
		# Paint order (z-index equivalent)
		self.paint_order: Optional[int] = None
		# Convenience visibility and interactivity flags (set during enrichment)
		self.is_visible: Optional[bool] = None
		self.is_interactive: Optional[bool] = None

	def append_child(self, node: DOMNode) -> None:
		node.parent = self
		self.children.append(node)

	def get_ancestors(self) -> List['DOMElementNode']:
		anc = []
		p = self.parent
		while p:
			anc.append(p)
			p = p.parent
		return anc

	# --------- Internal searches by predicate -------------

	def find_all(self, predicate: Callable[['DOMElementNode'], bool]) -> List['DOMElementNode']:
		"""
		Recursively traverses the subtree, returns all
		DOMElementNode instances for which predicate(e) is True.
		"""
		results: List['DOMElementNode'] = []
		if isinstance(self, DOMElementNode) and predicate(self):
			results.append(self)
		for child in self.children:
			if isinstance(child, DOMElementNode):
				results.extend(child.find_all(predicate))
		return results

	def find_by_id(self, element_id: str) -> Optional['DOMElementNode']:
		matches = self.find_all(lambda e: e.attributes.get('id') == element_id)
		return matches[0] if matches else None


class DOMTextNode(DOMNode):
	"""
	Pure text node.
	"""

	def __init__(self, node_id: int, backend_node_id: int, frame_id: str, text: str):
		super().__init__(node_id, backend_node_id, frame_id)
		self.text: str = text


class DOMTree:
	"""
	Encapsulates a complete DOM tree (with root) and offers
	convenience search methods.
	"""

	def __init__(self, root: DOMElementNode):
		self.root = root

	# --------- Search methods -------------

	def get_all_elements(self) -> List[DOMElementNode]:
		return self.root.find_all(lambda e: True)

	def get_visible_elements(self) -> List[DOMElementNode]:
		return self.root.find_all(lambda e: e.is_visible)

	def get_interactive_elements(self) -> List[DOMElementNode]:
		"""Get elements that are interactive (enriched data when available)"""
		return self.root.find_all(lambda e: e.is_interactive)

	def get_elements_with_bounding_box(self) -> List[DOMElementNode]:
		"""Get elements that have bounding box data from layout"""
		return self.root.find_all(lambda e: e.bounding_box is not None)

	def get_elements_by_paint_order(self, min_paint_order: int = 0) -> List[DOMElementNode]:
		"""Get elements with paint order >= min_paint_order (higher values are on top)"""
		return self.root.find_all(lambda e: e.paint_order is not None and e.paint_order >= min_paint_order)

	# --------- LLM translation -------------

	def translate_all_to_llm(self, format: str = 'json') -> str:
		all_elements = self.get_all_elements()
		if format == 'json':
			return self._to_llm_json(all_elements)
		elif format == 'csv':
			return self._to_llm_csv(all_elements)
		else:
			raise ValueError(f'Invalid format: {format}')

	def translate_clickable_to_llm(self, format: str = 'json') -> str:
		clickable_elements = self.get_clickable_elements()
		if format == 'json':
			return self._to_llm_json(clickable_elements)
		elif format == 'csv':
			return self._to_llm_csv(clickable_elements)
		else:
			raise ValueError(f'Invalid format: {format}')

	def translate_visible_to_llm(self, format: str = 'json') -> str:
		visible_elements = self.get_visible_elements()
		if format == 'json':
			return self._to_llm_json(visible_elements)
		elif format == 'csv':
			return self._to_llm_csv(visible_elements)
		else:
			raise ValueError(f'Invalid format: {format}')

	# --------- LLM translation utils -------------

	def _to_llm_json(self, elements: List[DOMElementNode]) -> str:
		# JSON field meanings: i=index, p=parentId, t=tag, tx=text, aria=aria-label(if different), int=interactive, nid=node_id, bid=backend_node_id, fid=frame_id
		nodes = []

		for i, element in enumerate(elements):
			node = {'i': i, 't': element.tag, 'nid': element.node_id, 'bid': element.backend_node_id, 'fid': element.frame_id}

			if element.parent:
				node['p'] = element.parent.node_id

			if element.text_content.strip():
				node['tx'] = element.text_content.strip()

			aria_label = element.attributes.get('aria-label', '')
			if aria_label and aria_label != element.text_content.strip():
				node['aria'] = aria_label

			if element.is_clickable or element.is_focusable:
				node['int'] = True

			nodes.append(node)

		return json.dumps({'n': nodes}, separators=(',', ':'))

	def _to_llm_csv(self, elements: List[DOMElementNode]) -> str:
		# CSV format: ni=nodeId, bni=backendNodeId, p=parentId, t=tag, tx=text, aria=aria-label(if different), int=interactive(0/1), nid=node_id, bid=backend_node_id, fid=frame_id
		lines = ['nid|bnid|p|t|tx|aria|int']

		for i, element in enumerate(elements):
			parent_id = element.parent.node_id if element.parent else ''
			tag = element.tag
			text = element.text_content.replace('|', ' ').replace('\n', ' ').strip()
			aria_label = element.attributes.get('aria-label', '')
			# Only include aria-label if it's different from text content
			aria = aria_label if aria_label and aria_label != text else ''
			interactive = '1' if element.is_clickable or element.is_focusable else '0'
			node_id = element.node_id
			backend_node_id = element.backend_node_id
			frame_id = element.frame_id

			lines.append(f'{i}|{parent_id}|{tag}|{text}|{aria}|{interactive}|{node_id}|{backend_node_id}|{frame_id}')

		return '\n'.join(lines)

	def _to_llm_text(self, elements: List[DOMElementNode]) -> str:
		return '\n'.join([f'{e.tag} {e.attributes} {e.text_content}' for e in elements])

	def _to_llm_html(self, elements: List[DOMElementNode]) -> str:
		return '\n'.join([f'<{e.tag} {e.attributes}>{e.text_content}</{e.tag}>' for e in elements])

	def _to_llm_markdown(self, elements: List[DOMElementNode]) -> str:
		return '\n'.join([f'## {e.tag}\n{e.attributes}\n{e.text_content}' for e in elements])
