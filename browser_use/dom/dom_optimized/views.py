import asyncio
import json
from collections.abc import Callable
from typing import (
	Any,
	Optional,
)
from urllib.parse import urlparse

from playwright.async_api import CDPSession, Page


class DOMNode:
	"""
	Base node for any node in the DOM tree.
	"""

	def __init__(self, node_id: int, backend_node_id: int, frame_url: str):
		# CDP node identifier
		self.node_id: int = node_id
		# CDP backend node identifier
		self.backend_node_id: int = backend_node_id
		# Frame URL instead of frame ID
		self.frame_url: str = frame_url
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
		frame_url: str,
		tag: str,
		attributes: dict[str, str] | None = None,
		text_content: str | None = None,
	):
		super().__init__(node_id, backend_node_id, frame_url)
		# Tag name, e.g. "div", "span", "a", etc.
		self.tag: str = tag.lower()
		# Attributes as they come from HTML: id, class, href, onclick…
		self.attributes: dict[str, str] = attributes or {}
		# Direct text content (only for elements that contain text)
		self.text_content: str = text_content or ''
		# Children in order
		self.children: list[DOMNode] = []
		# Computed styles or data (e.g. display, visibility, boundingBox…)
		self.computed_styles: dict[str, Any] = {}
		# Other useful properties (e.g. scrollHeight, clientHeight…)
		self.computed_properties: dict[str, Any] = {}
		# Bounding box from layout data
		self.bounding_box: dict[str, float] | None = None
		# Paint order (z-index equivalent)
		self.paint_order: int | None = None
		# Convenience visibility and interactivity flags (set during enrichment)
		self.is_visible: bool | None = None
		self.is_interactive: bool | None = None

	def append_child(self, node: DOMNode) -> None:
		node.parent = self
		self.children.append(node)

	def get_ancestors(self) -> list['DOMElementNode']:
		anc = []
		p = self.parent
		while p:
			anc.append(p)
			p = p.parent
		return anc

	async def get_session(self, page: Page) -> CDPSession:
		"""
		Get the CDP session to interact with the element by matching frame URL.
		"""

		iframe_frame = None
		for i, frame in enumerate(page.frames):
			frame_url = frame.url

			if self.frame_url == frame_url:
				iframe_frame = frame
				break

		if not iframe_frame:
			return None

		# Create a CDP session for this specific frame
		return await asyncio.wait_for(page.context.new_cdp_session(iframe_frame), timeout=3.0)

	# --------- Internal searches by predicate -------------

	def find_all(self, predicate: Callable[['DOMElementNode'], bool]) -> list['DOMElementNode']:
		"""
		Recursively traverses the subtree, returns all
		DOMElementNode instances for which predicate(e) is True.
		"""
		results: list['DOMElementNode'] = []
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

	def __init__(self, node_id: int, backend_node_id: int, frame_url: str, text: str):
		super().__init__(node_id, backend_node_id, frame_url)
		self.text: str = text


class DOMTree:
	"""
	Encapsulates a complete DOM tree (with root) and offers
	convenience search methods.
	"""

	def __init__(self, root: DOMElementNode):
		self.root = root

	# --------- Search methods -------------

	def get_all_elements(self) -> list[DOMElementNode]:
		return self.root.find_all(lambda e: True)

	def get_visible_elements(self) -> list[DOMElementNode]:
		return self.root.find_all(lambda e: e.is_visible)

	def get_interactive_elements(self) -> list[DOMElementNode]:
		"""Get elements that are interactive (enriched data when available)"""
		return self.root.find_all(lambda e: e.is_interactive)

	def get_elements_with_bounding_box(self) -> list[DOMElementNode]:
		"""Get elements that have bounding box data from layout"""
		return self.root.find_all(lambda e: e.bounding_box is not None)

	def get_elements_by_paint_order(self, min_paint_order: int = 0) -> list[DOMElementNode]:
		"""Get elements with paint order >= min_paint_order (higher values are on top)"""
		return self.root.find_all(lambda e: e.paint_order is not None and e.paint_order >= min_paint_order)

	def get_element_by_id(self, node_id: int, backend_node_id: int) -> DOMElementNode | None:
		"""Get element by node_id or backend_node_id"""
		return self.root.find_all(lambda e: e.node_id == node_id or e.backend_node_id == backend_node_id)

	def get_element_by_condition(self, condition: Callable[['DOMElementNode'], bool]) -> DOMElementNode | None:
		"""Get element by condition"""
		return self.root.find_all(condition)

	# --------- LLM translation -------------

	def translate_all_to_llm(self, format: str = 'json') -> str:
		all_elements = self.get_all_elements()
		match format:
			case 'json':
				return self._to_llm_json(all_elements)
			case 'csv':
				return self._to_llm_csv(all_elements)
			case 'html':
				return self._to_llm_html(all_elements)
			case 'markdown':
				return self._to_llm_markdown(all_elements)
			case _:
				raise ValueError(f'Invalid format: {format}')

	def translate_interactive_to_llm(self, format: str = 'json') -> str:
		interactive_elements = self.get_interactive_elements()
		match format:
			case 'json':
				return self._to_llm_json(interactive_elements)
			case 'csv':
				return self._to_llm_csv(interactive_elements)
			case 'html':
				return self._to_llm_html(interactive_elements)
			case 'markdown':
				return self._to_llm_markdown(interactive_elements)
			case _:
				raise ValueError(f'Invalid format: {format}')

	def translate_visible_to_llm(self, format: str = 'json') -> str:
		visible_elements = self.get_visible_elements()
		match format:
			case 'json':
				return self._to_llm_json(visible_elements)
			case 'csv':
				return self._to_llm_csv(visible_elements)
			case 'html':
				return self._to_llm_html(visible_elements)
			case 'markdown':
				return self._to_llm_markdown(visible_elements)
			case _:
				raise ValueError(f'Invalid format: {format}')

	# --------- LLM translation utils -------------

	def _to_llm_json(self, elements: list[DOMElementNode]) -> str:
		# JSON field meanings: i=index, p=parentId, t=tag, tx=text, aria=aria-label(if different), int=interactive, nid=node_id, bid=backend_node_id, fid=frame_url
		nodes = []

		for _, element in enumerate(elements):
			node = {
				'i': element.node_id,
				't': element.tag,
				'nid': element.node_id,
				'bid': element.backend_node_id,
				'fid': urlparse(element.frame_url).netloc,
			}

			if element.parent:
				node['p'] = element.parent.node_id

			if element.text_content.strip():
				node['tx'] = element.text_content.strip()

			aria_label = element.attributes.get('aria-label', '')
			if aria_label and aria_label != element.text_content.strip():
				node['aria'] = aria_label

			if element.is_interactive:
				node['int'] = True

			nodes.append(node)

		return json.dumps({'n': nodes}, separators=(',', ':'))

	def _to_llm_csv(self, elements: list[DOMElementNode]) -> str:
		# CSV format: ni=nodeId, bni=backendNodeId, p=parentId, t=tag, tx=text, aria=aria-label(if different), int=interactive(0/1), nid=node_id, bid=backend_node_id, fid=frame_url
		lines = ['nid|bnid|pid|t|tx|aria|int|fid']

		for _, element in enumerate(elements):
			parent_id = element.parent.node_id if element.parent else ''
			tag = element.tag
			text = element.text_content.replace('|', ' ').replace('\n', ' ').strip()
			aria_label = element.attributes.get('aria-label', '')
			# Only include aria-label if it's different from text content
			aria = aria_label if aria_label and aria_label != text else ''
			interactive = '1' if element.is_interactive else '0'
			node_id = element.node_id
			backend_node_id = element.backend_node_id
			frame_url = urlparse(element.frame_url).netloc

			lines.append(f'{node_id}|{backend_node_id}|{parent_id}|{tag}|{text}|{aria}|{interactive}|{frame_url}')

		return '\n'.join(lines)

	def _to_llm_text(self, elements: list[DOMElementNode]) -> str:
		return '\n'.join([f'{e.tag} {e.attributes} {e.text_content}' for e in elements])

	def _to_llm_html(self, elements: list[DOMElementNode]) -> str:
		html_lines = []
		for e in elements:
			# Convert attributes dict to HTML attribute string
			attrs_str = ''
			if e.attributes:
				attrs_str = ' ' + ' '.join([f'{k}="{v}"' for k, v in e.attributes.items()])

			# Build the HTML element
			if e.text_content.strip():
				html_lines.append(f'<{e.tag}{attrs_str}>{e.text_content}</{e.tag}>')
			else:
				# Self-closing for empty elements
				html_lines.append(f'<{e.tag}{attrs_str} />')

		return '\n'.join(html_lines)

	def _to_llm_markdown(self, elements: list[DOMElementNode]) -> str:
		return '\n'.join([f'## {e.tag}\n{e.attributes}\n{e.text_content}' for e in elements])
